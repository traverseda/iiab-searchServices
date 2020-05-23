import hug
import asyncio

@hug.cli(output=hug.output_format.pretty_json)
@hug.get()
def search(query:str, offset:int=0, limit:int=10):
    from lcars.index import parser, searchIndex, get_highlights
    with searchIndex.searcher() as searcher:
        queryParsed = parser.parse(query)
        corrected = searcher.correct_query(queryParsed, query)
        results = searcher.search(queryParsed)
        results.fragmenter.surround = 50
        data = dict(
            offset=offset,limit=limit,
            query_text=query,
            query_parsed=str(queryParsed),
            corrected=corrected.string,
            result_count=results.estimated_length(),
            #Turns out this is no slow than the built in paginator...
            # which is to to say higher pages will be slower regardless.
            results=list(map(get_highlights,results[offset:offset+limit])),
        )
        return data

@hug.cli()
@hug.get()
def index(url:str):
    """ Add a url to the queue of pages to be indexed
    """
    from lcars.index import index
    index(url)

@hug.cli()
@hug.get()
def queue_status():
    """Print the current status of the queue
    """
    pass

@hug.cli()
def monitor():
    """Watch the log
    """
    raise NotImplementedError

@hug.cli()
def env_info():
    """Print information needed to create a uwsgi file
    """
    import sys, os
    return dict(
        virtualenv=os.getenv("VIRTUAL_ENV",""),
        module="lcars.server:server",
        version=sys.version,
    )

@hug.cli(output=hug.output_format.pretty_json)
@hug.get()
def info():
    """Information about the search index
    """
    from lcars.index import searchIndex, schema
    return {
        "doc_count": searchIndex.doc_count(),
        "uncleaned_docs":searchIndex.doc_count()-searchIndex.doc_count(),
        "last_modified": searchIndex.last_modified(),
        "schema": schema.names(),
    }

def main():
    hug.API(__name__).cli()

if __name__ == '__main__':
    main()