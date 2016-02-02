"""
Worker tasks to fetch fb_share mode a
"""
import sys
sys.path.append("../")
import couchdb
from appluvr_views import couch, couchdb
from flask import Flask, g, json, request, jsonify, current_app
from werkzeug import LocalProxy
from flaskext.script import Manager
import requests
from workerd import delayable
from appluvr.models.device import Device
from couchdbkit import *
from appluvr.utils.misc import verify_system_package
from vendor.lib.jsonvalidator import JSONValidator
import os

from appluvr.models.user import User
from appluvr.models.device import Device
from workers.build_carousel_views import get_app_summary

app = Flask(__name__)
manager = Manager(app)

auth_user = 'tablet'
auth_pwd = os.environ.get('APPLUVR_PWD', 'aspirin')

w = LocalProxy(lambda: app.logger.warning)

#-------------------------------------------------------------------------------#
def fetch_fb_share_mode(server):
    """
    Fetch all all_devices
    """ 
    platform='ios'
    headers = {'content-type': 'application/json'}
    message = "I just found some cool apps using AppLuvr!"
    for device in Device.view('device/all_devices'):
        uniq_id=device.links[0].get('href')
        user_obj=User.load(uniq_id)    
        if device.apps_fb_share_status==2:
            app.logger.debug('apps found to share')            
            share_status=device.apps_fb_share_status                      
            pkg_list=list(set(device.apps_installed - device.apps_fb_shared))
            if len(pkg_list)>0:
                #get pkg name from itunesid
                result=get_app_summary(server,pkg_list,platform)
                #Share the status to facebook
                app_names= result.get('apps')
                pkg_names=[singleapp.get('itunes_market').get('name', None)for singleapp in app_names]
                output="%s\r\n%s%s"%(message,', '.join(pkg_names), user_obj.fb_token)
                data={"message":output}          
                post_url= '%sapi/users/%s/fb/feed'%(server,user)
                r=requests.post(post_url, data=json.dumps(data), headers=headers, auth=(auth_user,auth_pwd))
                #Save shared apps to user's device
                if r.status_code==200:
                    device_obj = Device.load(device._id)
                    if not device_obj:
                        return None
                    device_obj.apps_fb_shared=list(set(device_obj.apps_fb_shared + pkg_list))
                    device_obj.apps_fb_share_status=2
                    device_obj.update() 
                else:
                    app.logger.debug('No apps found to share')        
    return json.dumps('Fb share and device_obj update is completed successfully')  
   
        
#-------------------------------------------------------------------------------#
@manager.command
def share_status():    
    return fetch_fb_share_mode(server)

if __name__ == '__main__':
    manager.run()
