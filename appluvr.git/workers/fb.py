from flask import json, request, current_app
import requests
import grequests

#from utils import merge_lists
from appluvr.models.user import User


auth_user = 'tablet'


def my_friends_list(server, user, device, auth_pwd, debug, block=False):
    """
    Fetch list of friends/experts
    For each of the friends/experts, inject their full name and profile picture link
    """
    target='%sviews/users/%s/fb/friends/recent?block=%s' % (server, user, block) 
    friends_profile = get_friends_profile(target, server, user, device, auth_pwd)
    if friends_profile:
        return friends_profile
    else:
        friends_profile = dict(count = len([]), data = [])
        return friends_profile  

def get_only_friends(server, user, device, auth_pwd, debug, block=False):
    """
    Fetch list of friends
    For each of the friends, inject their full name and profile picture link
    """
    target='%sviews/users/%s/fb/only_friends/recent?block=%s' % (server, user, block) 
    only_friend_profile = get_friends_profile(target, server, user, device, auth_pwd)
    if only_friend_profile:
        return only_friend_profile
    else:
        only_friend_profile = dict(count = len([]), data = [])
        return only_friend_profile  

def get_only_advisor_friends(server, user, device, auth_pwd, debug, block=False):
    """
    Fetch list of experts
    For each of the experts, inject their full name and profile picture link
    """
    target='%sviews/users/%s/only_advisors?block=%s' % (server, user, block)
    advisors_profile = get_friends_profile(target, server, user, device, auth_pwd)
    if advisors_profile:
        return advisors_profile
    else:
        advisors_profile = dict(count = len([]), data = [])
        return advisors_profile 

def get_friends_profile(target, server, user, device, auth_pwd):
    """
    Fetch list of friends/experts
    For each of the friends/experts, inject their full name and profile picture link
    """
    r = requests.get(target, auth = (auth_user, auth_pwd))
    if r.status_code == 200:              
        user_profile_dict = {}
        all_uniq_ids=[]       
        fb_friends = json.loads(r.content).get('data')  
        all_uniq_ids=[friend_info.get('uniq_id',None) for friend_info in fb_friends]
        for friend_info in fb_friends:
            user_profile_dict.update({friend_info.get('uniq_id',None):friend_info})

        user_picture_info=[]
        ids=[]
        user_picture_fb=[]
        if len(all_uniq_ids)>0:
            for _id in all_uniq_ids:
                user_obj=User.load(_id)
                if user_obj:
                    if user_obj.advisor is not None and (user_obj.fb_id is None or user_obj.fb_id == "") and user_obj.apic_url is not None:
                        user_picture_info.append(dict(uniq_id=_id, profile_picture=user_obj.apic_url))
                    else:                    
                        ids.append(_id)
                else:
                    ids.append(_id)
        if len(ids) >0:
            user_picture_fb = profile_picture(server, ids, auth = (auth_user, auth_pwd))
        user_picture = user_picture_info + user_picture_fb      
        friend_profile=user_profile(server, all_uniq_ids, auth = (auth_user, auth_pwd))

        for profile in friend_profile:
            if profile.get('uniq_id') in user_profile_dict.keys():                   
                user_profile_dict.get(profile.get('uniq_id')).update({'user_name':profile.get('user_name'),'advisor':profile.get('advisor',None),'first_name':profile.get('first_name',None),'last_name':profile.get('last_name',None)})

        for pic in user_picture:
            if pic.get('uniq_id') in user_profile_dict.keys():
                user_profile_dict.get(pic.get('uniq_id')).update({'profile_picture':pic.get('profile_picture')})

        reordered = user_profile_dict.values()    
        result = dict(count=len(reordered), data=reordered)
        return result          
    else:
        print 'Worker failed with error code: %s' % r.status_code
        return None


def user_profile(server, user_data, auth):
    """
    Fetch friends/experts info
    """
    users_list=[]
    users_id= [(user if user is not None else '') for user in user_data]
    target='%sapi/users?uniq_ids=%s'% (server,','.join(users_id))
    r = requests.get(target, auth=auth)
    all_app_users=json.loads(r.content).get('data')
    if r.status_code == 200:
        users_list=[dict(uniq_id=app_users.get('uniq_id',None),user_name=app_users.get('name',None),advisor=app_users.get('advisor',None), first_name=app_users.get('first_name',None), last_name=app_users.get('last_name',None))for app_users in all_app_users]
        return users_list  
    else:
        return users_list

def profile_picture(server, users_id, auth):
    """
    Fetch profile_picture link
    """
    picture_list=[]
    urls = ['%sviews/users/%s/fb/profile/pic'% (server, uniq_id) for uniq_id in users_id]
    qs = (grequests.get(url, auth=auth) for url in urls)
    rs = grequests.map(qs)
    responses = zip(rs, users_id)
    for r, uniq_id in responses:
        if r.status_code == 200:
            picture_list.append(dict(uniq_id=uniq_id, profile_picture=r.json.get('profile_picture', None)))
        else:
            user_obj=User.load(uniq_id)
            if user_obj is not None:
                if user_obj.fb_id is None or user_obj.fb_id == "":
                    if user_obj.apic_url is not None:
                        picture_list.append(dict(uniq_id=uniq_id, profile_picture=user_obj.apic_url))
                else:
                    picture_list.append(dict(uniq_id=uniq_id, profile_picture=None))   
            else:
                picture_list.append(dict(uniq_id=uniq_id, profile_picture=None))

    return  picture_list



