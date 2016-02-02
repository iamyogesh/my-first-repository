from appluvr import couchdb
from couchdbkit.schema import *
from couchdbkit import *
import appluvr.utils
from appluvr.prefix import *
from base import LinkedDocument
from flask import current_app

"""
.. autoclass:: Interest
"""
class Interest(LinkedDocument):
    doc_type = 'interest'
    name = StringProperty()
    categories = StringProperty() # CSL
    description = StringProperty()
    picture = StringProperty()
    #all_interests = ViewDefinition('interest','all_interests','')
    #all_categories = ViewDefinition('interest', 'all_categories','')

    @staticmethod
    def _interests():
        ret = Interest.view('interest/all_interests')
        return [interest.name for interest in ret]


    @staticmethod
    def _categories():
        ret = Interest.view('interest/all_categories')
        categ = [set(row.key.split(',')) for row in ret]
        all_categ = set()
        for item in categ:
            all_categ = all_categ | item
        return list(all_categ)
        

    def toDict(self):
        return dict(super(Interest, self).toDict(), **dict(name=self.name, categories=self.categories, description=self.description, picture=self.picture))


    def __repr__(self):
        return '<Interest %r>' % self.name


'''

Form validation classes

Importing this further down to avoid the TextField conflict with couch

'''

from flask_wtf import Form, TextField, Required, Email, Optional, Length, ValidationError



class InterestCreateForm(Form):
    name = TextField('Interest name/number', validators=[Length(min=1,max=120),Required('Please provide an interest name')])
    categories = TextField('Categories', validators=[Optional()])
    description = TextField('Description', validators=[Optional()])
    picture = TextField('Picture', validators=[Optional()])
    
    def validate_categories(form, field):
        if field.data:
            try:
                cats = field.data.split(',')
                cats = [cat.strip() for cat in cats]
            except:
                raise ValidationError('Invalid category list')


class InterestUpdateForm(Form):
    name = TextField('Interest name/number', validators=[Length(min=1,max=120),Optional()])
    categories = TextField('Categories', validators=[Optional()])
    description = TextField('Description', validators=[Optional()])
    picture = TextField('Picture', validators=[Optional()])

    
    def validate_categories(form, field):
        if field.data:
            try:
                cats = field.data.split('.')
                cats = [cat.strip() for cat in cats]
            except:
                raise ValidationError('Invalid category list')
    

__all__ = ['Interest', 'InterestCreateForm', 'InterestUpdateForm']

