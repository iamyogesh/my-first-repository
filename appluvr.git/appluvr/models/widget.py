from appluvr import couchdb
from couchdbkit.schema import *
from couchdbkit import *
import appluvr.utils
from appluvr.prefix import *
from base import LinkedDocument
from flask import current_app, jsonify
from appluvr.utils.misc import crypto

class AttWidget(LinkedDocument):   

    doc_type = 'att_widget' 

    # widget status
    widget_status = StringProperty()  
    #widget type
    widget_type = StringProperty()
    #promo_copy
    promo_copy = StringProperty(default=None)
    #appo data
    app_data = ListProperty(default=[])

    #set Priority
    priority = StringProperty(default='0')

    def toDict(self):
        priority = 9999 if self.priority=='' else int(self.priority)
        return dict(_id = self._id, app_data = self.app_data, promo_copy =self.promo_copy, priority = priority, widget_status = self.widget_status, widget_type= self.widget_type)
#    @property
    def __repr__(self):
        return '<widget %r>' % self._id


from flask_wtf import Form, TextField, Required, Email, Optional, Length, ValidationError

class AttWidgetCreateForm(Form):    

    widget_type = TextField('widget_type', validators=[Required('Please provide widget type')])
    app_data = TextField('app_data', validators=[Required('Please provide app details')])
    widget_status = TextField('widget status', validators=[Optional()])     
    promo_copy = TextField('promo_copy', validators=[Optional()])      

    priority = TextField('priority', validators=[Optional()])    



    def validate_deal(form, field):
        if field.data:
            try:
                cats = field.data.split(',')
                cats = [cat.strip() for cat in cats]
            except:
                raise ValidationError('Invalid category list')


class AttWidgetUpdateForm(Form): 

    widget_type = TextField('widget_type', validators=[Required('Please provide widget type')])
    app_data = TextField('app_data', validators=[Required('Please provide app details')])
    widget_status = TextField('widget status', validators=[Optional()])

    priority = TextField('priority', validators=[Optional()]) 

  



    def validate_deal(form, field):
        if field.data:
            try:
                cats = field.data.split(',')
                cats = [cat.strip() for cat in cats]
            except:
                raise ValidationError('Invalid category list')


__all__ = ['AttWidget', 'AttWidgetCreateForm', 'AttWidgetUpdateForm']

