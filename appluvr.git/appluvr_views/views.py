# -*- coding: utf-8 -*-
import couchdb
from appluvr_views import d, couch, couchdb, cache
from functools import wraps
from flask import Flask, abort, jsonify, request, json, render_template, flash, g, url_for, redirect, current_app, Response, Blueprint
from flaskext.couchdbkit import *
from werkzeug.datastructures import MultiDict
import os, sys, time, string, re, gzip
import urllib
import requests
from promo import inject_promos, itunesid_to_packagename
from ordereddict import OrderedDict
from httplib import HTTPSConnection
from dict2xml import dict2xml
import os
import time
import datetime
import arrow

from prefix import *
from appluvr.models.app import *
from appluvr.models.app_packs import *
from appluvr.models.user import *
from appluvr.models.device import *
from appluvr.models.app import *
from appluvr.models.settings import *
from appluvr.models.interest import *
from appluvr.models.comment import *
from appluvr.models.notifications import *
from appluvr.utils.Counter import Counter
from appluvr.utils.misc import *
#from appluvr.routes import zcache

from uuid import uuid4
from hashlib import md5
import hashlib
import random
from operator import itemgetter
import base64

# Workerd Imports
from redis import Redis, ConnectionError

from workers.invite_friends import send_friends_invitation
from workers.ios_notification import fetch_amf_notification
from workers.build_carousel_views import  fetch_recos, fetch_my_apps, fetch_mfa, fetch_my_friends, fetch_only_mfa, fetch_only_friends, fetch_only_advisors, fetch_all_my_friends,fetch_appdetails_for_fb_share,share_iosapps2fb, fetch_all_app_packs, fetch_all_app_packs_by_user, fetch_recommended_apps, fetch_featured_carousel, fetch_my_comments, fetch_carousel_counts, fetch_att_widget_carousels, fetch_mixes_search_carousel, fetch_device, get_all_widget_app_summary
from workers.build_card_views import get_all_friends_card_details,get_filtered_my_apps_from_hot_apps, fetch_app_card, fetch_friend_card, app_separation, fetch_app_pack_card
from workers.process_device_apps import  update_device_apps, update_ios_device_apps
from workers.ios_notification import  send_afy_notification, notify_ios_friends, fetch_amf_notification,test_lev_tag_notification
from workers.fb_share_mode import  fetch_fb_share_mode
from workers.deal_of_the_day import  fetch_deal_app

''' My Verizon Hardwired User Details'''
my_vz_user = os.environ.get('MY_VZ_USER',None)
my_vz_device=os.environ.get('MY_VZ_DEVICE',None)


views = Blueprint('views', __name__, template_folder='templates', static_folder='static')

#@cache.memoize(FULL_DAY)
def carousel_setting():
    ret = Settings.load('carousel_settings')
    if ret:
        #cms_setting = simplejson.loads(ret.toDict().get('value','{}'))
        cms_setting = eval(ret.value)
    else:
        cms_setting = {}
    #current_app.logger.debug(cms_setting)
    retval = default_carousel_settings
    retval.update(cms_setting)
    #current_app.logger.debug(retval)
    return retval.get('CarouselSettings')

#@cache.memoize(FULL_DAY)
def promo_list(carousel):
    auth_user = 'tablet'
    auth_pwd = os.environ.get('APPLUVR_PWD', 'aspirin')
    url = '%sapi/platform/settings/%s_promo_list'%(APPLUVR_VIEW_SERVER,carousel)
    ret = requests.get(url,auth=(auth_user,auth_pwd))
    if ret.status_code is 200:
        promo_apps = ret.json.get('value')
        promo_apps = simplejson.loads(promo_apps)
    else:
        promo_apps = []
    return promo_apps

def user_device(uniq_id, udid):
    user = User.load(uniq_id)
    device = Device.load(udid)
    if user is None or device is None:
        abort(404)
    else:
        return user, device

#-------------------------------------------------------------------------------#

def request_wants_json():
    best = request.accept_mimetypes \
        .best_match(['application/json', 'text/html'])
    return best == 'application/json' and \
        request.accept_mimetypes[best] > \
        request.accept_mimetypes['text/html']

@views.errorhandler(404)
def not_found(error):
    return current_app.make_response(('Object not found', 404))

@views.errorhandler(400)
def bad_request(error):
    return current_app.make_response(('Bad request. Please refer to the API documentation for details on the expected parameters.', 400))

@views.errorhandler(401)
def not_permitted(error):
    return current_app.make_response(('The server could not verify that you are authorized to access the resource you requested. In case you may have supplied the wrong credentials, please check your user-id and password and try again.', 401))

@views.route('/users/<id>/devices/<udid>/deals', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
def get_deals(id, udid): 
    device=Device.load(udid)
    user = User.load(id)
    if not user:
        abort(404)
    if not device:
        abort(404)        
    dealstatus = request.args.get('dealstatus','False')
    #platform = device.get_platform()
    platform, carrier = get_user_device_carrier_platform(user)
    deals = fetch_deal_app(APPLUVR_VIEW_SERVER, id, udid, platform, carrier, dealstatus, auth_pwd=APPLUVR_PWD, debug=True)
    if deals:
        return json.dumps(deals)
    else:
        abort(404) 

@views.route('/users/<id>/all_my_apps', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
def get_user_all_my_apps(id):
    """
    List of user apps across all his devices, with app summary details injected.
    """
    platform = request.args.get('platform','android')
    return get_cached_user_all_my_apps(id, platform.encode('ascii'))

@cache.memoize(BALI_CACHE_TIME)
def get_cached_user_all_my_apps(id, platform=None):
    user = User.load(id)
    if user is None:
        current_app.logger.debug('User not found %s' % id)
        abort(404)
    all_apps = []
    for x in dict(user.apps()).values():
        for y in x:
            all_apps.append(y)
    if not len(all_apps):
        return jsonify(data=all_apps, _count=len(all_apps))
    pkgs = ','.join(all_apps)
    appo_status_code, appo_content = get_appo_summary_view(APPO_URL,'apps/details?', pkgs, '&summary=true', platform )
    assert(appo_content)
    if appo_status_code == 200:
        if platform is 'ios':
            app_details = itunesid_to_packagename(simplejson.loads(appo_content))
        else:
            app_details = simplejson.loads(appo_content)
        if not len(app_details):
            abort(404)
        return jsonify(data=app_details, _count=len(app_details))
    else:
        return appo_content, appo_status_code

@views.route('/users/<id>/comments', methods=['GET',])
@support_etags
@requires_auth
def get_all_user_comments_uncache(id):
    return get_all_user_comments(id)

@cache.memoize(BALI_CACHE_TIME)
def get_all_user_comments(id=None):
    user = User.load(id)
    if user is None:
        abort(404)
    keys=[]
    keys.append(id)
    rows = Comment.view('comment/user_comments', keys=keys)
    comments = [comment.toDict() for comment in rows]
    return jsonify(data=comments, _count=len(comments))

@views.route('/users/<id>/devices/<udid>/my_comments', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_my_comments(id, udid, platform='android'):       
    user, device = user_device(id, udid)
    if not user:
        current_app.logger.debug('Invalid user %s' % (id))
        abort(404)
    if not device:
        current_app.logger.debug('Invalid device %s' % (udid))  
        abort(404)

    max_size_my_comments = carousel_setting().get('My Comments')
    return fetch_my_comments(APPLUVR_VIEW_SERVER, max_size_my_comments, id, platform, debug=True)

@views.route('/users/<id>/devices/<udid>/mixes_search/', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_mixed_carousel(id, udid):
    output = []
    query_term = request.args.get('query', None)
    if query_term:
        user, device = user_device(id, udid)
        if not user:
            current_app.logger.debug('Invalid user %s' % (id))
            abort(404)
        if not device:
            current_app.logger.debug('Invalid device %s' % (udid))  
            abort(404)
        platform = device.get_platform()
        return fetch_mixes_search_carousel(APPLUVR_VIEW_SERVER, id, udid, platform, query_term, debug=False)
    else:
        return jsonify(dict(count = len(output), data = (output)))

@views.route('/users/<id>/only_advisors', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_user_only_advisors(id):
    user = User.load(id)
    if user is None:
        abort(404)
    all_blocked = user.blocked_friends() + user.blocking_friends()
    should_block = False if request.args.get('block', None) == 'False' else True
    my_apps = User.load(id).all_apps()
    if should_block == False:
        advisors_list = [dict(uniq_id=advisor['uniq_id'], first_created=advisor['first_created'], advisor=advisor['advisor'], common_apps=len(get_common_apps(my_apps,advisor['uniq_id'])) ) for advisor in filter_advisors(id)] if user.advisor is None else []
    else:
        advisors_list = [dict(uniq_id=advisor['uniq_id'], first_created=advisor['first_created'], advisor=advisor['advisor'], common_apps=len(get_common_apps(my_apps,advisor['uniq_id'])) ) for advisor in filter_advisors(id) if advisor['uniq_id'] not in all_blocked] if user.advisor is None else []
    retval = advisors_list
    return jsonify(data=retval, count=len(retval))

@views.route('/users/<id>/devices/<udid>/prefetch', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def load_friends_carousel_and_cards(id, udid):
    user, device = user_device(id,udid)
    if not user:
        abort(404)
    if not device:
        abort(404)
    platform, carrier = get_user_device_carrier_platform(user)
    should_block = False if request.args.get('block', None) == 'False' else True 
    prefetch_data = get_all_friends_card_details(APPLUVR_VIEW_SERVER, id, udid, platform, should_block, auth_pwd=APPLUVR_PWD, debug=False)
    #current_app.logger.debug(prefetch_data)  
    #current_app.logger.debug(len(prefetch_data)) 
    return jsonify(status='Done!!')
    
@views.route('/users/<id>/fb/only_friends/recent', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_user_only_friends_recent(id):       
    should_block = request.args.get('block', 'True')   
    return get_cached_user_only_friends_recent(id, should_block.encode('ascii'))

@cache.memoize(BALI_CACHE_TIME)
def get_cached_user_only_friends_recent(id=None, should_block=None):   
    should_block = False if should_block == 'False' else True   
    user = User.load(id)
    if user is None:
        abort(404)

    all_blocked = user.blocked_friends() + user.blocking_friends()
    current_app.logger.debug('%s\'s blocked friends list: %r', id, all_blocked)

    all_friends = user.fb_friends(should_block)
    current_app.logger.debug('%s\'s list of friends: %s', id, all_friends)
    recent_list = []
    my_apps = User.load(id).all_apps()
    for friend_id in all_friends:
        friend = User.load(friend_id)
        if friend is not None:
            recent_list.append((friend.first_created or '1321809540',friend_id))
        else:
            recent_list.append(('1321809540',friend_id))

    recent_dict = sorted(recent_list, key=lambda item:item[0], reverse=True)
    recent_dict = [(a,b) for (b,a) in recent_dict]
    retval = [dict(uniq_id=friend, first_created=time, common_apps=len(get_common_apps(my_apps,friend)))  for (friend, time) in recent_dict]

    return jsonify(data=retval, count=len(retval))

@views.route('/users/<id>/cache/invalidation', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@cache.memoize(BALI_CACHE_TIME)
@requires_auth
def cache_invalidations(id=None):
    current_app.logger.debug(id)
    return str(random.randrange(1,10))

@views.route('/users/<id>/fb/only_friends/apps', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_user_only_friends_apps(id):
    platform = request.args.get('platform','android')
    return get_cached_user_only_friends_apps(id, platform.encode('ascii'))
    
@cache.memoize(BALI_CACHE_TIME)
def get_cached_user_only_friends_apps(id=None, platform=None):
    user = User.load(id)
    if user is None:
        abort(404)
    # straight list of all friends apps
    all_friends_apps = []
    # list of all friends app with timestamps
    all_friends_apps_ts = []  
    all_friends = user.fb_friends() 
    # For all his friends
    for friend_id in all_friends:
        friend = User.load(friend_id)
        friends_apps = []
        android_apps=[]
        android_apps_ts=[]   
        ios_apps=[] 
        ios_apps_ts=[]  

        if platform == 'android':
            get_friends_apps(friend,ios_apps,android_apps,ios_apps_ts,android_apps_ts)    
            get_mapping_apps(ios_apps,friends_apps)        
            
            for i in ios_apps_ts:
                for j in friends_apps:
                    if i.get('package_name') ==j[0]:
                        i.update({'package_name':j[1]})
                        android_apps_ts.append(i)
                        android_apps.append(j[1])
                    else:
                        pass 
            friends_pkgs=android_apps
            friends_pkgs_ts=android_apps_ts         

        else:       
            get_friends_apps(friend,ios_apps,android_apps,ios_apps_ts,android_apps_ts)
            get_mapping_apps(android_apps,friends_apps)          
            
            for i in android_apps_ts:
                for j in friends_apps:
                    if i.get('package_name') ==j[1]:
                        i.update({'package_name':j[0]})
                        ios_apps_ts.append(i)
                        ios_apps.append(j[0]) 
                    else:
                        pass 
            friends_pkgs=ios_apps
            friends_pkgs_ts=ios_apps_ts 

        # Masala mix list of all his friends apps across all devices
        all_friends_apps += friends_pkgs
        all_friends_apps_ts += friends_pkgs_ts  

    # Sequence based on most recently installed apps
    # Consolidate list
    all_friends_apps_ts_tuples = [(app.get('first_created'),app.get('package_name')) for app in all_friends_apps_ts]
    # Sort list
    recent_all_friends_apps = sorted(all_friends_apps_ts_tuples, key=lambda item:item[0], reverse=True)
    # Swap ordering
    recent_all_friends_apps_with_dups = [(a,b) for (b,a) in recent_all_friends_apps]
    recent_all_friends_apps = []

    # Remove dups by on the fly comparison with a dict of tuples
    # to generate a fresh clean list - more complicated due to the ordering
    # which needs to be retained
    for pkg, ts in recent_all_friends_apps_with_dups:
        if pkg not in dict(recent_all_friends_apps):
            recent_all_friends_apps.append((pkg, ts))

    # Count the uniq apps and group into tuples
    count_tuples = Counter(all_friends_apps).most_common()
    app_counts = dict(count_tuples)

    recent_all_friends_apps_list = [dict(package_name=pkg, common_friends=app_counts.get(pkg,0), first_created=ts) for (pkg,ts) in recent_all_friends_apps]
    sorted_all_friends_apps = recent_all_friends_apps_list
    return jsonify(data=sorted_all_friends_apps, _count=len(sorted_all_friends_apps))

@views.route('/users/recent/', methods=['GET',])
def get_recent_users():
    user_objs = User.view('user/all_users')
    users = [(user['uniq_id'], user['first_created'], user['name']) for user in user_objs]
    recent_users = sorted(users, key=lambda item:item[1], reverse=True)
    recent_users_formatted = [dict(uniq_id=user, first_created=time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.localtime(epoch)), name=name) for user, epoch, name in recent_users]
    return jsonify(data=recent_users_formatted)


@views.route('/users/<id>/fb/friends/notify', methods=['GET',])
@requires_auth
def notify_fb_friends(id):
    if os.environ.has_key('REDISTOGO_URL'):
        urlparse.uses_netloc.append('redis')
        url = urlparse.urlparse(os.environ['REDISTOGO_URL'])
        REDIS = Redis(host=url.hostname, port=url.port, db=0, password=url.password)
        redis = REDIS
        print 'Redis parameters are %s (hostname), %s (port), %s (password)' % (url.hostname, url.port, url.password)
    else:
        redis = Redis()
  
    redis.hset('count.'+id, 'mf', "1347511521")
    redis.hset('count.'+id, 'mfa', "1347511521")
    redis.hdel('count.'+id,'mf')
    redis.hdel('count.'+id,'mfa')

    retval = notify_ios_friends(APPLUVR_VIEW_SERVER, id)
    return jsonify(status=retval)

def get_user_device_carrier_platform(user):
    platform = None
    carrier = None
    device_ids = [link['href'] for link in user.links if link['rel'] == 'device']
    if device_ids:
        devices = [Device.load(i).toDict() for i in device_ids if Device.load(i) is not None]
        if devices:
            platform = (devices[0]['make']=='Apple') and  'ios' or 'android'
            if "verizon" in devices[0]['carrier'].lower():
                carrier = "Verizon"
            elif "att" in devices[0]['carrier'].lower() or "at&t" in devices[0]['carrier'].lower():
                carrier = "ATT"
            else:
                carrier = "BM"
    else:
        platform="android"
        carrier ="Verizon"
    return platform,carrier


def filter_advisors(id):
    user = User.load(id)
    if not user:
        abort(404)
    device_platform, device_carrier = get_user_device_carrier_platform(user)
    if device_platform is None and device_carrier is None:
        return jsonify(advisors=[])
    #current_app.logger.debug("User's Carrier %s"%device_carrier)
    advisors =[]
    advisor_list =  User.view('user/v3_advisors')
    for advisor in advisor_list:
        advisor_platform, advisor_carrier_frm_device = get_user_device_carrier_platform(advisor)
        advisor_carrier = advisor['advisor_carrier'] if 'advisor_carrier' in advisor and advisor['advisor_carrier'] else advisor_carrier_frm_device
        #current_app.logger.debug("deb::::Advisor:%s -->|%s| %s,%s,%s"%(advisor['_id'], advisor['advisor_carrier'],advisor_carrier,advisor_platform, advisor_carrier_frm_device))
        if (advisor_platform == device_platform) and (advisor_carrier == device_carrier):
            #current_app.logger.debug("Advisor's Carrier %s"%advisor_carrier)
            advisors.append(advisor.toDict())
    return advisors

@views.route('/users/<id>/fb/friends/recent', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_user_friends_recent(id):
    user = User.load(id)
    if user is None:
        abort(404)

    all_blocked = user.blocked_friends() + user.blocking_friends()
    current_app.logger.debug('%s\'s blocked friends list: %r', id, all_blocked)
    # Grab list of blocked users to filter out advisors
    advisors_list = [advisor['uniq_id'] for advisor in filter_advisors(id) if advisor['uniq_id'] not in all_blocked] if user.advisor is None else []
    should_block = False if request.args.get('block', None) == 'False' else True
    all_friends = user.fb_friends(should_block)
    current_app.logger.debug('%s\'s list of friends: %s', id, all_friends)
    recent_list = []
    my_apps = User.load(id).all_apps()
    for friend_id in all_friends:
        friend = User.load(friend_id)
        recent_list.append((friend.first_created or '1321809540',friend_id))

    recent_dict = sorted(recent_list, key=lambda item:item[0], reverse=True)
    recent_dict = [(a,b) for (b,a) in recent_dict]
    recent_list = [dict(uniq_id=friend, first_created=time, common_apps=len(get_common_apps(my_apps,friend)))  for (friend, time) in recent_dict]

    max_size = carousel_setting().get('My Friends')
    recent_list = recent_list[:max_size]

    #current_app.logger.debug('%s\'s friends list: %r', id, recent_list)
    if request.args.get('block', None) == 'False':
        # Only filter out friends who are blocking me
        all_blocked = user.blocking_friends()
    else:
        # Grab list of blocked users to filter advisors
        all_blocked = user.blocked_friends() + user.blocking_friends()
    #current_app.logger.debug('%s\'s blocked friends list: %r', id, all_blocked)
    # Add advisors feed into the friends list if the advisor is not blocked
    advisors_list = [dict(uniq_id=advisor['uniq_id'], first_created=advisor['first_created'], advisor=advisor['advisor'], common_apps=len(get_common_apps(my_apps,advisor['uniq_id'])) ) for advisor in filter_advisors(id) if advisor['uniq_id'] not in all_blocked] if user.advisor is None else []
    #current_app.logger.debug('%s\'s advisors list: %r', id, advisors_list)
    # Straight concat to add advisors at the end
    retval = recent_list + advisors_list
    #get android equivalent ios apps and retrive common apps  
    '''my_apps = User.load(id).all_apps()
    user_id = User.load(id)
    for index,data in enumerate(retval):
        retval=get_android_equivalent_common_apps(user_id,my_apps,retval,index,data)
    #current_app.logger.debug('Final list %r', retval)'''
    return jsonify(data=retval, count=len(retval))

def get_common_apps(users_apps,friend):
    common_apps=[]
    friend_obj = User.load(friend)

    if not friend_obj:
        return common_apps
    
    friend_apps = friend_obj.all_apps() 
    if len(users_apps)==0 or len(friend_apps)==0:
        return common_apps

    pkgs=','.join(friend_apps)    
    data=get_xmap_results_from_server(pkgs)   
    if users_apps and users_apps[0].isdigit():
        if friend_apps and friend_apps[0].isdigit():
            common_apps=list(set(users_apps) & set(friend_apps))
        else:          
            common_apps=list(set(users_apps) & set([app.get('itunesID')for app in data]))
    else:  
        if friend_apps and friend_apps[0].isdigit():         
            common_apps=list(set(users_apps) & set([app.get('androidPackageName')for app in data]))            
        else:
            common_apps=list(set(users_apps) & set(friend_apps))
    return common_apps

@views.route('/users/<id>/fb/friends/apps', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_user_friends_apps(id):
    platform = request.args.get('platform','android')
    #current_app.logger.debug(platform)
    user = User.load(id)
    if user is None:
        abort(404)
    # straight list of all friends apps
    all_friends_apps = []
    # list of all friends app with timestamps
    all_friends_apps_ts = []      
    all_blocked = user.blocked_friends() + user.blocking_friends()
    current_app.logger.debug('%s\'s blocked friends list: %r', id, all_blocked)
    # Grab list of blocked users to filter out advisors
    advisors_list = [advisor['uniq_id'] for advisor in filter_advisors(id) if advisor['uniq_id'] not in all_blocked] if user.advisor is None else []
    all_friends = user.fb_friends() + advisors_list
    # For all his friends
    for friend_id in all_friends:
        friend = User.load(friend_id)
        friends_apps = []
        android_apps=[]
        android_apps_ts=[]   
        ios_apps=[] 
        ios_apps_ts=[]  

        if platform == 'android':
            get_friends_apps(friend,ios_apps,android_apps,ios_apps_ts,android_apps_ts)    
            get_mapping_apps(ios_apps,friends_apps)        
            
            for i in ios_apps_ts:
                for j in friends_apps:
                    if i.get('package_name') ==j[0]:
                        i.update({'package_name':j[1]})
                        android_apps_ts.append(i)
                        android_apps.append(j[1])
                    else:
                        pass 
            friends_pkgs=android_apps
            friends_pkgs_ts=android_apps_ts         

        else:       
            get_friends_apps(friend,ios_apps,android_apps,ios_apps_ts,android_apps_ts)
            get_mapping_apps(android_apps,friends_apps)          
            
            for i in android_apps_ts:
                for j in friends_apps:
                    if i.get('package_name') ==j[1]:
                        i.update({'package_name':j[0]})
                        ios_apps_ts.append(i)
                        ios_apps.append(j[0]) 
                    else:
                        pass 
            friends_pkgs=ios_apps
            friends_pkgs_ts=ios_apps_ts 

        # Masala mix list of all his friends apps across all devices
        all_friends_apps += friends_pkgs
        all_friends_apps_ts += friends_pkgs_ts


    # Fetch max size of MFA carousel
    max_size = carousel_setting().get('My Friends Apps')
    all_friends_apps_ts = all_friends_apps_ts[:2*max_size]

    # Sequence based on most recently installed apps
    # Consolidate list
    all_friends_apps_ts_tuples = [(app.get('last_modified'),app.get('package_name')) for app in all_friends_apps_ts]
    # Sort list
    recent_all_friends_apps = sorted(all_friends_apps_ts_tuples, key=lambda item:item[0], reverse=True)
    # Swap ordering
    recent_all_friends_apps_with_dups = [(a,b) for (b,a) in recent_all_friends_apps]
    recent_all_friends_apps = []

    # Remove dups by on the fly comparison with a dict of tuples
    # to generate a fresh clean list - more complicated due to the ordering
    # which needs to be retained
    for pkg, ts in recent_all_friends_apps_with_dups:
        if pkg not in dict(recent_all_friends_apps):
            recent_all_friends_apps.append((pkg, ts))

    # Count the uniq apps and group into tuples
    count_tuples = Counter(all_friends_apps).most_common()
    app_counts = dict(count_tuples)

    recent_all_friends_apps_list = [dict(package_name=pkg, common_friends=app_counts.get(pkg,0), last_modified=ts) for (pkg,ts) in recent_all_friends_apps]
    recent_all_friends_apps_list = recent_all_friends_apps_list[:max_size]

    #count_tuples = [{"package_name":x[0],"common_friends":x[1]} for x in count_tuples]
    # Do some ordered dict magic to group the counts into the final json
    #sorted_all_friends_apps = OrderedDict(count_tuples)
    #sorted_all_friends_apps = count_tuples
    sorted_all_friends_apps = recent_all_friends_apps_list
    return jsonify(data=sorted_all_friends_apps, _count=len(sorted_all_friends_apps))

@views.route('/users/<id>/fb/friends/apps/<pkg>/likes', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_user_apps_friends_in_common_likes_uncache(id, pkg):
    return get_user_apps_friends_in_common_likes(id, pkg)

@cache.memoize(BALI_CACHE_TIME)
def get_user_apps_friends_in_common_likes(id=None, pkg=None):
    user = User.load(id)
    if user is None:
        abort(404)
    if pkg is None:
        abort(404)
    # Proceed even if app doesnt exist
    app = App.load(pkg)
    all_friends_ids = []
    android_likers =[]
    android_dislikers=[]
    ios_likers=[]
    ios_dislikers=[]
    app_likers=[]
    app_dislikers=[]
    likers = []
    dislikers = []
    if app:
        app_likers=app.liked
        app_dislikers=app.disliked

    all_blocked = user.blocked_friends() + user.blocking_friends()
    # Filter out blocked advisors
    advisors_list = [advisor['uniq_id'] for advisor in filter_advisors(id) if advisor['uniq_id'] not in all_blocked] if user.advisor is None else []
    all_friends = user.fb_friends() + advisors_list
    # For all his friends
    #current_app.logger.debug(all_friends)
    for friend_id in all_friends:
        friend = User.load(friend_id)
        if friend:
            friends_apps = dict(friend.apps()).values()
            friends_apps = [item for sublist in friends_apps for item in sublist]

        friends_apps = list(set(friends_apps))
        (android_apps,ios_apps)=app_separation(friends_apps)
        if pkg.isdigit():     
            if len(android_apps)>0:
                applist = ','.join(android_apps)
                data=get_xmap_results_from_server(','.join(android_apps))
                itunes_apps=list(set(ios_apps+[x.get('itunesID',None) for x in data]))
            else:
                itunes_apps = ios_apps    
            if pkg in itunes_apps: 
                all_friends_ids.append(friend_id)
                pkg_data=get_xmap_results_from_server(pkg)                
                androidPackageName=','.join([x.get('androidPackageName',None) for x in pkg_data])
                app = App.load(androidPackageName)            
                if app:
                    android_likers=app.liked
                    android_dislikers=app.disliked                            
        else:   
            if len(ios_apps)>0:
                data=get_xmap_results_from_server(','.join(ios_apps))
                android_pkgs=list(set(android_apps+[x.get('androidPackageName',None) for x in data]))  
            else:
                android_pkgs=android_apps
            if pkg in android_pkgs:                
                all_friends_ids.append(friend_id)
                pkg_data=get_xmap_results_from_server(pkg)                
                itunes_pkg=','.join([x.get('itunesID',None) for x in pkg_data])
                app = App.load(itunes_pkg)
                if app:
                    ios_likers=app.liked
                    ios_dislikers=app.disliked              
    #if app is None:
        # If there are no entries for this app yet
    #    return jsonify(data=dict(likers=[], dislikers=[], neutral=all_friends_ids, all=all_friends_ids))

    likers=app_likers+android_likers+ios_likers
    dislikers=app_dislikers+android_dislikers+ios_dislikers

    #current_app.logger.debug(likers)
    #current_app.logger.debug(dislikers)
    #current_app.logger.debug(all_friends_ids)
    friends_likers = list(set(likers) & set(all_friends_ids))
    friends_dislikers = list(set(dislikers) & set(all_friends_ids))
    friends_neutral = list(set(all_friends_ids) - (set(friends_likers) | set(friends_dislikers)))

    return jsonify(data=dict(likers=friends_likers, dislikers=friends_dislikers, neutral=friends_neutral, all=all_friends_ids))


@views.route('/users/<id>/fb/friends/apps/<pkg>/comments', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_user_apps_friends_in_common_comments_uncache(id, pkg):
    return get_user_apps_friends_in_common_comments(id, pkg)

@cache.memoize(BALI_CACHE_TIME)
def get_user_apps_friends_in_common_comments(id=None, pkg=None):
    user = User.load(id)
    if user is None:
        abort(404)
    app = App.load(pkg)
    if not app:
        current_app.logger.debug('app doesnt exist')
        #abort(404)
    all_friends_ids = []
    all_blocked = user.blocked_friends() + user.blocking_friends()
    # Filter out blocked advisors
    advisors_list = [advisor['uniq_id'] for advisor in filter_advisors(id) if advisor['uniq_id'] not in all_blocked] if user.advisor is None else []
    all_friends = user.fb_friends() + advisors_list
    # Disable this check for installed apps since starting v2
    # Friends can comment on any app
    # even if they dont have it installed
    # instead, accept all friends
    all_friends_ids = all_friends

    """
    for friend_id in all_friends:
        friend = User.load(friend_id)
        friends_apps = dict(friend.apps()).values()
        friends_apps = [item for sublist in friends_apps for item in sublist]
        current_app.logger.debug(friends_apps)
        if pkg in friends_apps:
            all_friends_ids.append(friend_id)
    """
    #current_app.logger.debug(all_friends_ids)

    all_friend_comments = []
    itunes2android_keys2 =[]
    android2itunes_key3=[]
    if pkg.isdigit():
        data=get_xmap_results_from_server(pkg)
        if data:
            for x in data:
                itunes_equivalent_pkg=x.get('androidPackageName',None)
                [itunes2android_keys2.append('%s+%s' % (friend_id, itunes_equivalent_pkg)) for friend_id in all_friends_ids]
        else:
            current_app.logger.debug('No Android equivalent found for iOS App:%s' % pkg)
    else:
        data=get_xmap_results_from_server(pkg)
        if data:
            for x in data:
                itunes_equivalent_pkg=x.get('itunesID',None)
                [android2itunes_key3.append('%s+%s' % (friend_id, itunes_equivalent_pkg)) for friend_id in all_friends_ids]
        else:
            current_app.logger.debug('No Android equivalent found for iOS App:%s' % pkg)
    native_keys = ['%s+%s' % (friend_id, pkg) for friend_id in all_friends_ids]    
    keys = android2itunes_key3 + itunes2android_keys2 + native_keys
    comments = Comment.view('comment/all_comments', keys=keys)
    for comment in comments:        
        all_friend_comments.append(dict(uniq_id=comment.uniq_id,
                common_apps=len(user.common_apps(comment.uniq_id)),
                comment = comment.toDict().get('comment'),
                last_modified = comment.toDict().get('last_modified')
                )
           )

    """
    for friend_id in all_friends_ids:
        comment = Comment.load('%s+%s' %(friend_id,pkg))
        if comment is not None:
            all_friend_comments.append(dict(uniq_id=friend_id,
                                            common_apps=len(user.common_apps(friend_id)),
                                            comment = comment.toDict().get('comment'),
                                            last_modified = comment.toDict().get('last_modified')
                                            )
                                       )
    """

    return jsonify(data=all_friend_comments, count=len(all_friend_comments))


@views.route('/users/<id>/fb/friends', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
#@cache.memoize(60)
def get_user_fb_friends(id):
    user = User.load(id)
    if user is None:
        abort(404)
    # Get list of fb friends
    max_size = carousel_setting().get('My Friends')
    should_block = False if request.args.get('block', None) == 'False' else True
    applvr_friends = user.fb_friends(should_block)
    # For all friends and their apps across devices, pull together a count and stuff it in a dict
    # Compute set intersection between user and his friend's apps
    friends_list = [dict(uniq_id=friend,common_apps=len(user.common_apps(friend))) for friend in applvr_friends]
    def compare(a, b):
        return -1 * cmp(a.get('common_apps', None), b.get('common_apps', None))
    friends_list = sorted(friends_list, compare)
    current_app.logger.debug('%s\'s friends list: %r', id, friends_list)
    if request.args.get('block', None) == 'False':
        # Only filter out friends who are blocking me
        all_blocked = user.blocking_friends()
    else:
        # Grab list of blocked users to filter advisors
        all_blocked = user.blocked_friends() + user.blocking_friends()
    current_app.logger.debug('%s\'s blocked friends list: %r', id, all_blocked)
    # Add advisors feed into the friends list if the advisor is not blocked
    advisors_list = [dict(uniq_id=advisor['uniq_id'], advisor=advisor['advisor'], common_apps=len(user.common_apps(advisor['uniq_id']))) for advisor in filter_advisors(id) if advisor['uniq_id'] not in all_blocked] if user.advisor is None else []
    # Straight concat to add advisors at the end
    retval = friends_list + advisors_list
    retval = retval[:max_size]
    #current_app.logger.debug('Final list %r', retval)
    return jsonify(data=retval, count=len(retval))


@views.route('/users/<platform>/<id1>/fb/friends/<id2>', methods=['GET',])
@views.route('/users/<id1>/fb/friends/<id2>', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_user_friends_apps_in_common(id1, id2,platform='android'):
    common_apps=[]
    user = User.load(id1)
    friend = User.load(id2)
    if user is None or friend is None:
        abort(404)
    # Compute set intersection between user and his friend's apps
    user_apps = list(user.all_apps())
    friends_apps = list(friend.all_apps())

    if len(user_apps)==0 or len(friends_apps)==0:
        return jsonify(data=common_apps)

    pkgs=','.join(friends_apps)
    data=get_xmap_results_from_server(pkgs)

    if user and user_apps[0].isdigit():
        if friend and friends_apps[0].isdigit():
            common_apps=list(set(user_apps) & set(friends_apps))            
        else:
            common_apps=list(set(user_apps) & set([app.get('itunesID')for app in data]))      
    else: 
        if friend and friends_apps[0].isdigit():     
            common_apps=list(set(user_apps) & set([app.get('androidPackageName')for app in data])) 
        else:
            common_apps=list(set(user_apps) & set(friends_apps))
    return jsonify(data=common_apps)


@views.route('/users/<id>/fb/profile', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_user_fb_profile_uncache(id):
    return get_user_fb_profile(id)

@cache.memoize(BALI_CACHE_TIME)
def get_user_fb_profile(id=None):
    # TODO: Need to validate role of this call in v2.x
    user = User.load(id)
    if user is None:
        abort(404)
    token = user.fb_token #get('fb_token',None)
    if token is None:
        return jsonify(fb_logged_in=False)
    fml_endpoint = FB_ME + token
    r = requests.get(fml_endpoint)
    fb_response = r.content
    fb_status = r.status_code
    #current_app.logger.debug(fb_response)
    #current_app.logger.debug(fb_status)
    if fb_status == 200:
        fb_data = simplejson.loads(fb_response)
        # If we dont have a user name so far, grab it now
        if user.name is None:
            if fb_data.get('name', None):
                user.name = fb_data.get('name')
                
        user.first_name = fb_data.get('first_name')
        user.last_name = fb_data.get('last_name')
        user.update()
        return jsonify(fb_logged_in=True,uniq_id=id,fb_profile=fb_data)
    if fb_status == 400:
        # If the response is a bad request
        # invalidate the current user token
        user['fb_token'] = None
        user.fb_id = None
        user.update()
    # For all other error status, return a logged in false status
    return jsonify(fb_logged_in=False,fb_error=fb_response)


def _parse_fb_headers(user, headers):
    auth_status = headers.get('www-authenticate', None)
    if auth_status:
        if 'Error' in auth_status and 'OAuth' in auth_status:
            current_app.logger.info('FB Oauth error - wiping tokens for user %s' % user.uniq_id)
            # Remove token & id
            user.fb_id = None
            user.fb_token = None
            user.update()
            pass
    return headers

@views.route('/users/<id>/fb/profile/pic', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_user_fb_pic_uncache(id):
    return get_user_fb_pic(id)

@cache.memoize(FULL_DAY)
def get_user_fb_pic(id=None):
    user = User.load(id)
    if user is None:
        abort(404)
    else:
        token = user.fb_token #get('fb_token',None)
        if token is None:
            abort(401)
        fml_endpoint = FB_PROFILE_PICTURE+token
        current_app.logger.debug('Opening FB HEAD request')
        r = requests.head(fml_endpoint, params=dict(height=200,width=200))        
        fb_response = r.content
        fb_headers = _parse_fb_headers(user, r.headers)
        fb_status = r.status_code
        # Good response - send back url
        # Added handler for 302 since in some cases Facebook responds
        # to a HEAD request with a 302, esp from Heroku infrastructure
        if fb_status == 200 or fb_status == 302:
            if not r.headers.get('location'):
                # FB Error, token invalid
                pass
            return jsonify(profile_picture=r.headers.get('location'))
        # Bad response - check oauth errors
        if fb_status == 400:
            # Note: Flag a bad request, should we wipe out auth token?
            #user.fb_token = None
            # Attempt to fetch public profile picture
            fml_endpoint = FB_PUBLIC_PROFILE_PICTURE % user.fb_id            
            r = requests.get(fml_endpoint, params=dict(height=200,width=200))
            fb_response = r.content
            fb_headers = _parse_fb_headers(user, r.headers)
            fb_status = r.status_code
            # If we get a public profile picture, send it back
            # Added handler for 302 since in some cases Facebook responds
            # to a HEAD request with a 302, esp from Heroku infrastructure
            if fb_status == 200 or fb_status == 302:
                return jsonify(profile_picture=r.headers.get('location'))
        # All falls through here
        # Note - not passing back the FB status code
        abort(404)


@views.route('/users/<id>/profile', methods=['GET',])
@support_jsonp
@support_etags
@print_timing
@cache.memoize(60)
def get_user_profile(id=None):
    user = User.load(id)
    if not user:
        abort(404)
    return jsonify(user.profile())

@views.route('/users/<id>/devices/<udid>/user_app_packs', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_app_packs_by_user(id,udid):
    user, device = user_device(id, udid)
    if not user:
        current_app.logger.debug('Invalid user %s' % (id))
        abort(404)
    if not device:
        current_app.logger.debug('Invalid device %s' % (udid))  
        abort(404)
    app_packs_by_user = fetch_all_app_packs_by_user(APPLUVR_VIEW_SERVER, id, udid, auth_pwd=APPLUVR_PWD, debug=True)
    if app_packs_by_user:  
        return app_packs_by_user
    else:
        return jsonify(count = len([]), data = [])   

@views.route('/users/<id>/devices/<udid>/app_packs', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_app_packs(id,udid):
    user, device = user_device(id, udid)
    if not user:
        current_app.logger.debug('Invalid user %s' % (id))
        abort(404)
    if not device:
        current_app.logger.debug('Invalid device %s' % (udid))  
        abort(404)
    max_size = carousel_setting().get('Mixes Carousel',20)
    app_packs_carrousel = fetch_all_app_packs(APPLUVR_VIEW_SERVER, id, udid, auth_pwd=APPLUVR_PWD, debug=True)
    if app_packs_carrousel:    
        return jsonify(dict(count = len(app_packs_carrousel[:max_size]), data = app_packs_carrousel[:max_size]))
    else:
        current_app.logger.debug("%s: device doesn't has insatlled app packs." % (udid)) 
        return jsonify(count = len([]), data = []) 

@views.route('/users/<id>/devices/<udid>/featured_apps', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_featured_apps(id, udid,  platform = 'android'):
    user, device = user_device(id, udid)
    platform, carrier = get_user_device_carrier_platform(user)
    if not user:
        current_app.logger.debug('Invalid user %s' % (id))
        abort(404)
    if not device:
        current_app.logger.debug('Invalid device %s' % (udid))  
        abort(404)

    max_size_featured = carousel_setting().get('Featured Apps')   
    return fetch_featured_carousel(APPLUVR_VIEW_SERVER, id, udid, max_size_featured, platform, carrier, debug=True)

@views.route('/users/<id>/devices/<udid>/hot_apps', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_hot_apps_uncache(id, udid):    
    return get_hot_apps(id, udid)

#@cache.memoize(FULL_DAY)
def get_hot_apps(id=None, udid=None):  
    platform = request.args.get('platform','android') 
    user, device = user_device(id, udid)
    if "verizon" in device.carrier.lower():
        carrier_prefix = 'vz'
    elif "att" in device.carrier.lower() or "at&t" in device.carrier.lower():
        carrier_prefix = 'att'
    else:
        carrier_prefix = 'bm'

    promo_apps_view="promoapp/%s_%s_hot_apps"%(carrier_prefix,platform)
    source_url = "".join([APPO_BASE_URL, APPO_VERSION, APPO_HOT_APPS])
    max_size = carousel_setting().get('Hot Apps')
    appo_id = user.appo_profile().get('uid') if user else False
    # Fetch 2x the target max size since we'll be filtering later
    carousel_max_size = 2*max_size if 2*max_size<=70 else 70
    r = requests.get(source_url,params=dict(uid=appo_id,max_size=carousel_max_size), auth=APPO_BASIC_AUTH)
    if r.status_code == 200:
        obj = simplejson.loads(r.content)
        trending_apps=obj.get('hot_apps', None)
        random.shuffle(trending_apps)
        if trending_apps: 
            if carrier_prefix is not 'default': 
                interests = [interest.strip() for interest in user.interests] if user.interests else [] 
                promolist = dict([(row['key'],row['value']) for row in PromoApp.view(promo_apps_view)]) 
                promo=get_promo_order(promolist)              
                promo_interests=promo.get('promo_interests')              
                promo_orders=promo.get('promo_orders') 
                recommendations = inject_promos(orig_list=trending_apps, all_promos=promo_interests, my_interests=interests, promo_order=promo_orders, carousel='hot_apps', my_apps=user.all_apps())
            else: 
                recommendations = trending_apps 
            if platform == 'ios': 
                recommendations = itunesid_to_packagename(recommendations) 
            recommendations_output=get_filtered_my_apps_from_hot_apps(recommendations,udid)
            return jsonify(data=recommendations_output[:max_size], count=len(recommendations_output[:max_size]))  
        else: 
            return jsonify(data=[],count=0) 
    return current_app.make_response((r.content, r.status_code))


@views.route('/users/<id>/devices/<udid>/apps_for_you', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def _get_apps_for_you(id,udid):
    platform = request.args.get('platform','android')
    user, device = user_device(id, udid)
    if "verizon" in device.carrier.lower():
        carrier_prefix = 'vz'
    elif "att" in device.carrier.lower() or "at&t" in device.carrier.lower():
        carrier_prefix = 'att'
    else:
        carrier_prefix = 'bm'
    promo_apps_view="promoapp/%s_%s_apps_for_you"%(carrier_prefix,platform)
    source_url = "".join([APPO_BASE_URL, APPO_VERSION, APPO_APPS_FOR_YOU])
    max_size = carousel_setting().get('Apps For You')
    odp_installed = device.odp_installed if device else False
    appo_id = user.appo_profile().get('uid') if user else False
    # Fetch 2x the target max size since we'll be filtering later
    current_app.logger.debug("AFY: %s %s" %(source_url,dict(uid=appo_id,max_size=2*max_size)))

    # Binary flag for Appo
    odp_installed = '1' if odp_installed else '0'
    carousel_max_size = 2*max_size if 2*max_size<=70 else 70
    r = requests.get(source_url,params=dict(uid=appo_id,max_size=carousel_max_size,odp_installed=odp_installed), auth=APPO_BASIC_AUTH)
    if r.status_code == 200:
        obj = simplejson.loads(r.content)
        recommended_apps=obj.get('recommendations', None)
        random.shuffle(recommended_apps)
        #current_app.logger.debug(recommended_apps)
        if recommended_apps: 
            if carrier_prefix is not 'default': 
                interests = [interest.strip() for interest in user.interests] if user.interests else [] 
                promolist = dict([(row['key'],row['value']) for row in PromoApp.view(promo_apps_view)]) 
                #current_app.logger.debug(promolist) 
                #current_app.logger.debug(interests) 

                promo=get_promo_order(promolist)                
                promo_interests=promo.get('promo_interests') 
                promo_orders=promo.get('promo_orders') 
                #current_app.logger.debug(promo_interests) 
                #current_app.logger.debug(promo_orders) 
                recommendations = inject_promos(orig_list=recommended_apps, all_promos=promo_interests, my_interests=interests, promo_order=promo_orders, carousel='apps_for_you', my_apps=user.all_apps())
            else: 
                recommendations = recommended_apps 
            if platform == 'ios': 
                recommendations = itunesid_to_packagename(recommendations) 
            return jsonify(data=recommendations[:max_size],count=len(recommendations[:max_size])) 
        else: 
            return jsonify(data=[],count=0) 
    return current_app.make_response((r.content, r.status_code))

#--------------------------------------------------------------------------------------#

import urlparse


APPLUVR_VIEW_SERVER = os.environ.get('APPLUVR_VIEW_SERVER', 'http://localhost:5000/v5-cache/')
APPLUVR_PWD = os.environ.get('APPLUVR_PWD', 'aspirin')
WORKER_MAX_ATTEMPTS = os.environ.get('APPLUVR_WORKER_MAX_ATTEMPTS', 8)
WORKER_BLOCKING_MODE = os.environ.get('APPLUVR_WORKER_BLOCKING_MODE', True)

if os.environ.has_key('REDISTOGO_URL'):
    urlparse.uses_netloc.append('redis')
    url = urlparse.urlparse(os.environ['REDISTOGO_URL'])
    REDIS = Redis(host=url.hostname, port=url.port, db=0, password=url.password)
    redis = REDIS
    print 'Redis parameters are %s (hostname), %s (port), %s (password)' % (url.hostname, url.port, url.password)
else:
    redis = Redis()

@views.route('/workers/complete', methods=['GET',])
def get_complete_workers():
    from pickle import loads
    queue_key = current_app.config['REDIS_COMPLETED_QUEUE_KEY']
    workers = redis.lrange(queue_key,0,-1)
    result = []
    for worker in workers:
        obj = json.loads(worker)
        result.append(obj)
    return jsonify(result=result) if request_wants_json() else render_template('jobstatus.html', messages=result)

@views.route('/workers/complete/trim', methods=['POST',])
def trim_complete_workers():
    queue_key = current_app.config['REDIS_COMPLETED_QUEUE_KEY']
    queue_max = current_app.config['REDIS_COMPLETED_QUEUE_MAX']
    redis.ltrim(queue_key,0,queue_max)
    return str(redis.llen(queue_key)), 200

@views.route('/workers/results/all', methods=['DELETE',])
def del_all_task_results():
    [redis.delete(x) for x in redis.keys() if 'vz-view-redis-workers:result' in x]
    return '',204

@views.route('/workers/results/<key>', methods=['DELETE',])
def del_task_results(key):
    redis.delete(key)
    return '',204


@views.route('/workers/queued')
def get_queued_workers():
    from pickle import loads
    queue_key = current_app.config['REDIS_QUEUE_KEY']
    workers = redis.lrange(queue_key,0,-1)
    return jsonify(result=workers)

@views.route('/users/<id>/devices/<udid>/apps', methods=['GET'])
@print_timing
@requires_auth
def get_device_installed_apps_details(id, udid):
    user, device = user_device(id, udid)
    data = []
    try:
        data = device.apps_installed_ts
    except:
        # Older users dont have the attribute
        pass
    return jsonify(data=data)


@views.route('/users/<id>/devices/<udid>/apps/', methods=['POST','PUT'])
@print_timing
@requires_auth
def update_device_installed_apps(id, udid):
    user, device = user_device(id, udid)   
    server = APPLUVR_VIEW_SERVER
    args = request.form
    apps = args.get('apps', None)
    odp_installed = args.get('odp_installed', '0')
    #current_app.logger.debug('Received app string for insertion: %s' % apps)
    if not apps:
        return make_400('Invalid parameters. Please refer to the documentation')
    live = args.get('live', None)
    if live:
        """
        Live fetch - update apps, set read installed apps, post appo profile, check for available recos
        """   
        
        result = update_device_apps(server, id, udid, apps, odp_installed, auth_pwd=APPLUVR_PWD, debug=True)
        # Post Appo Profile
        # Check Recommendations
        # TODO: Work on these after the Appo integration for 2.x starts
        # Delete cached my_apps data
        # Fire off new background job to fetch new data
        clear_all_carousels(id, udid)        
        get_carousel(id, udid, 'my_apps')
        return result, 200
    else:
        """
        Not a live call - update apps as a background job
        """
        task = update_device_apps.delay(server, id, udid, apps, odp_installed, auth_pwd=APPLUVR_PWD, debug=True)
        return task.id, 200

@views.route('/users/<id>/devices/<udid>/ios/apps/', methods=['POST','PUT'])
@print_timing
@requires_auth
def update_ios_device_installed_apps(id, udid):
    user, device = user_device(id, udid)    
    server = APPLUVR_VIEW_SERVER
    args = request.form
    apps = args.get('apps', None)
    #current_app.logger.debug('Received app string for insertion: %s' % apps)
    if not apps:
        return make_400('Invalid parameters. Please refer to the documentation')
    live = args.get('live', None)
    if live:
        """
        Live fetch - update apps, set read installed apps, post appo profile, check for available recos
        """   

        result = update_ios_device_apps(server, id, udid, apps, auth_pwd=APPLUVR_PWD, debug=True)
        # Post Appo Profile
        # Check Recommendations
        # TODO: Work on these after the Appo integration for 2.x starts
        # Delete cached my_apps data
        # Fire off new background job to fetch new data
        clear_all_carousels(id, udid)
        get_carousel(id, udid, 'my_apps',platform='ios')
        return result, 200
    else:
        """
        Not a live call - update apps as a background job
        """
        task = update_ios_device_apps.delay(server, id, udid, apps, auth_pwd=APPLUVR_PWD, debug=True)
        return task.id, 200

@views.route('/users/<uniq_id>/devices/<udid>/apps/', methods=['DELETE',])
@requires_auth
def delete_device_apps(uniq_id, udid):
    user, device = user_device(uniq_id, udid)
    if not device:
        abort(404)
    if device.make == "Apple":
        device.apps_url_schemes =[]
        device.apps_process_names =[]
        
    device.apps_installed = []
    device.apps_installed_ts = []
    device.read_apps = False
    device.update()
    
    #invalidate cache login or on new app installation.
    target = '%sapi/user/%s/uncache' %(APPLUVR_VIEW_SERVER, uniq_id)
    r = requests.get(target, auth = ('tablet',APPLUVR_PWD))
    if r .status_code == 200:
        current_app.logger.debug("invalidating %s's and his friends apps cards and carousels status : %s" %(user, r.content))

    # TODO: Wire to Appo profile post call
    clear_all_carousels(uniq_id, udid)
    get_carousel(uniq_id, udid, 'my_apps')

    response = current_app.make_response(jsonify(id=device._id))
    response.status_code = 204
    return response

@views.route('/cards/<uniq_id>/profile/')
@views.route('/cards/<uniq_id>/friends/<friend_id>/')
@views.route('/cards/<platform>/<uniq_id>/profile/')
@views.route('/cards/<platform>/<uniq_id>/friends/<friend_id>/')
@print_timing
def get_friend_card(uniq_id,friend_id=None,platform='android'):
    user = User.load(uniq_id)
    if not user:
        abort(404)
    if friend_id is not None:
        friend = User.load(friend_id)
        if not friend:
            abort(404)
    #user, device = user_device(uniq_id, udid)
    server = APPLUVR_VIEW_SERVER

    if WORKER_BLOCKING_MODE:
        #current_app.logger.debug("%s:%s:%s:%s:%s"%(server,uniq_id,APPLUVR_PWD,platform,friend_id))
        return fetch_friend_card(server, uniq_id, "udid", friend_id, auth_pwd=APPLUVR_PWD, debug=True, platform=platform)

    task_id = redis.hget(uniq_id, 'profile')
    if task_id is None:
        task = fetch_friend_card.delay(server, uniq_id, "udid", friend_id, auth_pwd=APPLUVR_PWD, debug=True, platform=platform)
        redis.hset(uniq_id, 'profile', task.id)

        return 'Processing new request %s, please try again after some time. (1)' % task.id, 202
    else:
        current_app.logger.debug('..loading results from task %s' % task_id)
        task = fetch_friend_card.get_task(task_id)
        if task is None:
            task = fetch_friend_card.delay(server, uniq_id, "udid", friend_id, auth_pwd=APPLUVR_PWD, debug=True,platform=platform)
            redis.hset(uniq_id, 'profile', task.id)

            return 'Processing request %s again, please try again after some time. (2)' % task.id, 202
        elif task.return_value is None:
            attempt = int(request.args.get('attempt', 0))
            if attempt % WORKER_MAX_ATTEMPTS == 1:
                del_task_results(task.id)
                task_id = fetch_friend_card.delay(server, uniq_id, "udid", friend_id, auth_pwd=APPLUVR_PWD, debug=True,platform=platform)
                return 'Re-processing the request %s, please try again after some time. (4)' % task_id, 202
            else:
                return 'Processing request %s and waiting for response, please try again after some time. (3)' % task.id, 202
        else:
            return task.return_value, 200

@views.route('/cards/<userid>/<devid>/app/<appid>/userprefstatus',  methods=['GET'])
@print_timing
def get_user_app_preference(userid,devid,appid): 
    user, device = user_device(userid, devid)   
    if appid in user.apps_liked:
        user_app_preference_current= 'like'
    elif appid in user.apps_disliked:
        user_app_preference_current= 'dislike'
    else:
        user_app_preference_current='none'
    if appid in device.apps_installed:
        app_installed_current=True
    else:
        app_installed_current=False
    return jsonify(dict(user_app_preference_current=user_app_preference_current,app_installed_current=app_installed_current))


@views.route('/cards/<uniq_id>/<udid>/app_pack/<apppck_id>/', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
def get_app_pack_card(uniq_id, udid, apppck_id):
    user, device = user_device(uniq_id, udid)
    if user is None and device is None:
        abort(404)
    platform = device.get_platform()
    app_packs = fetch_app_pack_card(APPLUVR_VIEW_SERVER, uniq_id, udid, apppck_id, platform, auth_pwd=APPLUVR_PWD, debug=True)
    if app_packs:
        if platform == 'ios':
            return itunesid_to_packagename(app_packs)
        else:
            return app_packs
    else:
        current_app.logger.debug('invalid app pack')
        abort(404)


@views.route('/cards/<uniq_id>/<udid>/app/<pkg>/')
@print_timing
def get_app_card(uniq_id, udid, pkg):
    user, device = user_device(uniq_id, udid)
    server = APPLUVR_VIEW_SERVER

    if WORKER_BLOCKING_MODE:
        return fetch_app_card(server, uniq_id, udid, pkg, auth_pwd=APPLUVR_PWD, debug=True)

    task_id = redis.hget(udid, pkg)
    if task_id is None:
        task = fetch_app_card.delay(server, uniq_id, udid, pkg, auth_pwd=APPLUVR_PWD, debug=True)
        redis.hset(udid, pkg, task.id)

        return 'Processing new request %s, please try again after some time. (1)' % task.id, 202
    else:
        current_app.logger.debug('..loading results from task %s' % task_id)
        task = fetch_app_card.get_task(task_id)
        if task is None:
            task = fetch_app_card.delay(server, uniq_id, udid, pkg, auth_pwd=APPLUVR_PWD, debug=True)
            redis.hset(udid, pkg, task.id)

            return 'Processing request %s again, please try again after some time. (2)' % task.id, 202
        elif task.return_value is None:
            attempt = int(request.args.get('attempt', 0))
            if attempt % WORKER_MAX_ATTEMPTS == 1:
                del_task_results(task.id)
                task_id = fetch_app_card.delay(server, uniq_id, udid, pkg, auth_pwd=APPLUVR_PWD, debug=True)
                return 'Re-processing the request %s, please try again after some time. (4)' % task_id, 202
            else:
                return 'Processing request %s and waiting for response, please try again after some time. (3)' % task.id, 202
        else:
            return task.return_value, 200

''' Convert dict to String and replace market:// links to FQDN for Google Play 
    * Required for my_verizon api calls for hot_apps and apps_for_you
    * Returns json
'''
def linkify_market(dict_in):
    str_json = json.dumps(dict_in)
    str_json = str_json.replace('market://details', 'https://play.google.com/store/apps/details')
    return json.loads(str_json)


@views.route('/myverizon/android/apps_for_you')
def myvz_android_afy():
    if my_vz_user is None or my_vz_device is None:
        return 'MyVZ Objects not set', 500
    max_size = request.args.get('max_size', '')
    results = json.loads(linkify_market(get_carousel_blocking(my_vz_user, my_vz_device, 'apps_for_you')))
    if max_size.isdigit() and int(max_size)>0:
        max_size = int(max_size)
        resultsdata = results["data"]
        results = {'count': len(resultsdata[:max_size]), 'data':resultsdata[:max_size]}
    return dict2xml(results, 'xml')


@views.route('/myverizon/android/hot_apps')
def myvz_android_ha():
    if my_vz_user is None or my_vz_device is None:
        return 'MyVZ Objects not set', 500
    max_size = request.args.get('max_size','')
    results = json.loads(linkify_market(get_carousel_blocking(my_vz_user, my_vz_device, 'hot_apps')))
    if max_size.isdigit() and int(max_size)>0:
        max_size = int(max_size)
        resultsdata = results["data"]
        results = {'count': len(resultsdata[:max_size]), 'data':resultsdata[:max_size]}
    return dict2xml(results, 'xml')

@views.route('/myverizon/ios/apps_for_you')
@views.route('/myverizon/ios/hot_apps')
def myvz_ios_api():
    results = {'count':0}
    return dict2xml(results, 'xml')

@views.route('/users/<uniq_id>/devices/<udid>/only_mf/reset/', methods = ['POST',])
def get_only_new_friends_reset(uniq_id,udid):
    user,device = user_device(uniq_id,udid)
    if not user:
        abort(404)
    if not device:
        abort(404)
    cache.delete_memoized(get_only_new_friends_notification, uniq_id, udid) 
    cache.delete_memoized(get_only_new_friends_notification, uniq_id, udid)     
    cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, udid, auth_pwd=APPLUVR_PWD, block=False, debug=False)
    cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, udid, auth_pwd=APPLUVR_PWD, block=True, debug=True)
    last_viewed = int(time.time())
    redis.hset('count.'+uniq_id, 'mf', last_viewed)
    current_app.logger.debug("------> reset %s MF to %s"%(uniq_id, redis.hget('count.'+uniq_id,'mf')))
    return jsonify(last_viewed = last_viewed)

@views.route('/users/<uniq_id>/devices/<udid>/only_mfa/reset/', methods = ['POST',])
def get_only_new_friends_apps_reset(uniq_id,udid): 
    user,device = user_device(uniq_id,udid)
    if not user:
        abort(404)
    if not device:
        abort(404)

    usrplatform,usercarrier = get_user_device_carrier_platform(user)
    cache.delete_memoized(get_only_new_friends_apps_notification, uniq_id, udid) 
    cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, uniq_id, udid, auth_pwd=APPLUVR_PWD, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, uniq_id, udid, auth_pwd=APPLUVR_PWD, debug=True, platform=unicode(usrplatform))
    last_viewed = arrow.utcnow().timestamp
    redis.hset('count.'+uniq_id, 'mfa', last_viewed)
    current_app.logger.debug("------> reset %s MFA to %s"%(uniq_id, redis.hget('count.'+uniq_id,'mfa')))
    return jsonify(last_viewed = last_viewed)


@views.route('/users/<uniq_id>/devices/<udid>/only_mf/count/')
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_only_new_friends_notification_uncache(uniq_id, udid):
    return get_only_new_friends_notification(uniq_id, udid)

@cache.memoize(BALI_CACHE_TIME)
def get_only_new_friends_notification(uniq_id=None,udid=None):  
    new_friend_users_id = []
    user = User.load(uniq_id)
    if not user:
        abort(404)   

    all_friends = user.fb_friends()
    friends_max_count = carousel_setting().get('My Friends')
    lastviewed = int(redis.hget('count.'+uniq_id,'mf')) if redis.hget('count.'+uniq_id,'mf') else 0
    new_friend_users_id = list(set([friend for friend in all_friends if User.load(friend) and (User.load(friend).fb_login > lastviewed or User.load(friend).first_created > lastviewed)]))
    #new_friend_users_id = list(set([friend for friend in all_friends if User.load(friend) and (User.load(friend).first_created) > (lastviewed)]))
    
    new_friend_users_id = new_friend_users_id[:int(friends_max_count)]
    return jsonify(data = new_friend_users_id, count = len(new_friend_users_id))

@views.route('/users/<uniq_id>/devices/<udid>/only_mfa/count/')
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_only_new_friends_apps_notification_uncache(uniq_id, udid): 
    return get_only_new_friends_apps_notification(uniq_id, udid)

@cache.memoize(BALI_CACHE_TIME)
def get_only_new_friends_apps_notification(uniq_id=None,udid=None): 
    new_friends_apps = [] 
    new_friends_apps_with_user = []
    filterd_list_final = [] 
    user = User.load(uniq_id)
    device = Device.load(udid)
    if not user:
        abort(404) 
    if not device:
        abort(404)

    platform = device.get_platform()
    all_friends = user.fb_friends()
    friends_apps_max_count = carousel_setting().get('My Friends Apps')
    lastviewed = int(redis.hget('count.'+uniq_id,'mfa')) if redis.hget('count.'+uniq_id,'mfa') else 0
    current_app.logger.debug("----> Last viewed time %s"%lastviewed)  
    for friend in all_friends:
        friend_obj = User.load(friend)
        if friend_obj:                  
            friendapps = dict(friend_obj.apps_ts()).values() 
            applists = [app.get('package_name') for apps in friendapps for app in apps if app.get('first_created') > lastviewed]
            if len(applists)>0:               
                if platform == 'android':                    
                    if applists[0].isdigit():                         
                        xmap = get_xmap_results_from_server(','.join(applists))
                        android_equivalent_apps = [apps.get('androidPackageName',None) for  apps in xmap if xmap]
                        [new_friends_apps_with_user.append(dict(package_name = package, name = friend_obj.name, first_name = friend_obj.first_name, last_name = friend_obj.last_name )) for package in android_equivalent_apps]                
                    else:                        
                        [new_friends_apps_with_user.append(dict(package_name = package, name = friend_obj.name, first_name = friend_obj.first_name, last_name = friend_obj.last_name )) for package in applists]                
                else:
                    if applists[0].isdigit():                         
                        [new_friends_apps_with_user.append(dict(package_name = package, name = friend_obj.name, first_name = friend_obj.first_name, last_name = friend_obj.last_name )) for package in applists]                
                    else:                        
                        xmap = get_xmap_results_from_server(','.join(applists))       
                        ios_equivalent_apps = [apps.get('itunesID',None) for  apps in xmap if xmap]
                        [new_friends_apps_with_user.append(dict(package_name = package, name = friend_obj.name, first_name = friend_obj.first_name, last_name = friend_obj.last_name )) for package in ios_equivalent_apps]                
   
    for apps in new_friends_apps_with_user:
        if apps.get('package_name') not in new_friends_apps:
            new_friends_apps.append( apps.get('package_name'))
            filterd_list_final.append(apps)

    filterd_list = filterd_list_final[:int(friends_apps_max_count)]    
    return jsonify(data = filterd_list, count = len(filterd_list))
    
# AT&T Click Tracking Stub
@views.route('/track/<endpoint>/<sub_id>/<pkg_id>/')
def track_att_recommendations(endpoint,sub_id,pkg_id):
    if sub_id and pkg_id:
        return jsonify(status=True)
    else:
        abort(404)

#AT&T Endpoints API
@views.route('/carousels/<sub_id>/recommendations/')
@requires_att_auth
def get_att_recommendations(sub_id = None):
    output = []  
    #Get Auth Username to figure out endpoint calling it
    auth = request.authorization
    current_endpoint = auth.username   
    max_size_recommended =  50 if not request.args.get('max_size') else request.args.get('max_size')  
    return_output = fetch_device(APPLUVR_VIEW_SERVER, sub_id)
    device = json.loads(return_output).get('device')
    if device == '':
        json_server = 'http://www.vzwtopapps.com/'
        target = '%sapi/topapps.json'%(json_server)        
        r = requests.get(target, auth = ('api','jpw421z'))
        if r.status_code == 200: 
            output = json.loads(r.content).get('xml').get('data')           
        output = output[:int(max_size_recommended)]
        return jsonify(count = len(output), data = output)
    device_obj = Device.load(device)
    if not device_obj:
        abort(404)
    platform =  device_obj.get_platform()
    user = device_obj.uniq_id
    user_obj =  User.load(user)  
    if not user_obj:
        abort(404)

    promo_pkgs = [app.get('key') for app in PromoApp.view('promoapp/'+current_endpoint)]
    promo_app_appo_summary = get_all_widget_app_summary(APPLUVR_VIEW_SERVER, promo_pkgs, platform)

    odp_installed = device_obj.odp_installed if device else False
    max_size_hot_apps = carousel_setting().get('Hot Apps')
    max_size_recommendation = carousel_setting().get('Apps For You')
    appo_id = user_obj.appo_profile().get('uid') if user else False
    afy_percentage = carousel_setting().get('Percentage for AFY')
    afy_percentage = afy_percentage if afy_percentage else 50
    ha_percentage = 100-afy_percentage
    hot_apps_carousel_max_size = 2*max_size_hot_apps if 2*max_size_hot_apps<=70 else 70    
    recommendation_carousel_max_size = 2*max_size_recommendation if 2*max_size_recommendation<=70 else 70         
    return_data =  fetch_recommended_apps(APPLUVR_VIEW_SERVER, user, device, platform = platform, auth_pwd = APPLUVR_PWD)
    return_data = json.loads(return_data).get('data')
    return_data = return_data + promo_app_appo_summary.values()
    for appo in return_data:
        pkg_id = appo.get('package_name')
        # Can't URL assiged in nginix, so have to set the external URL 
        # as an env variable to read out of 
        ext_server_url = os.environ.get('ATT_Click_track_URL',APPLUVR_VIEW_SERVER)
        appo['clicktrack'] = ext_server_url+'views/track/'+current_endpoint+'/'+sub_id+'/'+pkg_id+'/'
        if platform == 'android':      
            download_mobileurl = appo.get('android_market').get('download_url')               
            download_weburl = download_mobileurl.replace('market://','https://play.google.com/store/apps/')             
            android_market = appo.get('android_market')          
            android_market.update({"download_weburl":download_weburl, "download_mobileurl":download_mobileurl})
            del android_market['download_url']
            appo.update({"android_market":android_market})
            output.append(appo)  
        else:    
            download_mobileurl = appo.get('itunes_market').get('download_url')            
            itunes_market = appo.get('itunes_market')          
            itunes_market.update({"download_weburl":download_mobileurl, "download_mobileurl":download_mobileurl})
            del itunes_market['download_url']
            appo.update({"itunes_market":itunes_market})
            output.append(appo)
    random.shuffle(output)
    output = output[:recommendation_carousel_max_size]
    return jsonify(count = len(output), data = output)   


@views.route('/carousels/<uniq_id>/<udid>/<platform>/counts/')
def get_carousel_counts(uniq_id,udid,platform):
    user, device = user_device(uniq_id, udid)
    if not user:
        current_app.logger.debug('Invalid user %s' % (id))
        abort(404)
    if not device:
        current_app.logger.debug('Invalid device %s' % (udid))  
        abort(404)
    return fetch_carousel_counts(APPLUVR_VIEW_SERVER, uniq_id, udid, platform, APPLUVR_PWD, debug=False)

@views.route('/carousels/<uniq_id>/<udid>/<platform>/<carousel>/')
@views.route('/carousels/<uniq_id>/<udid>/<carousel>/')
@print_timing
def user_carousel(uniq_id, udid, carousel, platform = 'android'):
    user, device = user_device(uniq_id, udid)
    task_id = redis.hget(udid, carousel)
    if WORKER_BLOCKING_MODE:
        return get_carousel_blocking(uniq_id, udid, carousel,platform)

    if task_id is None:
        task_id = get_carousel(uniq_id, udid, carousel,platform)
        return 'Processing new request %s, please try again after some time. (1)' % task_id, 202
    else:
        current_app.logger.debug('..loading results from task %s' % task_id)
        task = fetch_recos.get_task(task_id)
        if task is None:
            # TODO: Fire off new task
            task_id = get_carousel(uniq_id, udid, carousel,platform)
            return 'Processing request %s again, please try again after some time. (2)' % task_id, 202
        elif task.return_value is None:
            attempt = int(request.args.get('attempt', 0))
            if attempt % WORKER_MAX_ATTEMPTS == 1:
                del_task_results(task.id)
                task_id = get_carousel(uniq_id, udid, carousel,platform)
                return 'Re-processing the request %s, please try again after some time. (4)' % task_id, 202

            else:
                return 'Processing request %s and waiting for response, please try again after some time. (3)' % task.id, 202
        else:
            return task.return_value, 200


def clear_carousel(uniq_id, udid, carousel):
    print 'Carousel: %s, %s, %s' %(uniq_id, udid, carousel)
    user, device = user_device(uniq_id, udid)
    redis.hdel(udid, carousel)

def clear_all_carousels(uniq_id, udid):
    user, device = user_device(uniq_id, udid)
    with redis.pipeline() as pipe:
        pipe.hdel(udid, 'amf')
        pipe.hdel(udid, 'mf')
        pipe.hdel(udid, 'apps_for_you')
        pipe.hdel(udid, 'hot_apps')
        pipe.hdel(udid, 'mfa')
        pipe.hdel(udid, 'my_apps')
        pipe.hdel(udid, 'app_packs')
        pipe.hdel(udid, 'user_app_packs')
        pipe.hdel(udid, 'recommended_apps')
        pipe.hdel(udid, 'featured_apps')
        pipe.hdel(udid, 'only_mf')
        pipe.hdel(udid, 'only_mfa')
        pipe.hdel(udid, 'only_advisors')
        pipe.hdel(udid, 'my_comments')
        pipe.execute()

@print_timing
def get_carousel(uniq_id, udid, carousel, platform='android'):
    print 'Carousel: %s, %s, %s' %(uniq_id, udid, carousel)
    user, device = user_device(uniq_id, udid)
    server = APPLUVR_VIEW_SERVER
    user = uniq_id
    device = udid
    task = None
    if carousel == 'amf':
        task = fetch_all_my_friends.delay(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
        redis.hset(udid, 'amf', task.id)
    if carousel == 'mf':
        task = fetch_my_friends.delay(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
        redis.hset(udid, 'mf', task.id)
    if carousel == 'apps_for_you':
        task = fetch_recos.delay('apps_for_you',server, user, device, auth_pwd=APPLUVR_PWD,debug=True, platform=platform)
        redis.hset(udid, 'apps_for_you',task.id)
    if carousel == 'hot_apps':
        task = fetch_recos.delay('hot_apps',server, user, device, auth_pwd=APPLUVR_PWD,debug=True, platform=platform)
        redis.hset(udid, 'hot_apps', task.id)
    if carousel == 'my_apps' or carousel =='apps_i_use':
        task = fetch_my_apps.delay(server, user, device, auth_pwd=APPLUVR_PWD, debug=True, platform=platform)
        redis.hset(udid, 'my_apps', task.id)
    if carousel == 'mfa':
        task = fetch_mfa.delay(server, user, device, auth_pwd=APPLUVR_PWD, debug=True,platform=platform)
        redis.hset(udid, 'mfa', task.id)
    if carousel == 'app_packs':
        task = get_app_packs.delay(user, device)
        redis.hset(udid, 'app_packs', task.id)
    if carousel == 'user_app_packs':
        task = get_app_packs_by_user.delay(user, device)
        redis.hset(udid, 'user_app_packs', task.id)
    if carousel == 'recommended_apps':
        task = fetch_recommended_apps.delay(server, uniq_id, udid, platform, auth_pwd=APPLUVR_PWD)
        redis.hset(udid, 'recommended_apps', task.id)
    if carousel == 'featured_apps':
        task = get_featured_apps.delay(uniq_id, udid, platform)
        redis.hset(udid, 'featured_apps', task.id)
    if carousel == 'only_mf':
        task = fetch_only_friends.delay(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
        redis.hset(udid, 'only_mf', task.id)
    if carousel == 'only_mfa':
        task = fetch_only_mfa.delay(server, user, device, auth_pwd=APPLUVR_PWD, debug=True, platform=platform)
        redis.hset(udid, 'only_mfa', task.id)
    if carousel == 'only_advisors':
        task = fetch_only_advisors.delay(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
        redis.hset(udid, 'only_advisors', task.id)
    if carousel == 'my_comments':
        task = get_my_comments.delay(uniq_id, udid, platform)
        redis.hset(udid, 'my_comments', task.id)
    print 'Task %s ' % task
    return task.id if task else None


def get_carousel_blocking(uniq_id, udid, carousel, platform = 'android'):
    print 'Carousel: %s, %s, %s' %(uniq_id, udid, carousel)
    user, device = user_device(uniq_id, udid)
    server = APPLUVR_VIEW_SERVER
    user = uniq_id
    device = udid
    if carousel == 'amf':
        return fetch_all_my_friends(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    if carousel == 'mf':
        return fetch_my_friends(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    if carousel == 'apps_for_you':
        return fetch_recos('apps_for_you',server, user, device, auth_pwd=APPLUVR_PWD,debug=True, platform=platform)
    if carousel == 'hot_apps':
        return fetch_recos('hot_apps',server, user, device, auth_pwd=APPLUVR_PWD,debug=True, platform=platform)
    if carousel == 'my_apps' or carousel =='apps_i_use':
        return fetch_my_apps(server, user, device, auth_pwd=APPLUVR_PWD, debug=True,platform=platform)
    if carousel == 'mfa':
        return fetch_mfa(server, user, device, auth_pwd=APPLUVR_PWD, debug=True, platform=platform)
    if carousel == 'app_packs':
        return get_app_packs(user, device)
    if carousel == 'user_app_packs':
        return get_app_packs_by_user(user, device)
    if carousel == 'recommended_apps':
        return fetch_recommended_apps(server, uniq_id, udid, platform, auth_pwd=APPLUVR_PWD)
    if carousel == 'featured_apps':
        return get_featured_apps(uniq_id, udid, platform)
    if carousel == 'only_mf':
        return fetch_only_friends(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    if carousel == 'only_mf_with_blocked':
        return fetch_only_friends(server, user, device, auth_pwd=APPLUVR_PWD, block=False, debug=True)
    if carousel == 'only_mfa':
        return fetch_only_mfa(server, user, device, auth_pwd=APPLUVR_PWD, debug=True, platform=platform)
    if carousel == 'only_advisors':
        return fetch_only_advisors(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    if carousel == 'only_advisors_with_blocked':
        return fetch_only_advisors(server, user, device, auth_pwd=APPLUVR_PWD, block=False, debug=True)
    if carousel == 'my_comments':
        return get_my_comments(uniq_id, udid, platform)
    if carousel == 'att_widgets':
        return fetch_att_widget_carousels(server, user, device, platform = 'android', auth_pwd = APPLUVR_PWD, debug = True)
    abort(404)

def get_promo_order(interests):    
    promo_orders=[]
    promo_interests={}
    orderd_promo_pkg=[]
    for pkg in interests:                  
        promo_interests[pkg]=interests[pkg][0]
        promo_pkgs={"pkg":pkg, "priority":int(interests[pkg][1])}
        promo_orders.append(promo_pkgs)  
        promo_interests.update()
        new_list=sorted(promo_orders, key=itemgetter('priority'))
        orderd_promo_pkg=[pkgs.get('pkg', None) for pkgs in new_list]
    return dict(promo_interests=promo_interests,promo_orders=orderd_promo_pkg)

@views.route('/users/<uniq_id>/devices/<udid>/fetch_carousels', methods=['GET',])
@print_timing
def get_fetch_carousels(uniq_id, udid):
    user, device = user_device(uniq_id, udid)
    server = APPLUVR_VIEW_SERVER
    user = uniq_id
    device = udid
    task5 = fetch_my_friends.delay(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    redis.hset(udid, 'mf', task5.id)
    task1 = fetch_recos.delay('apps_for_you',server, user, device, auth_pwd=APPLUVR_PWD,debug=True)
    redis.hset(udid, 'apps_for_you',task1.id)
    task2 = fetch_recos.delay('hot_apps',server, user, device, auth_pwd=APPLUVR_PWD,debug=True)
    redis.hset(udid, 'hot_apps', task2.id)
    task3 = fetch_my_apps.delay(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    redis.hset(udid, 'my_apps', task3.id)
    task4 = fetch_mfa.delay(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    redis.hset(udid, 'mfa', task4.id)
    task6 = fetch_only_friends.delay(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    redis.hset(udid, 'only_mf', task6.id)
    task7 = fetch_only_mfa.delay(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    redis.hset(udid, 'only_mfa', task7.id)
    task8 = fetch_only_advisors.delay(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    redis.hset(udid, 'only_advisors', task8.id)


    return jsonify(apps_for_you=url_for('views.task_progress',tid=task1.id,_external=True),
                   hot_apps=url_for('views.task_progress',tid=task2.id,_external=True),
                   my_apps=url_for('views.task_progress',tid=task3.id,_external=True),
                   mfa=url_for('views.task_progress',tid=task4.id,_external=True),
                   mf=url_for('views.task_progress',tid=task5.id,_external=True),
                   only_mf=url_for('views.task_progress',tid=task7.id,_external=True),
                   only_mfa=url_for('views.task_progress',tid=task6.id,_external=True),
                   only_advisors=url_for('views.task_progress',tid=task8.id,_external=True))
                  
@views.route('/users/<uniq_id>/devices/<udid>/fetch_carousels/blocking', methods=['GET',])
@print_timing
def get_fetch_carousels_blocking(uniq_id, udid):
    user, device = user_device(uniq_id, udid)
    server = APPLUVR_VIEW_SERVER
    user = uniq_id
    device = udid
    task5 = fetch_my_friends(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    task1 = fetch_recos('apps_for_you',server, user, device, auth_pwd=APPLUVR_PWD,debug=True)
    task2 = fetch_recos('hot_apps',server, user, device, auth_pwd=APPLUVR_PWD,debug=True)
    task3 = fetch_my_apps(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    task4 = fetch_mfa(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    task6 = fetch_only_friends(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    task7 = fetch_only_mfa(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    task8 = fetch_only_advisors(server, user, device, auth_pwd=APPLUVR_PWD, debug=True)
    return jsonify(apps_for_you=task1,
                   hot_apps=task2,
                   my_apps=task3,
                   mfa=task4,
                   mf=task5,
                   only_mf=task6,
                   only_mfa=task7,
                   only_advisors=task8)


@views.route('/progress')
def task_progress():
    task_id = request.args.get('tid')
    return render_template('progress.html', task_id=task_id) if task_id else abort(404)


@views.route('/poll')
def task_poll():
    """Called by the progress page using AJAX to check whether the task is complete."""
    task_id = request.args.get('tid')
    try:
        task = fetch_recos.get_task(task_id)
    except ConnectionError:
        # Return the error message as an HTTP 500 error
        return 'Coult not connect to the task queue. Check to make sure that <strong>redis-server</strong> is running and try again.', 500
    ready = task.return_value is not None if task else None
    return jsonify(ready=ready)


@views.route('/results')
def task_results():
    """When poll_task indicates the task is done, the progress page redirects here using JavaScript."""
    task_id = request.args.get('tid')
    task = fetch_recos.get_task(task_id)
    if not task:
        abort(404)
    result = task.return_value
    if not result:
        return redirect(url_for('views.task_progress',tid=task.id))
    # Need to store the task results
    #task.delete()
    return result
    #return render_template('results.html', value=result)


#--------------------------------------------------------------------------------------#


# About
@views.route('/about', methods=['GET',])
@cache.memoize(60)
def about_platform():
    import platform
    from appluvr_views import __version__
    return jsonify(appluvr=dict(version=str(__version__), routes=repr(current_app.url_map)),python=dict(version=platform.python_version(), implementation=platform.python_implementation()), server=dict(node=platform.node(),version=platform.version()) )


@views.route('/rel/<rel>/<id>/', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
def get_rel_href(rel, id):
    if rel is None or id is None:
        abort(400)
    return url_map(rel, id)

# Echo test
@views.route("/echo/<str>", methods=['GET', 'POST'])
def echo(str):
    return 'Hello %s' % str


'''
@views.route('/test-del-cache/<int:num>', methods=['GET',])
def zdelcache(num):
    cache.delete_memoized(zcache,num)
    return 'Deleted %d' % num
'''

@cache.memoize(60)
def _sub(a, b):
    return a - b - random.randrange(0, 1000)

@views.route('/api/add/<int:a>/<int:b>')
def add(a, b):
    return str(_add(a, b))

@views.route('/api/sub/<int:a>/<int:b>')
def sub(a, b):
    return str(_sub(a, b))

@views.route('/api/cache/delete/<int:a>/<int:b>')
def delete_cache(a, b):
    cache.delete_memoized(_sub, a, b)
    return 'OK'

def get_friends_apps(friend,ios_apps,android_apps,ios_apps_ts,android_apps_ts):
    if friend:
        for x in dict(friend.apps()).values():
            for y in x:
                if y.isdigit():
                    ios_apps.append(y)
                else:
                    android_apps.append(y)

        for x in dict(friend.apps_ts()).values():
            for y in x:
                if y.get('package_name').isdigit():
                    ios_apps_ts.append(y)
                else:
                    android_apps_ts.append(y)
    return [ios_apps,android_apps,ios_apps_ts,android_apps_ts]

def get_mapping_apps(pkg_list,friends_apps):
    if len(pkg_list)>0:
        pkg=','.join(pkg_list)
        data=get_xmap_results_from_server(pkg)
        if data:
            [friends_apps.append((x.get('itunesID',None),x.get('androidPackageName',None)))for x in data]
        else:
            current_app.logger.debug('no android equivalent found for ios App:')
    return friends_apps

@views.route('/apps/summary/', methods=['GET','POST'])
@support_jsonp
@support_etags
@requires_auth
def get_v3_app_summary_bulk():
    #d(request.args)
    if request.method == 'POST':
        pkgs = request.form.get('ids', None)
        platform_via_get = request.args.get('platform',None)
        if platform_via_get:
            platform = platform_via_get  
        else: 
            platform = request.form.get('platform','android')
    else:
        pkgs = request.args.get('ids', None)
        platform = request.args.get('platform','android') 
    if not pkgs:
        return make_400({'ids':['Unable to lookup details about the package provided. Please check the package id to ensure it is correct. Multiple package names need to be in a comma separated list']})
    #d(APPO_URL+'apps/details?ids='+pkgs+'&summary=true')
    pkg_list = pkgs.split(',')
    (android_pkgs,ios_pkgs) = app_separation(pkg_list)
    if platform == 'ios':
        if len(android_pkgs)>0:           
            pkg=','.join(android_pkgs)
            data=get_xmap_results_from_server(pkg)
            if data:
                apk = [x.get('itunesID',None) for x in data]
                pkg_list = list(set(apk + ios_pkgs))
                pkgs = ','.join(pkg_list)
            else:
                pkgs = ','.join(ios_pkgs)
    else:
        if len(ios_pkgs)>0:
            pkg=','.join(ios_pkgs)
            data=get_xmap_results_from_server(pkg)
            if data:
                apk = [x.get('androidPackageName',None) for x in data]
                pkg_list = list(set(apk + android_pkgs))
                pkgs = ','.join(pkg_list)
            else:
                pkgs = ','.join(android_pkgs)

    #current_app.logger.debug("final list of pkgs %s"%pkgs)
    #end of X-Platform Mapping
    #url = '%s%s%s%s&platform=%s' % (APPO_URL, 'apps/details?ids=', pkgs, '&summary=true',platform)
    #r = requests.get(url, auth=APPO_BASIC_AUTH)
    appo_status_code, appo_content = get_appo_summary_view(APPO_URL,'apps/details?', pkgs, 'summary=true', platform )
    
    if appo_content == '{}':
        abort(404)
    if platform == 'ios':
        output= itunesid_to_packagename(appo_content)
    else:
        output = appo_content
    return output, appo_status_code

@cache.memoize(3600)
def get_appo_summary_view(APPO_URL,url ,pkgs,summary,platform):
    payload = {'ids': pkgs}
    url = '%s%s%s&platform=%s' % (APPO_URL, url, summary,platform)
    r = requests.post(url, auth=APPO_BASIC_AUTH,data=payload)
    return r.status_code, r.content

@views.route('/apps/<pkg>/details', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
def get_v3_app_details(pkg):
    platform = request.args.get('platform','android')
    return get_appo_app_details(pkg,platform.encode('ascii'))

#@cache.memoize(FULL_DAY)
def get_appo_app_details(pkg=None,platform=None):
    if not pkg:
        return make_400({'pkg':['Unable to lookup details about the package provided. Please check the package id to ensure it is correct.']})
    if platform == 'android' and not verify_package(pkg):
        return make_400({'pkg':['Not a valid java package name. Please check the package name and try again.']})
    if platform == 'ios' and not pkg.isdigit():
        return make_400({'pkg':['Not a valid itunes id . Please check the app\'s itunes id and try again.']})
    appo_status_code, appo_content = get_appo_summary_view(APPO_URL,'apps/details?', pkg, '', platform )
    if appo_content == '{}':
        abort(404)
    if appo_status_code == 200:
        if platform == 'android':
            return jsonify(json.loads(appo_content).get(pkg,{}))
        elif platform =='ios':
            content = itunesid_to_packagename(json.loads(appo_content).get(pkg,{}))
            return jsonify(content)
    return appo_content, appo_status_code



#@routes.route('/apps/search', methods=['GET',])
@views.route('/users/<uniq_id>/devices/<udid>/apps/search', methods=['GET',])
@print_timing
@requires_auth
def get_search_results(uniq_id, udid,platform='android'):
    user, device = user_device(uniq_id, udid)
    #adding utf-8 encode since search strings with unicode like Über were throwing errors
    req_args = dict([(k.encode('utf-8'), v.encode('utf-8')) for k, v in request.args.items()])
    query = urllib.urlencode(req_args)
    max_size = carousel_setting().get('Search Carousel Apps')
    odp_installed = user.odp_installed() if user else False
    # Binary flag for Appo
    odp_installed = '1' if odp_installed else '0'
    appo_id = user.safe_serialize_appo_id() if user else None
    d('%s%s?%s&uid=%s&max_size=%s&odp_installed=%s' % (APPO_URL,APPO_SEARCHES,query,appo_id,max_size,odp_installed))
    r = requests.get(APPO_URL+APPO_SEARCHES+'?'+query, params=dict(uid=appo_id,max_size=max_size,odp_installed=odp_installed),auth=APPO_BASIC_AUTH)
    assert(r.content)
    if r.status_code == 200:
        results = json.loads(r.content).get('apps', None)
        return jsonify(data=results, count=len(results))
    else:
        return r.content, r.status_code

@views.route('/device/<model>/<number>/details/', methods=['GET',])
@views.route('/device/<model>/<number>/<make>/details/', methods=['GET',])
#@cache.memoize(3600)
#@requires_auth
def fetch_ddb_details(model,number,make=None):
    if (model and number):
        if make == "Apple":
            dev_image = 'http://ddbservice.herokuapp.com/static/images/iphone-generic.png'
        else:
            dev_image = 'http://ddbservice.herokuapp.com/static/images/default_phone.png'
        ddb_target='http://vzw.appluvr.com/ddb/api/1.0/device/get/%s/%s/' % (model,number)
        r_dev_image = requests.get(ddb_target)
        dev_is_tablet=False
        dev_marketing_name=None
        if r_dev_image.status_code is 200:
            r_dev_results = json.loads(r_dev_image.content)
            if r_dev_results.has_key('rows') and len(r_dev_results.get('rows'))>0:
                queryrow = len(r_dev_results['rows']) - 1
                if 'marketing_name' in r_dev_results['rows'][queryrow]:
                    dev_marketing_name = r_dev_results['rows'][queryrow].get('marketing_name')
                else:
                    dev_marketing_name = None
                if 'is_tablet' in r_dev_results['rows'][queryrow]:
                    dev_is_tablet  = r_dev_results['rows'][queryrow].get('is_tablet')
                else:
                    dev_is_tablet = False
                if 'image' in r_dev_results['rows'][queryrow]:
                    dev_image = r_dev_results['rows'][queryrow].get('image')
                else:
                    if dev_is_tablet:
                        dev_image = 'http://ddbservice.herokuapp.com/static/images/default_tablet.png'
                    elif make == "Apple":
                        dev_image = 'http://ddbservice.herokuapp.com/static/images/iphone-generic.png'
                    else:
                        dev_image = 'http://ddbservice.herokuapp.com/static/images/default_phone.png'
        else:
            current_app.logger.debug("No device are present")
        dev_profiles=dict(device_image_url=dev_image,device_isTablet=dev_is_tablet,device_marketing_name=dev_marketing_name)
        return jsonify(dev_profiles)
    else:
        return make_400('Invalid parameters. Please refer to the documentation')

# API to get the apps to share. 
@views.route('/user/<uid>/device/<uuid>/fb/share', methods=['GET',])
def get_fb_apps2share(uid,uuid):
    results = fetch_appdetails_for_fb_share(APPLUVR_VIEW_SERVER, uid, uuid)
    if results:
        return jsonify(json.loads(results))
    else:
        return make_400('Invalid user or device')

# API to share the apps on FB
@views.route('/user/<uid>/device/<uuid>/fb/share', methods=['POST',])
def set_fb_apps2share(uid,uuid):
    #Share the status to facebook
    #Save shared apps to user's device
    args = MultiDict(request.json) if request.json else request.form
    req = json.loads(args.get("data"))
    '''if not form.validate_on_submit():
        return make_400(form.errors)
    if request.form:
        req = request.form
    else: 
        return make_400('Invalid parameters. Please refer to the documentation')'''
    result = share_iosapps2fb(APPLUVR_VIEW_SERVER, uid, uuid, req)
    return result

@views.route('/user/<uid>/device/<uuid>/fb/share/status', methods=['GET',])
def get_fb_sharestatus(uid,uuid):  
    device_obj = Device.load(uuid)
    if not device_obj:
        return make_400('Invalid user or device')
    else:
        results = {'fb_share':device_obj.apps_fb_share_status}
        return json.dumps(results)

@views.route('/getattsub/',methods=['GET',])
def get_att_subid():
    att_subid = request.headers.get('x-up-subno',None)
    if att_subid:
        return hashlib.md5(att_subid).hexdigest()
    return ''
   
# App X-Map routine
#@cache.memoize(FULL_DAY)
def get_xmap_results_from_server(pkgs):
    xmap_server = "http://vzw.appluvr.com/xmap/"
    if pkgs :
        payload = {"pkgs": pkgs}
        url = '%sapi/1.0/getxmapby/combined/'% (xmap_server)
        r = requests.post(url,data=payload)
        if r.status_code == 200:
            data=json.loads(r.content).get('results',None)
            return data
        else:
            return []
    else:
        return []


@views.route('/notifications/afy', methods=['GET',])
def push_notifications_for__afy():
    a = send_afy_notification()
    return a

@views.route('/notifications/lev_tag_afy', methods=['GET',])
def push_lev_tag_notification():
    a = test_lev_tag_notification()
    return a

@views.route('/user/<uid>/device/<uuid>/app/<pkg>/installed', methods=['GET',])
def get_app_installed_status(uid,uuid,pkg):
    user = User.load(uid)
    device = Device.load(uuid)
    if user is None or device is None:
        abort(404)
    else:
        apps_installed_ts = device.apps_installed
        if pkg in apps_installed_ts:
            return jsonify(installed=True)
        else:
            return jsonify(installed=False)

@views.route('/users/<uid>/fb/friends/all', methods=['GET',])
def get_user_fb_friends_raw(uid):
    user = User.load(uid)
    if user:
        fb_status, fb_content = user.fb_fetch_friends(pic=True)
        return fb_content
    return jsonify(data=[])


@views.route('/users/<id>/fb/friends/invite', methods=['GET',])
@requires_auth
def get_fb_frinds_invite(id):
    user = User.load(id)
    if user is None:
        abort(404)
    appluvr_filter = False if (request.args.get('appluvr_filter', 'False') == 'False' or  request.args.get('appluvr_filter', 'False') == 'false') else True
    return send_friends_invitation(APPLUVR_VIEW_SERVER,id, appluvr_filter)


def encodeparamsmix(userid, platform, appid, type):
    user = User.load(userid)
    if user is None:
        abort(404)
    if appid and platform and userid and type:
        if type == 'download':
            appluvr_download_params = {'user':userid,'platform':platform}
            encoded_url = base64.urlsafe_b64encode(json.dumps(appluvr_download_params).encode("utf-8"))
            share_url = current_app.config['SHARE_WEB_URL_PREFIX']
            appluvr_download_url = '%s%s/%s' % (share_url, type, encoded_url)
            gURL_json = json.dumps({'longUrl': appluvr_download_url})
            r = requests.post('https://www.googleapis.com/urlshortener/v1/url', gURL_json, headers={'Content-Type': 'application/json'})
            if r.status_code == 200:
                appluvr_download_url = r.json['id']
            return appluvr_download_url 
        else:
            paramsdict = {'pack_id':appid,'platform':platform,'user':userid}
            encoded_url = base64.urlsafe_b64encode(json.dumps(paramsdict).encode("utf-8"))
            share_url = current_app.config['SHARE_WEB_URL_PREFIX']
            final_share_url = '%s%s/%s' % (share_url, type, encoded_url)
            gURL_json = json.dumps({'longUrl': final_share_url})
            r = requests.post('https://www.googleapis.com/urlshortener/v1/url', gURL_json, headers={'Content-Type': 'application/json'})
            if r.status_code == 200:
                final_share_url = r.json['id']
            return final_share_url  


@views.route('/users/<userid>/<platform>/<type>/<appid>', methods=['GET',])
@views.route('/users/<userid>/getshareurl/<platform>/<type>/<appid>', methods=['GET',])
@views.route('/users/<userid>/getshareurl/<platform>/<type>', methods=['GET',])
@requires_auth
def get_share_web_url_data(userid, platform, type, appid=None):
    user = User.load(userid)
    share_url_data=''
    if user is None:
        abort(404)
    if type == 'app':
        share_url_data = encodeparamsmix(userid, platform, appid, type)
        return share_url_data
    elif type == 'mix':
        share_url_data = encodeparamsmix(userid, platform, appid, type)
        return share_url_data
    elif type == 'download':
        share_url_data = encodeparamsmix(userid, platform, 'com.appluvr.verizon', type)
        return share_url_data
    else:
        return None

       
 
@views.route('/', defaults={'path': ''})
@views.route('/<path:path>')
def catch_all(path):
    return 'The resource you are trying to access at path: %s is not available.' % path
#--------------------------------------------------------------------------------------#
