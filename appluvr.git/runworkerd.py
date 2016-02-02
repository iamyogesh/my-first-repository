#/usr/bin/python

from appluvr_views import create_app
from workers.workerd import TaskWorker
from redis import Redis
from time import sleep
import os, urlparse

app = create_app('../config/config.py')

if os.environ.has_key('REDISTOGO_URL'):
    urlparse.uses_netloc.append('redis')
    url = urlparse.urlparse(os.environ['REDISTOGO_URL'])
    REDIS = Redis(host=url.hostname, port=url.port, db=0, password=url.password)
    redis = REDIS
    print 'Redis parameters are %s (hostname), %s (port), %s (password)' % (url.hostname, url.port, url.password)
else:
    redis = Redis()

workers = []
for i in range(3):
    # 500 ms cache of worker results
    workers.append(TaskWorker(app, worker_name="Worker %d" % i, completed_queue_key=app.config['REDIS_COMPLETED_QUEUE_KEY'], rv_ttl=500, redis=redis))
map(lambda w: w.start(), workers)
while any(filter(lambda w: w.is_alive(), workers)):
    sleep(1)
print 'Task worker stopped.'

