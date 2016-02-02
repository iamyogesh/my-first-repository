"""
Worker tasks to collate amf_notification data for a user
Example Usage:
    python ios_notification.py amf_notification http://leann.herokuapp.com/v2/ de18aff1d36b4ff0858b6ca4a5a05cc3 f7da8334122d19330be1eb5d21e0fbba383878ad  -d
"""
#import sys
#sys.path.append("../")
import couchdb
from appluvr_views import couch, couchdb
from flask import Flask, g, json, request, jsonify, current_app
from werkzeug import LocalProxy
from flaskext.script import Manager
import requests
from workerd import delayable
import grequests
from couchdbkit import *
from appluvr.utils.misc import verify_system_package
from vendor.lib.jsonvalidator import JSONValidator
import grequests
import os
import datetime
from redis import Redis
import urlparse

from appluvr.models.user import *
from appluvr.models.device import *
from build_card_views import get_xmap_results_from_server



app = Flask(__name__)
manager = Manager(app)
auth_user = 'tablet'
auth_pwd = os.environ.get('APPLUVR_PWD', 'aspirin')

w = LocalProxy(lambda: app.logger.warning)
app.debug=True


#-------------------------------------------------------------------------------#
if os.environ.has_key('REDISTOGO_URL'):
    urlparse.uses_netloc.append('redis')
    url = urlparse.urlparse(os.environ['REDISTOGO_URL'])
    REDIS = Redis(host=url.hostname, port=url.port, db=0, password=url.password)
    redis = REDIS
    print 'Redis parameters are %s (hostname), %s (port), %s (password)' % (url.hostname, url.port, url.password)
else:
    redis = Redis()

@delayable
def fetch_amf_notification(server):
    app.debug = debug
    """
    Fetch all my friends created date and compare output with lastmf_check send new friends notification.      
    """
    friends_notification_ids=[]
    friends_data=[(users.get('href',None),device.first_created)for device in Device.view('device/all_devices') for users in device.links if device.make=='Apple']
    for user, first_created in friends_data:
        user_obj = User.load(user)
        friendcount = 0
        now = datetime.datetime.now().strftime("%s")
        if user_obj is not None:
            if user_obj.lastmf_check:
                last_mf_check_data = json.loads(user_obj.lastmf_check)
                mfcheck_date = last_mf_check_data["date"]
                mfcheck_friendcount = last_mf_check_data["friendcount"]
                if int(now)>int(mfcheck_date):
                    #get user friend count
                    url = "%sviews/users/%s/fb/friends"%(server,user)
                    r= requests.get(url, auth=(auth_user,auth_pwd))
                    if r.status_code==200:
                        friendcount = r.json['count']
                        if mfcheck_friendcount < friendcount:
                            friends_notification_ids.append(user_obj._id)
            else:
                friends_notification_ids.append(user_obj._id) 
            user_obj.lastmf_check = json.dumps({"friendcount":friendcount,"date": datetime.datetime.now().strftime("%s")})
            user_obj.update() 

    if len(friends_notification_ids)>0:
        data={"aliases": friends_notification_ids, "aps": {"alert": "You have new AppLuvr Friends!", "sound":"gentle.aiff", "carouselType" : 3}}
        req_status, req_content = create_notification('push', json.dumps(data))
        if req_status == 200:
            return req_content
        else:
            current_app.logger.debug("AMF Push Failed. Status: %s"%req_content)
            return req_content
    else:
        return 'No new friends found for Notifications.'

def notify_ios_friends(server, uid):
    friend_device_id = []
    req_content = ''
    current_user = User.load(uid)
    if current_user:        
        applvr_friends = current_user.fb_friends()      
        for friend in applvr_friends:
            try:
                current_user_login = current_user.fb_login
            except KeyError:
                #If user object doesn't have FB Login Time take first_created
                current_user_login = current_user.first_created

            lastviewed = int(redis.hget('count.'+friend,'mf'))-135 if redis.hget('count.'+friend,'mf') else 0 
            current_app.logger.debug ("@@@ uid %s .. Created date %s .. Friend %s .. friend mfa time %s .. "%(uid,current_user_login,friend,lastviewed))            
            if current_user_login > lastviewed:           
                user_obj = User.load(friend)     
                if user_obj:                 
                    if hasattr(user_obj, 'links'):                            
                        links = user_obj.links            
                        for link in links:
                            if link["rel"] == "device":                                           
                                device_obj = Device.load(link["href"])
                                try:                           
                                    if device_obj.make == "Apple":                            
                                        friend_device_id.append(link["href"])
                                except:
                                    pass



    current_app.logger.debug("@@@Friends list for Notification: %s"%friend_device_id) 
    if len(friend_device_id)>0:
        
        new_build_deviceids = []
        old_build_deviceids = []
        for friendudid in friend_device_id:
            device_object = Device.load(friendudid)
            appluvrBuild = device_object.appluvr_build
            if appluvrBuild == None or appluvrBuild == '':
                old_build_deviceids.append(friendudid) 
            else:               
                appbuild = int(appluvrBuild[:1])
                if appbuild >= 3:                    
                    new_build_deviceids.append(friendudid)
                else:                
                    old_build_deviceids.append(friendudid)    
        
        url = "%sviews/users/%s/fb/profile"%(server,uid)
        r= requests.get(url, auth=(auth_user,auth_pwd))
        if r.status_code == 200:  
            user_data=json.loads(r.content)
            user_profile = user_data.get('fb_profile',None)
            if user_profile:  
                name = user_profile.get('name',None)
                if name:          
                    if len(new_build_deviceids)>0:
                        data={"aliases": new_build_deviceids, "aps": {"alert": "Your Facebook friend %s just joined AppLuvr!" %(name), "sound":"gentle.aiff", "carouselType" : 0}}
                        current_app.logger.debug("@@@ %s"%data)
                    elif len(old_build_deviceids)>0:                        
                        data={"aliases": old_build_deviceids, "aps": {"alert": "Your Facebook friend %s just joined AppLuvr!" %(name), "sound":"gentle.aiff", "carouselType" : 3}}
                        current_app.logger.debug("@@@ %s"%data)
                    else:
                        current_app.logger.debug("executaion should not come to this block")
                        data={"aliases": friend_device_id, "aps": {"alert": "Your Facebook friend %s just joined AppLuvr!" %(name), "sound":"gentle.aiff", "carouselType" : 3}}

                    #current_app.logger.debug("@@@ %s"%data)
                    req_status, req_content = create_notification('push', json.dumps(data))
                    if req_status == 200:
                        return req_content
                    else:
                        current_app.logger.debug("AMF Push Failed. Status: %s"%req_content)
                        return req_content
                else:
                    req_content = "No Attribute called name"
            else:
                req_content = "No Attribute called fb_profile"            
        else:
            current_app.logger.debug("users profile status: %s"%r.status_code)
    else:
        req_content = "No Friends for Notification"
    return req_content


def notify_friends_apps(server, uid, applist, platform):
    """
    stub to send new app dowladed notification to all fb friends.
    """

    ios_friend_device_id = []   
    current_user = User.load(uid)
    if current_user:        
        applvr_friends = current_user.fb_friends()
        for friend in applvr_friends:
            friend_obj = User.load(friend)
            if friend_obj:                 
                if hasattr(friend_obj, 'links'):                         
                    for link in friend_obj.links  :
                        if link["rel"] == "device":                                           
                            device_obj = Device.load(link["href"])                           
                            if device_obj.make == "Apple":                            
                                ios_friend_device_id.append(link["href"])
             
    #if number of apps downloaded apps are more and consider top app for notification
    current_app.logger.debug("@@@Friends list for Notification for MFA: %s"%ios_friend_device_id) 
    if len(ios_friend_device_id)>0:
        new_build_deviceids = []
        old_build_deviceids = []
        for friendudid in ios_friend_device_id:
            device_object = Device.load(friendudid)
            appluvrBuild = device_object.appluvr_build
            if appluvrBuild == None or appluvrBuild == '':
                old_build_deviceids.append(friendudid) 
            else:               
                appbuild = int(appluvrBuild[:1])
                if appbuild >= 3:                    
                    new_build_deviceids.append(friendudid)
                else:                
                    old_build_deviceids.append(friendudid) 

        if len(applist)>0:
            if platform == 'android':
                xmap_data = get_xmap_results_from_server(applist)                         
                cross_mapped_new_apps = [apps.get('itunesID',None) for  apps in xmap_data if  xmap_data] 
            else:
                cross_mapped_new_apps = applist
        else:
            cross_mapped_new_apps = []

           
        if len(cross_mapped_new_apps)>0: 
            new_pkg = cross_mapped_new_apps[0] 

            target1 = "%sviews/users/%s/fb/profile"%(server,uid) 
            target2 = '%sapi/apps/summary?ids=%s&platform=%s'% (server, new_pkg, 'ios')                       
            urls = [target1, target2]
            qs = (grequests.get(url, auth=(auth_user,auth_pwd)) for url in urls)
            rs = grequests.map(qs)                   
           
            if rs[0].status_code == 200:
                user_fb_profile = json.loads(rs[0].content).get('fb_profile',None)           
                if user_fb_profile is not None:                     
                    if user_fb_profile.get('first_name', None) is not None:  
                        username = user_fb_profile.get('first_name', None)  
                    else:
                        username = user_fb_profile.get('name', None)
                else:
                    username = None
            else:
                username = None

            if rs[1].status_code == 200:
                current_app.logger.debug("@@@MFA Push Status Success: %s"%rs[1].content)
                app_data = json.loads(rs[1].content)
                app_name = app_data[new_pkg].get('itunes_market').get('name')
            else:
                app_name = None
           
            if app_name is not None and username is not None:   
                if len(new_build_deviceids)>0:
                    data={"aliases": new_build_deviceids, "aps": {"alert": "%s downloaded a new app, %s. See all of %s's apps in Appluvr." %(username, app_name, username) , "sound":"gentle.aiff", "carouselType" : 0}}
                    current_app.logger.debug("@@@ %s"%data)
                elif len(old_build_deviceids)>0:
                    data={"aliases": old_build_deviceids, "aps": {"alert": "%s downloaded a new app, %s. See all of %s's apps in Appluvr." %(username, app_name, username) , "sound":"gentle.aiff", "carouselType" : 3}}
                    current_app.logger.debug("@@@ %s"%data)
                else:
                    current_app.logger.debug("executaion should not come to this block") 
                    data={"aliases": ios_friend_device_id, "aps": {"alert": "%s downloaded a new app, %s. See all of %s's apps in Appluvr." %(username, app_name, username) , "sound":"gentle.aiff", "carouselType" : 3}}

                #data={"aliases": ios_friend_device_id, "aps": {"alert": "%s downloaded a new app, %s. See all of %s's apps in Appluvr." %(username, app_name, username) , "sound":"gentle.aiff", "carouselType" : carouselTypeValue}}
                #current_app.logger.debug("@@@MFA Notification: %s"%data) 
                req_status, req_content = create_notification('push', json.dumps(data))                    
                if req_status == 200:
                    current_app.logger.debug("@@@MFA Push Status Success: %s"%req_content)
                    return req_content
                else:
                    current_app.logger.debug("@@@MFA Push Failed. Status: %s"%req_status)
                    return req_content
            else:
                req_content = "No Attribute called name"            
           
        else:
            req_content = "No Friends apps for Notification"
    else:
        req_content = "No ios Friends."
    return req_content 



def create_notification(notification_type,data):
    ua_user = os.environ.get('UA_APP_KEY', 'QH2GndBTSUa8tmPlDelszQ')
    ua_password = os.environ.get('UA_MASTER_KEY', 'D9JtxhSLRSaITzw8Rx20TQ')
    headers = {'content-type': 'application/json'}
    url = "https://go.urbanairship.com/api/%s/"%notification_type
    r= requests.post(url, data=data, headers=headers, auth=(ua_user,ua_password))         
    print r.content, r.status_code
    return (r.status_code, r.content)


def send_afy_notification():
    ''' Ensure all the relevant Build numbers are filled in for this for iOS Build > 3.0.0
        else Recomendation Notifications won't go out
    '''
    ''' Legacy 1.0 , 2.0 notifications to go to carousel 1'''
    ret_content =''
    data = '{"tags":["1.0.1","2.0.0"],"aps":{"alert":"You have new Recommendations","sound":"gentle.aiff","carouselType":1,"ll:":"You have new Apps For You! Click OK to check them out."}}'
    req_status, req_content = create_notification('push', data)
    if req_status == 200:
        ret_content = req_content
    else:
        current_app.logger.debug("AMF Push Failed for users < 3.0.0. Status: %s"%req_content)
        ret_content = req_content
    '''Additional Notification to 3.0.0 iOS apps since Carousel Positions have changed'''
    data = '{"tags":["3.0.0"],"aps":{"alert":"You have new Recommendations","sound":"gentle.aiff","carouselType":2,"ll:":"You have new Apps For You! Click OK to check them out."}}'
    req_status, req_content = create_notification('push', data)
    if req_status == 200:
        ret_content = ret_content+req_content
    else:
        current_app.logger.debug("AMF Push Failed for 3.0.0 users . Status: %s"%req_content)
        ret_content = ret_content+req_content
    return ret_content


def test_lev_tag_notification():
    data = '{"tags":["levitum"],"aps":{"alert":"You have new Recommendations","sound":"gentle.aiff","carouselType":2,"ll:":"You have new Apps For You! Click OK to check them out."}}'
    req_status, req_content = create_notification('push', data)
    if req_status == 200:
        return req_content
    else:
        current_app.logger.debug("AMF Push Failed for 3.0.0 users . Status: %s"%req_content)
        return req_content

#-------------------------------------------------------------------------------#
@manager.command
def amf_notification():    
    return fetch_amf_notification()
#-------------------------------------------------------------------------------#

@manager.command
def afy_notification():
    return send_afy_notification()

if __name__ == '__main__':
    manager.run()
