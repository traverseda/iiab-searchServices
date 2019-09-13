import xapian, json
from huey import SqliteHuey
from settings import indexDataDb, config
huey = SqliteHuey(filename='./queue.sqlite')
dbpath = config['Search']['index_dir']

@huey.lock_task('xapian-writer')
def saveToIndex(bodyText, data):
    db = xapian.WritableDatabase(dbpath, xapian.DB_CREATE_OR_OPEN)
    doc = xapian.Document()

    termgenerator = xapian.TermGenerator()
    termgenerator.set_document(doc)
    termgenerator.set_database(db)
    termgenerator.set_stemmer(xapian.Stem("en"))

    termgenerator.index_text(data['title'], 1, 'S')
    termgenerator.index_text(data['title'])
    termgenerator.increase_termpos()
    termgenerator.index_text(bodyText)

    doc.add_boolean_term("Q"+data['url'])
    doc.set_data(json.dumps(data))

    db.replace_document("Q"+data['url'], doc)

def dedupe():
    pass

import requests, lxml
import lxml.html
from lxml.html.clean import Cleaner
import hashlib, base64
import time
@huey.task()
def scrapeSite(url,root=None):
    #This code is pretty unclead. ToDo: rewrite the scrapeSite function to be clearer
    url = url.split("#")[0]
    db = xapian.Database(dbpath)
    session = requests.Session()
    #Don't redownload the same url over and over again
    lastIndex = indexDataDb.get(url+'lastIndexDate',0)
    if time.time()-lastIndex < 30*60:
        #Don't re-index within a 30 minute window
        return
    modifiedTime = indexDataDb.get(url+'lastModifiedHeader',None)
    if modifiedTime:
        session.headers.update({'If-Modified-Since': modifiedTime})
    contentType = indexDataDb.get(url+'contentType',None)
    if contentType != None and not contentType.startswith('text'):
        #Don't bother indexing binary data
        return

    response = session.get(url)
    if response.status_code == 304:
        indexDataDb[url+'lastIndexDate']=int(time.time())
        return
    contentType = response.headers.get('Content-Type',"")
    indexDataDb[url+'contentType']= contentType
    if not contentType.startswith('text'):
        return

    print(url)

    h = hashlib.sha256()
    h.update(response.content)
    hashStr = base64.b64encode(h.digest()).decode("utf-8")

    cleaner = Cleaner()
    cleaner.javascript = True
    cleaner.style = True

    html = lxml.html.fromstring(response.content)
    title= html.find(".//title").text
    html = cleaner.clean_html(html)
    html.make_links_absolute(url, resolve_base_href=True)
    bodyText = "".join(html.itertext())
    data = {
#        "summary": list(summarize(bodyText))[:3],
        "title": title,
        "url": url,
        "hash": hashStr,
        "lastIndexDate": int(time.time()),
        "lastModified": response.headers.get("Last-Modified",""),
    }
    saveToIndex(bodyText,data)

    indexDataDb[url+'bodyText']=bodyText
    indexDataDb[url+'lastIndexDate']=int(time.time())
    indexDataDb[url+'contentType']=response.headers.get('Content-Type',"")
    indexDataDb[url+'lastModifiedHeader']=response.headers.get("Last-Modified",None)

    if not root: return #Don't process children if there's no root
    links = (i[2] for i in html.iterlinks())
    for link in links:
        if link.startswith(root):#Only process urls that are children of root
            scrapeSite(link)

huey.immediate = True
#scrapeSite("https://xapian.org/docs/omega/termprefixes.html")
scrapeSite("http://www.islandone.org/MMSG/aasm/AASMIndex.html", root="http://www.islandone.org")

