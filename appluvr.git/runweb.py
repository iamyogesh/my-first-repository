#/usr/bin/python

"""
Bootstrap and serve your application. If you're in a development environment,
envoke the script with:

    $ python runweb.py

You can also specify the port you want to use:

    $ python runweb.py 5555

You can easily test the production `tornado` server, too:

    $ python runweb.py --tornado

Alternatively, your application can be run with the `gevent` Python library:

    $ python runweb.py --gevent
"""

from werkzeug.wsgi import DispatcherMiddleware
import os
from appluvr import create_app

from gevent import monkey
monkey.patch_all()

config_file = os.path.abspath('config/config.py')

api = create_app(config_file)
#app.run(host='127.0.0.1',port=8080,use_debugger=True,use_reloader=True)
#/usr/bin/python

from appluvr_views import create_app

views = create_app(config_file)
#app.run(host='127.0.0.1',port=80,use_debugger=True,use_reloader=True)

#print api.url_map
#print views.url_map

from workers.workerd import TaskWorker
from redis import Redis
from time import sleep
import os, urlparse

if os.environ.has_key('REDISTOGO_URL'):
    urlparse.uses_netloc.append('redis')
    url = urlparse.urlparse(os.environ['REDISTOGO_URL'])
    REDIS = Redis(host=url.hostname, port=url.port, db=0, password=url.password)
    redis = REDIS
    print 'Redis parameters are %s (hostname), %s (port), %s (password)' % (url.hostname, url.port, url.password)
else:
    redis = Redis()

NUM_WORKERS = int(os.environ.get('APPLUVR_WORKERS', 1))

workers = []
for i in range(NUM_WORKERS):
    # 5 ms cache of worker results
    workers.append(TaskWorker(views, worker_name="Worker %d" % i, completed_queue_key=views.config['REDIS_COMPLETED_QUEUE_KEY'], rv_ttl=5, redis=redis, debug=True))
map(lambda w: w.start(), workers)
#while any(filter(lambda w: w.is_alive(), workers)):
#    sleep(1)
#print 'Task worker stopped.'


views.config['DEBUG'] = True
api.config['DEBUG'] = True

'''from flask import Flask
app = Flask(__name__)
print app.url_map

application = DispatcherMiddleware(app, {'/v4/api' : api, '/v4/views': views})
'''
import argparse

def parse_arguments():
    """Parse any additional arguments that may be passed to `bootstrap.py`."""
    parser = argparse.ArgumentParser()
    parser.add_argument('port', nargs='?', default=os.environ.get('PORT',5000), type=int,
                        help="An integer for the port you want to use.")
    parser.add_argument('--gevent', action='store_true',
                        help="Run gevent's production server.")
    parser.add_argument('--tornado', action='store_true',
                        help="Run gevent's production server.")
    args = parser.parse_args()
    return args


def serve_app(environment):
    """
    Serve your application. If `dev_environment` is true, then the
    application will be served using gevent's WSGIServer.
    """

    # Use the $PORT variable on heroku's environment.
    port = environment.port
    if environment.gevent:
        from gevent.wsgi import WSGIServer
        http_server = WSGIServer(('', port), application)
        http_server.serve_forever()
    elif environment.tornado:
        from tornado.wsgi import WSGIContainer
        from tornado.httpserver import HTTPServer
        from tornado.ioloop import IOLoop
        http_server = HTTPServer(WSGIContainer(application))
        http_server.listen(port)
        IOLoop.instance().start()
    else:
        from werkzeug.serving import run_simple
        #application.run_simple(debug=True, port=port)
        #run_simple('0.0.0.0', port, application, use_reloader=True)
        print views.url_map
        views.run(debug=True)

def main():
    dev_environment = parse_arguments()
    serve_app(dev_environment)


if __name__ == '__main__':
    main()
