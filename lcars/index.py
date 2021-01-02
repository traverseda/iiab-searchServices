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
                           'cache_size': -1 * 64000,  # 64MB
                           'foreign_keys': 1,
                           'ignore_check_constraints': 0,
                           'synchronous': 0}
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
        options = {'tokenize': 'porter','content': Document,}

def search(phrase):
    # Query the search index and join the corresponding Document
    # object on each search result.
    return (Document
            .select(Document,
                    #This controls the snippet generation, as per https://www.sqlite.org/fts3.html#the_snippet_function
                    fn.snippet(DocumentIndex._meta.entity,"<b>","</b>","<b>...</b>",-1,-128).alias('snippet'),
                    )
            .join(
                DocumentIndex,
                on=(Document.id == DocumentIndex.rowid))
            .where(DocumentIndex.match(phrase))
            .order_by(DocumentIndex.bm25())
            )

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

@handle_mimetype("text/html")
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

def save_to_sqlite(document):
    #Remove extra whitespace...
    body=(i.strip() for i in document['body'].splitlines())
    body=(i for i in body if i)
    body="\n".join(body)
    with db.atomic("EXCLUSIVE"):
        db_content={
            "url":document['url'],
            "title":document['title'],
            "body":body,
        }

        Document.insert(**db_content).on_conflict(conflict_target=Document.url,update=db_content).execute()
        d=Document.get(url=document['url'])

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
