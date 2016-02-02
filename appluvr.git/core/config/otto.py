import os
#SERVER = os.environ.get('FLASKEXT_COUCHDB_SERVER', 'http://172.16.67.39:5984')
SERVER = os.environ.get('FLASKEXT_COUCHDB_SERVER', 'http://localhost:5984')
CSRF_ENABLED = False
CSRF_SESSION_KEY = 'thisisatestkey'
CACHE_DEFAULT_TIMEOUT=30
CACHE_TYPE='simple'
DEBUG=False
TESTING=True
API_FOLDER='otto'
CLEAR_DB=True
DATABASE = os.environ.get('FLASKEXT_COUCHDB_DATABASE', 'vz-appluvr-auto-otto')
