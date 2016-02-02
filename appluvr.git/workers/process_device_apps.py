"""
Worker tasks to process device data for a user

Example Usage:
python process_device_apps.py apps http://baadaami.herokuapp.com/v2/ arvi@alumni.iastate.edu 212361089207890 '[{"first_created": 1333375114, "last_modified": 1333375586, "package_name": "com.google.earth"}, {"first_created": 1333375114, "last_modified": 1333375586, "package_name": "com.rovio.angrybirds"}]' -d

"""


import couchdb
from appluvr_views.extensions import cache, appocatalog
from appluvr_views import couch, couchdb
from flask import Flask, g, json, request, jsonify, current_app
from werkzeug import LocalProxy
from flaskext.script import Manager
import requests
from workerd import delayable
from appluvr.models.device import Device
from appluvr.models.user import User
from couchdbkit import *
from appluvr.utils.misc import verify_system_package
from vendor.lib.jsonvalidator import JSONValidator
import os, sys
from build_carousel_views import get_app_summary
import time
from ios_notification import notify_friends_apps
from build_card_views import  fetch_app_card, fetch_friend_card

app = Flask(__name__)
manager = Manager(app)

auth_user = 'tablet'
auth_pwd = os.environ.get('APPLUVR_PWD', 'aspirin')

w = LocalProxy(lambda: app.logger.warning)

schema = [{'package_name':'string', 'last_modified':0, 'first_created':0}]
validator = JSONValidator(schema)

ios_schema = {"apps_process_names":[{'package_name':'string', 'last_modified':0, 'first_created':0}],"apps_url_schemes":[{'package_name':'string', 'last_modified':0, 'first_created':0}],"apps_user_added":[{'package_name':'string', 'last_modified':0, 'first_created':0}],"apps_user_removed":[{'package_name':'string', 'last_modified':0, 'first_created':0}]}
ios_validator = JSONValidator(ios_schema)

#-------------------------------------------------------------------------------#

@delayable
def update_device_apps(server, user, device, apps_in, odp_installed_in, auth_pwd=auth_pwd, debug=False):
    """
    apps_in can be either a json formatted string or a python object
    """

   
    #invalidate cache login or on new app installation.
    target = '%sapi/user/%s/uncache' %(server, user)
    r = requests.get(target, auth = (auth_user,auth_pwd))
    if r .status_code == 200:
        current_app.logger.debug("invalidating %s's and his friends apps cards and carousels status : %s" %(user, r.content))

    app.debug = debug
    apps = None
    odp_installed = bool(int(odp_installed_in))
    try:
        apps = validator.validate(apps_in)
    except Exception as e:
        app.logger.error('CRITICAL: updated_device_apps: invalid json critical error. %s' %  repr(e))
        return None
    #app.logger.debug('Harvested apps: %s' % apps)
    apps = [x for x in apps if not verify_system_package(x.get('package_name'))]
    app.logger.debug('Post filter of system apps: %s' % apps)

    time_stamp = int(time.time())
    new_apps = []
    apps_to_install = []

    apps=[{'first_created':time_stamp,'last_modified':time_stamp ,'package_name':pkg_id.get('package_name')} for pkg_id in apps]

    pkgs = [x.get('package_name') for x in apps]
    pkgs = filter_blacklist_apps(server, user, device, pkgs)
    #current_app.logger.debug('----->pkgs :%s'%pkgs)
    if len(pkgs) > 0:
        pkgs = ','.join(pkgs)
        r = requests.get(u'%sviews/apps/summary?ids=%s&platform=android' % (server, pkgs), auth=(auth_user, auth_pwd))
        app.logger.debug('Received summary status %s ' % r.status_code)
        if r.status_code == 200:
            list = [x for x in json.loads(r.content).keys()]
            apps = [x for x in apps if x.get('package_name') in list]
            #app.logger.debug('Post filter of apps that are not in Appos catalog %s' % apps)
            # Load up device object, store updates
            device_obj = Device.load(device)
            try:
                d_apps_ts = device_obj.apps_installed_ts
            except AttributeError:
                d_apps_ts = []
            try:
                d_apps = device_obj.apps_installed
            except AttributeError:
                d_apps = []

            if len(d_apps_ts)>len(apps):
                filterd_uninstalled_apps = []
                filterd_uninstalled_apps_ts = []

                filter_deleted_apps = [each.get('package_name')for each in apps]
                for index, item in enumerate(d_apps_ts):           
                    if item.get('package_name') in filter_deleted_apps:
                        filterd_uninstalled_apps.append(item.get('package_name'))
                        filterd_uninstalled_apps_ts.append(item)

                filtered_encoded_apps_ts = [dict(last_modified= item.get('last_modified'), first_created= item.get('first_created'), package_name= unicode(item.get('package_name')) ) for item in filterd_uninstalled_apps_ts]
                device_obj.apps_installed = filterd_uninstalled_apps
                # Store app install details
                device_obj.apps_installed_ts = filtered_encoded_apps_ts
                
            else:                
                installed_apps = [pkgs_1.get('package_name') for pkgs_1 in d_apps_ts]                 
                for index, item in enumerate(apps):           
                    if item.get('package_name') not in installed_apps:
                        apps_to_install.append(item)
               
                for item in apps_to_install:
                    if item not in d_apps:
                        d_apps.append(item.get('package_name'))
                        d_apps_ts.append(item)
                        new_apps.append(item.get('package_name'))

                encoded_apps_ts = [dict(last_modified= item.get('last_modified'), first_created= item.get('first_created'), package_name= unicode(item.get('package_name')) ) for item in d_apps_ts]
                device_obj.apps_installed = d_apps           
                # Store app install details
                device_obj.apps_installed_ts = encoded_apps_ts

            # Set read apps to True
            device_obj.read_apps = True
            device_obj.odp_installed = odp_installed 
            try:
                device_obj.update()
                if len(new_apps)>0:                        
                    friends_apps_notification = notify_friends_apps(server, user, new_apps, platform = 'android')
                    app.logger.debug("MFA Push Status: %s"%friends_apps_notification)
                app.logger.debug('Updated device details for %s' % device)

            #except couchdb.http.ResourceConflict:
                #app.logger.error('Worker failure writing installed apps, Device %s resource conflict' % device)
            except:
                app.logger.error('Couch Update Exception Caught - %s' % sys.exc_info()[0])
        else:
            app.logger.error('Worker failure in fetching app summaries, status code %s' % r.status_code)
    else:
        app.logger.warning('Empty app list uploaded')
    return json.dumps(apps)

def get_apps_by_processname(server, processName_list,time_stamp):
    list_index=0;
    process_apps=[]
    #target='%sprocessnames/?pkgs=%s'%(server, ','.join([apps for apps in processName_list]))
    target='%sprocessnames/'%server
    body = {'pkgs': ",".join([apps for apps in processName_list])} 
    r=requests.get(target)
    #r=requests.post(target,data=body)
    if r.status_code==200:
        app_data=json.loads(r.content).get('results',None)
        apps_ids=[data.get('itunesID',None)for data in app_data]         
        process_apps=[{'package_name':itunesID,'first_created':time_stamp,'last_modified':time_stamp}for itunesID in  apps_ids]
        return process_apps ,apps_ids
    else:
        app.logger.debug('No processnames mapped %s - Server target %s' % (r.status_code,target))
        return [],[]

def get_apps_by_urlscheme(server, urlScheme_list,time_stamp):
    list_index=0;
    urlScheme_apps=[]
    #target='%surlschemes/?pkgs=%s'%(server, ','.join([apps for apps in urlScheme_list])) 
    target='%surlschemes/'%server
    body = {'pkgs': ",".join([apps for apps in urlScheme_list])} 
    r=requests.post(target,data=body)
    if r.status_code==200:
        app_data=json.loads(r.content).get('results',None)
        apps_ids=[data.get('itunesID',None)for data in app_data]
        urlScheme_apps=[{'package_name':itunesID,'first_created':time_stamp,'last_modified':time_stamp} for itunesID in apps_ids]
        return urlScheme_apps,apps_ids
    else:
        app.logger.debug('No processnames mapped: %s  - Server target %s' % (r.status_code,target))
        return [],[]

@delayable
def update_ios_device_apps(server, user, device, apps_in, auth_pwd=auth_pwd, debug=False, cmdline=False):
    """
    apps_in can be either a json formatted string or a python object
    """
    app.debug = debug
    apps = None
    p0=u0=p1=u1=[]
    user_added_ts = []
    apps=[]
    appsid=[]
    apps_ts = []
    new_apps = [] 
    apps_to_install = []
    raw_apps = json.loads(apps_in)
    '''->> TODO: fix validator'''
    #try:
    #    apps = ios_validator.validate(apps_in)
    #except Exception as e:
    #    app.logger.error('CRITICAL: updated_device_apps: invalid json critical error. %s' %  repr(e))
    #    return None

    #invalidate cache login or on new app installation.
    target = '%sapi/user/%s/uncache' %(server, user)
    r = requests.get(target, auth = (auth_user,auth_pwd))
    if r .status_code == 200:
        current_app.logger.debug("invalidating %s's and his friends apps cards and carousels status : %s" %(user, r.content))

    #Extract TimeStamp of call
    time_stamp = int(time.time())
    device_obj = Device.load(device)
    #Extract Processes from input
    processes = raw_apps['apps_process_names']
    urlschemes = raw_apps['apps_url_schemes']
    user_removed_apps_ids = raw_apps.get('apps_user_removed',None) 
    user_added_apps_ids = raw_apps.get('apps_user_added',None) 
    user_removed_apps=[{'first_created':time_stamp,'last_modified':time_stamp ,'package_name':pkg_id} for pkg_id in raw_apps.get('apps_user_removed',None)] 
    if user_removed_apps_ids:
        device_obj.apps_user_removed = list(set(device_obj.apps_user_removed + user_removed_apps_ids))
        device_obj.apps_user_added = list ((set(device_obj.apps_user_added)) - set(device_obj.apps_user_removed))
    if user_added_apps_ids:
        device_obj.apps_user_added = list(set(device_obj.apps_user_added + user_added_apps_ids))
        device_obj.apps_user_removed = list ((set(device_obj.apps_user_removed)) - set(device_obj.apps_user_added))
    user_added_ts=[{'first_created':time_stamp,'last_modified':time_stamp ,'package_name':pkg_id} for pkg_id in device_obj.apps_user_added]
    #Process List Calculation
    #New Processlist is merged with the list found on device
    processes = list(set(device_obj.apps_process_names + processes))
    if processes:
        #app.logger.debug('input to xmap api: %s'%processes)
        p0,p1=get_apps_by_processname('http://vzw.appluvr.com/xmap/api/1.0/getappsby/', processes,time_stamp)  
        #app.logger.debug('applist from processnames = %s'% p1)
    device_obj.apps_process_names = processes

    #Load URL schemes from Device if input is empty
    #New Load of Urlschemes overwrites the older list
    if urlschemes:
        device_obj.apps_url_schemes = urlschemes
    else:
        urlschemes = device_obj.apps_url_schemes

    #Extract URL schemes from input
    if urlschemes:
        u0,u1 = get_apps_by_urlscheme('http://vzw.appluvr.com/xmap/api/1.0/getappsby/', urlschemes,time_stamp) 
        #app.logger.debug('applist from urlschemes = %s'% u1)

    #Creating app list from processlist, url schemes & User adds
    apps= p0 + u0 + user_added_ts
    # #1851 Ticket code(Remove Apps from the Apps list when a user flags an app for removal)
    [apps.pop(key) for key ,value in enumerate(apps) if value.get('package_name') in device_obj.apps_user_removed ]
    apps=[dict(tupleized) for tupleized in set(tuple(item.items()) for item in apps)] 
    appids = list(set(p1 + u1 + device_obj.apps_user_added))
    appids = [appid for appid in appids if appid not in device_obj.apps_user_removed]
    #app.logger.debug('applist combined = %s'% appids)

    #verify with Appo if the appids exist
    pkgs = filter_blacklist_apps(server, user, device, appids)
    pkgs = ','.join(pkgs)

    if len(pkgs) > 0:
        r_appo = requests.get(u'http://verizon.appolicious.com/api/verizon/v3/apps/details?platform=ios&ids=%s&summary=1' %(pkgs), auth=('brandmobility', 'verizon') )
        #app.logger.debug('Received summary status %s ' % r_appo.status_code)
        if r_appo.status_code == 200:
            appolist = [x for x in json.loads(r_appo.content).keys()] 
            apps = [x for x in apps if x.get('package_name') in appolist]
            #app.logger.debug('Post filter of apps that are in Appos catalog %s' % apps)
            # Older apps_installed field for v1 compatibility
            try:
                d_apps_ts = device_obj.apps_installed_ts
            except AttributeError:
                d_apps_ts = []
            try:
                d_apps = device_obj.apps_installed
            except AttributeError:
                d_apps = []
   
            if len(d_apps_ts)>len(apps):
                filterd_uninstalled_apps = []
                filterd_uninstalled_apps_ts = []
                uninstalledapps = []

                filter_deleted_apps = [each.get('package_name')for each in apps]
                for index, item in enumerate(d_apps_ts):           
                    if item.get('package_name') in filter_deleted_apps:
                        filterd_uninstalled_apps.append(item.get('package_name'))
                        filterd_uninstalled_apps_ts.append(item)

                filtered_encoded_apps_ts = [dict(last_modified= item.get('last_modified'), first_created= item.get('first_created'), package_name= unicode(item.get('package_name')) ) for item in filterd_uninstalled_apps_ts]
                device_obj.apps_installed = filterd_uninstalled_apps
                # Store app install details
                device_obj.apps_installed_ts = filtered_encoded_apps_ts

                for index, item in enumerate(d_apps_ts):  
                    if item.get('package_name') not in filter_deleted_apps:
                        uninstalledapps.append(item.get('package_name'))

                #Invalidate app card cache on app uninstall.                
                for apppkg in uninstalledapps:
                        cache.delete_memoized(fetch_app_card, server, user, device, unicode(apppkg), auth_pwd=auth_pwd, debug=False)
                        cache.delete_memoized(fetch_app_card, server, user, device, unicode(apppkg), auth_pwd=auth_pwd, debug=True)

            else:                
                installed_apps = [pkgs_1.get('package_name') for pkgs_1 in d_apps_ts]                 
                for index, item in enumerate(apps):           
                    if item.get('package_name') not in installed_apps:
                        apps_to_install.append(item)
               
                for item in apps_to_install:
                    if item not in d_apps:
                        d_apps.append(item.get('package_name'))
                        d_apps_ts.append(item)
                        new_apps.append(item.get('package_name'))

                encoded_apps_ts = [dict(last_modified= item.get('last_modified'), first_created= item.get('first_created'), package_name= unicode(item.get('package_name')) ) for item in d_apps_ts]
                device_obj.apps_installed = d_apps           
                # Store app install details
                device_obj.apps_installed_ts = encoded_apps_ts

            # Set read apps to True
            device_obj.read_apps = True
            try:
                device_obj.update()
                if len(new_apps)>0:
                    friends_apps_notification = notify_friends_apps(server, user, new_apps, platform = 'ios')
                    for apppkg in new_apps:
                        cache.delete_memoized(fetch_app_card, server, user, device, unicode(apppkg), auth_pwd=auth_pwd, debug=False)
                        cache.delete_memoized(fetch_app_card, server, user, device, unicode(apppkg), auth_pwd=auth_pwd, debug=True)
        
                app.logger.debug('Updating Device with update in apps')
                #app.logger.debug('Updated device details for %s' % device)
            #except couchdb.http.ResourceConflict:
            #    app.logger.error('Worker failure writing installed apps, Device %s resource conflict' % device)
            except:
                app.logger.error('Couch Update Exception Caught - %s ' % sys.exc_info()[0])
            #Fb Share
            app.logger.debug("FB_Share_Status : %s"%device_obj.apps_fb_share_status)
            if device_obj.apps_fb_share_status == '2':
                platform='ios'
                headers = {'content-type': 'application/json'}
                message = "I just found some cool apps using AppLuvr!"
                installed_apps = device_obj.apps_installed
                fb_shared_apps = device_obj.apps_fb_shared
                apps2share=list(set(installed_apps) - set(fb_shared_apps))
                app.logger.debug("Apps2Share to FB: %s"%apps2share)
                if len(apps2share)>0:            
                    result= get_app_summary(server,apps2share,platform)
                    app_names= result.get('apps')
                    pkg_list=[singleapp.get('itunes_market').get('name', None)for singleapp in app_names]
                    #Share the status to facebook
                    output="%s\r\n%s"%(message,', '.join(pkg_list))
                    data={"message":output} 
                    post_url= '%sapi/users/%s/fb/feed'%(server,user)
                    r=requests.post(post_url, data=json.dumps(data), headers=headers, auth=(auth_user,auth_pwd))
                    fbstatus = r.status_code  
                    if r.status_code==200:
                        device_obj.apps_fb_shared=list(set(device_obj.apps_fb_shared + apps2share)) 
                        device_obj.update()                         
                    else:        
                        fbstatus=400
                    app.logger.debug('apps shared status= %s'% fbstatus)
        else:
            device_obj.update()
            app.logger.error('Worker failure in fetching app summaries, status code %s' % r.status_code)
    else:
        device_obj.apps_installed_ts =[]
        device_obj.apps_installed=[]
        device_obj.update()
        app.logger.warning('No More Apps in AFY build_carousel_views')

    try:
        apps_I_use = device_obj.apps_installed_ts
    except(AttributeError, TypeError, KeyError):
        apps_I_use = []

    return json.dumps(apps_I_use)

def filter_blacklist_apps(server, user, device, installed_apps):
    """
    stub to filter blocklisted apps from the installed apps list.
    """
    my_apps = installed_apps
    user_obj = User.load(user)
    platform, carrier = get_user_device_appo_carrier_platform(user_obj)
    target = '%sapi/apps/blacklist/?platform=%s&carrier=%s' %(server, platform, carrier)
    r = requests.get(target, auth = (auth_user, auth_pwd))
    if r. status_code == 200:
        blacklist_apps = json.loads(r.content).get('blacklisted_apps')
        
        if platform == 'android':
            blacklisted_apps = [apps.get('package_name') for apps in blacklist_apps]
        else:
            blacklisted_apps = [apps.get('itunes_id') for apps in blacklist_apps]

        my_apps = [pkg for pkg in installed_apps if pkg not in blacklisted_apps]
    return my_apps

def get_user_device_appo_carrier_platform(user):
    platform = None
    carrier = None

    if user is not None:
        device_ids = [link['href'] for link in user.links if link['rel'] == 'device']
    else:
        device_ids = []

    if device_ids:
        devices = [Device.load(i).toDict() for i in device_ids if Device.load(i) is not None]
        if devices:
            platform = (devices[0]['make']=='Apple') and  'ios' or 'android'
            if "verizon" in devices[0]['carrier'].lower():
                carrier = "verizon"
            elif "att" in devices[0]['carrier'].lower() or "at&t" in devices[0]['carrier'].lower():
                carrier = "att"
            else:
                carrier = "verizon"
    else:
        platform="android"
        carrier ="Verizon"
    return platform,carrier
#-------------------------------------------------------------------------------#
@manager.command
def apps(server, user, device, json, auth_pwd=auth_pwd, debug=False):
    return update_device_apps(server, user, device, json, auth_pwd, debug)

@manager.command
def ios_apps(server, user, device, json, auth_pwd=auth_pwd, debug=False):
    return update_ios_device_apps(server, user, device, json, auth_pwd, debug,cmdline=True)
#-------------------------------------------------------------------------------#
if __name__ == '__main__':
    manager.run()


