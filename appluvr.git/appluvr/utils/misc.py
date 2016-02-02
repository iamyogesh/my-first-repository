# -*- coding: utf-8 -*-
from functools import wraps
from flask import Flask, Request, abort, jsonify, request, json, render_template, flash, g, url_for, redirect, current_app, Response, Blueprint
from appluvr import prefix
from uuid import uuid4
from werkzeug import LocalProxy
from flask.ext.cache import Cache
import os, sys, time, string, re, gzip
import urllib
import requests
import json as simplejson
from hashlib import md5
import string
import re
import zlib
import struct
from itsdangerous import URLSafeSerializer
import math

spit = LocalProxy(lambda: current_app.logger.debug)

#---------- Round off Number -------------#
def round_off_numbers(x, base=10):
    return int(base * math.floor(float(x)/base))

serializer = URLSafeSerializer('esarhpsihtegnahctnod', salt='leviosa')

#-------------------------------------------------------------------------------#

def safe_serialize(str):
	return serializer.dumps(str)

def safe_deserialize(str):
	return serializer.loads(str)

#-------------------------------------------------------------------------------#

# Snippet from http://flask.pocoo.org/snippets/5/

import re
from unicodedata import normalize

_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

def slugify(text, delim=u'-'):
    """Generates an slightly worse ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        word = normalize('NFKD', word).encode('ascii', 'ignore')
        if word:
            result.append(word)
    return unicode(delim.join(result))

#-------------------------------------------------------------------------------#

def not_modified():
    return Response('304 Not Modified', 304, {})


def test_decorator(f):
    """ Test decorator """
 #   @wraps(f)
    def decorated(*arg, **kwargs):
        import pdb; pdb.set_trace()
        return '1976%s' % f(*arg, **kwargs)
    return decorated



def print_timing(f):
    """ Decorator for printing timing information """
    @wraps(f)
    def decorated(*arg, **kwargs):
        should_time = current_app.config['TESTING'] or current_app.config['DEBUG']
        if should_time:
            t1 = time.time()
            res = f(*arg, **kwargs)
            t2 = time.time()
            print 'TIMER reports that %s took %0.3f ms' % (f.func_name, (t2-t1)*1000.0)
            return res
        else:
            return f(*arg, **kwargs)
    return decorated


def support_etags(f):
    """ Decorator for handling etags """
    @wraps(f)
    def decorated(*args, **kwargs):
        if_none_match = request.headers.get('If-None-Match', False)
        """ Current calling the underlying function and hashing the result
        and then comparing it with the etag sent up later. We should change
        this to use the Cache result instead later """
        foo = f(*args, **kwargs)
        try:
            spit(foo)
            hash_value = crypto.hash(str(foo.data))
        except (TypeError, AttributeError):
            # Bails if the returned data is not a string type do to an exception
            # Bubbles it up for handling
            return foo
        # Ok, now that we have a hash, lets see if it matches up fine
        if if_none_match and crypto.match(if_none_match, hash_value):
            # And return a not modified code if it hasnt
            return not_modified()
        # And if it was, stamp in the hash value
        foo.headers['etag'] = str(crypto.hash(str(foo.data)))
        return foo
    return decorated


def check_auth(username, password):
    # :TODO: Wire this to a pull of pwd hashes from the DB
    return username == os.environ.get('APPLUVR_USER','tablet') and password == os.environ.get('APPLUVR_PWD','aspirin')

def check_att_auth(username,password):
    s1 = (username == 'attnet' and password == 'testing123')
    s2 = (username == 'myatt' and password == 'testing321')
    return s1 or s2

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with the appropriate credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    """ Decorator for handling authentication """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Bypass auth for unit testing
        if current_app.config['TESTING']:
            return f(*args, **kwargs)
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

#ATT Endpoint Authentication
def requires_att_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_att_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def make_conflict_409(id):
    response = current_app.make_response(jsonify({id:'Unable to process your request to update %s due a database resource update conflict. Please try again.' % id}))
    response.status_code = 409
    return response

def make_409(id):
    response = current_app.make_response(jsonify({id:'Object with this identifier already exists and cannot be created'}))
    response.status_code = 409
    return response

def make_400(output):
    response = current_app.make_response(jsonify(errors=output))
    response.status_code = 400
    return response

def support_jsonp(f):
    """Wraps JSONified output for JSONP"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        callback = request.args.get('callback', False)
        if callback:
            content = str(callback) + '(' + str(f().data) + ')'
            return current_app.response_class(content, mimetype='application/json')
        else:
            return f(*args, **kwargs)
    return decorated_function


#-------------------------------------------------------------------------------#

def verify_system_package(packageName):
	matchObject = re.match("android.*|com.android.*|com.google.android.*|com.motorola.*|com.sec.android.*|com.samsung.sec.*", packageName)
	return matchObject is not None

def test_verify_system_package():
	print verify_system_package('com.levitum.abc') #False
	print verify_system_package('com.motorola.abc') #True
	print verify_system_package('com.sec.androi') #False
	print verify_system_package('com.sec.foo') #False
	print verify_system_package('com.samsung.sec.test') #True


def verify_package(packageName):
    matchObject = re.match("([a-zA-Z_]{1}[a-zA-Z0-9_]*(\.[a-zA-Z_]{1}[a-zA-Z0-9_]*)*)$",
                           packageName)

    return  matchObject is not None

#-------------------------------------------------------------------------------#

'''
Ext URL map
'''

def url_map(rel, id):
    if rel == 'user':
        return url_for('routes.get_user',id=id, _external=True)
    if rel == 'device':
        return url_for('routes.get_device',id=id,_external=True)
    if rel == 'apps':
        return url_for('routes.get_all_device_apps',id=id,_external=True)
    if rel == 'friends_apps':
        return "" #url_for('views.get_user_friends_apps',id=id,_external=True)
    if rel == 'friends':
        return "" #url_for('views.get_user_fb_friends',id=id,_external=True)
    if rel == 'hot_apps':
        return "" #url_for('views.get_hot_apps',id=id,_external=True)
    if rel == 'apps_for_you':
        return "" #url_for('views.get_apps_for_you',id=id,_external=True)
    return ""

#-------------------------------------------------------------------------------#

'''
Misc crypto stuff - not in use any more 
Candidates for clean up
'''
class crypto(object):

    # Private translation map for user ids
    fn = string.maketrans(u'abcdefghijklmnopqrstuvwxyz@.-_1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ%',u'otkgpurzxfqewyndjhmscbaliv#$^!7396258140FUDQAEJNRMITXHGSVYBPZKCLWO.')
    inv_fn = string.maketrans(u'otkgpurzxfqewyndjhmscbaliv#$^!7396258140FUDQAEJNRMITXHGSVYBPZKCLWO.',u'abcdefghijklmnopqrstuvwxyz@.-_1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ%')

    @staticmethod
    def hash(str):
        return md5(str).hexdigest()

    @staticmethod
    def match(old_hash, new_hash):
        return old_hash == new_hash

    @staticmethod
    def push(str):
        return str.encode('ascii').translate(crypto.fn)[::1]

    @staticmethod
    def pop(str):
        return str.encode('ascii').translate(crypto.inv_fn)[::1]

#-------------------------------------------------------------------------------#



#-------------------------------------------------------------------------------#

# Method rewriting to support possible older clients
# mostly for use in the future since the native apps
# will not need this
# http://flask.pocoo.org/snippets/38

from werkzeug import url_decode

class MethodRewriteMiddleware(object):

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        if 'METHOD_OVERRIDE' in environ.get('QUERY_STRING', ''):
            args = url_decode(environ['QUERY_STRING'])
            method = args.get('__METHOD_OVERRIDE__')
            if method in ['GET', 'POST', 'PUT', 'DELETE']:
                method = method.encode('ascii', 'replace')
                environ['REQUEST_METHOD'] = method
        return self.app(environ, start_response)

#-------------------------------------------------------------------------------#

## {{{ http://code.activestate.com/recipes/473786/ (r1)
class AttrDict(dict):
    """A dictionary with attribute-style access. It maps attribute access to
    the real dictionary.  """
    def __init__(self, init={}):
        dict.__init__(self, init)

    def __getstate__(self):
        return self.__dict__.items()

    def __setstate__(self, items):
        for key, val in items:
            self.__dict__[key] = val

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, dict.__repr__(self))

    def __setitem__(self, key, value):
        return super(AttrDict, self).__setitem__(key, value)

    def __getitem__(self, name):
        return super(AttrDict, self).__getitem__(name)

    def __delitem__(self, name):
        return super(AttrDict, self).__delitem__(name)

    __getattr__ = __getitem__
    __setattr__ = __setitem__

    def copy(self):
        ch = AttrDict(self)
        return ch
## end of http://code.activestate.com/recipes/473786/ }}}