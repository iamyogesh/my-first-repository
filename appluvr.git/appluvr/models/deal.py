from appluvr import couchdb
from couchdbkit.schema import *
from couchdbkit import *
import appluvr.utils
from appluvr.prefix import *
from base import LinkedDocument
from flask import current_app, jsonify
from appluvr.utils.misc import crypto

class Deal(LinkedDocument):   

    doc_type = 'all_deals'
    # app Name
    name = StringProperty()
    # app id
    package_name = StringProperty()
    # deal title
    deal_title = StringProperty()
    # app_download url
    download_url = StringProperty()    
    # description of the app
    editorial_description = StringProperty()
    #couchdb document ids
    deal_id = StringProperty()    
    # app price on dealed day
    original_price=StringProperty() 
    # deal start date
    deal_start = StringProperty()
    # deal end date
    deal_end = StringProperty()
    # platform
    platform = StringProperty()
    # carrier
    carrier = StringProperty()


    def toDict(self):
        return dict(name=self.name, package_name=self.package_name, deal_title=self.deal_title, download_url=self.download_url, editorial_description=self.editorial_description, deal_id=self._id, original_price=self.original_price, platform = self.platform, carrier =self.carrier, deal_start =self.deal_start, deal_end = self.deal_end)
        #return dict(super(Deal, self).toDict(), **dict(name=self.name, package_name=self.package_name, first_created=1321809540, last_modified=1321809540, deal_title=self.deal_title, download_url=self.download_url, editorial_description=self.editorial_description, deal_id=self._id, original_price=self.original_price, platform = self.platform, carrier =self.carrier))

#    @property
    def current_deal_toDict(self):        
        return dict(name=self.name, package_name=self.package_name, deal_title=self.deal_title, download_url=self.download_url, editorial_description=self.editorial_description, deal_id=self._id, original_price=self.original_price)

#    @property
    def __repr__(self):
        return '<Deal %r>' % self.deal_id


from flask_wtf import Form, TextField, Required, Email, Optional, Length, ValidationError

class DealCreateForm(Form):
    
    name = TextField('app name',validators=[Length(min=1,max=120),Required('Please provide package name')])
    package_name = TextField('package_name', validators=[Length(min=1,max=120),Required('Please provide package id')])
    editorial_description = TextField('editorial_description', validators=[Optional()])
    download_url = TextField('download_url',  validators=[Length(min=1,max=120),Required('Please provide download url')])
    platform = TextField('platform',  validators=[Length(min=1,max=120),Required('Please provide platform')])
    carrier = TextField('carrier',  validators=[Length(min=1,max=120),Required('Please provide carrier')])
    deal_title = TextField('deal_title', validators=[Length(min=1,max=120),Required('Please provide deal title')])
    original_price = TextField('original_price', validators=[Length(min=0,max=120),Optional()])
    deal_start= TextField('deal_start', validators=[Length(min=1,max=120),Required('Please provide deal start date')])
    deal_end = TextField('deal_end', validators=[Length(min=1,max=120),Required('Please provide deal end date')])

    def validate_deal(form, field):
        if field.data:
            try:
                cats = field.data.split(',')
                cats = [cat.strip() for cat in cats]
            except:
                raise ValidationError('Invalid category list')


class DealUpdateForm(Form):

    name = TextField('app name',validators=[Optional()])
    package_name = TextField('Categories', validators=[Optional()])
    editorial_description = TextField('editorial_description', validators=[Optional()])
    download_url = TextField('download_url',  validators=[Optional()])
    deal_title = TextField('deal_title', validators=[Optional()])
    original_price = TextField('original_price', validators=[Optional()])
    platform = TextField('platform',  validators=[Optional()])
    carrier = TextField('carrier',  validators=[Optional()])
    deal_start= TextField('deal_start', validators=[Optional()])
    deal_end = TextField('deal_end', validators=[Optional()])
    
    def validate_categories(form, field):
        if field.data:
            try:
                cats = field.data.split('.')
                cats = [cat.strip() for cat in cats]
            except:
                raise ValidationError('Invalid category list')


__all__ = ['Deal', 'DealCreateForm', 'DealUpdateForm']

