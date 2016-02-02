import os
SERVER = os.environ.get('FLASKEXT_COUCHDB_SERVER', 'http://localhost:5984/')
CSRF_ENABLED = False
CSRF_SESSION_KEY = '\xf8\xf5\xf9\x0eKF\x82\xcd\xdc\x04\xc7\xca\xcc\\\xd0\x0b\x05\xb6\xac\x9c\x89:f\x03'
CACHE_DEFAULT_TIMEOUT=30
CACHE_TYPE='simple'
DEBUG=False
TESTING=True
FOLDER='qa'
CLEAR_DB=True
DATABASE = os.environ.get('FLASKEXT_COUCHDB_DATABASE', 'vz-appluvr-auto-'+FOLDER)
