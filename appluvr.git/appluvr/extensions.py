# -*- coding: utf-8 -*-

#from flaskext.couchdb import *
from flask.ext.cache import Cache
from flaskext.uploads import *
from flask import current_app
from flaskext.couchdbkit import CouchDBKit


couchdb = CouchDBKit()
cache = Cache()
#manager = CouchDBManager(auto_sync=False)

appocatalog = UploadSet('appocatalog',extensions=('gz'), default_dest=lambda foo: '/tmp/appocatalog')


"""
from beaker.cache import CacheManager
from beaker.util import parse_cache_config_options

cache_opts = {
    'cache.data_dir': '/tmp/cache/data',
    'cache.lock_dir': '/tmp/cache/lock',
    'cache.type': 'ext:memcached',
    'cache.url': '127.0.0.1:11211',
    'cache.expire': '3600'
}


bcache = CacheManager(**parse_cache_config_options(cache_opts))
"""
