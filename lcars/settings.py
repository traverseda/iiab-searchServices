import os
import collections
from environs import Env
from appdirs import user_data_dir

data_dir=user_data_dir("LCARS", "traverseda")

defaultConf = {
    "redis_url": "",
    "data_root": data_dir,
    "lcars_api_key": "",
    'lcars_title': ' - lcars',
    'lcars_tasks_cache': '128',
    'lcars_tagline':' Library Computer Access/Retrieval System',
    #Pipe and comma seperated list of extra menu links
    "extra_menu_urls": "",#example1,http://example.com|example2,http://example.com
}

basesettings = collections.ChainMap(
    #This is where other data source would go...
    defaultConf)

settings = collections.ChainMap(os.environ,basesettings)

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
    from huey import RedisHuey
    HUEY=RedisHuey(url=settings['redis_url'])
else:
    from huey import SqliteHuey
    HUEY=SqliteHuey(filename=data_root/"queue.sqlite3",cache_mb=10)
