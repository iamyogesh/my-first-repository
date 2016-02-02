"""
Worker tasks to collate card data for a user

Example Usage:
python build_card_views.py app_card http://baadaami.herokuapp.com/v2/ andrew_zobydvq_koziara@tfbnw.net d2184055785c-3300-b0e6-9b86-00000012 com.google.earth -d

"""
from appluvr_views import d, couch, couchdb, cache
from flask import Flask, g, json, request, jsonify,current_app
from werkzeug import LocalProxy
from flaskext.script import Manager
from workerd import delayable
from operator import itemgetter
import requests
import grequests
import os

from appluvr_views.prefix import *
from utils import merge_lists
from appluvr.models.user import User
from appluvr.models.device import Device
from appluvr.models.app_packs import Packages


app = Flask(__name__)
manager = Manager(app)

auth_user = 'tablet'
auth_pwd = os.environ.get('APPLUVR_PWD', 'aspirin')

w = LocalProxy(lambda: app.logger.warning)

#-------------------------------------------------------------------------------#
@delayable
@cache.memoize(BALI_CACHE_TIME)
def fetch_app_card(server, user, device, pkg, auth_pwd=auth_pwd, debug=False):
    """
    Stub for inserting app card details views
    """
    app.debug = debug
    if pkg.isdigit():
        platform = 'ios'

        url1 = '%sviews/user/%s/device/%s/app/%s/installed' % (server,user, device, pkg)        
        url2 = '%sapi/users/%s/apps/%s/like' % (server, user, pkg)
        url3 ='%sapi/users/%s/apps/%s/dislike' % (server, user, pkg)  
        urls = [url1, url2, url3]
        qs = (grequests.get(url, auth=(auth_user,auth_pwd)) for url in urls)
        rs = grequests.map(qs)
        app_installed_current=get_app_status(rs[0])
        user_app_preference_current=get_app_rating_status(rs[1],rs[2])

        app_installed=False 
        user_apps_preference='none'
        url='%sviews/users/%s/profile'%(server,user)
        r = requests.get(url, auth=(auth_user,auth_pwd))
        if r.status_code == 200:
            list_profile=json.loads(r.content)           
            if pkg in list_profile.get('user_profile', None).get('apps_liked',None):
               user_apps_preference='liked'
            elif pkg in list_profile.get('user_profile', None).get('apps_disliked',None):
                user_apps_preference='disliked'
     
            for apps in list_profile.get('device_profiles', None):
                if pkg in apps.get('apps_installed',None):
                    app_installed=True
                else:
                    app_installed=False 
                  
        else:
            print "Worker failed with error code: %s" % r.status_code
    else:
        platform = 'android'

    target1 = '%sviews/apps/%s/details?platform=%s' % (server,pkg,platform)
    target2 = '%sviews/users/%s/fb/friends/apps/%s/likes' % (server, user, pkg)
    target3 = '%sapi/users/%s/apps/%s/comment'% (server, user, pkg)
    target4 ='%sviews/users/%s/fb/friends/apps/%s/comments' % (server, user, pkg)
    urls = [target1, target2, target3, target4]

    qs = (grequests.get(url, auth=(auth_user,auth_pwd)) for url in urls)

    rs = grequests.map(qs)

    if platform is 'ios':
        card_data =  dict(user_id=user,user_app_preference=user_apps_preference,user_app_preference_current=user_app_preference_current,app_installed_current=app_installed_current, app_installed=app_installed, data=dict(app=apps_details(rs[0]),friends=app_friends(rs[1], server, user, pkg),comments=friends_comments(rs[2], rs[3], server, user, pkg)))
    else:
        card_data = dict(data=dict(app=apps_details(rs[0]),friends=app_friends(rs[1], server, user, pkg),comments=friends_comments(rs[2], rs[3], server, user, pkg))) 

    return json.dumps(card_data)

def get_app_status(r):
    installed_status=None
    if r.status_code==200:
        installed_status= json.loads(r.content).get('installed',None)
        return installed_status
    else:
        return installed_status

def get_app_rating_status(r1,r2):
    rating='none'
    if r1.status_code == 200 and r2.status_code == 404:
        rating='like'
    elif r1.status_code == 404 and r2.status_code == 200:
        rating='dislike'
    elif r1.status_code == 404 and r2.status_code == 404:
        rating = 'none'
    return rating

def app_friends(r, server, user, pkg):
    """
    Stub for fetching friends properties of app card details views
    """
    app_friends_list=[]
    user_picture_fb =[]
    if r.status_code == 200:
        friends_data = json.loads(r.content).get('data')
        pkg_friends=friends_data.get('likers') + friends_data.get('dislikers') + friends_data.get('neutral')
        if len(pkg_friends)>0:
            fb_friends_data=user_profile(server, pkg_friends)
            user_picture_info=[]
            user_picture_fb =[]
            ids=[]
            for _id in pkg_friends:
                user_obj=User.load(_id)
                if user_obj and (user_obj.advisor is not None and (user_obj.fb_id is None or user_obj.fb_id =="") and user_obj.apic_url is not None):
                    user_picture_info.append(dict(uniq_id=_id, profile_picture=user_obj.apic_url))
                else:                    
                    ids.append(_id)
            if len(ids) >0:
                user_picture_fb= profile_picture(server, ids)
            user_picture = user_picture_info + user_picture_fb 
            
            for uniq_id in pkg_friends:
                if uniq_id in friends_data.get('likers'):
                    rating='likes'
                elif uniq_id in friends_data.get('dislikers'):
                    rating='dislikes'
                elif uniq_id in friends_data.get('neutral'):
                    rating=None
                fb_friends=dict(uniq_id=uniq_id, app_rating=rating)
                app_friends_list.append(fb_friends)
            all_friends_data=merge_lists(fb_friends_data, app_friends_list, user_picture)
            return all_friends_data
        else:
            app.logger.debug("No friends present")
            return app_friends_list
    else:
        app.logger.error('Worker failed with error code: %s' % r.status_code)
        return app_friends_list

def friends_comments(r1, r2, server, user, pkg):
    """
    Stub for fetching comments properties of app card details views
    """
    all_user_comments=[]
    comments_list=[]
    user_picture_fb=[]
    my_comment_data={}
    if r1.status_code == 200:
        my_comments = json.loads(r1.content)
        if len(my_comments)>0 :
            my_comment_data['uniq_id']=my_comments.get('uniq_id')
            my_comment_data['common_apps']=0
            my_comment_data['last_modified']=my_comments.get('last_modified')
            my_comment_data['comment']= my_comments.get('comment')
        else:
            app.logger.debug('No current user comments present')
    else:
        app.logger.debug('No current user or user comments present')

    r = r2
    if r.status_code == 200:
        app_comments = json.loads(r.content).get('data')
        if len(my_comment_data)>0:
            app_comments.append(my_comment_data)
        if len(app_comments)>0 :
            user_details=[]
            all_user_id=[user_id.get('uniq_id') for user_id in app_comments]
            all_user_info= user_profile(server, all_user_id)
            user_picture_info=[]
            ids=[]                     
            for _id in all_user_id:
                user_obj=User.load(_id)
                if user_obj and (user_obj.advisor is not None and (user_obj.fb_id is  None or  user_obj.fb_id =="") and user_obj.apic_url is not None):
                    user_picture_info.append(dict(uniq_id=_id, profile_picture=user_obj.apic_url))
                else:                    
                    ids.append(_id)
            if len(ids)>0:
                user_picture_fb= profile_picture(server, ids)  
            user_picture = user_picture_info + user_picture_fb

            for user in all_user_info:
                del user['advisor']
                user_details.append(user)
            for comment_data in app_comments:
                if len(comment_data)!=0:
                    uniq_id=comment_data.get('uniq_id',None)
                    comments_list.append(comment_data)
                else:
                    pass
            all_user_comments=merge_lists(comments_list, user_details, user_picture)
            sorted_comments=sorted(all_user_comments,key=itemgetter('last_modified'),reverse=True)
            return sorted_comments
        else:
            app.logger.debug("No comments present")
            return  all_user_comments
    else:
        app.logger.error('Worker failed with error code: %s' % r.status_code)
        return  all_user_comments

def apps_details(r):
    """
    Stub for fetching package details of app card details views
    """
    apps={}
    if r.status_code == 200:
        app_details = json.loads(r.content)
        return app_details
    else:
        app.logger.debug("No package data present")
        return  apps


def user_profile(server, user_data):
    """
    Fetch friends/experts info
    """
    users_list=[]
    users_id= [(user if user is not None else '') for user in user_data]
    target='%sapi/users?uniq_ids=%s'% (server,','.join(users_id))
    r = requests.get(target, auth=(auth_user,auth_pwd))
    all_app_users=json.loads(r.content).get('data')
    if r.status_code == 200:
        for app_users in all_app_users:
            uniq_id=  app_users.get('uniq_id',None)
            name= app_users.get('name',None)
            first_name= app_users.get('first_name',None)
            last_name= app_users.get('last_name',None)
            advisor =  app_users.get('advisor',None)
            user_info={'uniq_id':uniq_id, 'user_name':name, 'advisor':advisor, 'first_name':first_name, 'last_name':last_name}
            users_list.append(user_info)
        return users_list
    else:
        return users_list

def profile_picture(server, users_id):
    """
    Fetch profile_picture link
    """
    picture_list=[]
    urls = ['%sviews/users/%s/fb/profile/pic'% (server, uniq_id) for uniq_id in users_id]
    qs = (grequests.get(url, auth=(auth_user,auth_pwd)) for url in urls)
    rs = grequests.map(qs)
    responses = zip(rs, users_id)
    
    for r, uniq_id in responses:
        if r.status_code == 200:
            picture_list.append(dict(uniq_id=uniq_id, profile_picture=r.json.get('profile_picture', None)))
        else:
            user_obj=User.load(uniq_id)
            if user_obj and (user_obj.fb_id is None or user_obj.fb_id == ""):
                if user_obj.apic_url is not None:
                    picture_list.append(dict(uniq_id=uniq_id, profile_picture=user_obj.apic_url))
            else:
                picture_list.append(dict(uniq_id=uniq_id, profile_picture=None))         
    
    return  picture_list


@delayable
@cache.memoize(BALI_CACHE_TIME)
def fetch_friend_card(server, user, device, friend=None, auth_pwd=auth_pwd, debug=False,platform='android'):
    """
    Stub for inserting friend card details views
    """
    app.debug = debug
    app.logger.debug("Platform in Fetch Friend card %s"%platform)
    if friend == None:
        target1='%sapi/users/%s' % (server,user)
        target2='%sapi/interests' % (server)
        target3='%sviews/users/%s/comments' % (server,user)
        target4 = '%sapi/users/%s/apps' % (server, user)
        target5='%sviews/users/%s/fb/profile/pic' % (server,user)
        target6='%sviews/users/%s/profile' % (server, user)


        urls = [target1,target2,target3,target4,target5,target6]

        qs = (grequests.get(url, auth=(auth_user,auth_pwd)) for url in urls)
        rs = grequests.map(qs)

        user_data=  get_user_data(rs[0])
        details_of_intersts= get_user_interests(rs[1],user_data.get('interest'))
        user_comments=  get_user_comments(rs[2],server,user_data.get('name'),platform)
        all_my_apps= get_all_my_apps(rs[3],server, user, platform)
        rating_apps= get_rating_of_apps(rs[5],server,platform,user)
        user_obj=User.load(user)      
        if user_obj and (user_obj.advisor is not None and (user_obj.fb_id is  None or  user_obj.fb_id =="") and user_obj.apic_url is not None):
            profile_picture=user_obj.apic_url
            user_fb_id='advisor'
        else:            
            profile_picture= get_profile_pic(rs[4])
            user_fb_id=user_data.get('fb_id')        
        
        output = dict(name=user_data.get('name'),uniq_id=user_data.get('uniq_id'),appluvr_since=user_data.get('appluvr_since'),advisor=user_data.get('advisor'),about=user_data.get('about'),interests=details_of_intersts,comments= user_comments,all_apps=all_my_apps,pic_url= profile_picture,rating=rating_apps.get('summary_for_apps'),device_profiles=rating_apps.get('device_profiles'),fb_id=user_fb_id,email=user_data.get('email'),first_name=user_data.get('first_name'),last_name=user_data.get('last_name'))
        friend_card_output=json.dumps(output)
        print friend_card_output
        return friend_card_output
    else:
        user_object=User.load(friend)
        if user_object and (user_object.advisor is None or user_object.advisor == '') :
            friend_device=','.join([link['href'] for link in user_object.links if link['rel'] == 'device'])     
            device_obj=Device.load(friend_device)
            if device_obj:
                friend_read_apps=device_obj.read_apps
            else:
                friend_read_apps=False
        else:
            friend_read_apps=True            

        target1='%sapi/users/%s' % (server,friend)
        target2='%sapi/interests' % (server)
        target3='%sviews/users/%s/comments' % (server,friend)
        target4 = '%sapi/users/%s/apps' % (server, friend)
        target5='%sviews/users/%s/fb/profile/pic' % (server,friend)
        target6='%sviews/users/%s/profile' % (server, friend)
        target7 = '%sviews/users/%s/%s/fb/friends/%s' % (server, platform, user, friend)


        urls = [target1,target2,target3,target4,target5,target6,target7]

        qs = (grequests.get(url, auth=(auth_user,auth_pwd)) for url in urls)
        rs = grequests.map(qs)

        user_data=  get_user_data(rs[0])          
        details_of_intersts= get_user_interests(rs[1],user_data.get('interest'))
        user_comments=  get_user_comments(rs[2],server,user_data.get('name'),platform)
        all_my_apps= get_all_my_apps(rs[3],server, user,platform)
        rating_apps= get_rating_of_apps(rs[5],server,platform, user)
        common_apps= get_common_apps(rs[6],server,platform)

        user_obj=User.load(friend)
        if user_obj and (user_obj.advisor is not None and (user_obj.fb_id is  None or  user_obj.fb_id =="") and user_obj.apic_url is not None):
            profile_picture=user_obj.apic_url
            friend_fb_id='advisor'
        else:
            profile_picture= get_profile_pic(rs[4])
            friend_fb_id=user_data.get('fb_id')
       
        output = dict(name=user_data.get('name'),uniq_id=user_data.get('uniq_id'),appluvr_since=user_data.get('appluvr_since'),advisor=user_data.get('advisor'),about=user_data.get('about'),interests=details_of_intersts,comments= user_comments,all_apps=all_my_apps,pic_url= profile_picture,rating=rating_apps.get('summary_for_apps'),device_profiles=rating_apps.get('device_profiles'),common_apps=common_apps,fb_id=friend_fb_id,email=user_data.get('email'),first_name=user_data.get('first_name'),last_name=user_data.get('last_name'),friend_read_apps=friend_read_apps)
        friend_card_output=json.dumps(output)
        print friend_card_output
        return friend_card_output

def get_user_data(r1):
    """
    Stub for fetching friend data
    """
    user_data={}
    if r1.status_code is 200:
        data=json.loads(r1.content)
        return {"name":data.get('name'),"uniq_id":data.get('uniq_id'),"appluvr_since":data.get('first_created'),"advisor":data.get('advisor'),"about":data.get('about'),"interest":data.get('interests'),"fb_id":data.get('fb_id'),"email":data.get('email'),"first_name":data.get('first_name'),"last_name":data.get('last_name',None)}
    else:
        app.logger.error('Worker failed with error code: %s' % r1.status_code)
        app.logger.debug("object not found")
        return user_data

def get_user_interests(r2, user_interests):
    interest_list=[]   
    if user_interests is None:
        app.logger.debug("No interests present")
        return interest_list
    else:
        if r2 .status_code is 200:
            data=json.loads(r2.content).get('data',None)
            details_of_interest= [interest_details for interest_details in data if interest_details.get('name') in user_interests]
            return details_of_interest
        else:
            app.logger.error('Worker failed with error code: %s' % r2.status_code)
            return interest_list

def get_user_comments(r3,server,user_name,platform='android'):
    """
    Stub for fetching all the comments & required summary for apps
    """
    user_comments=[]
    if r3.status_code == 200:
        comments_data=json.loads(r3.content).get('data', None)
        if len(comments_data) == 0:
            app.logger.debug("No comments are present")
            return user_comments
        else:            
            app_comments= get_app_detail(server, comments_data, user_name, platform)
            sorted_comments =  sorted(app_comments, key=itemgetter('last_modified'), reverse=True)
            return sorted_comments
    else:
        app.logger.error('Worker failed with error code: %s' % r3.status_code)
        return user_comments


def get_all_my_apps(r4,server, user,platform='android'):
    """
    Stub for fetching details of installed apps
    """
    all_apps=[]
    if r4.status_code == 200:
        packages = json.loads(r4.content).get('data',None)
        pkg_names=','.join(json.loads(r4.content).get('data',None))
        user_obj = User.load(user)
        for link in user_obj.links:
            if link['rel'] == 'device':
                if link['href']:
                    device_obj = Device.load(link['href'])
                    if "verizon" in device_obj.carrier.lower():
                        carrier_prefix = 'vz'
                    elif "att" in device_obj.carrier.lower() or "at&t" in device_obj.carrier.lower():
                        carrier_prefix = 'att'
                    else:
                        carrier_prefix = 'bm'
                if len(pkg_names) == 0:
                    app.logger.debug("get_all_my_apps: No package ids are present")
                    return all_apps
                else:
                    blacklisted_apps=get_blacklisted_apps(server, carrier_prefix)
                    pkg_names_final=[each_pkg_name for each_pkg_name in packages if each_pkg_name not in blacklisted_apps]
                    pkg_names_final=','.join(pkg_names_final)
                    my_apps= get_summary_of_apps(server, pkg_names_final,platform)
                    return my_apps
    else:
        app.logger.error('Worker failed with error code: %s' % r4.status_code)
        return all_apps


def get_filtered_my_apps_from_hot_apps(recommendations, device):
    device_obj = Device.load(device)
    if not device_obj:
        return None
    installed_apps = device_obj.apps_installed
    filter_app=[each_myapp for each_myapp in recommendations if each_myapp.get('package_name') not in installed_apps]
    return filter_app


def get_blacklisted_apps(server, carrier_prefix):
    all_apps=[]
    target1='%sapi/apps/blacklist/?platform=%s&carrier=%s'%(server, 'ios', carrier_prefix)
    r1=requests.get(target1, auth=(auth_user,auth_pwd))
    if r1.status_code==200:
        array1=json.loads(r1.content).get('blacklisted_apps',None)
        blacklisted_apps1=[each.get('itunes_id', None) for each in array1]
    else:
        return all_apps
    target2='%sapi/apps/blacklist/?platform=%s&carrier=%s'%(server, 'android', carrier_prefix)
    r2=requests.get(target2, auth=(auth_user,auth_pwd))
    if r2.status_code==200:
        array2=json.loads(r2.content).get('blacklisted_apps',None)
        blacklisted_apps2=[each.get('package_name', None) for each in array2]
    else:
        return all_apps
    blacklisted_apps=blacklisted_apps1+blacklisted_apps2
    return blacklisted_apps


def get_rating_of_apps(r6,server,platform='android', user='None'):
    """
    Stub for inserting fetching device data & rating of apps
    """
    #rating_apps=[] 
    if r6.status_code == 200:
        data=json.loads(r6.content)
        liked_apps=data.get('user_profile').get('apps_liked',None)
        disliked_apps=data.get('user_profile').get('apps_disliked',None)
        device_profiles=data.get('device_profiles',None)
        if len(device_profiles)>0:
            ddb_details= get_ddb_details(server,device_profiles)
            device_profiles[0].update(dict(device_image_url=ddb_details.get('device_image_url'),device_isTablet=ddb_details.get('device_isTablet'),device_marketing_name=ddb_details.get('device_marketing_name')))
        else:
            app.logger.debug('No device present')

        pkgs=liked_apps + disliked_apps       
        applist=[]
        (android_apps,ios_apps)= app_separation(pkgs) 
        if platform == 'android':
            if len(ios_apps)>0:
                data= get_xmap_results_from_server(ios_apps)              
                if data:
                    mapped_apps=[apps.get('androidPackageName',None) for  apps in data]
                    liked_apps=[apps.get('androidPackageName',None) for  apps in data if apps.get('itunesID',None) in liked_apps]
                    disliked_apps=[apps.get('androidPackageName',None) for  apps in data if apps.get('itunesID',None) in disliked_apps]                   
                    applist= android_apps + mapped_apps
            else:
                applist= android_apps
        else:
            if len(android_apps)>0:             
                data= get_xmap_results_from_server(android_apps)
                if data:
                    mapped_apps=[apps.get('itunesID',None) for  apps in data]
                    liked_apps=[apps.get('itunesID',None) for  apps in data if apps.get('androidPackageName',None) in liked_apps]
                    disliked_apps=[apps.get('itunesID',None) for  apps in data if apps.get('androidPackageName',None) in disliked_apps]
                    applist= ios_apps + mapped_apps
            else:
                applist= ios_apps

        if len(applist) == 0:
            app.logger.debug("No liked/disliked apps are present")
            #return (rating_apps, device_profiles)
            return dict(summary_for_apps=[],device_profiles=device_profiles)

        else:
            pkgs=",".join(applist)     
            summary_for_apps= get_summary_of_apps(server, pkgs, platform)
            for app_summary in summary_for_apps:          
                del app_summary['appo_category']
                del app_summary['punchline']
                if app_summary['package_name'] in liked_apps:
                    app_summary['app_rating']='likes'
                elif app_summary['package_name'] in disliked_apps:
                    app_summary['app_rating']='dislikes'    
            #return (summary_for_apps, device_profiles)
            return dict(summary_for_apps=summary_for_apps,device_profiles=device_profiles)
    else:
        app.logger.error('Worker failed with error code: %s' % r6.status_code)
        #return rating_apps
        return dict(summary_for_apps=[],device_profiles=[])


def get_ddb_details(server,device_profiles):
    """
    Stub for fetching device details
    """
    target = '%sviews/device/%s/%s/%s/details/' % (server, device_profiles[0]['model'],device_profiles[0]['number'],device_profiles[0]['manufacturer'])
    r = requests.get(target, auth=(auth_user, auth_pwd))
    if r.status_code == 200:
        data = json.loads(r.content)
        return data
    else:
        return {}


def get_summary_of_apps(server, package_list,platform='android'):
    """
    fetching the summary of apps
    """
    summary=[]
    payload = {"ids":package_list,"platform":platform} 
    target5 = '%sviews/apps/summary/' % (server)
    r5 = requests.post(target5, data = payload, auth=(auth_user, auth_pwd))
    if r5.status_code == 200:
        data=json.loads(r5.content)
        summary_of_apps= [data[key] for key in data]
        return summary_of_apps
    else:
        app.logger.error('Worker failed with error code: %s' % r5.status_code)
        return summary


def get_profile_pic(r5):
    """
    Stub for fetching profile picture
    """
    if r5.status_code is 200:
        picture_link=(json.loads(r5.content).get('profile_picture',None))
        return picture_link
    else:
         picture_link=None


def get_app_detail(server, comments_data, name,platform='android'):
    """
    Stub for inserting fetching required data from app summary
    """    
    app_detail=[]
    itune_apps={}
    commented_packages = []
    xmap_data = []

    list_of_packages=[comments.get('pkg', None) for comments in comments_data]
    (android_apps, ios_apps) = app_separation(list_of_packages)
    if platform == 'android':
        if len(ios_apps)>0:
            xmap_data = get_xmap_results_from_server(ios_apps)
            if xmap_data:
                mapped_apps=[apps.get('androidPackageName',None) for  apps in xmap_data]
                commented_packages = android_apps + mapped_apps
            else:
                commented_packages = android_apps 
        else:
            commented_packages = android_apps     
    else:     
        if len(android_apps)>0:
            xmap_data = get_xmap_results_from_server(android_apps)         
            if xmap_data:
                mapped_apps=[apps.get('itunesID',None) for  apps in xmap_data]              
                commented_packages = ios_apps + mapped_apps
            else:

                commented_packages = ios_apps 
        else:
            commented_packages = ios_apps
    
    package_list = ','.join(commented_packages)
    payload = {"ids":package_list,"platform":platform} 
    target7 = '%sviews/apps/summary/' % (server)
    r7 = requests.post(target7, data = payload, auth=(auth_user, auth_pwd))
    if r7.status_code == 200:
        data=json.loads(r7.content)     
        if platform == 'android':       
            for user_comment in  comments_data:                
                pkg = user_comment.get('pkg', None)
                if pkg in data.keys():
                    app_icon= data[pkg].get('icon_url' ,None)
                    vcast_market= data[pkg].get('vcast_market', None)
                    android_market= data[pkg].get('android_market',None)
                    app_detail.append(dict(package_name=pkg,app_icon_url=app_icon,vcast_market=vcast_market,android_market=android_market,comment=user_comment.get('comment', None),uniq_id=user_comment.get('uniq_id', None),last_modified=user_comment.get('last_modified', None),user_name=name))
                else:
                    app_data=dict(package_name=pkg,comment=user_comment.get('comment', None),uniq_id=user_comment.get('uniq_id', None),last_modified=user_comment.get('last_modified', None),user_name=name)
                    itune_apps.update({pkg:app_data})

            for itunes2android in xmap_data:
                itunes_pkg = itunes2android.get('androidPackageName',None) 
                pkg_name = itunes2android.get('itunesID',None)
                if itunes_pkg in data.keys():
                    app_icon = data[itunes_pkg].get('icon_url' ,None)                    
                    vcast_market = data[itunes_pkg].get('vcast_market', None)
                    android_market = data[itunes_pkg].get('android_market',None)               
                    if pkg_name in itune_apps.keys():
                        app_detail.append(dict(package_name=itune_apps[pkg_name].get('package_name'),app_icon_url=app_icon,vcast_market=vcast_market,android_market=android_market,comment=itune_apps[pkg_name].get('comment', None),uniq_id=itune_apps[pkg_name].get('uniq_id', None),last_modified=itune_apps[pkg_name].get('last_modified', None),user_name=name))
        else:           
            for user_comment in  comments_data:               
                pkg = user_comment.get('pkg', None)                  
                if pkg in data.keys():
                    app_icon = data[pkg].get('icon_url' ,None)
                    itunes_market = data[pkg].get('itunes_market',None)
                    app_detail.append(dict(package_name=pkg,app_icon_url=app_icon,itunes_market=itunes_market,comment=user_comment.get('comment', None),uniq_id=user_comment.get('uniq_id', None),last_modified=user_comment.get('last_modified', None),user_name=name))
                else:
                    app_data=dict(package_name=pkg,comment=user_comment.get('comment', None),uniq_id=user_comment.get('uniq_id', None),last_modified=user_comment.get('last_modified', None),user_name=name)
                    itune_apps.update({pkg:app_data})
            
            for itunes2android in xmap_data:
                itunes_pkg=itunes2android.get('itunesID',None) 
                pkg_name=itunes2android.get('androidPackageName',None)
                if itunes_pkg in data.keys():
                    app_icon= data[itunes_pkg].get('icon_url' ,None)
                    itunes_market= data[itunes_pkg].get('itunes_market',None)
                    if pkg_name in itune_apps.keys():
                        app_detail.append(dict(package_name=itune_apps[pkg_name].get('package_name'),app_icon_url=app_icon,itunes_market=itunes_market,comment=itune_apps[pkg_name].get('comment'),uniq_id=itune_apps[pkg_name].get('uniq_id'),last_modified=itune_apps[pkg_name].get('last_modified'),user_name=name))
        return app_detail
    else:
         app.logger.error('Worker failed with error code: %s' % r7.status_code)
         return app_detail

def get_common_apps(r7,server,platform='android'):
    """
    Stub for fetching details of common_apps
    """
    all_common_apps=[]
    if r7.status_code == 200:
        pkg_names=json.loads(r7.content).get('data',None)
        if len(pkg_names) == 0:
            app.logger.debug("get_common_apps: No package ids are present")
            return all_common_apps
        else:
            common_apps_details= get_summary_of_apps(server, ','.join(pkg_names),platform)
            return common_apps_details
    else:
        app.logger.error('Worker failed with error code: %s' % r7.status_code)
        return all_common_apps

#@cache.memoize(86400)
def get_xmap_results_from_server(pkgs):
    xmap_server = "http://vzw.appluvr.com/xmap/"
    if pkgs :
        payload = {"pkgs": ",".join(pkgs)}
        url = '%sapi/1.0/getxmapby/combined/'% (xmap_server)
        r = requests.post(url,data=payload)
        if r.status_code == 200:
            data=json.loads(r.content).get('results',None)           
            return data
        else:
            return []
    else:
        return []

def app_separation(apps):
    android_apps=[]
    ios_apps=[]
    [ios_apps.append(app) if app.isdigit() else android_apps.append(app) for app in apps]       
    return (android_apps,ios_apps)

@delayable
def fetch_app_pack_card(server, uniq_id, udid, apppck_id, platform = 'android', auth_pwd =auth_pwd, debug=True):
    """
    stub for fetching app pack details.
    """
    packages = Packages.load(apppck_id)
    if not packages:
        return None 
    user =  User.load(uniq_id)   
    app_summary_list=[]
    
    if user.fb_id == packages.fb_id:
        app_pack_details=dict(app_pack_id = packages._id,user_name = packages.user_name, apppack_img = packages.apppack_img, apppack_name = packages.apppack_name, user_picurl = packages.user_picurl, app_pack_description = packages.apppack_description, user_bio = packages.user_bio, current_user_created = True, data = dict(apps = app_summary_list), apppack_square_img = packages.apppack_square_img )
    else:
        app_pack_details=dict(app_pack_id = packages._id,user_name = packages.user_name, apppack_img = packages.apppack_img, apppack_name = packages.apppack_name, user_picurl = packages.user_picurl, app_pack_description = packages.apppack_description, user_bio = packages.user_bio, current_user_created = packages.current_user_created, data = dict(apps = app_summary_list), apppack_square_img = packages.apppack_square_img)
    apps_list=[str(pkg.get('package_name')) for pkg in  packages.apps]
    if len(apps_list)>0:
        url = '%sapi/apps/details?ids=%s&platform=%s' %(server , ','.join(apps_list), platform) 
        r = requests.get(url , auth = (auth_user, auth_pwd))
        if r.status_code == 200:
            app_summary = json.loads(r.content)        
            for pkg in  packages.apps:           
                package =str(pkg.get('package_name'))            
                if package in  app_summary.keys():                     
                    app_details= app_summary.get(package)
                    app_details['comment'] = pkg.get('comment')
                    app_summary_list.append(app_details)
            app_pack_details['data'] = dict(apps = app_summary_list)
    return json.dumps(app_pack_details)

def get_all_friends_card_details(server, user_id, device_id, platform, should_block, auth_pwd=auth_pwd, debug=False):
    """
    stub to load all friends cards.
    """
    all_friends_devices = []
    user = User.load(user_id)
    all_friends = user.fb_friends(should_block)

    friends_apps_url = '%sviews/carousels/%s/%s/%s/only_mfa'% (server, user_id, device_id, platform)
    my_apps_url = '%sviews/carousels/%s/%s/%s/my_apps'% (server, user_id, device_id, platform)
    recs_url = '%sviews/carousels/%s/%s/%s/recommended_apps'% (server, user_id, device_id, platform)

    urls = [friends_apps_url,my_apps_url,recs_url]
    qs = (grequests.get(url, auth=(auth_user,auth_pwd)) for url in urls)
    rs = grequests.map(qs)

    if rs[0].status_code==200:        
        friends_apps=json.loads(rs[0].content).get('data')
    else:       
        friends_apps = []
    if rs[1].status_code==200:
        my_apps = json.loads(rs[1].content).get('data')
    else:
        my_apps = []
    if rs[2].status_code==200:
        rec_apps = json.loads(rs[2].content).get('data')
    else:
        rec_apps = []

    caching_apps = friends_apps+my_apps+rec_apps

    app_card_caching_apps = list(set([each.get('package_name')for each in caching_apps]))
  
    app_card_urls = []   
    for pkg in app_card_caching_apps:
        app_card_urls.append('%sviews/cards/%s/%s/app/%s/'% (server, user_id, device_id, pkg)) 

    only_friends_urls = ['%sviews/carousels/%s/%s/%s/only_mf'% (server, user_id, device_id, platform)]
    friend_cards_urls = ['%sviews/cards/%s/%s/friends/%s'% (server, platform, user_id, friendid ) for friendid in all_friends]
    urls= only_friends_urls+app_card_urls+friend_cards_urls    

    qs = (grequests.get(url, auth=(auth_user,auth_pwd)) for url in urls)
    rs = grequests.map(qs)  
    return rs
    
    
#-----------------------------------------------------------------------#
@manager.command
def friend_card(server, user, device, friend=None, auth_pwd=auth_pwd, debug=False):
    return fetch_friend_card(server, user, device, friend, auth_pwd, debug)

@manager.command
def app_pack_card(server, user, device, apppck_id, platform = 'android', auth_pwd=auth_pwd, debug=False):
    return fetch_app_pack_card(server, user, device, apppck_id, platform, auth_pwd, debug)

@manager.command
def app_card(server, user, device, pkg, auth_pwd=auth_pwd, debug=False):
    return fetch_app_card(server, user, device, pkg, auth_pwd, debug)
#---------------------------------------------------------------------------#
if __name__ == '__main__':
    manager.run()




