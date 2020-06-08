import whoosh
from whoosh.fields import Schema, TEXT, KEYWORD, ID, STORED, IDLIST, DATETIME
from whoosh.analysis import StemmingAnalyzer
from whoosh import fields, index
from huey.utils import Error

schema = Schema(url=ID(stored=True,unique=True),
                title=ID(stored=True),
                links=IDLIST(stored=True),
                body=TEXT(analyzer=StemmingAnalyzer(cachesize=-1),stored=True),
                last_indexed=DATETIME(stored=True),
                tags=KEYWORD(lowercase=True,stored=True,))

import lcars.settings as settings

indexDir = settings.data_root/"searchIndex"
(settings.data_root/"searchIndex").mkdir(parents=True, exist_ok=True)
try:
    searchIndex = index.open_dir(indexDir)
except whoosh.index.EmptyIndexError:
    searchIndex = index.create_in(settings.data_root/"searchIndex", schema)

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
    """Moves body to body_cached if text takes too long
    to collect.
    """
    #ToDo, some way to differentiate between a missing body
    # and one that is intentionally left blank...
    @wraps(func)
    def wrapper(*args, **kwargs):
        start=time.monotonic()
        result = func(*args,**kwargs)
        timeDiff=time.monotonic()-start
        if timeDiff < 0.4:
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

from whoosh.qparser import MultifieldParser
from whoosh.qparser import QueryParser
parser = QueryParser("body", schema=schema)

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

@huey.on_startup()
def setup_writer():
    global writer
    global seg_doc_count
    writer = None
    seg_doc_count=0

@huey.task(priority=10)
@huey.lock_task("whoosh-optimize")
def optimize_whoosh(segment):
    writer = searchIndex.writer()
    writer.segments.append(segment)
    writer.commit()

import threading
#This is multiprocess safe, but this makes it safe to use
#with thread-based workers as well.
# We don't use huey's task lock because that would lock across processes.
whooshlock = threading.Lock()

@huey.on_shutdown()
def finalize_index():
    if writer:
        segment = writer._finalize_segment()
        optimize_whoosh(segment)

def save_to_whoosh(document):
    whooshlock.acquire()
    global writer
    global seg_doc_count
    if not writer:
        from whoosh import index
        from whoosh.writing import SegmentWriter
        ix = index.open_dir(indexDir)
        writer = SegmentWriter(ix, _lk=False)
    writer.update_document(**document)
    seg_doc_count+=1
    if seg_doc_count > 64:
        fieldnames = writer.pool.fieldnames
        segment = writer._finalize_segment()
        optimize_whoosh(segment)
        writer = None
        seg_doc_count=0
    whooshlock.release()
    return

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
        save_to_whoosh(document)
        return
    print(f"unhandled mimetype `{mimetype}` at {url}")
    return
