#/usr/bin/python

from appluvr_views import create_app

app = create_app('../config/config.py')
app.run(host='127.0.0.1',port=80,use_debugger=True,use_reloader=True)
