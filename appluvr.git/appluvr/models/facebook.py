import appluvr.utils
from appluvr.prefix import *
from base import LinkedDocument
from flask import current_app



'''

Form validation classes

Importing this further down to avoid the TextField conflict with couch

'''

from flask_wtf import Form, TextField, Required, Email, Optional, Length, ValidationError, url, FieldList
from flask_wtf.html5 import URLField



class FacebookLoginForm(Form):
    fb_token = TextField('Facebook auth token', validators=[Length(min=1,max=1024), Required()])
    #
    # Commenting fb_id, name and email since the backend will get these details and populate from now on
    #
    #fb_id = TextField('Facebook identifier', validators=[Length(min=1,max=50), Required()])
    # Naming convention sans fb since v1 app is already sending this up
    #name = TextField('Facebook name', validators=[Length(min=1,max=1024), Required()])
    #email = TextField('Facebook Email', validators=[Required('Please provide an email address'),Email()])


__all__ = ['FacebookLoginForm']
