import hug
import asyncio
from playhouse.shortcuts import model_to_dict

@hug.cli()
def rebuild_index():
    from lcars.index import Document
    from lcars.index import DocumentIndex
    doc_count=Document.select().count()
    DocumentIndex.rebuild()
    DocumentIndex.optimize()
    print(f"Re-generated indexes for {doc_count} documents")

@hug.cli(output=hug.output_format.pretty_json)
@hug.get()
def search(query:str, offset:int=0, limit:int=10):
    from lcars.index import search
    count = search(query).count()
    query=search(query).limit(limit).offset(offset)
    print(query)
    return {"count":count,
            "limit":limit,
            "offset":offset,
            "documents":query.execute(),
            }

@hug.cli()
@hug.get()
def index(url:str,recursive:bool=True,root:str=None):
    """ Add a url to the queue of pages to be indexed
    """
    from lcars.index import index
    if recursive and not root:
        root = url
    task = index(url,root=root)
    print(f"task added to queue as: {task}")

@hug.cli()
@hug.get()
def queue_status():
    """Print the current status of the queue
    """
    import collections
    from lcars.settings import HUEY
    import lcars.tasks
    #pending = (c.__class__ for c in HUEY.pending()+HUEY_SINGLETON.pending())
    #pending = ('.'.join((c.__module__, c.__qualname__)) for c in pending)
    #pending = collections.Counter(pending)
    return {
        "queue_size": HUEY.storage.queue_size(),
    }
    pass

@hug.cli()
def monitor():
    """Watch the queue
    """
    import time
    print("Gather data...")
    while True:
        startCount=info()['doc_count']
        time.sleep(4)
        endcount = info()['doc_count']-startCount
        print(endcount/4, "documents indexed per second")

@hug.cli(output=hug.output_format.pretty_json)
def env_info():
    """Print information needed to create a uwsgi file, as well as all settings
    """
    import sys, os, lcars.settings
    return dict(
        virtualenv=os.getenv("VIRTUAL_ENV",""),
        module="lcars.server:server",
        version=sys.version,
        env_settings=lcars.settings.printable_settings()
    )

@hug.cli(output=hug.output_format.pretty_json)
@hug.get()
def info():
    """Information about the search index
    """
    from lcars.index import Document
    return {
        "doc_count": Document.select().count(),
    }

def main():
    hug.API(__name__).cli()

if __name__ == '__main__':
    main()
