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


class User(LinkedDocument):
    doc_type = 'user'

    first_name = StringProperty()
    last_name = StringProperty()
    apps_liked = ListProperty()
    apps_disliked = ListProperty()
    interests = ListProperty()
    fb_id = StringProperty()
    fb_token = StringProperty()
    name = StringProperty()
    email = StringProperty()
    advisor = StringProperty()
    uniq_id = StringProperty()
    about = StringProperty()
    lastmf_check = StringProperty()
    apic_url = StringProperty()
    advisor_carrier = StringProperty()
    fb_login = IntegerProperty(default=None)

    # Returns tupled list of apps with counts
    def apps(self):
        devices = [link['href'] for link in self.links if link['rel'] == 'device']
        applist = [(i,Device.load(i).apps_installed) for i in devices if Device.load(i)]
        return applist

    # Returns tupled list of timestamped apps with counts
    def apps_ts(self):

        devices = [link['href'] for link in self.links if link['rel'] == 'device']

        def massage_apps(app_tuple_list):
            # Massage apps for v1 users and experts
            if len(app_tuple_list):
                # pull tuple details
                device_id = app_tuple_list[0][0]
                expert_apps = app_tuple_list[0][1]
            else:
                # initialize if they dont exist
                device_id = expert_apps = None
            applist = [(device_id, [dict(package_name=pkg, first_created=1321809540, last_modified=1321809540) for pkg in expert_apps])] if expert_apps is not None else []           
            return applist

        if self.advisor is None:
            try:
                applist = [(i,Device.load(i).apps_installed_ts) for i in devices if Device.load(i)]
            except:
                #v1 user doesnt have associated capabilities
                user_apps = self.apps()
                applist = massage_apps(user_apps)
        else:
            # Massage data set for advisors to inject past timestamps
            # Note: Assumes experts have only one device
            user_apps = self.apps()
            applist = massage_apps(user_apps)
        return applist


    # Returns a list of all the apps across devices
    # TODO: Cleanup naming vis-a-vis apps(self)
#    @property
    def all_apps(self):
        retval = []
        devices = [link['href'] for link in self.links if link['rel'] == 'device']
        devices_objs = [Device.load(i) for i in devices if Device.load(i) is not None]
        if devices_objs:
            applist = [d.apps_installed for d in devices_objs]
            retval = [item for sublist in applist for item in sublist]
            spit('%s \'s apps: %r', self.uniq_id, retval)
        return retval

    # List of apps in common with a friend
    def common_apps(self, friend_id):
        friend = User.load(friend_id)
        if not friend:
            return []
        friends_apps = friend.all_apps()
        my_apps = self.all_apps()
        common_apps = set(friends_apps) & set(my_apps)
        spit('Common apps %s', common_apps)
        return list(common_apps)


#    @property
    def only_blocked_friends(self):
        perms = UserDisallow.load('perms.'+self.uniq_id)  
        if not perms or perms.blocked_friends is None:
            return []
        only_blocked_friends = [user.strip() for user in perms.blocked_friends.split(',')]
        active_blocked_friends = User.view('user/all_users', keys=only_blocked_friends)        
        only_blocked_friends = [user._id for user in active_blocked_friends if user.advisor is None]
        return only_blocked_friends


#    @property
    def only_blocked_advisors(self):
        perms = UserDisallow.load('perms.'+self.uniq_id)   
        if not perms or perms.blocked_friends is None:
            return []
        only_blocked_advisors = [user.strip() for user in perms.blocked_friends.split(',')]
        active_blocked_friends = User.view('user/all_users', keys=only_blocked_advisors)       
        blocked_advisors = [user._id for user in active_blocked_friends if user.advisor is not None ]
        return blocked_advisors

#    @property
    def blocked_friends(self):
        perms = UserDisallow.load('perms.'+self.uniq_id)       
        if not perms or perms.blocked_friends is None:
            return []
        blocked_friends = [user.strip() for user in perms.blocked_friends.split(',')]
        active_blocked_friends = User.view('user/all_users', keys=blocked_friends)
        blocked_friends = [user._id for user in active_blocked_friends]
        return blocked_friends

#    @property
    def blocking_friends(self):
        rows = UserDisallow.view('user_disallow/inward', key=self.uniq_id)
        blocking_friends = [row['value'] for row in rows]
        return blocking_friends

    @cache.memoize(60)
    def fb_fetch_friends(self,pic=False):
        if pic:
            fml_endpoint = '%s%s' %(FB_FRIENDS_WITH_PIC,self.fb_token)
        else:
            fml_endpoint = '%s%s' % (FB_FRIENDS, self.fb_token)
        fb_response = requests.get(fml_endpoint)
        # We dont bubble the fb error up
        return fb_response.status_code, fb_response.content

    #@cache.memoize(60)
    def fb_friends(self, block=True):
        # If we dont have a token, bail
        if not self.fb_token:
            return []
        #:Fetch list of all fb users
        fb_response_status_code,fb_response_content = self.fb_fetch_friends()
        applvr_friends = []
        # We dont bubble the fb error up
        if fb_response_status_code != 200:
            if fb_response_status_code is 400:
                # Flag a bad request, wipe out auth token
                self.fb_token = None
            return []
        fb_response = fb_response_content
        fb_data = simplejson.loads(fb_response)["data"]
        fbids = [fbuser[u"id"] for fbuser in fb_data]
        rows = User.view('user/user_for_fb_id', keys=fbids)
        applvr_friends = [row['value'] for row in rows]
        if block == True:
            block_list = self.blocked_friends() + self.blocking_friends()
        else:
            block_list = self.blocking_friends()    
        # Commented these lines to temporarily fix odd document update conflict error
        #self.friends = applvr_friends
        #self.update()
        return list(set(applvr_friends) - set(block_list))


 #   @property
    def odp_installed(self):
        device_ids =  [link['href'] for link in self.links if link['rel'] == 'device']
        devices = [Device.load(i) for i in device_ids]
        device_profiles = [dict(manufacturer=d.make, odp_installed=d.odp_installed, model=d.model, number=d.number, os_version=d.os_version, apps_installed = d.apps_installed) for d in devices]
        user_profile = dict(interests_liked = self.interests)
        try:
            #Grabs the first device (Needs to be extended for v2)
            device_profile = device_profiles.pop()
        except IndexError as e:
            spit('No devices attached to this user %s', self.uniq_id)
            device_profile = {}
        return device_profile.get('odp_installed',None)


 #   @property
    def profile(self):
        device_ids =  [link['href'] for link in self.links if link['rel'] == 'device']
        devices = [Device.load(i) for i in device_ids if Device.load(i) is not None]
        device_profiles = [dict(manufacturer=d.make, odp_installed=d.odp_installed, model=d.model, number=d.number, os_version=d.os_version, apps_installed = d.apps_installed, uid=d.appo_id(), carrier = d.carrier) for d in devices]
        user_profile = dict(interests_liked = self.interests, apic_url=self.apic_url, advisor_carrier=self.advisor_carrier)
        uid=self.appo_id()
        print self.toDict()
        print self.apps_disliked
        print self.apps_liked
        user_profile['apps_liked'] = self.apps_liked
        user_profile['apps_disliked'] = self.apps_disliked
        member_profile = dict( \
            uid=uid, \
                device_profiles=device_profiles, \
                user_profile=user_profile \
                )
        spit(member_profile)
        spit(jsonify(json=member_profile))
        return member_profile


    def appo_profile(self):
        # Rewrote appo profile lookup to not use the couchdb view
        my_profile = self.profile()
        user = my_profile.get('user_profile')
        if len(my_profile.get('device_profiles'))>0:
            device = my_profile.get('device_profiles').pop()
        else:
            device = my_profile.get('device_profiles')
        user = AttrDict(user)
        device = AttrDict(device)        
        profile = dict(
            uid = safe_serialize(my_profile.get('uid'))[:24],
            device_profile = dict(
                os_version = device.get('os_version'),
                apps_installed = device.get('apps_installed',[]),
                apps_liked = user.get('apps_liked', []),
                apps_disliked = user.get('apps_disliked', []),
                model = device.get('model'),
                manufacturer = device.get('manufacturer'),
                odp_installed = device.get('odp_installed'),
                number = device.get('number'),
                udid = safe_serialize(device.get('uid'))[:24],
                carrier = device.get('carrier')
                ),
            user_profile = dict(
                # Appo v1 format requires a serialized list of interests
                interests_liked = ','.join(user.interests_liked) if user.interests_liked is not None else None,
                interests = user.get('interests_liked', [])
            )
        )        
        return profile

#    @property
    @cache.memoize(60)
    def appo_id(self):
        """
        Function that takes the user's unique identifer,
        applies a reversible crypto function to it
        and returns the result for transmission to Appo
        """
        return crypto.push(self._id)

    def safe_serialize_appo_id(self):
        my_profile = self.profile()
        return safe_serialize(my_profile.get('uid'))[:24]

    def toDict(self):
        return dict(super(User, self).toDict(), **dict(uniq_id=self.uniq_id, fb_id=self.fb_id, name=self.name, email=self.email,interests=self.interests,advisor=self.advisor,about=self.about, first_name = self.first_name, last_name = self.last_name,))

    def negative_interests_toDict(self):
        return dict(_id= self._id, uniq_id = self.uniq_id, interests = self.interests)

    def __repr__(self):
        return '<User %r>' % self.name


class UserDisallow(LinkedDocument):
    doc_type = 'user_disallow'
    # Uniq id of this user
    me = StringProperty()
    # Uniq ids of the user's friends who are blocked
    blocked_friends = StringProperty()

    def toDict(self):
        return dict(super(UserDisallow, self).toDict(), **dict(me=self.me, blocked_friends = self.blocked_friends))

    def __repr__(self):
        return '<User %r -> Blocked Friends %r>' % self.user % self.blocked_friends

'''

Form validation classes

Importing this further down to avoid the TextField conflict with couch

'''

from flask_wtf import Form, TextField, Required, Email, Optional, Length, ValidationError, url
from flask_wtf.html5 import URLField



class UserCreateForm(Form):
    name = TextField('User Name', validators=[Length(min=1,max=120),Required('Please provide a user name')])
    uniq_id = TextField('Unique user identifier', validators=[Length(min=4,max=100),Required('Please provide an unique identifier for the user')])
    fb_id = TextField('Facebook ID', validators=[Optional()])
    first_name = TextField('First Name', validators=[Optional()])
    last_name = TextField('Last Name', validators=[Optional()])
    fb_token = TextField('Facebook Token', validators=[Length(min=10,max=250),Optional()])
    email = TextField('User Email', validators=[Required('Please provide an email address'),Email()])
    advisor = TextField('Advisor type', validators=[Length(min=2,max=20),Optional()])
    interests = TextField('User interests', validators=[Length(min=3,max=300),Optional()])

    def validate_advisor(form, field):
        if field.data == "Verizon" or field.data == "Appolicious" or field.data =="ATT" or field.data=="BM":
            return True
        else:
            return False

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


class UserUpdateForm(Form):
    name = TextField('Name',validators=[Optional()])
    first_name = TextField('First Name', validators=[Optional()])
    last_name = TextField('Last Name', validators=[Optional()])
    fb_id = TextField('Facebook ID', validators=[Optional()])
    fb_token = TextField('Facebook Token', validators=[Length(min=10,max=250),Optional()])
    email = TextField('User Email', validators=[Email(),Optional()])
    advisor = TextField('Advisor type', validators=[Length(min=2,max=20),Optional()])
    interests = TextField('User interests', validators=[Length(min=3,max=300),Optional()])

    def validate_advisor(form, field):
        if field.data == "Verizon" or field.data == "Appo":
            return True
        else:
            return False

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


class UserDisallowForm(Form):
    me = TextField('User unique identifier', validators=[Required('Please provide a unique user identifier')])
    blocked_friends = TextField('Blocked friends comma separated list', validators=[Optional()])

    def validate_blocked_friends(form, field):
        if field.data:
            try:
                friends_str = field.data.split(',')
                friends = [friend.strip() for friend in friends_str]
                count = len(friends)
                my_friends = User.view('user/all_users', keys=friends)
                if len(my_friends) < count:
                    raise ValidationError('Invalid friend provided > ')
            except Exception as e:
                raise ValidationError('Invalid friend provided: ' + str(e))
                

class UserFBPostForm(Form):
    message = TextField('Message', validators=[Length(min=1,max=60000),Required('Please enter a message to post on the Wall')])
    picture = URLField('Picture to include with the post', validators=[url(),Optional()])


class UserNegativeInterests(LinkedDocument):
    doc_type = 'user_negative_interest'

    negative_interests = ListProperty(default =[])
    uniq_id = StringProperty()

    def negative_interests_toDict(self):
        return dict(_id = self._id, uniq_id = self.uniq_id, negative_interests = self.negative_interests)

    #    @property
    def __repr__(self):
        return '<user_negative_interest %r>' % self._id

class UserNegativeInterestsCreateForm(Form):
    uniq_id = TextField('Unique user identifier', validators=[Length(min=4,max=100),Required('Please provide an unique identifier for the user')])
    negative_interests = TextField('user interests', validators=[Optional()])

    def validate_user_negative_interests(form, field):
        if field.data:
            try:
                cats = field.data.split(',')
                cats = [cat.strip() for cat in cats]
            except:
                raise ValidationError('Invalid category list')

class UserNegativeInterestsUpdateForm(Form):
    uniq_id = TextField('Unique user identifier', validators=[Length(min=4,max=100),Required('Please provide an unique identifier for the user')])
    negative_interests = TextField('user interests', validators=[Optional()])

    def validate_user_negative_interests(form, field):
        if field.data:
            try:
                cats = field.data.split(',')
                cats = [cat.strip() for cat in cats]
            except:
                raise ValidationError('Invalid category list')

class UserSeenDeal(LinkedDocument):
    doc_type = 'deal_by_user'
    seen_deal = ListProperty(default = [])
    uniq_id = StringProperty()

    def deal_seen_toDict(self):
        return dict (_id = self._id, seen_deal = self.seen_deal, uniq_id = self.uniq_id)

    #    @property
    def __repr__(self):
        return '<user_seen_deal %r>' % self.deal_id

class UserSeenDealCreateForm(Form):
    uniq_id = TextField('Unique user identifier', validators=[Length(min=4,max=100),Required('Please provide an unique identifier for the user')])
    seen_deal = TextField('user seen deal', validators=[Optional()])

    def validate_user_deal_seen(form, field):
        if field.data:
            try:
                cats = field.data.split(',')
                cats = [cat.strip() for cat in cats]
            except:
                raise ValidationError('Invalid category list')

class UserSeenDealUpdateForm(Form):
    uniq_id = TextField('Unique user identifier', validators=[Length(min=4,max=100),Required('Please provide an unique identifier for the user')])
    seen_deal = TextField('user seen deal', validators=[Optional()])

    def validate_user_deal_seen(form, field):
        if field.data:
            try:
                cats = field.data.split(',')
                cats = [cat.strip() for cat in cats]
            except:
                raise ValidationError('Invalid category list')


__all__ = ['User', 'UserDisallow', 'UserCreateForm', 'UserUpdateForm', 'UserFBPostForm', 'UserDisallowForm', 'UserNegativeInterests', 'UserNegativeInterestsCreateForm', 'UserNegativeInterestsUpdateForm', 'UserSeenDeal', 'UserSeenDealCreateForm', 'UserSeenDealUpdateForm']
