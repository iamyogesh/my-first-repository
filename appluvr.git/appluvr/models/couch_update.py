from appluvr import couchdb
from appluvr_views.extensions import cache
from appluvr.prefix import *
from base import LinkedDocument
#from flaskext.couchdb import *
from couchdbkit.schema import *
from couchdbkit import *
from werkzeug import LocalProxy
from flask import current_app, jsonify, json
import json as simplejson
from appluvr.models.device import Device
from appluvr.models.interest import Interest
from appluvr.utils.misc import crypto, AttrDict, safe_serialize
import requests

spit = LocalProxy(lambda: current_app.logger.debug)

class CouchCreateForm(LinkedDocument):
    doc_type = 'user'   
    emails = ListProperty(default=[])

    def toDict(self):
        return dict( emails = self.emails)

    def __repr__(self):
        return '<emails : %r>'  % self.emails


from flask_wtf import Form, TextField, Required, Email, Optional, Length, ValidationError, validators, url
from flask_wtf.html5 import URLField

class UpdateCouchCreateForm(Form):    
    emails = TextField('Email Address',[validators.Required('Please provide users email address')])

    def validate_email(form, field):        
        if field.data:        
            try:
                cats = field.data.split(',')          
                cats = [cat.strip() for cat in cats]           
            except:
                raise ValidationError('Invalid category list')

__all__ = ['CouchCreateForm', 'UpdateCouchCreateForm']