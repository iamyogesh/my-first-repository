# -*- coding: utf-8 -*-

''''
@author Arvi Krishnawamy
June 2011



'''

__version__ = "5.0.0.0"

from flask import Flask, abort, jsonify, request, json, render_template, flash, g, current_app, Blueprint
#import couchdb
from werkzeug import LocalProxy
from extensions import cache, couchdb, appocatalog, configure_uploads, patch_request_class 
import os, logging
import json as simplejson
from raven.contrib.flask import Sentry

def create_app(config_filename):
    app = Flask(__name__)
    app.config.from_object(__name__)
    app.config['FOLDER'] = None
    try:
        app.config.from_pyfile(config_filename)
    except ImportError:
        import sys
        print >> sys.stderr, "Unable to import config file"
    app.config['COUCHDB_SERVER'] = app.config['SERVER']
    app.config['COUCHDB_DATABASE'] = app.config['DATABASE']
    #provide an override which can be set on the shell for stg & prod
    app.config.from_envvar('APPLUVR_SETTINGS', silent=True)

    # Sentry
    if app.config.get('SENTRY_DSN'):
        sentry = Sentry(app)
        print 'Initializing Appluvr with %s' % app.config.get('SENTRY_DSN')

    cache.init_app(app)

    # Configure Flask-Uploads with the upload set instance
    configure_uploads(app, appocatalog)
    # 32MB max
    patch_request_class(app, 32 * 1024 * 1024)

    from appluvr.models import User, UserDisallow, Device, App, Interest, Settings, PromoApp, Comment
    from appluvr.utils.misc import MethodRewriteMiddleware
    """
    :Database Configuration
    """
    couchdb.init_app(app)

    from appluvr.routes import routes as routes_blueprint

    if app.config.get('API_FOLDER', None):
        app.register_blueprint(routes_blueprint, url_prefix='/'+str(app.config.get('API_FOLDER')))
    else:
        app.register_blueprint(routes_blueprint)
    app.wsgi_app = MethodRewriteMiddleware(app.wsgi_app)
    app.secret_key = '\xf8\xf5\xf9\x0eKF\x82\xcd\xdc\x04\xc7\xca\xcc\\\xd0\x0b\x05\xb6\xac\x9c\x89:f\x01'
    
    return app

d = LocalProxy(lambda: current_app.logger.debug)
couch = LocalProxy(lambda: g.couch)
