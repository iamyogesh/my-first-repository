#/usr/bin/python

from appluvr import create_app

app = create_app('/Users/arvi/Dev/VZ/vz_views/config/config.py')
app.run(host='0.0.0.0',port=80,use_debugger=True,use_reloader=True)
