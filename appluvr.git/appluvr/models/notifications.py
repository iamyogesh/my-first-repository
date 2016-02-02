from appluvr import couchdb
from couchdbkit.schema import *
from couchdbkit import *
import appluvr.utils
from appluvr.prefix import *
from appluvr.models.interest import *
from base import LinkedDocument
from flask import current_app


class MfNotification(LinkedDocument):
    """
    .. autoclass:: Notifiction
    """

    # Doc type definition for design document
    doc_type = 'mf_notification'
    
    # Fields that are populated by Appo bulk upload
    last_viewed = IntegerProperty(default=0)
    uniq_id = StringProperty()

    def toDict(self):
        return dict(_id = self._id, uniq_id = self.uniq_id, last_viewed = self.last_viewed)

    def __repr__(self):
        return '<MfNotification %r>' % self.uniq_id

class MfaNotification(LinkedDocument):
    """
    .. autoclass:: Notifiction
    """

    # Doc type definition for design document
    doc_type = 'mfa_notification'
    
    # Fields that are populated by Appo bulk upload
    last_viewed = IntegerProperty(default=0)
    uniq_id = StringProperty()

    def toDict(self):
        return dict(_id = self._id, uniq_id = self.uniq_id, last_viewed = self.last_viewed)

    def __repr__(self):
        return '<MfaNotification %r>' % self.uniq_id
        
__all__ = ['MfNotification','MfaNotification']
