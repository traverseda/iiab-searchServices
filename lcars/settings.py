from configparser import ConfigParser, ExtendedInterpolation
config = ConfigParser(interpolation=ExtendedInterpolation())
config.read('./defaults.cfg')

#Open the database once to make sure it exists
import xapian
xapian.WritableDatabase(config['Search']['index_dir'], xapian.DB_CREATE_OR_OPEN)

#with open('example.cfg', 'w+') as configfile:
#  config.write(configfile)


import zict, msgpack
#I'd use json but it can't dump just a raw string without a container
dumps = lambda d: msgpack.packb(d, use_bin_type=True)
loads = lambda d: msgpack.unpackb(d, raw=False)
indexDataDb = zict.lmdb.LMDB(config['Search']['data_dir'])
#Why not just store this data in xapian? A lot of it is going to be
# for urls we didn't index, images, videos, etc.
indexDataDb = zict.Func(dumps, loads, indexDataDb)
