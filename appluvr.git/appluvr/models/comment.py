from appluvr import couchdb
from couchdbkit.schema import *
from couchdbkit import *
import appluvr.utils
from appluvr.prefix import *
from appluvr.models.interest import *
from base import LinkedDocument
from flask import current_app


class Comment(LinkedDocument):
    """
    .. autoclass:: Comment
    """

    # Doc type definition for design document
    doc_type = 'comment'
    
    pkg = StringProperty()
    comment = StringProperty()
    uniq_id = StringProperty()

    #all_comments = ViewDefinition('comment', 'all_comments','')
    #user_comments = ViewDefinition('comment', 'user_comments','')

    def toDict(self):
        return dict(super(Comment, self).toDict(), **dict(pkg=self.pkg, uniq_id=self.uniq_id, comment=self.comment))

    def __repr__(self):
        return '<Comment %r>' % self.pkg



'''

Form validation classes

Importing this further down to avoid the TextField conflict with couch

'''

from flask_wtf import Form, TextField, Required, Email, Optional, Length, ValidationError, url, FieldList
from flask_wtf.html5 import URLField



class CommentCreateForm(Form):
    comment = TextField('Brief comment', validators=[Length(min=1,max=512), Required()])

class CommentUpdateForm(CommentCreateForm):
    pass



__all__ = ['Comment', 'CommentCreateForm', 'CommentUpdateForm']
