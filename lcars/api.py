import hug
import asyncio

@hug.cli()
@hug.get()
def queue_status():
    pass

@hug.cli()
def monitor():
    raise NotImplementedError

@hug.cli()
@hug.get()
def index(url:str):
    raise NotImplementedError

@hug.cli()
def env_info():
    import sys, os
    return dict(
        virtualenv=os.getenv("VIRTUAL_ENV",""),
        module="lcars.server:server",
        version=sys.version,
    )

if __name__ == '__main__':
    hug.API(__name__).cli()
