from whoosh.fields import Schema, TEXT, KEYWORD, ID, STORED, IDLIST, DATETIME
from whoosh.analysis import StemmingAnalyzer
from whoosh import fields, index

schema = Schema(url=ID(stored=True,unique=True),
                title=ID(stored=True),
                links=IDLIST(stored=True),
                body=TEXT(analyzer=StemmingAnalyzer()),
                last_index=DATETIME,
                #For when creating the highlights again would take too long.
                body_cached=TEXT(analyzer=StemmingAnalyzer(),stored=True),
                tags=KEYWORD(lowercase=True,stored=True,))

import settings

(settings.data_root/"searchIndex").mkdir(parents=True, exist_ok=True)
searchIndex = index.create_in(settings.data_root/"searchIndex", schema)

from selectolax.parser import HTMLParser
import time
import requests
import unicodedata
from functools import wraps

def cache_if_slow(func):
    """Moves body to body_cached if text takes too long
    to collect.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start=time.monotonic()
        result = func(*args,**kwargs)
        timeDiff=time.monotonic()-start
        if timeDiff > 0.4:
            result['body_cached']=result['body']
            del result['body']
        return result
    return wrapper

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
    links = { requests.compat.urljoin(url,i).split("#")[0].split('?')[0] for i in links }
    text = tree.body.text(separator='\n')
    entry = dict(
        url=url,
        links=links,
        body=text,
        title=tree.css_first("title").text() or url,
    )
    return entry

def index_pdf(url):
    raise NotImplemented

def index_epub(url):
    raise NotImplemented
