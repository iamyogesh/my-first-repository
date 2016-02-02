"""
Worker tasks to invite friends to use Appluvr.
Example Usage:
    python invite_friends.py invite_Friends http://leann.herokuapp.com/v2/ de18aff1d36b4ff0858b6ca4a5a05cc3 f7da8334122d19330be1eb5d21e0fbba383878ad  -d
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
from couchdbkit import *
from appluvr.utils.misc import verify_system_package
import os
from appluvr.models.user import *
from operator import itemgetter

app = Flask(__name__)
manager = Manager(app)

auth_user = 'tablet'
auth_pwd = os.environ.get('APPLUVR_PWD', 'aspirin')

#-------------------------------------------------------------------------------#

@delayable
def send_friends_invitation(server, uid, appluvr_filter ):
    '''
    stub to invite friends .
    '''
     # ----To get all appluvr friends--------------------------

    user = User.load(uid)
    url  = '%sviews/users/%s/fb/friends/all' % (server, uid)
    r= requests.get(url, auth=(auth_user,auth_pwd))
    if r.status_code==200:    
        fb_status, fb_content = user.fb_fetch_friends(pic=True) 
        usrfbcontent = json.loads(fb_content).get('data')
        if usrfbcontent is None:
            return jsonify(count = len([]), data = [])
        only_appluvr_friends = sorted(usrfbcontent, key = itemgetter('name'))
    else:
        only_appluvr_friends = []


    #---- Filter appluvr friends from fb friends ------------

    if appluvr_filter is True:
        url_app = '%sviews/users/%s/fb/friends/recent' % (server, uid)
        r1 = requests.get(url_app, auth=(auth_user,auth_pwd))
        if r1.status_code==200:  
            ret_data = json.loads(r1.content).get('data')
            list_uniqid = [each.get('uniq_id', None)for each in ret_data]
        else:
            list_uniqid = []
        if len(list_uniqid) > 0:
            url2 = '%sapi/users?uniq_ids=%s' % (server, ','.join(list_uniqid))
            r2 =  requests.get(url2, auth=(auth_user,auth_pwd))
            if r2.status_code==200:  
                info = json.loads(r2.content).get('data')
                list_fbid = [each_fbid.get('fb_id', None) for each_fbid in info]
                fbid_list = [fbid for fbid in list_fbid if fbid]
                if len(fbid_list) > 0:
                    for index,each in enumerate(only_appluvr_friends):
                        if each.get('id') in fbid_list:
                            only_appluvr_friends.pop(index)
                    fb_friends_list = only_appluvr_friends
                    return jsonify(count = len(fb_friends_list), data = fb_friends_list)
            else:
                return jsonify(count = len(only_appluvr_friends), data = only_appluvr_friends)
        else:
            return jsonify(count = len(only_appluvr_friends), data = only_appluvr_friends)
    else:
        return jsonify(count = len(only_appluvr_friends), data = only_appluvr_friends)

#-----------------------------------------------------------------------------------

@manager.command
def get_user_info(server, userid):
    return send_friends_invitation(server, userid)


if __name__ == '__main__':
    manager.run()