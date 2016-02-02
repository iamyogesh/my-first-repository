from appluvr import couchdb
from couchdbkit.schema import *
from couchdbkit import *
import appluvr.utils
from appluvr.prefix import *
from base import LinkedDocument
from flask import current_app, jsonify
from appluvr.utils.misc import crypto

class Packages(LinkedDocument):   

    doc_type = 'app_pack'
    # user Name
    user_name = StringProperty()
    # app name
    apppack_name = StringProperty()
    # users device id
    fb_id = StringProperty()
    # users profile pic
    user_picurl = StringProperty() 
    #app_pack created date
    apppack_created_date = IntegerProperty(default=None)
    #app pack data
    apps = ListProperty(default=[])
    # app pack image 
    apppack_img = StringProperty()
    # app apppack_square_img image 
    apppack_square_img = StringProperty()
    #app pack description
    apppack_description = StringProperty()
    # app pack status
    apppack_status = StringProperty()
    #user details
    user_bio = StringProperty()
    #app_created user flag 
    current_user_created = BooleanProperty(default = False)    
   
    def toDict(self):
        return dict(app_id = self._id, user_name = self.user_name, fb_id = self.fb_id, user_picurl = self.user_picurl, apppack_name = self.apppack_name, apppack_img = self.apppack_img, apppack_description = self.apppack_description, apppack_status = self.apppack_status, user_bio = self.user_bio, apps = self.apps, apppack_created_date = self.apppack_created_date, current_user_created = self.current_user_created,apppack_square_img = self.apppack_square_img)
    
#    @property
    def __repr__(self):
        return '<App_packs %r>' % self._id


from flask_wtf import Form, TextField, Required, Email, Optional, Length, ValidationError

class PackagesCreateForm(Form):    
    
    user_name = TextField('user name',validators=[Optional()])
    fb_id = TextField('fb_id',  validators=[Optional()])
    user_picurl = TextField('user profile pic',  validators=[Optional()])
    apppack_name= TextField('app pack name', validators=[Optional()])
    apppack_img = TextField('apppack_img', validators=[Optional()])
    apppack_description = TextField('apppack description', validators=[Optional()])
    user_bio = TextField('user details', validators=[Optional()])
    apppack_status = TextField('apppack_status', validators=[Required('Please provide apppack_status')])
    apps = TextField('app packs', validators=[Required('Please provide atleast 3 apps to create app packs.')])

    def validate_deal(form, field):
        if field.data:
            try:
                cats = field.data.split(',')
                cats = [cat.strip() for cat in cats]
            except:
                raise ValidationError('Invalid category list')


class PackagesUpdateForm(Form):

    user_name = TextField('user name',validators=[Optional()])
    fb_id = TextField('fb_id',  validators=[Optional()])
    user_picurl = TextField('user profile pic',  validators=[Optional()])
    apppack_name= TextField('apppack_name', validators=[Optional()])
    apppack_img = TextField('apppack_img', validators=[Optional()])
    apppack_description = TextField('apppack_description', validators=[Optional()])
    user_bio = TextField('user details', validators=[Optional()])
    apppack_status = TextField('apppack_status', validators=[Optional()])
    apps = TextField('app pack data', validators=[Optional()])
    
    def validate_categories(form, field):
        if field.data:
            try:
                cats = field.data.split('.')
                cats = [cat.strip() for cat in cats]
            except:
                raise ValidationError('Invalid category list')


__all__ = ['Packages', 'PackagesCreateForm', 'PackagesUpdateForm']

