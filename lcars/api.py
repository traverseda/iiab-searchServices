import hug
import asyncio

@hug.cli()
@hug.get()
def queue_status():
    pass

@hug.cli()
def monitor():
    raise NotImplementedError

@hug.cli(output=hug.output_format.pretty_json)
@hug.get()
def info():
    """Information about the search index
    """
    from index import searchIndex, schema
    return {
        "doc_count": searchIndex.doc_count(),
        "uncleaned_docs":searchIndex.doc_count()-searchIndex.doc_count(),
        "last_modified": searchIndex.last_modified(),
        "schema": schema.names(),
    }

@hug.cli(output=hug.output_format.pretty_json)
@hug.get()
def search(query:str, offset:int=0, limit:int=10):
    from index import parser, searchIndex
    with searchIndex.searcher() as searcher:
        queryParsed = parser.parse(query)
        corrected = searcher.correct_query(queryParsed, query)
        results = searcher.search(queryParsed)
        data = dict(
            offset=offset,limit=limit,
            query_text=query,
            query_parsed=str(queryParsed),
            corrected=corrected.string,
            result_count=results.estimated_length(),
            results=[r.fields() for r in results[offset:offset+limit]],
        )
        return data

@hug.cli()
@hug.get()
def index(url:str):
    from index import index
    index(url)

@hug.cli()
def env_info():
    import sys, os
    return dict(
        virtualenv=os.getenv("VIRTUAL_ENV",""),
        module="lcars.server:server",
        version=sys.version,
    )

def main():
    hug.API(__name__).cli()

if __name__ == '__main__':
    main()
