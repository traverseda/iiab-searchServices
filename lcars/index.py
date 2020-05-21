import whoosh
from whoosh.fields import Schema, TEXT, KEYWORD, ID, STORED, IDLIST, DATETIME
from whoosh.analysis import StemmingAnalyzer
from whoosh import fields, index

schema = Schema(url=ID(stored=True,unique=True),
                title=ID(stored=True),
                links=IDLIST(stored=True),
                body=TEXT(analyzer=StemmingAnalyzer(),stored=True),
                last_indexed=DATETIME(stored=True),
                tags=KEYWORD(lowercase=True,stored=True,))

import settings

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

def handle_mimetype(mimetypes):
    def register_mimetype(func,mimetypes=mimetypes):
        if type(mimetypes) == str:
            mimetypes = (mimetypes,)
        for mimetype in mimetypes:
            mimetype_handlers[mimetype]=func
        return func
    return register_mimetype

def cache_if_slow(func):
    """Moves body to body_cached if text takes too long
    to collect.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start=time.monotonic()
        result = func(*args,**kwargs)
        timeDiff=time.monotonic()-start
        if timeDiff < 0.4:
            result['_stored_body']=""
        return result
    return wrapper

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
    links = [ i.attrs['href'] for i in tree.tags("a") ]
    links = [ requests.compat.urljoin(url,i).split("#")[0].split('?')[0] for i in links ]
    text = tree.body.text(separator='\n')
    entry = dict(
        url=url,
        links=links,
        body=text,
        last_indexed=datetime.datetime.utcnow(),
        title=tree.css_first("title").text() or url,
    )
    return entry

def index_pdf(url):
    raise NotImplemented

def index_epub(url):
    raise NotImplemented


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

from settings import HUEY as huey
#from whoosh.writing import AsyncWriter
#writer = AsyncWriter(searchIndex)
writer = searchIndex.writer()

#@huey.task()
def index(url, force=False):
    last_indexed = get_last_index_time(url)
    if last_indexed:
        metadata = requests.head(url,headers={
            'If-Modified-Since':last_indexed,
        })
        if metadata.status_code==304:
            print(f"Not grabbing `{url}` as it hasn't been modified")
            return
    else:
        metadata = requests.head(url)
    mimetype = metadata.headers['content-type'].split(";")[0]
    if mimetype in mimetype_handlers.keys():
        document = mimetype_handlers[mimetype](url)
        writer.update_document(**document)
        writer.commit()
        return
    return
