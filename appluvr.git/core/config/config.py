import os
import urlparse

CSRF_ENABLED = False
CSRF_SESSION_KEY = 'thisisalongsessioncsrfkeythatcouldbelongerbutthismightjustsufficesinceasciiaintutf'

#API_FOLDER='api'
#VIEWS_FOLDER='views'
APPLUVR_VIEW_SERVER = os.environ.get('APPLUVR_VIEW_SERVER', 'http://localhost/v2/')

DEBUG=bool(os.environ.get('APPLUVR_DEBUG',True))
TESTING=False

SENTRY_DSN=os.environ.get('SENTRY_DSN','https://944f1d0a256c4b9ea61d9057cd7ec2da:c5991e571d304936b54698e9ead3a094@app.getsentry.com/1056')

#SERVER = os.environ.get('FLASKEXT_COUCHDB_SERVER', 'http://localhost:5984/')
#DATABASE = os.environ.get('FLASKEXT_COUCHDB_DATABASE', 'vz-appluvr-api')

# Redis Heroku setup
REDISTOGO_URL=os.environ.get('REDISTOGO_URL',None)

#Primary queue key for redis worker jobs
REDIS_QUEUE_KEY = 'vz-view-redis-workers'
#Queue key for completed jobs
REDIS_COMPLETED_QUEUE_KEY = 'vz-view-redis-completed-workers'
#Max completed queue size - determines pruning of older queue items
REDIS_COMPLETED_QUEUE_MAX = 100
# Fetches Heroku's cloudant environment variable, falls back on localhost if that fails

SERVER = os.environ.get('CLOUDANT_URL','http://localhost:5984/')
DATABASE = os.environ.get('COUCHDB_DATABASE','vz-appluvr-db')


# Redis cache setup
CACHE_DEFAULT_TIMEOUT=60
CACHE_REDISTOGO_URL = os.environ.get('CACHE_REDIS',os.environ.get('REDISTOGO_URL',None))
if CACHE_REDISTOGO_URL is not None:
    # Heroku config

    urlparse.uses_netloc.append('redis')
    url = urlparse.urlparse(CACHE_REDISTOGO_URL)
    CACHE_TYPE='redis'
    CACHE_REDIS_HOST = url.hostname
    CACHE_REDIS_PORT = url.port
    CACHE_REDIS_PASSWORD = url.password
else:
    # Localhost config
    CACHE_TYPE='redis'
    CACHE_REDIS_HOST = 'localhost'
    CACHE_REDIS_PORT = 6379
