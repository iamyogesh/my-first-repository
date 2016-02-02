# -*- coding: utf-8 -*-

''''
@author Arvi Krishnawamy
June 2011



'''

__version__ = "4.0.0"

from flask import Flask, abort, jsonify, request, json, render_template, flash, g, current_app, Blueprint
#import couchdb
from werkzeug import LocalProxy
from extensions import cache, couchdb, appocatalog, configure_uploads, patch_request_class 
import os, logging
import json as simplejson
from raven.contrib.flask import Sentry
import hoover

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

    handler = hoover.LogglyHttpHandler(token='616a9cfe-90b4-4077-8f08-24e2d5ca2850')
    log = logging.getLogger('MyApp')
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    #app.logger.addHandler(log)
    app.logger.info("AppLuvr is in the house.")
    app.logger.debug("...flask configuration complete")

    cache.init_app(app)

    from appluvr.models import User, UserDisallow, Device, App, Interest, Settings, PromoApp, Comment
    from appluvr.utils.misc import MethodRewriteMiddleware 

    """
    :Database Configuration

    manager.setup(app)
    manager.sync(app)
    """
    couchdb.init_app(app)

    from views import views as views_blueprint
    from appluvr.routes import routes as routes_blueprint

    '''if app.config.get('API_FOLDER', None):
        app.register_blueprint(views_blueprint, url_prefix='/'+str(app.config.get('VIEWS_FOLDER')))
    else:
        app.register_blueprint(views_blueprint)
    if app.config.get('API_FOLDER', None):
        app.register_blueprint(routes_blueprint, url_prefix='/'+str(app.config.get('API_FOLDER')))
    else:
        app.register_blueprint(routes_blueprint)'''
    app.register_blueprint(views_blueprint, url_prefix='/'+app.config.get('APPLUVR_API_VERSION')+'/'+str(app.config.get('VIEWS_FOLDER')))
    app.register_blueprint(routes_blueprint, url_prefix='/'+app.config.get('APPLUVR_API_VERSION')+'/'+str(app.config.get('API_FOLDER')))
    app.wsgi_app = MethodRewriteMiddleware(app.wsgi_app)
    app.secret_key = '\x0c!G\x9b[\xe1X\xa4\x82\xa8\xc9\xa7\xf1\x99\x7f\xd4\x8c\x1f@\xfc\xcb5\xe3e'

    return app

d = LocalProxy(lambda: current_app.logger.debug)
couch = LocalProxy(lambda: g.couch)
