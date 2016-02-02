#/usr/bin/python

from appluvr import create_app

'''
import sys
from werkzeug import run_simple
from werkzeug.contrib.profiler import ProfilerMiddleware, MergeStream
'''

app = create_app('../config/config.py')
print app.url_map

'''
f = open('/tmp/profiler.log','w')
app = ProfilerMiddleware(app, MergeStream(sys.stderr, f))
run_simple('localhost',80, app, use_reloader=True, use_debugger=True)
'''

app.run(host='0.0.0.0',port=8082,use_debugger=True,use_reloader=True)
