from defaultUsersSettings import *

#Open the database once to make sure it exists
import xapian
xapian.WritableDatabase(str(XAPIAN_INDEX), xapian.DB_CREATE_OR_OPEN)

#Waiting on https://bugs.python.org/issue1410680 for preserving comments
#At that point we can do some fun things with plugins.
#with open('example.cfg', 'w+') as configfile:
#  config.write(configfile)


import zict, msgpack
#I'd use json but it can't dump just a raw string without a container
dumps = lambda d: msgpack.packb(d, use_bin_type=True)
loads = lambda d: msgpack.unpackb(d, raw=False)
indexDataDb = zict.lmdb.LMDB(str(METADATA_INDEX))
#Why not just store this data in xapian? A lot of it is going to be
# for urls we didn't index, images, videos, etc.
indexDataDb = zict.Func(dumps, loads, indexDataDb)

huey = TASKQUEUE
