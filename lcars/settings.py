import os
import collections
from environs import Env
from appdirs import user_data_dir

data_dir=user_data_dir("LCARS", "traverseda")

defaultConf = {
    "redis_url": "", #export redis_url="redis://127.0.0.1:6379"
    "data_root": data_dir,
#    "lcars_api_key": "",
    'lcars_title': ' - lcars',
#    'lcars_tasks_cache': '128',
    'lcars_tasks_workers': '4',
    #Defaults to 4*128MB of cache?
    #ToDo: Autodetect some saner defaults
    'lcars_tagline':' Library Computer Access/Retrieval System',
    #Pipe and comma seperated list of extra menu links
    "extra_menu_urls": "",#example1,http://example.com|example2,http://example.com
}

basesettings = collections.ChainMap(
    #This is where other data source would go...
    defaultConf)

settings = collections.ChainMap(os.environ,basesettings)

def printable_settings():
    return {k:v for k,v in settings.items() if k in basesettings}

from pathlib import Path

THEME = {
    'title':settings['lcars_title'],
    'tagline':settings['lcars_tagline'],
    'menu_links': {i.split(",")[0]:i.split(',')[1] for i in settings["extra_menu_urls"].split("|") if i}
}

data_root=Path(settings['data_root'])
data_root.mkdir(parents=True, exist_ok=True)
search_root=data_root/"searchIndex"
search_root.mkdir(parents=True, exist_ok=True)

if settings['redis_url']:
    from huey import PriorityRedisHuey
    HUEY=PriorityRedisHuey(url=settings['redis_url'])
    HUEY_SINGLETON=PriorityRedisHuey("lcars-singleton",url=settings['redis_url'])
else:
    from huey import SqliteHuey
    HUEY=SqliteHuey(filename=data_root/"queue.sqlite3",cache_mb=10)
    HUEY_SINGLETON=SqliteHuey("lcars-singleton",filename=data_root/"queue.sqlite3",cache_mb=10)
