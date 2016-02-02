from appluvr import couchdb
from couchdbkit.schema import *
from couchdbkit import *
import appluvr.utils
from appluvr.prefix import *
from appluvr.models.interest import *
from base import LinkedDocument
from flask import current_app


class App(LinkedDocument):
    """
    .. autoclass:: App
    """

    # Doc type definition for design document
    doc_type = 'app'
    
    # Fields that are populated by Appo bulk upload
    pkg = StringProperty()
    appo = StringProperty()
    #android_market = DictField()
    #vcast_market = DictField()

    # Optional fields that get populated by the client
    liked = ListProperty()
    disliked = ListProperty()

    #all_apps = ViewDefinition('app','all_apps','')
    #all_app_pkgs = ViewDefinition('app','all_app_pkgs','')

    def toDict(self):
        return dict(super(App, self).toDict(), **dict(pkg=self.pkg, likes=self.liked, disliked=self.disliked))

    def __repr__(self):
        return '<App %r>' % self.pkg



class PromoApp(LinkedDocument):
    """
    .. autoclass:: PromoApp
    """

    # Doc type definition for design document
    doc_type = 'promoapp'
    
    pkg = StringProperty()
    # Type - either Verizon or Android market
    market = StringProperty()
    # List of interests it maps to, defaults to all
    interests = ListProperty()
    punchline = StringProperty()

    # Carousel to place the app in - can be either apps_for_you or hot_apps
    carousel = StringProperty()
    carrier = StringProperty(default='')
    platform = StringProperty(default='')
    priority = StringProperty(default='0')
    context_copy = StringProperty(default='')

    #all_apps = ViewDefinition('promoapp','all_apps','')
    #all_app_pkgs = ViewDefinition('promoapp','all_app_pkgs','')
    #all_app_interests = ViewDefinition('promoapp','all_app_interests','')
    #all_hot_apps = ViewDefinition('promoapp','all_hot_apps','')
    #all_apps_for_you = ViewDefinition('promoapp','all_apps_for_you','')


    def toDict(self):
        return dict(super(PromoApp, self).toDict(), **dict(promoid=self._id, pkg=self.pkg, carousel=self.carousel, interests=','.join(self.interests), market=self.market, punchline=self.punchline, platform=self.platform, carrier=self.carrier, priority=self.priority, context_copy= self.context_copy))

    def __repr__(self):
        return '<PromoApp %r>' % self.pkg



'''

Form validation classes

Importing this further down to avoid the TextField conflict with couch

'''

from flask_wtf import Form, TextField, Required, Email, Optional, Length, ValidationError, url, FieldList
from flask_wtf.html5 import URLField



class PromoCreateForm(Form):
    #market = TextField('Market Name', validators=[Length(min=1,max=20), Required('Please provide the name of the marketplace. Possible values are android_market and vcast_market')])
    interests = TextField('Interests List', validators=[Length(min=1,max=200), Required('Please provide the list of interests as a comma separated list. A promo needs to be associated with at least one interest')])
    #punchline = TextField('Punch line', validators=[Length(min=1, max=100), Required('Please provide the punch line associated with this app. This will override the default punch line')])
    carousel = TextField('Carousel for display', validators=[Length(min=1, max=20), Required('Please provide the carousel associated with this promo app. Possible values are apps_for_you and hot_apps')])
    context_copy = TextField('context_copy', validators=[Optional()])
    #def validate_market(form, field):
    #    return field.data == "android_market" or field.data == "vcast_market"

    def validate_carousel(form, field):
        return field.data == "apps_for_you" or field.data == "hot_apps"

    def validate_interests(form, field):
        if field.data:
            try:
                interests_str = field.data.split(',')
                interests = set([interest.strip() for interest in interests_str])
                all_interests = set(Interest._interests())
                invalid_entries = interests - all_interests
                print all_interests
                print interests
                print invalid_entries
                if len(invalid_entries) > 0:
                    raise ValidationError(str(list(invalid_entries)))
            except Exception as e:
                raise ValidationError('Invalid interests provided: ' + str(e))


class PromoUpdateForm(PromoCreateForm):
    market = TextField('Market Name', validators=[Length(min=1,max=20), Optional()])
    interests = TextField('Interests List', validators=[Length(min=1,max=200), Optional()])
    punchline = TextField('Punch line', validators=[Length(min=1, max=100), Optional()])
    carousel = TextField('Carousel for display', validators=[Length(min=1, max=20), Optional()])
    context_copy = TextField('context_copy', validators=[Optional()])


__all__ = ['App', 'PromoApp', 'PromoCreateForm', 'PromoUpdateForm']
