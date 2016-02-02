from appluvr import couchdb
from couchdbkit.schema import *
from couchdbkit import *
import appluvr.utils
from appluvr.prefix import *
from base import LinkedDocument
from flask import current_app, jsonify
from appluvr.utils.misc import crypto

class Device(LinkedDocument):
    """
    .. autoclass:: Device

    Main device class. Needs to be associated with a user.

    """

    doc_type = 'device'
    # Make Name
    make = StringProperty()
    # Model name
    model = StringProperty()
    # Model number
    number = StringProperty()
    # OS version
    os_version = StringProperty()
    # Device UDID
    udid = StringProperty()
    # Device Carrier
    carrier = StringProperty(default='')
    # Appluvr Build Number
    appluvr_build = StringProperty(default='')
    # List of apps installed
    apps_installed = ListProperty()
    #List of process, url schemes, user adds and removes for IOS apps
    apps_url_schemes = ListProperty()
    apps_process_names = ListProperty()
    apps_user_added = ListProperty()
    apps_user_removed = ListProperty()
    apps_fb_shared = ListProperty()
    apps_fb_share_status = StringProperty(default='')
    advertisingIdentifier = StringProperty(default='')
    advertisingTrackingEnabled = StringProperty(default='')
    # ODP Installed
    odp_installed = BooleanProperty(default=False)
    # Read Installed Apps
    read_apps = BooleanProperty(default=False)
    # Device MDN
    MDN = StringProperty(default='')
    ATT_subid = StringProperty(default='')

    #all_devices = ViewDefinition('device', 'all_devices','')


    def toDict(self):
        return dict(super(Device, self).toDict(), **dict(udid=self.udid, make=self.make, model=self.model, number=self.number, os_version = self.os_version, apps_installed=self.apps_installed, odp_installed=self.odp_installed, read_apps=self.read_apps, carrier=self.carrier, appluvr_build=self.appluvr_build, apps_fb_shared=self.apps_fb_shared,apps_fb_share_status=self.apps_fb_share_status,ATT_subid=self.ATT_subid,MDN = self.MDN if self.MDN != 'IiI.5_voOX4QaWZIjId9Q1TINTsSPnw' else ''))

#    @property
    def profile(self):
        d = self
        device_profile = dict(manufacturer=d.make, odp_installed=d.odp_installed, model=d.model, number=d.number, os_version=d.os_version, apps_installed = d.apps_installed, uid=d.appo_id, carrier=d.carrier, appluvr_build=self.appluvr_build, apps_fb_shared=self.apps_fb_shared, apps_fb_share_status=self.apps_fb_share_status,ATT_subid=self.ATT_subid) 
        member_profile = dict( \
                device_profile=device_profile \
                )
        spit(member_profile)
        spit(jsonify(json=member_profile))
        return member_profile

    def get_platform(self):
        if self.make == 'Apple':
            platform = 'ios'
        else:
            platform = 'android'
        return platform

#    @property
    def appo_id(self):
        """
        Function that takes the user's device's unique identifer, 
        applies a reversible crypto function to it
        and returns the result for transmission to Appo
        """
        return crypto.push(self._id)

#    @property
    def owners(self):
        links = self.get_links()
        owners = [link['href'] for link in links if link['rel'] == 'user' and link['href'] != '__stale__']
        return owners

    def __repr__(self):
        return '<Device %r>' % self.model


'''

Form validation classes

Importing this further down to avoid the TextField conflict with couch

'''

from flask_wtf import Form, TextField, Required, Email, Optional, Length, SelectMultipleField



class DeviceCreateForm(Form):
    make = TextField('Manufacturer name', validators=[Length(min=1,max=50),Required('Please provide the name of the Manufacturer')])
    model = TextField('Model name/number', validators=[Length(min=1,max=50),Required('Please provide a model name')])
    number = TextField('Model name/number', validators=[Length(min=1,max=50),Required('Please provide a model number')])
    os_version = TextField('OS version', validators=[Length(min=1,max=20),Required('Please provide the OS version number')])
    uniq_id = TextField('Unique user identifier', validators=[Length(min=4,max=100),Required('Please provide the unique identifier for the user who owns the device')])
    udid = TextField('Device UDID', validators=[Required('Please provide the device\'s unique identifier')])
    carrier = TextField('Device Carrier',validators=[Length(min=0,max=50)])
    notification_token = TextField('Device Push Notification Token',validators=[Length(min=0,max=100)])
    appluvr_build = TextField('AppLuvr Build',validators=[Length(min=0,max=50)])
    advertisingIdentifier = TextField('iOS advertisingIdentifier',validators=[Length(min=0,max=50)])
    advertisingTrackingEnabled = TextField('iOS advertisingTrackingEnabled',validators=[Length(min=0,max=50)])
    MDN = TextField('MDN for Android',validators=[Length(min=0,max=50)])
    ATT_subid = TextField('AT&T Subscriber ID',validators=[Length(min=0,max=50)])


class DeviceUpdateForm(Form):
    model = TextField('Model name/number', validators=[Length(min=1,max=50),Optional()])
    uniq_id = TextField('Unique user identifier', validators=[Length(min=4,max=100),Required('Please provide the unique identifier for the user who owns the device')])
    ATT_subid = TextField('AT&T Subscriber ID',validators=[Length(min=0,max=50)])


class DeviceCreateAppsForm(Form):
    pkgs = TextField('App packages', validators=[Length(min=1,max=40000),Required('Please provide a comma seperated list of app packages.')])



__all__ = ['Device', 'DeviceCreateForm', 'DeviceUpdateForm', 'DeviceCreateAppsForm']

