from huey.utils import Error
import logging

import peewee
import datetime
from playhouse.sqlite_ext import *
try:
    from playhouse.sqlite_ext import CSqliteExtDatabase as SqliteExtDatabase
except ImportError:
    pass

import lcars.settings as settings

indexDir = settings.data_root/"searchIndex"
(settings.data_root/"searchIndex").mkdir(parents=True, exist_ok=True)
db = SqliteExtDatabase(indexDir/'search_db.sqlite3',regexp_function=True,
                       timeout=60,#timeout not working?
                       pragmas={
                           'journal_mode': 'wal',
                           'cache_size': -1024 * 64}
                       )

class Document(Model):
    # Canonical source of data, stored in a regular table.
    url = TextField(null=False, unique=True)
    title = TextField(unique=False,default="")
    body = TextField(default="")
    mtime = DateTimeField(default=datetime.datetime.now)
    tags=TextField(default="")

    def get_body(self):
        if self.body: return self.body
        else:
            metadata = requests.head(self.url)
            mimetype = metadata.headers['content-type'].split(";")[0]
            document = mimetype_handlers[mimetype](self.url)
            return document['body']

    class Meta:
        database = db

class DocumentIndex(FTSModel):
    # Full-text search index.
    rowid = RowIDField()
    title = SearchField()
    body = SearchField()

    class Meta:
        database = db
        # Use the porter stemming algorithm to tokenize content.
        options = {'tokenize': 'porter'}

def search(phrase):
    # Query the search index and join the corresponding Document
    # object on each search result.
    return (Document
            .select()
            .join(
                DocumentIndex,
                on=(Document.id == DocumentIndex.rowid))
            .where(DocumentIndex.match(phrase))
            .order_by(DocumentIndex.bm25()))

db.create_tables([Document, DocumentIndex])
#print("Index Location:",settings.data_root/"searchIndex")

from selectolax.parser import HTMLParser
import time, datetime
import requests
import unicodedata
from functools import wraps

mimetype_handlers = {
}

def handle_mimetype(*mimetypes):
    def register_mimetype(func,mimetypes=mimetypes):
        for mimetype in mimetypes:
            mimetype_handlers[mimetype]=func
        return func
    return register_mimetype

def cache_if_slow(func):
    """Moves body to _stored_body if text takes too long
    to collect.
    """
    #ToDo, some way to differentiate between a missing body
    # and one that is intentionally left blank...
    @wraps(func)
    def wrapper(*args, **kwargs):
        start=time.monotonic()
        result = func(*args,**kwargs)
        timeDiff=time.monotonic()-start
        if timeDiff > 0.4:
            result['_stored_body']=result['body']
        else:
            result['_stored_body']=""
        return result
    return wrapper


@handle_mimetype("application/pdf","application/epub+zip","application/msword",
                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 )
@cache_if_slow
def index_textract(url):
    import textract, tempfile
    response = requests.get(url,stream=True)
    suffix = "."+url.split(".")[-1]
    if suffix not in textract.parsers._get_available_extensions():
        import mimetypes
        mimetypes.init()
        mimetype = response.headers['content-type'].split(";")[0]
        suffix=mimetypes.guess_extension(mimetype)
    suffix = "-"+url.split('/')[-1]
    tmpfile = tempfile.NamedTemporaryFile("wb",suffix=suffix,prefix="lcars-searchspider-",buffering=False)
    with tmpfile as fp:
        #ToDo: This only works on linux
        for chunk in response.iter_content(10000):
            fp.write(chunk)
        fp.flush()
        text = textract.process(fp.name,encoding="utf-8")
    if not isinstance(text,str):
        text=text.decode("utf-8")
    entry = dict(
        url=url,
        body=text,
        last_indexed=datetime.datetime.utcnow(),
        title=url.split('/')[-1] or url,
    )
    return entry

@handle_mimetype("text/html")
@cache_if_slow
def index_html(url):
    r = requests.get(url)
    tree = HTMLParser(r.text)
    #Remove non-text "text" content.
    for tag in tree.css('script'):
        tag.decompose()
    for tag in tree.css('style'):
        tag.decompose()
    links = [ i.attrs.get('href',None) for i in tree.tags("a") ]
    links = [ requests.compat.urljoin(url,i).split("#")[0].split('?')[0] for i in links ]
    text = tree.body.text(separator='\n')
    title = tree.css_first("title")
    if title: title=title.text()
    title = title or url
    entry = dict(
        url=url,
        links=links,
        body=text,
        last_indexed=datetime.datetime.utcnow(),
        title=title
    )
    return entry

def get_last_index_time(url):
    #ToDo: cache and otherwise optimize this, as it gets called
    # a lot.
    with searchIndex.searcher() as searcher:
        query = parser.parse("url:'{}'".format(url))
        results = searcher.search(query)
        if results[:1]:
            indexTime = results[0]['last_indexed']
            return indexTime.strftime('%a, %d %b %Y %H:%M:%S GMT')
        return False

from lcars.settings import HUEY as huey

def get_highlights(hitItem):
    """Turn a hitItem into a plain dict and generate highlights
    for it.
    """
    #ToDo: Investigate whether or not loading this all into memory is
    # a performance hit? I think the standard hitItem might be lazy-loading
    # large fields like "body", but I'm not sure if it matters since we
    # need to load the text to generate highlights anyway?
    itemDict = hitItem.fields()
    if not hitItem['body']:
        metadata = requests.head(hitItem['url'])
        mimetype = metadata.headers['content-type'].split(";")[0]
        document = mimetype_handlers[mimetype](hitItem['url'])
        itemDict['body'] = document['body']
    itemDict['highlights'] = hitItem.highlights("body",text=hitItem['body'],top=5,)
    itemDict['highlights'] = itemDict['highlights'] or itemDict['body'][:300] + " [...]"
    return hitItem.fields()

from retrying import retry

#@retry(stop_max_delay=60000)
def save_to_sqlite(document):
    with db.atomic():
        db_content={
            "url":document['url'],
            "title":document['title'],
            "body":document.get('_stored_body',""),
        }

        Document.insert(**db_content).on_conflict(conflict_target=Document.url,update=db_content).execute()
        d=Document.get(url=document['url'])

        try:
            DocumentIndex.insert({
                   DocumentIndex.rowid: d.id,
                   DocumentIndex.title: document['title'],
                   DocumentIndex.body: document['body']}).execute()
        except:
            DocumentIndex.update({
                   DocumentIndex.title: document['title'],
                   DocumentIndex.body: document['body']}).where(DocumentIndex.rowid==d.id).execute()

@huey.task()
def index(url, root=None, force=False):
    #ToDo, automatically delete trees that no longer exist...
    #ToDo, at some point this code got messy. Clean it up.
    import urllib.parse
    url = urllib.parse.unquote(url)

    #last_indexed = get_last_index_time(url)
    last_indexed = False
    if last_indexed:
        metadata = requests.head(url,headers={
            'If-Modified-Since':last_indexed,
        })
        if metadata.status_code==304:
            print(f"Not indexing `{url}` as it hasn't been modified")
            return
    else:
        metadata = requests.head(url)
    mimetype = metadata.headers['content-type'].split(";")[0]
    if mimetype not in mimetype_handlers.keys():
        import mimetypes as mtypes
        mimetype=mtypes.guess_type(url)[0]
    if mimetype in mimetype_handlers.keys():
        try:
            document = mimetype_handlers[mimetype](url)
        except Exception as e:
            err = f"""
    url: "{url}"
    mimetype: {mimetype}
    handler-name: {mimetype_handlers[mimetype]}
    handler-file: {mimetype_handlers[mimetype].__code__.co_filename}"""
            raise Exception(err) from e
        if root and document.get('links',False):
            links = [link for link in document['links'] if link.startswith(root)]
            for url in links:
                lastIndexed = huey.get(url, peek=True)
                if isinstance(lastIndexed,Error):
                    continue
                if lastIndexed: # and lastIndexed > int(time.time())-30*60: #A half hour
                    continue
                huey.put(url, int(time.time()))
                task = index.s(url, root=root)
                task.id = url
                result = huey.enqueue(task)
        document = {k:v for k,v in document.items() if v}
        save_to_sqlite(document)
        return
    logging.info(f"unhandled mimetype `{mimetype}` at {url}")
    return
