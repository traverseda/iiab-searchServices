import os
from pathlib import Path
data_root = Path(os.path.dirname(os.path.realpath(__file__)))

data_root = data_root/"lcars-data"

XAPIAN_INDEX = data_root/"xapianIndex"
METADATA_INDEX = data_root/"lmdbIndex"

import huey as h
TASKQUEUE = h.SqliteHuey(
    filename=data_root/'queue.sqlite',
    fsync = False #Slower, but more robust during a power failure
)

THEME = {
    'title':' - lcars',
    'tagline':'Library Computer Access/Retrieval System',
    'menu_links': {
#        'name': 'url',
#        'name2': 'url',
    },
}
