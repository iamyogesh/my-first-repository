from appluvr import couchdb
from couchdbkit.schema import *
from couchdbkit import *
import appluvr.utils
from appluvr.prefix import *
from base import LinkedDocument
from flask import current_app

"""
.. autoclass:: Settings
"""
class Settings(LinkedDocument):
    doc_type = 'settings',
    key = StringProperty()
    value = StringProperty()
    #all_settings = ViewDefinition('settings','all_settings','')

    def toDict(self):
        return dict(super(Settings, self).toDict(), **dict(key=self.key, value=self.value))


    def __repr__(self):
        return '<Settings %r>' % self.entry



__all__ = ['Settings']

