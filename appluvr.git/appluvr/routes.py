# -*- coding: utf-8 -*-
"""
Core REST API of Appluvr

"""
import os
from appluvr_views.extensions import cache, appocatalog
from workers.build_card_views import  fetch_app_card, fetch_friend_card
from workers.build_carousel_views import fetch_appo_data, fetch_recommended_apps, fetch_only_mfa, fetch_my_apps,fetch_only_friends
from appluvr_views.views import cache_invalidations,get_user_fb_profile, get_only_new_friends_notification,get_only_new_friends_apps_notification,get_user_profile, get_cached_user_all_my_apps,get_user_device_carrier_platform,get_user_fb_friends,get_user_friends_apps,get_user_fb_pic,get_cached_user_only_friends_recent,get_cached_user_only_friends_apps,get_all_user_comments,get_user_apps_friends_in_common_comments,get_user_apps_friends_in_common_likes
from appluvr import d, couch, couchdb
from functools import wraps
from flask import Flask, abort, jsonify, request, json, render_template, flash, g, url_for, redirect, current_app, Response, Blueprint
from flaskext.couchdbkit import *
from werkzeug.datastructures import MultiDict
import os, sys, time, string, re, gzip
import urllib
import requests
import urlparse
#from promo import inject_promos
from ordereddict import OrderedDict
from httplib import HTTPSConnection

from appluvr.prefix import *
from appluvr.models.user import *
from appluvr.models.device import *
from appluvr.models.app import *
from appluvr.models.settings import *
from appluvr.models.interest import *
from appluvr.models.comment import *
from appluvr.models.app_packs import *
from appluvr.models.deal import *
from appluvr.models.notifications import *
from appluvr.models.widget import *
from appluvr.models.couch_update import *
from appluvr.models.facebook import FacebookLoginForm
from appluvr.utils.Counter import Counter
from appluvr.utils.misc import *
from random_names import roulette
import grequests

from uuid import uuid4
from hashlib import md5
import hashlib
from operator import itemgetter
from indextank.client import ApiClient
import datetime
import calendar
from redis import Redis
import arrow

routes = Blueprint('routes', __name__, template_folder='templates')

# Adding a proxy for backward compatibility with the older ORM
couch = couchdb.db
couch.delete = couch.delete_doc


auth_user = 'tablet'
auth_pwd = os.environ.get('APPLUVR_PWD', 'aspirin')
APPLUVR_VIEW_SERVER = os.environ.get('APPLUVR_VIEW_SERVER', 'http://localhost:5000/v5-cache/')

@cache.memoize(FULL_DAY)
def carousel_setting():
    ret = Settings.load('carousel_settings')
    if ret:
        cms_setting = simplejson.loads(ret.toDict().get('value','{}'))
    else:
        cms_setting = {}
    d(cms_setting)
    retval = default_carousel_settings
    retval.update(cms_setting)
    d(retval)
    return retval.get('CarouselSettings')

#-------------------------------------------------------------------------------#

@routes.before_request
def before_request():
    if current_app.config['TESTING'] == True:
        d(request)
    pass


@routes.after_request
def after_request(response):
    if current_app.config['TESTING'] == True:
        d(str(response) + "\n")
    return response

'''
@routes.errorhandler(500)
def not_found(error):
    return current_app.make_response(('Oops, we are unable to process your request. Please try again later.', 500))
'''

@routes.errorhandler(404)
def not_found(error):
    return current_app.make_response(('Object not found', 404))

@routes.errorhandler(400)
def bad_found(error):
    return current_app.make_response(('Bad request. Please refer to the API documentation for details on the expected parameters.', 400))

@routes.errorhandler(401)
def not_permitted(error):
    return current_app.make_response(('The server could not verify that you are authorized to access the resource you requested. In case you may have supplied the wrong credentials, please check your user-id and password and try again.', 401))


#--------------------------------------------------------------------------------------#

def requires_user(f):
    """ Decorator for validating user exists """
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = kwargs.get('uniq_id')
        user = User.load(user_id)
        if user is None:
            abort(404)
        else:
            return f(*args, **kwargs)
        return decorated

def user_device(uniq_id, udid):
    user = User.load(uniq_id)
    device = Device.load(udid)
    if user is None or device is None:
        abort(404)
    else:
        return user, device

#--------------------------------------------------------------------------------------#

@routes.route('/att/widget/all', methods=['GET',])
@support_jsonp
@support_etags
def get_all_att_widget():
    return jsonify(data=sorted([widget.toDict() for widget in AttWidget.view('widgets/att_widget')],key = itemgetter('priority')))

@routes.route('/att/widget/active', methods=['GET',])
@support_jsonp
@support_etags
def get_active_att_widget():
    return jsonify(data=sorted([widget.toDict() for widget in AttWidget.view('widgets/active_att_widget')], key = itemgetter('priority')))

@routes.route('/att/widget/<id>', methods=['GET',])
@support_jsonp
@support_etags
@cache.memoize(60)
def get_att_widget(id):
    widget = AttWidget.load(id)
    if not widget:
        return abort(404)
    return jsonify(widget.toDict())


@routes.route('/att/widget/create', methods=['POST',])
@routes.route('/att/widget/<id>/update', methods=['PUT',])
@requires_auth
def create_widget(id=None):
    widget = None    
    args = MultiDict(request.json) if request.json else request.form
    form = AttWidgetCreateForm(args) if request.method == 'POST' else AttWidgetUpdateForm(args)
    # If the params arent validated right, bail out
    if not form.validate_on_submit():
        return make_400(form.errors)
    if id is None and request.method == "PUT":
        abort(404)
    if id is not None:
        widget= AttWidget.load(id) 
    apps = []  
    if args.get('widget_type')  == 'billboard':       
        apps = [dict(pkg =  app.get('pkg'), appname = app.get('appname'), image_url = app.get('image_url'))for app in json.loads(args.get('app_data'))]
    else:
        apps = [dict(pkg =  app.get('pkg'), appname = app.get('appname'))for app in json.loads(args.get('app_data'))]
    # Create or update?
    if request.method == 'POST':   
    # create new app pack
        if args.get('widget_type')  == 'group' or args.get('widget_type')  == 'banner':
            widget = AttWidget(widget_type = form.widget_type.data, promo_copy = form.promo_copy.data, priority = form.priority.data, app_data = apps, widget_status = form.widget_status.data)
        else:
            widget = AttWidget(widget_type = form.widget_type.data, priority = form.priority.data, app_data = apps, widget_status = form.widget_status.data)
    else:
        # If its a 'PUT', just make sure it exists
        if not widget:
            abort(404) 
        else:
            # Update fields
            for key in args:                       
                if key == 'app_data': 
                    widget['app_data'] = apps
                else:                
                    widget[key] = args[key]   
    widget.update()                 
    response = current_app.make_response(jsonify(_id=str(widget._id)))
    response.status_code = 201      
    response.headers['Location']=url_for('.get_all_att_widget', _id=widget._id, _external=True)
    if request.method == 'PUT':
        pass
        #cache.delete_memoized(get_all_att_widget,_id=widget._id)
    #cache.delete_memoized(get_all_att_widget)
    return response  


@routes.route('/att/widget/<id>', methods=['DELETE',])
def delete_att_widget(id):
    if id == None:
        abort(400)
    widget = AttWidget.load(id)
    if not widget:
        abort(404)
    couch.delete(widget)
    response = current_app.make_response(jsonify(id=id))
    response.status_code = 204
    #cache.delete_memoized(get_att_widget,id=id)
    return response  

#--------------------------------------------------------------------------------------#

@routes.route('/onlymf/notifications', methods=['GET',])
@support_jsonp
@support_etags
def get_friend_notification():
    return jsonify(data=[notification.toDict() for notification in MfNotification.view('notification/mf_notification')])

@routes.route('/onlymfa/notifications', methods=['GET',])
@support_jsonp
@support_etags
def get_friend_apps_notification():
    return jsonify(data=[notification.toDict() for notification in MfaNotification.view('notification/mfa_notification')])

#--------------------------------------------------------------------------------------#
@routes.route('/deals/seen', methods = ['GET',])
@support_jsonp
@support_etags
def get_user_seen_deal():
    return jsonify(data=[seendeal.deal_seen_toDict() for seendeal in UserSeenDeal.view('user/deal_by_user')])

@routes.route('/users/<uniq_id>/devices/<udid>/deals/seen/create', methods=['POST', 'PUT'])
@support_jsonp
@support_etags
def create_seen_deal(uniq_id = None, udid = None):
    dealseen = None  
    if not (uniq_id and udid) :
        abort(404)
          
    args = MultiDict(request.json) if request.json else request.form
    form = UserSeenDealCreateForm(args) if request.method == 'POST' else UserSeenDealUpdateForm(args)
    # If the params arent validated right, bail out
    if not form.validate_on_submit():
        return make_400(form.errors)
    if uniq_id is None and request.method == "PUT":
        abort(404)
    if uniq_id is not None:
        dealseen = UserSeenDeal.load("deal."+uniq_id)
    
    # Create or update? 
    seen_deals = [deal for deal in json.loads(args.get('seen_deal'))] 
    if request.method == 'POST':   
    # create new app pack
        if dealseen:
            return make_409(uniq_id)
        dealseen = UserSeenDeal(uniq_id = form.uniq_id.data, seen_deal = seen_deals)
        dealseen._id = "deal."+uniq_id
    else:
        # If its a 'PUT', just make sure it exists
        if not dealseen:
            abort(404) 
        else:
            # Update fields
            for key in args:
                if key == 'seen_deal':
                    dealseen['seen_deal'] = seen_deals
                else:
                    dealseen[key] = args[key]  

    dealseen.update() 
    response = current_app.make_response(jsonify(_id=str(dealseen._id)))
    response.status_code = 201   
    return response


#--------------------------------------------------------------------------------------#
@routes.route('/interest/negative', methods=['GET',])
@support_jsonp
@support_etags
def get_negative_interests():
    return jsonify(data=[neg_interest.negative_interests_toDict() for neg_interest in UserNegativeInterests.view('user/negative_interests')])

@routes.route('/users/<uniq_id>/devices/<udid>/interest/negative', methods=['GET',])
@support_jsonp
@support_etags
def get_users_negative_interests(uniq_id = None, udid = None):
    if not uniq_id :
        abort(404)
    NegInterests = UserNegativeInterests.load("NegInterests."+uniq_id)
    if not NegInterests:
        abort(404)
    return jsonify(NegInterests.negative_interests_toDict())

@routes.route('/users/<uniq_id>/devices/<udid>/interest/negative', methods=['POST', 'PUT'])
@support_jsonp
@support_etags
def create_users_negative_interests(uniq_id = None, udid = None):
    NegInterests = None  
    if not (uniq_id and udid) :
        abort(404)
          
    args = MultiDict(request.json) if request.json else request.form
    form = UserNegativeInterestsCreateForm(args) if request.method == 'POST' else UserNegativeInterestsUpdateForm(args)
    # If the params arent validated right, bail out
    if not form.validate_on_submit():
        return make_400(form.errors)
    if uniq_id is None and request.method == "PUT":
        abort(404)
    if uniq_id is not None:
        NegInterests = UserNegativeInterests.load("NegInterests."+uniq_id)
    
    # Create or update?
    neg_interests = []
    interests = args.get('negative_interests')
    if interests:        
        neg_interests = [interest for interest in json.loads(interests)] 
    if request.method == 'POST':   
    # create new app pack
        if NegInterests:
            return make_409(uniq_id)
        NegInterests = UserNegativeInterests(uniq_id = form.uniq_id.data, negative_interests = neg_interests)
        NegInterests._id = "NegInterests."+uniq_id
    else:
        # If its a 'PUT', just make sure it exists
        if not NegInterests:
            abort(404) 
        else:
            # Update fields
            for key in args:
                if key == 'negative_interests':
                    NegInterests['negative_interests'] = neg_interests
                else:
                    NegInterests[key] = args[key]  

    NegInterests.update()      
    response = current_app.make_response(jsonify(_id=str(NegInterests._id)))
    response.status_code = 201      
    response.headers['Location']=url_for('.get_negative_interests', _external=True)
    if request.method == 'PUT':
        pass
        #cache.delete_memoized(get_negative_interests)
    #cache.delete_memoized(get_negative_interests)
    return response

@routes.route('/users/<id>/devices/<udid>/interest/negative/remove', methods = ['POST','PUT'])
@support_jsonp
@support_etags
def delete_user_negative_interests(id = None,udid = None):

    name = request.args.get('name',None)       
    user, device = user_device(id, udid)
    NegInterests = UserNegativeInterests.load("NegInterests."+id)
    if not NegInterests: 
        abort(404)

    if not name:
        couch.delete(NegInterests)
        response = current_app.make_response(jsonify(_id=NegInterests._id))
        response.status_code = 204      
        return response

    if name in NegInterests.negative_interests:
        NegInterests.negative_interests.remove(name)

    NegInterests.update()    
    response = current_app.make_response(jsonify(NegInterests.negative_interests_toDict()))   
    return response

#--------------------------------------------------------------------------------------#

@routes.route('/update/couch/', methods=['POST',])
@requires_auth
def update_couch_duplicate_users():
    """
    remove duplicate users from database.
    """   
    unfriend_users_list = []
    deleted_user_docs = []
    deleted_device_docs = []
    commented_app_docs = []
    deleted_comment_docs = []
    deleted_neg_interests_docs = []  
    all_friends_rated_apps = []
    updated_app_docs = []    

    args = MultiDict(request.json) if request.json else request.form   
    form = UpdateCouchCreateForm(args)
    if request.method == 'POST':
        if not form.validate_on_submit():    
            return make_400(form.errors)

        unfriend_requests_list = [req_email for req_email in json.loads(args.get('emails'))]  
        loggen_in_users_docs=[user.toDict() for user in User.view('user/LoggedIn')]
        [unfriend_users_list.append(doc.get('_id')) for doc in loggen_in_users_docs if  doc.get('email') in unfriend_requests_list]

    for user_id in unfriend_users_list:
        freed_memory_allocation = clear_cache_on_delete(user_id)
        current_app.logger.debug('cleared all cache memory for the user.')

        user = User.load(user_id)  
        #get user commented app doc
        keys=[]
        keys.append(user_id)
        rows = Comment.view('comment/user_comments', keys=keys)
        comments = [comment.toDict() for comment in rows]
        [commented_app_docs.append(doc_id.get('_id')) for doc_id in comments] 

        #delete negattive interests doc from couch here.
        NegInterests = UserNegativeInterests.load("NegInterests."+user_id)
        if NegInterests is not None:
            try:
                couch.delete(NegInterests)  
                deleted_neg_interests_docs.append(NegInterests._id) 
            except:
                current_app.logger.debug('Couch Delete Exception Caught For Negative Interests: %s' %NegInterests._id)

        #get user doc and delete from couch           
        if user is not None:
            udid = ''.join([link['href'] for link in user.links if link['rel'] == 'device'])
            try:
                couch.delete(user)
                deleted_user_docs.append(user._id)
            except:
                current_app.logger.debug('Couch Delete Exception Caught For User: %s' %user._id)            

            #get device doc and delete from couch 
            device = Device.load(udid)
            if device is not None:   
                try:     
                    couch.delete(device)  
                    deleted_device_docs.append(device._id) 
                except:
                    current_app.logger.debug('Couch Delete Exception Caught For Device: %s' %device._id)
            else:
                pass

            #get all users app ratings from couch.
            all_friends_rated_apps = user.apps_liked+user.apps_disliked

        #delete all users rated app doc from couch.    
        if len(all_friends_rated_apps)>0 :   
            for pkg in all_friends_rated_apps:
                app_doc = App.load(pkg)            
                if app_doc is not None: 
                    app_likers = app_doc.liked
                    app_dislikers = app_doc.disliked       
                    if user_id in app_doc.liked:                                      
                        app_likers.remove(user_id)                                      
                    elif user_id in app_doc.disliked:                                        
                        app_dislikers.remove(user_id)                                  
                    
                    app_doc.liked = app_likers
                    app_doc.disliked = app_dislikers
                    try:                        
                        app_doc.update()
                        updated_app_docs.append(app_doc._id)
                    except:
                        current_app.logger.debug('Couch Update Exception Caught For Apps : %s' %app_doc._id)

    #delete commented app from couch go here.  
    if len(commented_app_docs)>0:
        for doc in commented_app_docs:
            comment = Comment.load(doc)
            if comment is not None:
                try:
                    couch.delete(comment)
                    deleted_comment_docs.append(comment._id)
                except:
                    current_app.logger.debug('Couch Delete Exception Caught For Comments -: %s' %comment._id)
            else:
                pass         
    
    current_app.logger.debug("successfully cleaned up invalid user documents.")
    return jsonify(_delated_user_docs = deleted_user_docs, _delated_device_docs = deleted_device_docs, _deleted_neg_interests_docs = deleted_neg_interests_docs, _deleted_comment_docs = deleted_comment_docs, _updated_app_docs = updated_app_docs)

def clear_cache_on_delete(uniq_id):
    user = User.load(uniq_id)
    if user is None:
        return jsonify(status=True) 

    # get user commented apps
    keys=[]
    keys.append(uniq_id)
    rows = Comment.view('comment/user_comments', keys=keys)
    comments = [comment.toDict() for comment in rows]
    user_commented_apps = [each.get('pkg').encode('ascii') for each in comments]
    
    usrplatform, usrcarrier = get_user_device_carrier_platform(user)
    device = ','.join([link['href'] for link in user.links if link['rel'] == 'device'])     

    apps = user.apps_liked + user.apps_disliked + user_commented_apps
    app_card_invalidating_apps = list(set(apps))

    cache.delete_memoized(get_cached_user_only_friends_recent, uniq_id, 'True')
    cache.delete_memoized(get_cached_user_only_friends_recent, uniq_id, 'False') 
    cache.delete_memoized(get_cached_user_only_friends_apps, uniq_id, usrplatform)   
    cache.delete_memoized(get_only_new_friends_apps_notification, uniq_id, unicode(device))      
    cache.delete_memoized(get_only_new_friends_notification, uniq_id, unicode(device))    
    cache.delete_memoized(get_cached_user_all_my_apps, uniq_id, platform=usrplatform)
    cache.delete_memoized(get_user_fb_pic,uniq_id)        
    cache.delete_memoized(get_user_fb_profile, uniq_id)  
    cache.delete_memoized(get_all_user_comments, uniq_id)
    cache.delete_memoized(get_user_apps, uniq_id)
    cache.delete_memoized(get_user_profile, uniq_id)   
    #invalidate my_apps , only_mfa, only_mf carousel on logout
    #current_app.logger.debug("@@@@@@@@@%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
    cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=False, platform=usrplatform)
    cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=True, platform=usrplatform)
    cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, block=False, debug=False)
    cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, block=True, debug=True)
    
    #current_app.logger.debug("%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    #invalidate friend card details without platform as part of url.
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=usrplatform)
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=usrplatform)
    
    #invalidate app card cache on logout. 
    #current_app.logger.debug("===========>apps for app card invalidations : %s  : <=========="%(app_card_invalidating_apps))   
    for pkg in app_card_invalidating_apps:       
        cache.delete_memoized(get_user_app_like, uniq_id, unicode(pkg))        
        cache.delete_memoized(get_user_apps_friends_in_common_likes, uniq_id, unicode(pkg))
        cache.delete_memoized(get_user_app_dislike, uniq_id, unicode(pkg))
        cache.delete_memoized(get_user_app_comment, uniq_id, unicode(pkg))        
        cache.delete_memoized(get_user_apps_friends_in_common_comments, uniq_id, unicode(pkg))     
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), unicode(pkg), auth_pwd=auth_pwd, debug=False)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), unicode(pkg), auth_pwd=auth_pwd, debug=True)

    all_appuvr_fb_friends = user.fb_friends()
    for userid in all_appuvr_fb_friends:
        friend_obj = User.load(userid)
        if friend_obj is not None:
            friendudid = ','.join( [link['href'] for link in friend_obj.links if link['rel'] == 'device'] )          
            platform, carrier = get_user_device_carrier_platform(friend_obj) 

            frienddeviceobj= Device.load(friendudid)
            if not frienddeviceobj:
                friends_apps = []
            else:
                friends_apps = frienddeviceobj.apps_installed

            # get user commented apps
            keys1=[]
            keys1.append(userid)
            rows = Comment.view('comment/user_comments', keys=keys1)
            friends_comments = [comment.toDict() for comment in rows]
            friends_commented_apps = [each.get('pkg').encode('ascii') for each in friends_comments]
            # user liked and disliked apps.    
            apps = friend_obj.apps_liked + friend_obj.apps_disliked + friends_commented_apps + friends_apps            
            friends_app_card_invalidating_apps = list(set(apps))                           
                         
            cache.delete_memoized(get_cached_user_only_friends_apps, unicode(userid), platform)  
            cache.delete_memoized(get_cached_user_only_friends_recent, unicode(userid), 'True')
            cache.delete_memoized(get_cached_user_only_friends_recent, unicode(userid), 'False') 
            cache.delete_memoized(get_all_user_comments, unicode(userid))      

            #on user logout invalidate friends only_mf and only_mfa carousels.            
            cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
            cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
            cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, block=False, debug=False)
            cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, block=True, debug=True)
            #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform,userid)) 
                           
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
            #invalidate friend card details without platform as part of url.
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=platform)
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=platform)
            #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,userid,auth_pwd,usrplatform,uniq_id))
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
            #invalidate friend card details without platform as part of url.
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=platform)
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=platform)
            
            #invalidate app card cache on logout. 
            #current_app.logger.debug("===========>apps for app card invalidations : %s  : <=========="%(friends_app_card_invalidating_apps))   
            for pkg in friends_app_card_invalidating_apps:      
                cache.delete_memoized(get_user_apps_friends_in_common_likes, unicode(userid), unicode(pkg))             
                cache.delete_memoized(get_user_apps_friends_in_common_comments, unicode(userid), unicode(pkg))
                cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), unicode(pkg), auth_pwd=auth_pwd, debug=False)
                cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), unicode(pkg), auth_pwd=auth_pwd, debug=True)
            keys1 = []

    current_app.logger.debug("@@@@@ successfully invalidated %s's friends apps cache  " %uniq_id)
    return jsonify(status=True)  

#--------------------------------------------------------------------------------------#
@routes.route('/subid/get/all', methods=['GET',])
@support_jsonp
@support_etags
@cache.memoize(60)
def get_all_subid_doc():
    return jsonify(data=[subid.toDict() for subid in Device.view('device/att_subid_devices')])

@routes.route('/app_packs/get/all', methods=['GET',])
@support_jsonp
@support_etags
@cache.memoize(60)
def get_all_packs():
    return jsonify(app_packs=[app.toDict() for app in Packages.view('app_packs/app_pack')])

@routes.route('/app_packs/get/active', methods=['GET',])
@support_jsonp
@support_etags
@cache.memoize(60)
def get_all_active_packs():
    return jsonify(app_packs=[app.toDict() for app in Packages.view('app_packs/active_app_packs')])

@routes.route('/app_packs/get/inactive', methods=['GET',])
@support_jsonp
@support_etags
@cache.memoize(60)
def get_all_inactive_packs():
    return jsonify(app_packs=[app.toDict() for app in Packages.view('app_packs/inactive_app_packs')])
    
@routes.route('/app_packs/get/<app_id>', methods=['GET',])
@support_jsonp
@support_etags
@cache.memoize(60)
def get_app_pack(app_id):
    packages = Packages.load(app_id)
    if not packages:
        return abort(404)
    return jsonify(packages.toDict())


@routes.route('/app_packs/<app_id>', methods=['DELETE',])
def delete_app_pack(app_id):
    
    mixes_endpoint,mixes_index = app_pack_index_config()
    api = ApiClient(mixes_endpoint)
    index = api.get_index(mixes_index)
    if app_id == None:
        abort(400)
    packages = Packages.load(app_id)
    if not packages:
        abort(404)
    couch.delete(packages)
    docids = [app_id]
    response_index = index.delete_documents(docids)
    response = current_app.make_response(jsonify(app_id=app_id))
    response.status_code = 204
    #cache.delete_memoized(get_app_pack,app_id=app_id)
    return response

@routes.route('/users/<uniq_id>/devices/<udid>/app_pack/<app_id>', methods=['DELETE',])
def delete_app_pack_by_user(uniq_id, udid, app_id):
    users= User.load(uniq_id)
    packages = Packages.load(app_id) 
    if not users:
        abort(404)
    if not packages:
        abort(404)       
    if users.fb_id == packages.fb_id:
        return delete_app_pack(app_id)
    else:
        return abort(403)
        
#===================create app_pack by user.=======================
def get_user_profile_pic(id):
    user = User.load(id)
    if user is None:
        return None
    else:
        token = user.fb_token #get('fb_token',None)
        if token is None:
            return None        
        fml_endpoint = FB_PROFILE_PICTURE+token        
        #current_app.logger.debug('Opening FB HEAD request')
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
            return r.headers.get('location')
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
                return r.headers.get('location')
        # All falls through here
        # Note - not passing back the FB status code
        return None

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

def app_pack_img_genereation(mix_id, pkgs):
    """
    Generate an app_pack_img_url, store generic details and return app_pack_img here.
    """   
    # get 3 pkgs from app_packs.    
    rect_image = pkgs[:3]  
    apppack_rect_img_api = 'http://mix-tile.herokuapp.com/createtileimage/%s/?pkgs=%s'%(mix_id, ','.join(rect_image))
    # get 4 pkgs from app_packs
    square_image = pkgs[:4]
    apppack_img_square_api = 'http://mix-tile.herokuapp.com/createsquaretileimage/%s/?pkgs=%s'%(mix_id, ','.join(square_image))    

    urls = [apppack_rect_img_api, apppack_img_square_api]
    qs = (grequests.get(url, auth=(auth_user,auth_pwd)) for url in urls)
    rs = grequests.map(qs)

    if rs[0].status_code == 200:
        apppack_rect_img_api = rs[0].content
    else:
        apppack_rect_img_api = None

    if rs[1].status_code == 200:
        apppack_img_square_api = rs[1].content 
    else:
        apppack_img_square_api = None

    return apppack_rect_img_api, apppack_img_square_api
        

@routes.route('/users/<uniq_id>/devices/<udid>/app_pack/create', methods=['POST',])
@requires_auth
def create_app_packs_by_user(uniq_id ,udid, app_id=None):
    packages = None    
    args = MultiDict(request.json) if request.json else request.form
    form = PackagesCreateForm(args) if request.method == 'POST' else PackagesUpdateForm(args)
    # If the params arent validated right, bail out
    if not form.validate_on_submit():
        return make_400(form.errors)
    if app_id is None and request.method == "PUT":
        abort(404)   

    created_date = int(time.time()) 
    app_order_int = []
    app_order_string = []
    [app_order_int.append(dict(package_name=app.get('package_name'), comment=app.get('comment'), app_order = int(app.get('app_order'))))if app.get('app_order') is not None and app.get('app_order')!='' else app_order_string.append(app)  for app in json.loads(args.get('apps'))] 
    app_order_int = sorted(app_order_int, key=itemgetter('app_order'))
    apps = app_order_int + app_order_string
    # get all pkgs from app_packs.
    pkgs = [pkg.get('package_name') for pkg in apps]
    # get 3 pkgs from app_packs.
    if len(pkgs)>3:
        pkgs = pkgs[:3]     

    # get_users_fb_profile_pic     
    user_profile_pic =  get_user_profile_pic(uniq_id)
    if user_profile_pic is None:
        user_profile_pic = form.user_picurl.data

    # get generated app_pack_img. 
    app_pack_img = app_pack_img_genereation(user_profile_pic, pkgs)
    if app_pack_img is None:
        app_pack_img = form.apppack_img.data   
    
    # Create or update?
    if request.method == 'POST':   
    # create new app pack
        packages = Packages(user_name = form.user_name.data, fb_id = form.fb_id.data, user_picurl = form.user_picurl.data, apppack_name =form.apppack_name.data, apppack_img = form.apppack_img.data, apppack_description = form.apppack_description.data, apppack_status = form.apppack_status.data, user_bio = form.user_bio.data, apps = apps, apppack_created_date= created_date)
        packages.update()        
        packages= Packages.load(packages._id)      
        if not packages:
            abort(404)
        else:
            # Update fields
            for key in args: 
                if key == 'apps':
                    packages['apps'] = apps  
                elif key == 'user_picurl':
                    packages['user_picurl'] = user_profile_pic 
                elif key == 'apppack_img':
                    packages['apppack_img'] = app_pack_img 
                else:
                    packages[key] = args[key]
            packages.update() 
    create_app_pack_index(app_id = packages._id)            
    response = current_app.make_response(jsonify(app_id=str(packages._id)))
    response.status_code = 201      
    response.headers['Location']=url_for('.get_all_packs', app_id=packages._id, _external=True)
    if request.method == 'PUT':
        pass
        #cache.delete_memoized(get_all_packs,app_id=packages._id)
    #cache.delete_memoized(get_all_packs)
    return response

#==============================End==============================

@routes.route('/app_packs/create', methods=['POST',])
@routes.route('/app_packs/<app_id>', methods=['PUT',])
@requires_auth
def create_app_packs(app_id=None):
    packages = None    
    args = MultiDict(request.json) if request.json else request.form
    form = PackagesCreateForm(args) if request.method == 'POST' else PackagesUpdateForm(args)
    # If the params arent validated right, bail out
    if not form.validate_on_submit():
        return make_400(form.errors)
    if app_id is None and request.method == "PUT":
        abort(404)
    if app_id is not None:
        packages= Packages.load(app_id)

    created_date = int(time.time())
    app_order_int = []
    app_order_string = []
    apps = []
    if args.get('apps'):
        [app_order_int.append(dict(package_name=app.get('package_name'), comment=app.get('comment'), app_order = int(app.get('app_order'))))if app.get('app_order') is not None and app.get('app_order')!='' else app_order_string.append(app)  for app in json.loads(args.get('apps'))] 
        app_order_int = sorted(app_order_int, key=itemgetter('app_order'))
        apps = app_order_int + app_order_string 

    pkgs = [pkg.get('package_name') for pkg in apps]
  
    # Create or update?
    if request.method == 'POST':   
    # create new app pack        
        if packages:
            return make_409(uniq_id)            
        packages = Packages(user_name = form.user_name.data, fb_id = form.fb_id.data, user_picurl = form.user_picurl.data, apppack_name =form.apppack_name.data, apppack_description = form.apppack_description.data, apppack_status = 'inactive', user_bio = form.user_bio.data, apps = apps, apppack_created_date= created_date)
    else:
        # If its a 'PUT', just make sure it exists
        if not packages:
            abort(404) 
        else:
            # Update fields
            for key in args: 
                if key == 'apps':
                    packages['apps'] = apps  
                else:
                    packages[key] = args[key] 
         
    pkgs_csv=",".join(pkgs)
    appo_app_name = [] 

    url1 = '%sviews/apps/summary/?ids=%s&platform=ios' % (APPLUVR_VIEW_SERVER, pkgs_csv)
    temp1 = requests.get(url1,auth=(auth_user,auth_pwd))
    if temp1.status_code == 200:
        data = json.loads(temp1.content) 
        appo_app_name = [data[each].get('itunes_market').get('name') for each in pkgs if each in data.keys()]
    app_name_csv = ",".join(appo_app_name)

    packages.update()    
    apppack_id = packages._id
    # get_generated app_pack_img. 
    apppack_img, apppack_square_img = app_pack_img_genereation(apppack_id, pkgs) 
    packages.apppack_img = apppack_img
    packages.apppack_square_img = apppack_square_img
    packages.apppack_status = form.apppack_status.data
    packages.update()
    
    create_app_pack_index(app_id = packages._id, app_name_csv=app_name_csv)     
    response = current_app.make_response(jsonify(app_id=str(packages._id)))
    response.status_code = 201      
    response.headers['Location']=url_for('.get_all_packs', app_id=packages._id, _external=True)
    if request.method == 'PUT':
        pass
        #cache.delete_memoized(get_all_packs,app_id=packages._id)
    #cache.delete_memoized(get_all_packs)
    return response

def app_pack_index_config():
    mixes_endpoint = os.environ.get('MIXES_URL', 'http://:beretyhusabu@rybaga.api.indexden.com')
    mixes_index = os.environ.get('MIXES_INDEX', 'mix_search_dev')
    return mixes_endpoint,mixes_index

    
def create_app_pack_index(app_id = None,app_name_csv = None):
    """
    create app_pack index.
    """
    mixes_endpoint,mixes_index = app_pack_index_config()
    api = ApiClient(mixes_endpoint)
    index = api.get_index(mixes_index)
    #Index a document
    packages= Packages.load(app_id)
    doc =  {'app_pack_id' : packages._id, 
         'apppack_name' : packages.apppack_name,
         'app_pack_description' : packages.apppack_description, 
         'user_name' : packages.user_name, 
         'user_bio' : packages.user_bio,
         'app_names': app_name_csv
          }
    id = doc['app_pack_id']
    index.add_document(id, doc) 
    return 'created index with query id : %s' %id

@routes.route('/app_pack/index/get/all', methods=['GET',])
@support_jsonp
@support_etags
def get_all_app_pack_index():
    """
    get all app_pack indexes.
    """
    app_packs = [app.toDict() for app in Packages.view('app_packs/app_pack')]
    for id in app_packs:
        app_id = id.get('app_id') 
        pkgs = [pkg.get('package_name') for pkg in id.get('apps')]
        pkgs_csv=",".join(pkgs)
        url1 = '%sviews/apps/summary/?ids=%s&platform=ios' % (APPLUVR_VIEW_SERVER, pkgs_csv)   
        temp1 = requests.get(url1, auth = (auth_user,auth_pwd))
        if temp1.status_code == 200:
            data = json.loads(temp1.content)            
            appo_app_name = [data[each].get('itunes_market').get('name') for each in pkgs if each in data.keys()]            
            app_name_csv = ",".join(appo_app_name)            
            create_app_pack_index(app_id, app_name_csv = app_name_csv)


    return 'Done!!'

@routes.route('/app_pack/index/query', methods=['GET',])
@support_jsonp
@support_etags
def get_app_pack_index_by_query_term():    
    """
       search query
    """
    output = []
    mixes_endpoint,mixes_index = app_pack_index_config()
    api = ApiClient(mixes_endpoint)
    index = api.get_index(mixes_index)

    query_term = request.args.get('query_term',None) 
    if query_term:
        query_format = 'apppack_name: {0} OR app_pack_description: {0} OR user_name:{0} OR comments:{0} OR user_bio:{0} OR app_names:{0} '
        query = query_format.replace('{0}', query_term)
        results = index.search(query)
        if not results:
            return jsonify(count = len(output), data = output)  
        else: 
            output  = [doc for doc in results['results']]
            return jsonify(count = len(output), data = output)
    else:
        return jsonify(count = len(output), data = output)
#--------------------------------------------------------------------------------------#
@routes.route('/deal/all', methods=['GET',])
@support_jsonp
@support_etags
#@cache.memoize(60)
def get_all_deals():    
    all_deals_list = []
    data=[deal.toDict() for deal in Deal.view('deal/all_deals')]
    for deal_app in data:
        deal_start_edt = int(deal_app.get('deal_start','1321809540'))
        deal_end_edt = int(deal_app.get('deal_end','1321809540')) 
        deal_app['deal_start_formatted'] = datetime.datetime.fromtimestamp(deal_start_edt).strftime('%Y-%m-%d %H:%M:%S')
        deal_app['deal_end_formatted'] = datetime.datetime.fromtimestamp(deal_end_edt).strftime('%Y-%m-%d %H:%M:%S')
        all_deals_list.append(deal_app)       
    return jsonify(deals = all_deals_list)  #.Dealed_Apps()])

@routes.route('/deal/<deal_id>', methods=['GET',])
@support_jsonp
@support_etags
#@cache.memoize(60)
def get_deal(deal_id):
    deal = Deal.load(deal_id)
    if not deal:
        return abort(404)
    deal_app= deal.toDict()
    deal_start_edt = int(deal_app.get('deal_start','1321809540')) 
    deal_end_edt = int(deal_app.get('deal_end','1321809540')) 
    deal_app['deal_start_formatted'] = datetime.datetime.fromtimestamp(deal_start_edt).strftime('%Y-%m-%d %H:%M:%S')
    deal_app['deal_end_formatted'] = datetime.datetime.fromtimestamp(deal_end_edt).strftime('%Y-%m-%d %H:%M:%S')
    return jsonify(deal_app)

@routes.route('/deal/<deal_id>', methods=['DELETE',])
def delete_deal(deal_id):
    if deal_id == None:
        abort(400)
    deal = Deal.load(deal_id)
    if not deal:
        abort(404)
    couch.delete(deal)
    response = current_app.make_response(jsonify(deal=deal_id))
    response.status_code = 204
    #cache.delete_memoized(get_deal,deal_id=deal_id)
    return response

@routes.route('/deal', methods=['POST',])
@routes.route('/deal/<deal_id>', methods=['PUT',])
@requires_auth
def create_deals(deal_id=None):
    deal = None    
    args = MultiDict(request.json) if request.json else request.form
    form = DealCreateForm(args) if request.method == 'POST' else DealUpdateForm(args)
    # If the params arent validated right, bail out
    if not form.validate_on_submit():
        return make_400(form.errors)
    if deal_id is None and request.method == "PUT":
        abort(404)
    if deal_id is not None:
        deal= Deal.load(deal_id)
    # Get start and End Times and Round off to nearest minute
    deal_start = list(time.strptime(form.deal_start.data, '%Y:%m:%d %H:%M:%S'))
    deal_start[5]=0
    deal_start[4] = round_off_numbers(deal_start[4], 30)
    deal_start = int(time.mktime(time.struct_time(tuple(deal_start))))
    deal_end = list(time.strptime(form.deal_end.data, '%Y:%m:%d %H:%M:%S'))
    deal_end[4] = round_off_numbers(deal_end[4], 30)
    deal_end[5] = 0
    deal_end = int(time.mktime(time.struct_time(tuple(deal_end))))
    # Create or update?
    if request.method == 'POST': 
    # create new deal
        deal = Deal(name = form.name.data, package_name = form.package_name.data, editorial_description = form.editorial_description.data, download_url = form.download_url.data, platform =form.platform.data, carrier = form.carrier.data, deal_title = form.deal_title.data, original_price = form.original_price.data, deal_start = str(deal_start), deal_end = str(deal_end))
    else:
        # If its a 'PUT', just make sure it exists
        if not deal:
            abort(404) 
        else:
            # Update fields
            for key in args:                
                deal[key] = args[key]
                deal['deal_start'] = str(deal_start)
                deal['deal_end'] =str(deal_end)
        
    deal.update()      
    response = current_app.make_response(jsonify(deal_id=str(deal._id)))
    response.status_code = 201      
    response.headers['Location']=url_for('.get_deal', deal_id=deal._id, _external=True)
    if request.method == 'PUT':
        pass
        #cache.delete_memoized(get_deal,deal_id=deal._id)
    #cache.delete_memoized(get_all_deals)
    return response


@routes.route('/deal/current', methods=['GET',])
@support_jsonp
@support_etags
#@cache.memoize(60)
def get_current_deals(): 
  #Get current time round off to nearest minute with second as 0
    current = list(time.localtime())
    current[5] = 0
    current[4] = round_off_numbers(current[4], 30)
    current = int(time.mktime(time.struct_time(tuple(current))))
    #current_app.logger.debug("----> %s"%current)
    deal = [deal.current_deal_toDict() for deal in Deal.view('deal/current_deal',  key = current)]
    return jsonify(data=deal)  #.Dealed_Apps()])

#--------------------------------------------------------------------------------------#

@routes.route('/interests', methods=['GET',])
@support_jsonp
@support_etags
#Removing caching for testing
#@cache.memoize(60)
def get_all_interests():
    return jsonify(data=[interest.toDict() for interest in Interest.view('interest/all_interests')])  #.all_interests()])


@routes.route('/interests/<name>', methods=['GET',])
@support_jsonp
@support_etags
#@cache.memoize(60)
def get_interest(name):
    interest = Interest.load(name)
    if not interest:
        return abort(404)
    return jsonify(interest.toDict())


@routes.route('/interests', methods=['POST','PUT',])
@support_jsonp
def create_interest():
    args = MultiDict(request.json) if request.json else request.form
    form = InterestCreateForm(args)
    if not form.validate_on_submit():
        return make_400(form.errors)

    interest = Interest.load(form.name.data)
    # Check to see if the interest exists already
    if not interest:
        interest = Interest(name=form.name.data)
        interest._id = form.name.data
    for key in args:
        interest[key] = args[key]
    interest.update()
    response = current_app.make_response(jsonify(interest=str(interest.name)))
    response.status_code = 201
    response.headers['Location']=url_for('.get_interest',name=interest.name, _external=True)
    if request.method == 'PUT':
        pass
        #cache.delete_memoized(get_interest,name=interest.name)
    #cache.delete_memoized(get_all_interests)
    return response

@routes.route('/interests/<name>', methods=['DELETE',])
def delete_interest(name):
    if name == None:
        abort(400)
    interest = Interest.load(name)
    if not interest:
        abort(404)
    couch.delete(interest)
    response = current_app.make_response(jsonify(interest=name))
    response.status_code = 204
    #cache.delete_memoized(get_interest,name=name)
    return response



#--------------------------------------------------------------------------------------#

@routes.route('/promoapps', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
@cache.memoize(60)
def get_promos():
    promo_data=[app.toDict() for app in PromoApp.view('promoapp/all_apps')]
    orderd_promos=sorted(promo_data, key=itemgetter('priority'))

    return jsonify(data=orderd_promos)  #all_apps()])

@routes.route('/promoapps/<pkg>', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
@cache.memoize(60)
def get_promo_for_pkg(pkg):
    app = PromoApp.load('promo.'+pkg)
    if not app:
        abort(404)
    return jsonify(app.toDict())

@routes.route('/promoapps/id/<id>', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
@cache.memoize(60)
def get_promo_for_id(id):
    app = PromoApp.load(id)
    if not app:
        abort(404)
    return jsonify(app.toDict())

@routes.route('/promoapps/<pkg>', methods=['POST','PUT'])
@requires_auth
def create_promo(pkg):
    args = MultiDict(request.json) if request.json else request.form
    form = PromoCreateForm(args) if request.method == 'POST' else PromoUpdateForm(args)
    # If the params arent validated right, bail out
    if not form.validate_on_submit():
        return make_400(form.errors)
    app = PromoApp.load('promo.'+pkg)
    # Create or update?
    if request.method == 'POST':
        # Check to see if the app already exists
        if app:
            return make_409(pkg)
        # Create new app
        app = PromoApp()
        app.pkg = pkg
        app._id = 'promo.'+app.pkg
    else:
        # If its a 'PUT', just make sure it exists
        if not app:
            abort(404)
    # load up the args
    for key in args:
        if key == 'interests':
            if not app.interests:
                    app.interests = []
            interests_str = args[key].split(',')
            interests = set([interest.strip() for interest in interests_str])
            app.interests = list(interests)
        else:
            app[key] = args[key]
    # Commit to database
    app.update()
    # Put together response
    #response = current_app.make_response(jsonify(pkg=str(app.pkg)))
    response = current_app.make_response(jsonify(data=app.toDict()))
    response.status_code = 201
    response.headers['Location']=url_for('.get_promo_for_pkg',pkg=app.pkg, _external=True)
    if request.method == 'PUT':
        pass
        #cache.delete_memoized(get_promo_for_pkg,pkg=pkg)
    return response


@routes.route('/promoapps/<pkg>', methods=['DELETE',])
@requires_auth
def delete_promo_for_pkg(pkg):
    app = PromoApp.load('promo.'+pkg)
    if not app:
        abort(404)
    couch.delete(app)
    response = current_app.make_response(jsonify(pkg=pkg))
    response.status_code = 204
    #cache.delete_memoized(get_promo_for_pkg,pkg=pkg)
    return response


@routes.route('/promoapps/id/<id>', methods=['DELETE',])
@requires_auth
def delete_promo_for_id(id):
    app = PromoApp.load(id)
    if not app:
        abort(404)
    couch.delete(app)
    response = current_app.make_response(jsonify(pkg=id))
    response.status_code = 204
    #cache.delete_memoized(get_promo_for_pkg,pkg=id)
    return response

@routes.route('/promoapps/id/<pkg>', methods=['POST'])   
@routes.route('/promoapps/id/<pkg>/<promoid>', methods=['PUT'])
@requires_auth
def create_promo_apps_by_promoid(pkg,promoid=None):
    app = None
    args = MultiDict(request.json) if request.json else request.form
    form = PromoCreateForm(args) if request.method == 'POST' else PromoUpdateForm(args)
    # If the params arent validated right, bail out
    if not form.validate_on_submit():
        return make_400(form.errors)
    if promoid is None and request.method == "PUT":
        abort(404)
    if promoid is not None:
        app= PromoApp.load(promoid)
    # Create or update?
    if request.method == 'POST':
    # Check to see if the app already exists
        if app:
            return make_409(pkg)
        # Create new app
        app = PromoApp()
        app.pkg = pkg 
        if app.carousel == 'featured_apps':
            app.context_copy = form.context_copy.data 
    else:
        # If its a 'PUT', just make sure it exists
        if not app:
            abort(404)            
    for key in args:
        if key == 'interests':
            if not app.interests:
                app.interests = []
            interests_str = args[key].split(',')
            interests = set([interest.strip() for interest in interests_str])
            app.interests = list(interests) 
        elif key == 'context_copy':
            app.context_copy = form.context_copy.data 
        else:
            app[key] = args[key]
    app.update()
    promoid = app._id
    response = current_app.make_response(jsonify(data=app.toDict()))
    response.status_code = 201
    current_app.logger.debug("promoid saved %s"%promoid)
    response.headers['Location']=url_for('.get_promo_for_id',id=promoid, _external=True)
    if request.method == 'PUT':
        pass
        #cache.delete_memoized(get_promo_for_pkg,id=promoid)
    return response

#--------------------------------------------------------------------------------------#

@routes.route('/apps/blacklist/', methods=['GET', ])
@support_etags
@requires_auth
def get_blacklist():
    carrier = request.args.get('carrier', 'verizon')
    platform  = request.args.get('platform','android')
    content,status = fetch_appo_blacklist(carrier,platform)
    return content,status

@cache.memoize(APPLVR_CACHE_APPO)    
def fetch_appo_blacklist(carrier,platform):
    carrier = request.args.get('carrier', 'verizon')
    platform  = request.args.get('platform','android')
    blacklisturl = APPO_URL+APPO_BLACK+"?platform="+platform+"&carrier="+carrier
    r = requests.get(blacklisturl, auth=APPO_BASIC_AUTH)
    return r.content, r.status_code  

@routes.route('/apps/<pkg>/summary', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
def get_app_summary_uncache(pkg):
    return get_app_summary(pkg)

@cache.memoize(FULL_DAY)
def get_app_summary(pkg=None):
    if not pkg:
        return make_400({'pkg':['Unable to lookup details about the package provided. Please check the package id to ensure it is correct.']})
    if not verify_package(pkg):
        return make_400({'pkg':['Not a valid java package name. Please check the package name and try again.']})
    d(APPO_URL+'apps/details?ids='+pkg+'&summary=true')
    t1 = time.time()
    r = requests.get(APPO_URL+'apps/details?ids='+pkg+'&summary=true', auth=APPO_BASIC_AUTH)
    t2 = time.time()
    d('>>>>TIMER reports that Appo call took %0.3f ms' % ((t2-t1)*1000.0))
    assert(r.content)
    if r.status_code == 200:
        app_details = simplejson.loads(r.content)
        # Kludgy fix for Appo issue until Appo returns error codes correctly
        if not len(app_details):
            abort(404)
        return jsonify(app_details[pkg])
    else:
        return r.content, r.status_code

@routes.route('/apps/summary', methods=['GET',])
@support_jsonp
@support_etags
#@cache.memoize(FULL_DAY)
@requires_auth
def get_app_summary_bulk():
    #d(request.args)
    pkgs = request.args.get('ids', None)
    platform  = request.args.get('platform','android')
    if not pkgs:
        return make_400({'ids':['Unable to lookup details about the package provided. Please check the package id to ensure it is correct. Multiple package names need to be in a comma separated list']})
    url = '%sapps/details?ids=%s&platform=%s&summary=true'%(APPO_URL, pkgs, platform)
    r = requests.get(url, auth=APPO_BASIC_AUTH)
    if r.content == '{}':
        abort(404)
    return r.content, r.status_code


@routes.route('/apps/<pkg>/details', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
def get_app_details_uncache(pkg):
    return get_app_details(pkg)

@cache.memoize(FULL_DAY)
def get_app_details(pkg=None):
    platform  = request.args.get('platform','android')
    if not pkg:
        return make_400({'pkg':['Unable to lookup details about the package provided. Please check the package id to ensure it is correct.']})
    #if not verify_package(pkg):
     #   return make_400({'pkg':['Not a valid java package name. Please check the package name and try again.']})
    #d(APPO_URL+'apps/details?ids='+pkg)
    url = '%sapps/details?ids=%s&platform=%s'%(APPO_URL,pkg,platform)
    r = requests.get(url,auth=APPO_BASIC_AUTH)
    if r.content == '{}':
        abort(404)
    if r.status_code == 200:
        return jsonify(r.json.get(pkg,{}))
    return r.content, r.status_code


@routes.route('/apps/details', methods=['GET',])
@support_jsonp
@support_etags
#@cache.memoize(FULL_DAY)
@requires_auth
def get_app_details_bulk():
    platform  = request.args.get('platform','android')
    pkgs = request.args.get('ids', None)
    if not pkgs:
        return make_400({'ids':['Unable to lookup details about the package provided. Please check the package id to ensure it is correct. Multiple package names need to be in a comma separated list']})
    #d('%s%s%s' % (APPO_URL,'apps/details?ids=',pkgs))
    url = '%s/apps/details?ids=%s&platform=%s'%(APPO_URL,pkgs,platform)
    r = requests.get(url, auth=APPO_BASIC_AUTH)
    if r.content == '{}':
        abort(404)
    return r.content, r.status_code

#@routes.route('/apps/search', methods=['GET',])
@routes.route('/users/<uniq_id>/devices/<udid>/apps/search', methods=['GET',])
@print_timing
@requires_auth
def get_search_results(uniq_id, udid):
    user, device = user_device(uniq_id, udid)
    #adding utf-8 encode since search strings with unicode like Über were throwing errors
    req_args = dict([(k.encode('utf-8'), v.encode('utf-8')) for k, v in request.args.items()])
    query = urllib.urlencode(req_args)
    max_size = carousel_setting().get('Search Carousel Apps')
    odp_installed = user.odp_installed() if user else False
    # Binary flag for Appo
    odp_installed = '1' if odp_installed else '0'
    appo_id = user.safe_serialize_appo_id() if user else None
    #d('%s%s?%s&uid=%s&max_size=%s&odp_installed=%s' % (APPO_URL,APPO_SEARCHES,query,appo_id,max_size,odp_installed))

    r = requests.get(APPO_URL+APPO_SEARCHES+'?'+query, params=dict(uid=appo_id,max_size=max_size,odp_installed=odp_installed),auth=APPO_BASIC_AUTH)

    assert(r.content)
    if r.status_code == 200:
        results = r.json.get('apps', None)
        return jsonify(data=results, count=len(results))
    else:
        return r.content, r.status_code

@routes.route('/apps/search/<platform>/trends/', methods=['GET',])
@routes.route('/apps/search/trends/', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
@cache.memoize(APPLVR_CACHE_APPO)
def get_search_trends(platform='android'):
    #d(APPO_URL+APPO_SEARCH_TRENDS)
    url = "%s%s?platform=%s"%(APPO_URL,APPO_SEARCH_TRENDS,platform)
    r = requests.get(url, auth=APPO_BASIC_AUTH)
    assert(r.content)
    if r.status_code == 200:
        trends = r.json.get('trending_terms', None)
        return jsonify(data=trends)
    else:
        return r.content, r.status_code


@routes.route('/apps/<pkg>/like', methods=['GET',])
@support_etags
@requires_auth
def get_app_likes_uncache(pkg):
    return get_app_likes(pkg)

#@cache.memoize(BALI_CACHE_TIME)
def get_app_likes(pkg=None):
    app = App.load(pkg)
    if not app:
        return jsonify(data=[])
    d(app.toDict())
    return jsonify(data=app.liked)

#-------------------------------------------------------------------------------#

'''def user_device(uniq_id, udid):
    user = User.load(uniq_id)
    device = Device.load(udid)
    if user is None or device is None:
        abort(404)
    else:
        return user, device
'''
#-------------------------------------------------------------------------------#

@routes.route('/devices/<udid>/testing/', methods=['GET',])
def foo_test(udid):
    device = Device.load(udid)
    print device
    owner = device.owners()
    print device.owners()
    return jsonify(data=device.toDict())

@routes.route('/users/<id>/reset', methods = ['PUT',])
def user_reset(id):
    old_user = User.load(id)
    from os import urandom
    master_name = 'Anon User - Master'
    master_uniq_id = '17b52da039f04cd2a5ab7206c54b7b74'
    master_user = User.load(master_uniq_id)
    if master_user is None:
        master_user = User(uniq_id=master_uniq_id, name=master_name)
        master_user._id = master_uniq_id
        master_user.update()
    couch.copy(master_user, old_user)
    new_user = User.load(id)
    new_user.name = 'Anon User - %s' % id
    new_user.uniq_id = new_user._id
    new_user.update()
    return jsonify(data=new_user.toDict())


@routes.route('/users/<id>/devices/<udid>/reset', methods = ['PUT',])
def user_device_reset(id,udid):
    old_device = Device.load(udid)
    old_device.apps_installed = None
    old_device.odp_installed = False
    old_device.read_apps = False
    try:
        old_device.update()
    except couchdb.http.ResourceConflict:
        return make_conflict_409(udid)
    return jsonify(data=old_device.toDict())

class Http400Error(Exception):
    def __init__(self, errors):
        self.errors = errors

class Http409Error(Exception):
    def __init__(self, id):
        self.id = id

class Http404Error(Exception):
    def __init__(self, id):
        self.id = id

def create_anonymous_user(udid, args):
    # Steps:
    # 1. Attempt to create an anonymous user,
    # 2. Register device to the anon user
    # Assumes device doesnt currently exist in the db - raises exception if it does
    # Returns a tuple of (user, device) objects
    uniq_name, uniq_id = roulette()

    if os.environ.has_key('REDISTOGO_URL'):
        urlparse.uses_netloc.append('redis')
        url = urlparse.urlparse(os.environ['REDISTOGO_URL'])
        REDIS = Redis(host=url.hostname, port=url.port, db=0, password=url.password)
        redis = REDIS
        print 'Redis parameters are %s (hostname), %s (port), %s (password)' % (url.hostname, url.port, url.password)
    else:
        redis = Redis()

    redis.hset('count.'+uniq_id, 'mf', "1347511521")
    redis.hset('count.'+uniq_id, 'mfa', "1347511521")
    redis.hdel('count.'+uniq_id,'mf')
    redis.hdel('count.'+uniq_id,'mfa')

    return create_new_user(udid, uniq_id, uniq_name, args)

def create_new_user(udid, uniq_id, uniq_name, args):
    device = Device.load(udid)
    if device:
        raise Http409Error(udid)
    user = User.load(uniq_id) if uniq_id else None
    if user is None:
        # Create an anon user
        current_app.logger.debug('..user doesnt exist, creating anon user')
        user = User(uniq_id=uniq_id, name=uniq_name)
        user._id = uniq_id
        user.update()
    else:
        # User already exists, but device did not
        # Only valid scenario for this is if the user is a FB Web User who had signed out
        current_app.logger.warning('..user exists, but device did not')
        pass
    params = {}

    for k in args:
        params[k] = args[k]
    params['uniq_id'] = uniq_id
    params['udid'] = udid
    params = MultiDict(params)
    form = DeviceCreateForm(params)
    # Check form data, bail if invalid
    #if not form.validate_on_submit():
    #    raise Http400Error(form.errors)

    device = Device(model=form.model.data, make=form.make.data, number=form.number.data, os_version=form.os_version.data, udid=form.udid.data, uniq_id=form.uniq_id.data, carrier=form.carrier.data, advertisingIdentifier=form.advertisingIdentifier.data, advertisingTrackingEnabled=form.advertisingTrackingEnabled.data, MDN=form.MDN.data, ATT_subid=form.ATT_subid.data,appluvr_build=form.appluvr_build.data)
    device._id = form.udid.data
    device.add_link('user', form.uniq_id.data)
    user.add_link('device', form.udid.data)
    try:
        current_app.logger.debug('..updating user with a new device')
        user.update()
        current_app.logger.debug('..updating device with backreference to user')
        device.update()
    except couchdb.http.ResourceConflict:
        # TODO: Rollback of user change if device fails
        raise Http409Error(udid)
    return (user, device)

def delete_anonymous_user(udid, args=None):
    """
    Deletes a v2+ anon user
    """
    device = Device.load(udid)
    if device:
        # Returning device
        current_app.logger.debug('..detected returning device, deleting old device')
        user = User.load(device.owners().pop()) if len(device.owners()) else None

        # TODO:
        # Delete needs to be wired via the model
        # so that backreferences to user are removed

        couch.delete(device)
        device = None
        if user:
            # Returning user
            current_app.logger.debug('...the user associated is %s (%s)' % (user.name, user._id))
            all_devices = [link['href'] for link in user.links if link['rel'] == 'device']
            if user.fb_id and user.fb_token:
                if current_app.config.get('APPLUVR_MULTI_DEVICE', None):
                    # Is this a multidevice user?
                    # In which case, we only disassociate, but not delete
                    current_app.logger.debug('..detecting returning FB user, detaching device')
                    # Reload user to avoid risk of document conflict
                    user = User.load(user.fb_id)
                    user.del_link(udid)
                    try:
                        user.update()
                    except couchdb.http.ResourceConflict:
                        current_app.logger.error('Unable to delink fb user %s and device %s' % (user.fb_id, udid))
                else:
                    # Not a multidevice user
                    # Blow away the user (although logged in to FB)
                    current_app.logger.debug('..detecting returning single-device user, deleting old user')
                    delete_all_user_comments(user.uniq_id)
                    couch.delete(user)
                    user = None
            else:
                # Or a regular anonymous user?
                current_app.logger.debug('..detecting returning user, deleting old user')
                delete_all_user_comments(user.uniq_id)
                couch.delete(user)
            user = None
        else:
            current_app.logger.debug('..unable to find returning user - not deleted')


def delete_all_user_comments(id):
    keys=[]
    keys.append(id)
    rows = Comment.view('comment/user_comments', keys=keys)
    current_app.logger.debug('Deleting %s comments made by user %s' % (len(rows), id))
    [couch.delete(comment) for comment in rows]
    return True


@routes.route('/devices/<udid>/signin/', methods=['POST',])
@routes.route('/devices/<udid>/signin/<mode>', methods=['POST',])
def get_user_details(udid, mode=None):
    """
    API to provide sign in via the device, where for a new user - a Device & User get created automatically
    So, an anonmyous user gets provisioned and initial data set is loaded up.
    If a user already exists, state information about him and his devices is loaded up.
    If its a new user or a factory reset user, the old device gets deleted and recreated.
    TODO:
    - If the user doesnt have other devices, the user is also recreated
    """

    args = request.form

    # Insert AT&T Subscriber ID if detected in headers
    attsubid = request.headers.get('x-up-subno','')
    args = dict(request.form.items())
    if attsubid != '':
        args['ATT_subid'] = hashlib.md5(attsubid).hexdigest()
    else:
        args['ATT_subid'] = ''
    args = MultiDict(args)
    device = Device.load(udid) if udid else None
    #uniq_id = udid[::-1]

    # If this is a FB logout
    # preload the params
    if mode == 'logout':
        args = dict(request.form.items())
        args['os_version'] = device.os_version
        args['make'] = device.make
        args['model'] = device.model
        args['number'] = device.number
        args['carrier'] = device.carrier
        args['device_token'] = device.notification_token
        args = MultiDict(args)

    # If this is a) a new user,
    # or, b) a returning user upon factory reset (where udid stayed the same)
    # we blow away the device

    if mode == 'new' or mode == 'logout':
        try:
            current_app.logger.debug('..new user')
            delete_anonymous_user(udid)
            device = None
        except Http404Error as e:
            abort(404)

    if mode == 'v1-upgrade':
        if device is not None:
            user = User.load(device.owners().pop()) if len(device.owners()) else None

            # v1 data consistency logic check here
            if not user:
                # user doesnt exist, but device does
                try:
                    current_app.logger.warning('..v1 user with device entity but no user entity')
                    # anonymize the device - data inconsistency case
                    delete_anonymous_user(udid)
                    device = None
                except Http404Error as e:
                    abort(404)

            # User exists, has interests, all of whom are character formatted (sum of length of indivuals equals total)
            if user and user.interests and sum([len(x) for x in user.interests]) == len(user.interests):
                interests_str = user.interests
                interest_list = ''.join(interests_str).split(',')
                user.interests = interest_list
                try:
                    user.update()
                except couchdb.http.ResourceConflict:
                    current_app.logger.error('Unable to delink upgrade v1 user')
                    return make_409(user.uniq_id)
                current_app.logger.debug('V1 user %s upgraded successfully' % user.uniq_id)
            else:
                current_app.logger.error('V1 user upgrade skipped - no user interests found that need to be changed found for device %s' % udid)
        else:
            current_app.logger.error('V1 user upgrade failed - no device %s found' % udid)

    if device is not None:
        # Device exists, return device and its user details
        current_app.logger.debug('..device exists, fetching user details')
        user = User.load(device.owners().pop()) if len(device.owners()) else None
        #TODO: Is there a case where the device exists, user doesnt? How do we handle it?
        assert(user)
    else:
        current_app.logger.debug('..device doesnt exist, checking user status')
        try:
            user,device = create_anonymous_user(udid, args)
        except Http400Error as e:
            return make_400(e.errors)
        except Http409Error as e:
            return make_409(e.id)
    # Return aggregated user and device details
    current_app.logger.debug('..returning user details and list of devices')
    device_ids = [link['href'] for link in user.links if link['rel'] == 'device']
    devices = [Device.load(i).toDict() for i in device_ids]
    # Load device details, build up dict
    return jsonify(user=user.toDict(), devices=devices)



#--------------------------------------------------------------------------------------

@routes.route('/devices', methods=['POST',])
@requires_auth
def create_device():
    args = MultiDict(request.json) if request.json else request.form
    form = DeviceCreateForm(args)
    if not form.validate_on_submit():
        return make_400(form.errors)

    device = Device.load(form.udid.data)
    # Check to see if the device exists already
    if not device:
        device = Device(model=form.model.data, make=form.make.data, number=form.number.data, os_version=form.os_version.data, udid=form.udid.data, carrier=form.carrier.data,MDN=form.MDN.data)
        device._id = form.udid.data
        user = User.load(form.uniq_id.data)
        # Associate the device with a user
        if user:
            device.add_link('user',form.uniq_id.data)
            user.add_link('device',form.udid.data)
            user.update()
            device.update()
        else:
            return make_400({'uniq_id':['Unable to lookup details about the user provided. Please check the unique id to ensure it is correct.']})
        response = current_app.make_response(jsonify(udid=str(device._id)))
        response.status_code = 201
        response.headers['Location']=url_for('.get_device',id=device._id, _external=True)
        return response
    else:
        return make_409(form.udid.data)


@routes.route('/devices/<id>', methods=['PUT',])
@requires_auth
def update_device(id):
    args = MultiDict(request.json) if request.json else request.form
    # Insert AT&T Subscriber ID if detected in headers
    attsubid = request.headers.get('x-up-subno','')
    #args = MultiDict(args)
    # Accept fb_id as an optional uniq_id parameter
    args = dict(args.items())
    if attsubid != '':
        args['ATT_subid']= hashlib.md5(attsubid).hexdigest()
    if args.get('uniq_id') is None:
        args['uniq_id'] = args.get('fb_id', None)
    args = MultiDict(args)
    form = DeviceUpdateForm(args)
    if not form.validate_on_submit():
        return make_400(form.errors)
    udid = id
    device = Device.load(udid)
    # Check to see if the device exists already
    if not device:
        abort(404)
    else:
        # If device owner has changed - wipe out old references
        if form.uniq_id.data and form.uniq_id.data not in device.owners():
            for owner in device.owners():
                olduser = User.load(owner)
                if olduser:
                    d('Device attached to old user %s, now belongs to new user %s', owner, form.uniq_id.data)
                    olduser.del_link(id)
                device.del_link(owner)
        # Load up the new data
        for key in args:
            if key == 'odp_installed':
                device.odp_installed = int(args[key])
            else:
                device[key] = args[key]
        # Load up the associated user
        user = User.load(form.uniq_id.data)
        # Associate the device with a user
        if user:
            device.add_link('user', form.uniq_id.data)
            user.add_link('device', udid)
            try:
                user.update()
                device.update()
            except couchdb.http.ResourceConflict:
                return make_conflict_409(id)
        else:
            return make_400({'uniq_id':['Unable to lookup details about the user provided. Please check the unique id to ensure it is correct.']})
        response = current_app.make_response(jsonify(udid=str(device._id),ATT_subid=device.ATT_subid))
        response.status_code = 201
        response.headers['Location']=url_for('.get_device',id=device._id, _external=True)
        #cache.delete_memoized(get_device,id=id)
        return response


@routes.route('/devices', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@requires_auth
@cache.memoize(60)
def all_devices():
    return jsonify(data=[device.toDict() for device in Device.view('device/all_devices')]) #Device.all_devices()])

@routes.route('/devices/<id>', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
@cache.memoize(60)
def get_device(id=None):
    assert(id)
    _device = Device.load(id)
    if _device is None:
        abort(404)
    else:
        device = _device.toDict()
    return jsonify(device)


@routes.route('/devices/<id>', methods=['DELETE',])
@support_jsonp
@requires_auth
def delete_device(id):
    device = Device.load(id)
    if device is None:
        abort(404)
    else:
        d('Deleting device ' + id + ' of ' + device.model)
        couch.delete(device)
        users = {}
        for user in User.view('user/all_users'):
            user.del_link(id)
            #user.update()
        response = current_app.make_response(jsonify(udid=id))
        response.status_code = 204
        cache.delete_memoized(get_device,id=id)
        return response

# Deprecated
@routes.route('/devices/<id>/apps', methods=['POST','PUT',])
@support_jsonp
@requires_auth
def create_device_apps(id):
    #Validate the rest of the form params
    args = MultiDict(request.json) if request.json else request.form
    form = DeviceCreateAppsForm(args)
    if not form.validate_on_submit():
        return make_400(form.errors)
    #Break out the comma separated list, strip out whitespace
    pkgs = form.pkgs.data.split(',')
    pkgs = [pkg.strip() for pkg in pkgs]
    #d('Apps harvested: %s',pkgs)
    pkgs = [pkg for pkg in pkgs if not verify_system_package(pkg)]
    #d('Post filter of system apps: %s', pkgs)

    """
    Note: disabling Appo catalog lookup

    if current_app.config['TESTING'] == False:
        res = App.view('app/all_app_pkgs', keys=pkgs)
        pkgs_in_catalog = [item.key for item in res]
        d('Post filter of packages not in catalog: %s', pkgs_in_catalog)
        #pkgs = pkgs_in_catalog
    """

    # Moving device data load here to reduce risk of
    # resource conflicts
    # Check to see if the device exists
    cache.delete_memoized(get_device,id=id)
    device = Device.load(id)
    if not device:
        abort(404)
    device.apps_installed = pkgs
    try:
        device.update()
    except couchdb.http.ResourceConflict:
        return make_conflict_409(id)
    cache.delete_memoized(get_device,id=id)
    response = current_app.make_response(jsonify(id=device._id,apps_installed=pkgs))
    response.status_code = 201
    response.headers['Location']=url_for('.get_all_device_apps',id=device._id, _external=True)
    return response

@routes.route('/devices/<id>/apps', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
@cache.memoize(60)
def get_all_device_apps(id):
    device = Device.load(id)
    if not device:
        abort(404)
    return current_app.make_response(jsonify(id=device._id, data=device.apps_installed))

@routes.route('/devices/<id>/apps/<pkg>', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
@cache.memoize(60)
def get_device_apps(id, pkg):
    device = Device.load(id)
    if not device:
        abort(404)
    if not pkg:
        abort(400)
    pkgs = device.apps_installed
    #d(pkg)
    #d(pkgs)
    if pkg in pkgs:
        return redirect(url_for('.get_app_details', pkg=pkg, _external=True))
    else:
        abort(404)

# Deprecated (v1)
@routes.route('/devices/<id>/apps', methods=['DELETE',])
@support_jsonp
@requires_auth
def delete_device_apps(id):
    device = Device.load(id)
    if not device:
        abort(404)
    device.apps_installed = []
    device.update()
    response = current_app.make_response(jsonify(id=device._id))
    response.status_code = 204
    return response


#--------------------------------------------------------------------------------------#


@routes.route('/users', methods=['POST'])
@support_jsonp
@requires_auth
def create_user():
    args = MultiDict(request.json) if request.json else request.form
    form = UserCreateForm(args)
    if not form.validate_on_submit():
        return make_400(form.errors)
    user = User.load(form.uniq_id.data)
    # Check to see if the user exists, if not add
    if not user:
        d(' '.join([form.uniq_id.data, form.fb_id.data, form.name.data, form.email.data]))
        user = User(uniq_id=form.uniq_id.data) #,fb_id=form.fb_id.data, name=form.name.data, email=form.email.data)
        for key in args:
            user[key] = args[key]
        user._id = form.uniq_id.data
        #Create symlinks
        user.add_link('friends',user._id)
        user.add_link('friends_apps',user._id)
        user.add_link('hot_apps',user._id)
        user.add_link('apps_for_you',user._id)
        user.update()
        response = current_app.make_response(jsonify(uniq_id=str(user._id),user=url_for('.get_user',id=user._id, _external=True)))
        response.status_code = 201
        response.headers['Location']=url_for('.get_user',id=user._id, _external=True)
        return response
    else:
        return make_409(form.uniq_id.data)


@routes.route('/users/<id>', methods=['PUT'])
@support_jsonp
def update_user(id):
    validation = MultiDict(request.json) if request.json else request.form
    form = UserUpdateForm(validation)
    if not form.validate_on_submit():
        return make_400(form.errors)
    user = User.load(id)
    # Check to see if the user exists, else dispatch 404
    if not user:
        abort(404)
    else:
        platform,carrier = get_user_device_carrier_platform(user)
        device = ','.join([link['href'] for link in user.links if link['rel'] == 'device'])
        args = request.form if request.json == None else request.json
        for key in args:
            if key == 'interests':               
                cache.delete_memoized(fetch_appo_data, APPLUVR_VIEW_SERVER, id, unicode(device), platform=platform, auth_pwd=auth_pwd)
                cache.delete_memoized(fetch_appo_data, APPLUVR_VIEW_SERVER, id, unicode(device), platform=unicode(platform),auth_pwd=auth_pwd)                
                
                #current_app.logger.debug("===> %s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
                cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
                cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
                #invalidate friend card details without platform as part of url.
                cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=platform)
                cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=platform)
                        
                recommended_prefetch = fetch_recommended_apps(APPLUVR_VIEW_SERVER, id, unicode(device), platform=platform, auth_pwd=auth_pwd) 
                if not user.interests:
                    user.interests = []
                interests_str = args[key].split(',')
                interests = set([interest.strip() for interest in interests_str])
                user.interests = list(interests)
            else:
                user[key] = args[key]
        user.update()
        response = current_app.make_response(jsonify(uniq_id=str(user._id),user=url_for('.get_user',id=user._id, _external=True)))
        response.status_code = 201
        response.headers['Location']=url_for('.get_user',id=user._id,_external=True)
        # Delete cached entry
        #cache.delete_memoized(get_user,id=id)
        #cache.delete_memoized(all_advisors)
        #cache.delete_memoized(all_user)
        return response

@routes.route('/internal/users/appo', methods=['GET',])
@requires_auth
def appo_users():
    users = [user for user in User.view('user/all_users')]
    appo_map = [(user.uniq_id, safe_serialize(user.appo_id())[:24]) for user in users]
    return jsonify(data=dict(appo_map), count=len(appo_map))


@routes.route('/users', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
def all_user():
    ids = request.args.get('uniq_ids', None)
    return jsonify(_all_user(ids))

@cache.memoize(60)
def _all_user(ids):
    if ids is not None:
        keys = ids.split(',') if ids is not None else []
        return dict(data=[user.toDict() for user in User.view('user/all_users', keys=keys)])#all_users()])
    else:
        return dict(data=[user.toDict() for user in User.view('user/all_users')])#all_users()])

@routes.route('/users/advisors', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
@cache.memoize(60)
def all_advisors():
    return jsonify(data=[user.toDict() for user in User.view('user/all_advisors')])   #all_advisors()])

@routes.route('/users/v3_advisors', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
@cache.memoize(60)
def all_v3_advisors():
    return jsonify(data=[user.toDict() for user in User.view('user/v3_advisors')])   #all_advisors()])


@routes.route('/users/<id>', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
#Removing caching for testing
#@cache.memoize()
def get_user(id):
    _user = User.load(id)
    if _user is None:
        abort(404)
    else:
        user = _user.toDict()
    return jsonify(user)

@routes.route('/users/<id>', methods=['DELETE',])
@requires_auth
def delete_user(id):
    user = User.load(id)
    only_mf_notification = MfNotification.load("only_mf_notification."+id)
    only_mfa_notification = MfaNotification.load("only_mfa_notification."+id)
    NegInterests = UserNegativeInterests.load("NegInterests."+id)
    if not NegInterests:
        pass
    else:
        couch.delete(NegInterests)
    if not only_mf_notification:
        pass
    else:
        couch.delete(only_mf_notification)
    if not only_mfa_notification:
        pass  
    else:
        couch.delete(only_mfa_notification) 
          
    if user is None:
        abort(404) 
    else:        
        couch.delete(user)      
        response = current_app.make_response(jsonify(uniq_id=id))
        response.status_code = 204
        #cache.delete_memoized(get_user,id=id)
        #cache.delete_memoized(all_advisors)
        #cache.delete_memoized(all_user)       
        return response


@routes.route('/users/search/', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
def get_user_search():
    fb_id = request.args.get('fb_id',None)
    appo_id = request.args.get('appo_id',None)
    if fb_id:
        params = []
        params.append(fb_id)
        rows = User.view('user/user_for_fb_id', keys=params)
        for row in rows:
            print 'Row %s' % row
        user_ids = [row['value'] for row in rows]
        users = [User.load(user_id).toDict() for user_id in user_ids]
        return jsonify(data=users)
    if appo_id:
       print appo_id
       uniq_id = safe_deserialize(appo_id)
       user = User.load(uniq_id)
       if user is None:
          abort(404)
       return jsonify(data=user.toDict())
    return make_400({'fb_id':['Provide this query parameter to look up user details using the facebook identifier.']})

@routes.route('/users/<uniq_id>/devices/<udid>/fb', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
#@cache.memoize(60)
def get_user_fb(uniq_id, udid):
    user = User.load(uniq_id)
    if user is None:
        abort(404)
    token = user.fb_token
    # Return only if token exists - do not expose user token via API
    fb_token = token is not None
    fb_id = user.fb_id
    return jsonify(fb_token=fb_token, fb_id=fb_id)


@routes.route('/users/<uniq_id>/devices/<udid>/fb', methods=['POST',])
@requires_auth
def post_user_fb(uniq_id, udid):
    """
    Flow handler for user's login to FB on a device
    - Checks to see if he is already logged in to FB elsewhere
    - Associates current device with that user account if true
    - If not, just updates user facebook creds
    """
    # # invalidate friends cards, carousels and profile cache on user login
    # cleared_cache = clear_cards_carousels_cache_login(uniq_id)

    user, device = user_device(uniq_id, udid)
    form = FacebookLoginForm(request.form)
    if not form.validate_on_submit():
        return make_400(form.errors)

    if current_app.config.get('APPLUVR_MULTI_DEVICE', None):
        # Handle multi-device use case
        fb_user = User.load(form.fb_id.data)
        if not fb_user:
            # Create fb user, load up the user with existing creds that are available
            current_app.logger.debug('Fb user %s being created' % form.fb_id.data)
            fb_user = User(uniq_id=form.fb_id.data, name=form.name.data, email=form.email.data, fb_token=form.fb_token.data, fb_id=form.fb_id.data)
            if user.interests is not None and len(user.interests) > 0:
                # If the existing user has valid interests
                # which may be the case of a v1 user
                # migrate his interests forward
                current_app.logger.debug('v1 user interests carried forward')
                fb_user.interests = user.interests
            if not fb_user.fb_login:
                fb_user.fb_login = int(time.time())
            fb_user._id = form.fb_id.data
            try:
                fb_user.update()
                # invalidate friends cards, carousels and profile cache on user login
                cleared_cache = clear_cards_carousels_cache_login(uniq_id)
            except couchdb.http.ResourceConflict:
                current_app.logger.debug('bad mojo, unable to user')
                return make_conflict_409(form.fb_id.data)
        else:
            current_app.logger.debug('Fb user %s already exists' % fb_user._id)
        # updates the device references to add this user
        # and removes references to the old user
        current_app.logger.debug('updating device refs from old user to new user')
        update_device(udid)

        # TODO: Migrate likes and comments
        # May need to keep old user around if like/comment migration is an async task

        # Delete or anonymize old user
        current_app.logger.debug('nuking old user')
        delete_user(uniq_id)
    else:
        # Handle single device use cases
        if hasattr(form, 'name'):
            #Android Flow
            user.name = form.name.data
            user.email = form.email.data
            user.fb_id = form.fb_id.data
            user.fb_token = form.fb_token.data
            if not user.fb_login:
                user.fb_login = int(time.time())
            try:
                user.update()
                # invalidate friends cards, carousels and profile cache on user login
                cleared_cache = clear_cards_carousels_cache_login(uniq_id)
            except couchdb.http.ResourceConflict:
                current_app.logger.error('Unable to update users Facebook credentials during login')
                return make_conflict_409(form.fb_id.data)
        else: 
            #IOS App Flow
            ##Get Details of user from FB's Graph API
            fb_graph_url = "https://graph.facebook.com/me?access_token=%s"%form.fb_token.data
            r = requests.get(fb_graph_url)
            if r.status_code == 200:
                fb_user = r.json
                user.name = fb_user.get('name')
                user.fb_id = fb_user.get('id')
                user.email = fb_user.get('email',None)
                user.fb_token = form.fb_token.data
                if not user.fb_login:
                    user.fb_login = int(time.time())

                try:
                    user.update()
                    # invalidate friends cards, carousels and profile cache on user login
                    cleared_cache = clear_cards_carousels_cache_login(uniq_id)
                except couchdb.http.ResourceConflict:
                    current_app.logger.error('Unable to update users Facebook credentials during login')
                    return make_conflict_409(form.fb_id.data)
            else:
                current_app.logger.error('FB Graph API failed to connect. Status %s'%r.status_code)
                return make_conflict_409(form.fb_token.data)
    current_app.logger.debug('retrieving user profile details')
    return get_user_details(udid)

@routes.route('/users/<uniq_id>/devices/<udid>/fb/logout', methods=['POST','PUT',])
@requires_auth
def delete_user_fb_x(uniq_id, udid):
    """
    Logs a user out of FB on a device.
    Anonymizes the user if it is his only device.
    Otherwise, creates a new anonymous user, passes the user creds to client.
    """

    user, device = user_device(uniq_id, udid)
    ##cache.delete_memoized(get_user_fb, uniq_id, udid)
    # resigns user in as a new user
    if os.environ.has_key('REDISTOGO_URL'):
        urlparse.uses_netloc.append('redis')
        url = urlparse.urlparse(os.environ['REDISTOGO_URL'])
        REDIS = Redis(host=url.hostname, port=url.port, db=0, password=url.password)
        redis = REDIS
        print 'Redis parameters are %s (hostname), %s (port), %s (password)' % (url.hostname, url.port, url.password)
    else:
        redis = Redis()

  
    redis.hset('count.'+uniq_id, 'mf', "1347511521")
    redis.hset('count.'+uniq_id, 'mfa', "1347511521")
    redis.hdel('count.'+uniq_id,'mf')
    redis.hdel('count.'+uniq_id,'mfa')


    # invalidate friends cards, carousels and profile cache on user logout
    cleared_cache = clear_cards_carousels_cache_logout(uniq_id)


    if current_app.config.get('APPLUVR_MULTI_DEVICE', None):
        return get_user_details(udid, mode='logout')
    else:
        only_mf_notification = MfNotification.load("only_mf_notification."+uniq_id)
        only_mfa_notification = MfaNotification.load("only_mfa_notification."+uniq_id)
        NegInterests = UserNegativeInterests.load("NegInterests."+uniq_id)
        if not NegInterests:
            pass
        else:
            couch.delete(NegInterests)
        if not only_mf_notification:
            pass
        else:
            couch.delete(only_mf_notification)
        if not only_mfa_notification:
            pass  
        else:
            couch.delete(only_mfa_notification)

        # Single user, blow away his comments
        delete_all_user_comments(user.uniq_id)
        #Cache Invalidation

        # Clear out the rest of his personalized details
        user.name = user.email = user.fb_token = user.fb_id = None
        user.interests = []
        user.fb_login = None
        user.apps_liked = None
        user.apps_disliked = None
        user.first_name = None
        user.last_name = None

        try:
            user.update()
        except couchdb.http.ResourceConflict:
            current_app.logger.error('Unable to update users Facebook credentials during login')
            return make_conflict_409(form.fb_id.data)
        return get_user_details(udid)

@routes.route('/user/<uniq_id>/uncache', methods=['GET',])
def clearuser_and_friendcache_app_install(uniq_id):   

        user = User.load(uniq_id)
        if user is None:
            abort(404)
        
        usrplatform, usrcarrier = get_user_device_carrier_platform(user)
        device = ','.join([link['href'] for link in user.links if link['rel'] == 'device'])
      
        cache.delete_memoized(get_user_apps, uniq_id)
        cache.delete_memoized(get_all_user_comments, uniq_id)         
        cache.delete_memoized(get_cached_user_all_my_apps, uniq_id, platform=usrplatform) 
        cache.delete_memoized(get_only_new_friends_apps_notification, uniq_id, unicode(device))
        cache.delete_memoized(get_cached_user_only_friends_apps, uniq_id, usrplatform)
        cache.delete_memoized(get_cached_user_only_friends_recent, uniq_id, 'True')
        cache.delete_memoized(get_cached_user_only_friends_recent, uniq_id, 'False')
        #invalidate my_apps, only_mfa, only_mf carousel on install of app.
        #current_app.logger.debug("@@@@@@@@@%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
        cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
        cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
        cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=False, platform=usrplatform)
        cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=True, platform=usrplatform)
        cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
        cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
        cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, block=False, debug=False)
        cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, block=True, debug=True)

        # cache.delete_memoized(fetch_recommended_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), platform=usrplatform,auth_pwd=auth_pwd,cache=False)
        # cache.delete_memoized(fetch_recommended_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), platform=usrplatform, auth_pwd=auth_pwd,cache=True)
        # cache.delete_memoized(fetch_recommended_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), platform=unicode(usrplatform),auth_pwd=auth_pwd,cache=False)
        # cache.delete_memoized(fetch_recommended_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), platform=unicode(usrplatform),auth_pwd=auth_pwd,cache=True)

        #current_app.logger.debug("===> %s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
        #invalidate friend card details without platform as part of url.
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=usrplatform)
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=usrplatform)
                
        #for All Friends, invalidate get_cached_user_only_friends_recent
        all_appuvr_fb_friends = user.fb_friends()
        for userid in all_appuvr_fb_friends: 
            friend_obj = User.load(userid)
            if friend_obj is not None: 

                friendudid = ','.join([link['href'] for link in friend_obj.links if link['rel'] == 'device'])           
                platform, carrier = get_user_device_carrier_platform(friend_obj)
       
                cache.delete_memoized(get_cached_user_only_friends_apps, unicode(userid), platform)
                cache.delete_memoized(get_only_new_friends_apps_notification, unicode(userid), unicode(friendudid))
                cache.delete_memoized(get_all_user_comments, unicode(userid))
                cache.delete_memoized(get_cached_user_only_friends_recent, unicode(userid), 'True')
                cache.delete_memoized(get_cached_user_only_friends_recent, unicode(userid), 'False')
                #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform,userid))             
                cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
                cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
                #invalidate my_apps , only_mfa, only_mf carousel on logout
                #current_app.logger.debug("@@@@@@@@@%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))                
                cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
                cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, debug=True, platform=unicode(platform))

                cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, block=False, debug=False)
                cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, block=True, debug=True)

                # cache.delete_memoized(fetch_recommended_apps, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), platform=platform,auth_pwd=auth_pwd,cache=False)
                # cache.delete_memoized(fetch_recommended_apps, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), platform=platform, auth_pwd=auth_pwd,cache=True)
                # cache.delete_memoized(fetch_recommended_apps, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), platform=unicode(platform),auth_pwd=auth_pwd,cache=False)
                # cache.delete_memoized(fetch_recommended_apps, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), platform=unicode(platform),auth_pwd=auth_pwd,cache=True)

                #invalidate friend card details without platform as part of url.
                cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=platform)
                cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=platform)
                #current_app.logger.debug("==>%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,userid,auth_pwd,usrplatform,uniq_id))
                cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
                cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
                #invalidate friend card details without platform as part of url.
                cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=platform)
                cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=platform)
                
        current_app.logger.debug("@@@@@ successfully invalidated %s's friends apps cache  " %uniq_id)
        return jsonify(status=True)


@routes.route('/user/<uniq_id>/uncache/logout', methods=['GET',])
def clear_cards_carousels_cache_logout(uniq_id): 
    user = User.load(uniq_id)
    if user is None:
        abort(404)

    # get user commented apps
    keys=[]
    keys.append(uniq_id)
    rows = Comment.view('comment/user_comments', keys=keys)
    comments = [comment.toDict() for comment in rows]
    user_commented_apps = [each.get('pkg').encode('ascii') for each in comments]
    
    usrplatform, usrcarrier = get_user_device_carrier_platform(user)
    device = ','.join([link['href'] for link in user.links if link['rel'] == 'device'])  
    deviceobj = Device.load(device)
    if not deviceobj:
        my_apps=[]
    else:
        my_apps=deviceobj.apps_installed

    recs = fetch_appo_data(APPLUVR_VIEW_SERVER, uniq_id, unicode(device), platform=unicode(usrplatform), auth_pwd=auth_pwd) 
    rec_data =  recs.get('recos')
    rec_apps = [apps.get('package_name') for apps in rec_data]
    # user liked and disliked apps.    
    apps = user.apps_liked + user.apps_disliked + user_commented_apps+my_apps+rec_apps
    app_card_invalidating_apps = list(set(apps))

    cache.delete_memoized(get_cached_user_only_friends_recent, uniq_id, 'True')
    cache.delete_memoized(get_cached_user_only_friends_recent, uniq_id, 'False') 
    cache.delete_memoized(get_cached_user_only_friends_apps, uniq_id, usrplatform)   
    cache.delete_memoized(get_only_new_friends_apps_notification, uniq_id, unicode(device))      
    cache.delete_memoized(get_only_new_friends_notification, uniq_id, unicode(device))    
    cache.delete_memoized(get_cached_user_all_my_apps, uniq_id, platform=usrplatform)
    cache.delete_memoized(get_user_fb_pic,uniq_id)        
    cache.delete_memoized(get_user_fb_profile, uniq_id)  
    cache.delete_memoized(get_all_user_comments, uniq_id)
    cache.delete_memoized(get_user_apps, uniq_id)
    cache.delete_memoized(get_user_profile, uniq_id)   
    #invalidate my_apps , only_mfa, only_mf carousel on logout
    #current_app.logger.debug("@@@@@@@@@%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
    cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=False, platform=usrplatform)
    cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=True, platform=usrplatform)
    cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, block=False, debug=False)
    cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, block=True, debug=True)
    
    # cache.delete_memoized(fetch_recommended_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), platform=usrplatform,auth_pwd=auth_pwd,cache=False)
    # cache.delete_memoized(fetch_recommended_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), platform=usrplatform, auth_pwd=auth_pwd,cache=True)
    # cache.delete_memoized(fetch_recommended_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), platform=unicode(usrplatform),auth_pwd=auth_pwd,cache=False)
    # cache.delete_memoized(fetch_recommended_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), platform=unicode(usrplatform),auth_pwd=auth_pwd,cache=True)

    #current_app.logger.debug("%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    #invalidate friend card details without platform as part of url.
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=usrplatform)
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=usrplatform)
    
    #invalidate app card cache on logout. 
    #current_app.logger.debug("===========>apps for app card invalidations : %s  : <=========="%(app_card_invalidating_apps))   
    for pkg in app_card_invalidating_apps:
        get_user_app_like
        cache.delete_memoized(get_user_app_like, uniq_id, unicode(pkg))        
        cache.delete_memoized(get_user_apps_friends_in_common_likes, uniq_id, unicode(pkg))
        cache.delete_memoized(get_user_app_dislike, uniq_id, unicode(pkg))
        cache.delete_memoized(get_user_app_comment, uniq_id, unicode(pkg))        
        cache.delete_memoized(get_user_apps_friends_in_common_comments, uniq_id, unicode(pkg))     
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), unicode(pkg), auth_pwd=auth_pwd, debug=False)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), unicode(pkg), auth_pwd=auth_pwd, debug=True)
        

    all_appuvr_fb_friends = user.fb_friends()
    for userid in all_appuvr_fb_friends:
        friend_obj = User.load(userid)
        if friend_obj is not None:
            friendudid = ','.join( [link['href'] for link in friend_obj.links if link['rel'] == 'device'] )          
            platform, carrier = get_user_device_carrier_platform(friend_obj) 

            frienddeviceobj= Device.load(friendudid)
            if not frienddeviceobj:
                friends_apps = []
            else:
                friends_apps = frienddeviceobj.apps_installed

            # get user commented apps
            keys1=[]
            keys1.append(userid)
            rows = Comment.view('comment/user_comments', keys=keys1)
            friends_comments = [comment.toDict() for comment in rows]
            friends_commented_apps = [each.get('pkg').encode('ascii') for each in friends_comments]
            # user liked and disliked apps.    
            apps = friend_obj.apps_liked + friend_obj.apps_disliked + friends_commented_apps + friends_apps            
            friends_app_card_invalidating_apps = list(set(apps)) 
                          
            cache.delete_memoized(get_only_new_friends_apps_notification, unicode(userid), unicode(friendudid))                       
            cache.delete_memoized(get_only_new_friends_notification, unicode(userid), unicode(friendudid))                  
            cache.delete_memoized(get_cached_user_only_friends_apps, unicode(userid), platform)  
            cache.delete_memoized(get_cached_user_only_friends_recent, unicode(userid), 'True')
            cache.delete_memoized(get_cached_user_only_friends_recent, unicode(userid), 'False')
            cache.delete_memoized(get_all_user_comments, unicode(userid))    

            #on user logout invalidate friends only_mf and only_mfa carousels.            
            cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
            cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
            cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, block=False, debug=False)
            cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, block=True, debug=True)
            #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform,userid)) 
                           
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
            #invalidate friend card details without platform as part of url.
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=platform)
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=platform)
            #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,userid,auth_pwd,usrplatform,uniq_id))
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
            #invalidate friend card details without platform as part of url.
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=platform)
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=platform)
            
            #invalidate app card cache on logout. 
            #current_app.logger.debug("===========>apps for app card invalidations : %s  : <=========="%(friends_app_card_invalidating_apps))   
            for pkg in friends_app_card_invalidating_apps:
                cache.delete_memoized(get_user_app_like, unicode(userid), unicode(pkg))
                cache.delete_memoized(get_user_apps_friends_in_common_likes, unicode(userid), unicode(pkg))
                cache.delete_memoized(get_user_app_dislike, unicode(userid), unicode(pkg))
                cache.delete_memoized(get_user_app_comment, unicode(userid), unicode(pkg))
                cache.delete_memoized(get_user_apps_friends_in_common_comments, unicode(userid), unicode(pkg))
                cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), unicode(pkg), auth_pwd=auth_pwd, debug=False)
                cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), unicode(pkg), auth_pwd=auth_pwd, debug=True)
            keys1 = []

    current_app.logger.debug("@@@@@ successfully invalidated %s's friends apps cache  " %uniq_id)
    return jsonify(status=True)  


@routes.route('/user/<uniq_id>/uncache/login', methods=['GET',])
def clear_cards_carousels_cache_login(uniq_id): 
    user = User.load(uniq_id)
    if user is None:
        abort(404)

    # get user commented apps
    keys=[]
    keys.append(uniq_id)
    rows = Comment.view('comment/user_comments', keys=keys)
    comments = [comment.toDict() for comment in rows]
    user_commented_apps = [each.get('pkg').encode('ascii') for each in comments]
    # user liked and disliked apps.    
    apps = user.apps_liked + user.apps_disliked + user_commented_apps
    app_card_invalidating_apps = list(set(apps))

    usrplatform, usrcarrier = get_user_device_carrier_platform(user)
    device = ','.join([link['href'] for link in user.links if link['rel'] == 'device']) 

    cache.delete_memoized(get_user_fb_pic,uniq_id)        
    cache.delete_memoized(get_user_fb_profile, uniq_id)  
    cache.delete_memoized(get_user_profile, uniq_id)         
    cache.delete_memoized(get_only_new_friends_apps_notification, uniq_id, unicode(device))  
    cache.delete_memoized(get_only_new_friends_notification, uniq_id, unicode(device)) 
    cache.delete_memoized(get_cached_user_only_friends_recent, uniq_id, 'True')
    cache.delete_memoized(get_cached_user_only_friends_recent, uniq_id, 'False')
    cache.delete_memoized(get_cached_user_only_friends_apps, uniq_id, usrplatform)   
    
    #on user login invalidate friends only_mf and only_mfa carousels.  
    cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))    
    cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=False, platform=usrplatform)
    cache.delete_memoized(fetch_my_apps, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=True, platform=usrplatform)       
    cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, block=False, debug=False)
    cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, block=True, debug=True)

    #current_app.logger.debug("%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    #invalidate friend card details without platform as part of url.
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=usrplatform)
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=usrplatform)

    #invalidate app card cache on logout.    
    #current_app.logger.debug("===========>apps for app card invalidations : %s  : <=========="%(app_card_invalidating_apps))
    for pkg in app_card_invalidating_apps:
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), unicode(pkg), auth_pwd=auth_pwd, debug=False)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), unicode(pkg), auth_pwd=auth_pwd, debug=True)

    all_appuvr_fb_friends = user.fb_friends()
    current_app.logger.debug("APPLUVR FB ONLINE FRIENDS :%s"%all_appuvr_fb_friends)
    for userid in all_appuvr_fb_friends:
        friend_obj = User.load(userid)
        if friend_obj is not None:
            friendudid = ','.join( [link['href'] for link in friend_obj.links if link['rel'] == 'device'] )          
            platform, carrier = get_user_device_carrier_platform(friend_obj)

            # get user commented apps
            keys1=[]
            keys1.append(userid)
            rows = Comment.view('comment/user_comments', keys=keys1)
            friends_comments = [comment.toDict() for comment in rows]
            friends_commented_apps = [each.get('pkg').encode('ascii') for each in friends_comments]
            # user liked and disliked apps.    
            apps = friend_obj.apps_liked + friend_obj.apps_disliked + friends_commented_apps
            friends_app_card_invalidating_apps = list(set(apps))

            cache.delete_memoized(get_only_new_friends_apps_notification, unicode(userid), unicode(friendudid))
            cache.delete_memoized(get_only_new_friends_notification, unicode(userid), unicode(friendudid))
            cache.delete_memoized(get_cached_user_only_friends_apps, unicode(userid), platform)  
            cache.delete_memoized(get_cached_user_only_friends_recent, unicode(userid), 'True')
            cache.delete_memoized(get_cached_user_only_friends_recent, unicode(userid), 'False')
            cache.delete_memoized(get_all_user_comments, unicode(userid))

            #on user login invalidate friends only_mf and only_mfa carousels.            
            cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
            cache.delete_memoized(fetch_only_mfa, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
            cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, block=False, debug=False)
            cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), auth_pwd=auth_pwd, block=True, debug=True)
    
            #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform,userid))                
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
            #invalidate friend card details without platform as part of url.
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=platform)
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=platform)
            #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,userid,auth_pwd,usrplatform,uniq_id))
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
            #invalidate friend card details without platform as part of url.
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=platform)
            cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=platform)
            
            
            #invalidate app card cache on logout. 
            #current_app.logger.debug("===========>apps for app card invalidations : %s  : <=========="%(friends_app_card_invalidating_apps))   
            for pkg in friends_app_card_invalidating_apps:
                cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), unicode(pkg), auth_pwd=auth_pwd, debug=False)
                cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friendudid), unicode(pkg), auth_pwd=auth_pwd, debug=True)
            keys1 = []
    
    current_app.logger.debug("@@@@@ successfully invalidated %s's friends apps cache  " %uniq_id)
    return jsonify(status=True)  
# Deprecated
@routes.route('/users/<id>/apps', methods=['GET',])
@support_jsonp
@support_etags
@print_timing
@requires_auth
def get_user_apps_uncache(id):
    return get_user_apps(id)


@cache.memoize(BALI_CACHE_TIME)
def get_user_apps(id=None): 
    user = User.load(id)
    if user is None:
        abort(404)
    all_apps = []
    for x in dict(user.apps()).values():
        for y in x:
            all_apps.append(y)
    return jsonify(data=all_apps, _count=len(all_apps))


@routes.route('/users/<uniq_id>/fb/feed', methods=['POST',])
@support_jsonp
@requires_auth
def post_user_fb_wall(uniq_id):
    args = MultiDict(request.json) if request.json else request.form
    form = UserFBPostForm(args)
    if not form.validate_on_submit():
        return make_400(form.errors)
    user = User.load(uniq_id)
    if user is None:
        abort(404)
    # Temporarily use a fallback token for testing purposes
    token = user.fb_token
    if token is None:
        abort(401)
    if user.fb_id is None:
        abort(401)
    fml_endpoint = FB_WALL_POST % user.fb_id
    #d(fml_endpoint)
    try:
        d('Opening FB POST request')
        appluvr_url = 'www.appluvr.com/vz'
        r = requests.post(fml_endpoint, params=dict(access_token=token,message=form.message.data, icon=form.picture.data, actions='{"name":"Meet Appluvr","link":"http://www.appluvr.com/vz"}'))
        #d(r.status_code)
        #d(r.content)
        if r.status_code == 200:
            return jsonify(fb_post=simplejson.loads(r.content))
        #cache.set(fml_endpoint, fb_data, 30 * 60)
    except Exception as e:
        d(e)
    return r.content, r.status_code


@routes.route('/users/<uniq_id>/devices/<udid>/appo/profile', methods=['GET',])
@requires_auth
def get_user_appo_profile(uniq_id, udid):
    user, device = user_device(uniq_id, udid)
    return jsonify(user.appo_profile())

@routes.route('/users/<uniq_id>/devices/<udid>/appo/profile', methods=['POST',])
@requires_auth
def post_user_appo_profile(uniq_id, udid):
    user, device = user_device(uniq_id, udid)
    source_url = "".join([APPO_BASE_URL, APPO_VERSION, APPO_PROFILE])
    #r = requests.post(source_url, headers={'Content-type':'application/json'},data=user.profile)
    profile = simplejson.dumps(user.appo_profile())
    current_app.logger.debug("Apppo Profile to post %s"%profile)
    r = requests.post(source_url, params=dict(json=profile), auth=APPO_BASIC_AUTH)
    current_app.logger.debug("Appo Profile Post Status code %s"%r.status_code)
    # Delete cached entry
    ##cache.delete_memoized(get_user_appo_profile,uniq_id, udid)
    return current_app.make_response(('', r.status_code))

#--------------------------------------------------------------------------------------#

@routes.route('/users/<uniq_id>/apps/<pkg>/comment', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
def get_user_app_comment_uncache(uniq_id, pkg):
    return get_user_app_comment(uniq_id, pkg)

@cache.memoize(BALI_CACHE_TIME)
def get_user_app_comment(uniq_id=None, pkg=None):
    user = User.load(uniq_id)
    if not user:
        abort(404)
    if not pkg:
        abort(400)
    comment = Comment.load('%s+%s' %(uniq_id,pkg))
    if not comment:
        abort(404)
    response = jsonify(comment.toDict())
    return response


@routes.route('/users/<uniq_id>/apps/<pkg>/comment', methods=['POST', 'PUT', ])
@support_jsonp
@requires_auth
def update_users_app_comment(uniq_id, pkg):
    user = User.load(uniq_id)    
    if not user:
        abort(404)
    if not pkg:
        abort(400)

    device = ','.join([link['href'] for link in user.links if link['rel'] == 'device'])
    device_obj = Device.load(device)    
    if not device_obj:
        abort(400)
    usrplatform = device_obj.get_platform()

    #current_app.logger.debug("%s:%s:%s:"%(uniq_id, pkg, usrplatform))
    cache.delete_memoized(get_user_app_comment,uniq_id, pkg)
    cache.delete_memoized(get_all_user_comments, uniq_id)
    cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), pkg, auth_pwd=auth_pwd, debug=False)  
    cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), pkg, auth_pwd=auth_pwd, debug=True)    
    #current_app.logger.debug("%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    #invalidate friend card details without platform as part of url.
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=usrplatform)
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=usrplatform)
    
    args = MultiDict(request.json) if request.json else request.form
    form = CommentCreateForm(args)
    if not form.validate_on_submit():
        return make_400(form.errors)
    # Create/update new comment
    comment = Comment.load('%s+%s' %(uniq_id,pkg))
    # Check to see if comment exists, if not create
    if not comment:
        comment = Comment(uniq_id=uniq_id,pkg=pkg,comment=form.comment.data)
        comment._id = '%s+%s' %(uniq_id,pkg)
    # Update fields
    for key in args:
        comment[key] = args[key]
    comment.update()
    d('Updated comment with details: %s' % comment)

    all_appuvr_fb_friends = user.fb_friends()
    for userid in all_appuvr_fb_friends:
        friend = User.load(userid)
        if friend is None:
            abort(404)
        friend_device = ','.join([link['href'] for link in friend.links if link['rel'] == 'device'])
        friend_device_obj = Device.load(friend_device)
        platform = friend_device_obj.get_platform()

        #current_app.logger.debug("%s:%s:%s:"%(uniq_id, pkg, usrplatform))
        cache.delete_memoized(get_user_apps_friends_in_common_comments, unicode(userid), pkg)
        cache.delete_memoized(get_all_user_comments, unicode(userid))
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), pkg, auth_pwd=auth_pwd, debug=False)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), pkg, auth_pwd=auth_pwd, debug=True)
        
        #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform,userid))                
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
        #invalidate friend card details without platform as part of url.
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=platform)
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=platform)
        #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,userid,auth_pwd,usrplatform,uniq_id))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
        #invalidate friend card details without platform as part of url.
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=platform)
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=platform)
    
    response = current_app.make_response(jsonify(data=comment.toDict()))
    response.status_code = 201
    response.headers['Location']=url_for('.get_user_app_comment_uncache',uniq_id=uniq_id, pkg=pkg, _external=True)  

    return response

@routes.route('/users/<uniq_id>/apps/<pkg>/comment', methods=['DELETE', ])
@support_jsonp
@requires_auth
def delete_user_app_comments(uniq_id, pkg):
    user = User.load(uniq_id)    
    if not user:
        abort(404)
    if not pkg:
        abort(400)

    device = ','.join([link['href'] for link in user.links if link['rel'] == 'device'])
    device_obj = Device.load(device)    
    if not device:
        abort(400)

    usrplatform = device_obj.get_platform()

    cache.delete_memoized(get_user_app_comment,uniq_id, pkg)
    cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), pkg, auth_pwd=auth_pwd, debug=False)  
    cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), pkg, auth_pwd=auth_pwd, debug=True) 
    #current_app.logger.debug("%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    #invalidate friend card details without platform as part of url.
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=usrplatform)
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=usrplatform)

    comment = Comment.load('%s+%s' %(uniq_id,pkg))
    if not comment:
        abort(404)
    couch.delete(comment) 

    all_appuvr_fb_friends = user.fb_friends()
    for userid in all_appuvr_fb_friends:
        friend = User.load(userid)
        if friend is None:
            abort(404)
        friend_device = ','.join([link['href'] for link in friend.links if link['rel'] == 'device'])
        friend_device_obj = Device.load(friend_device)
        platform = friend_device_obj.get_platform()
        
        cache.delete_memoized(get_user_apps_friends_in_common_comments, unicode(userid), pkg)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), pkg, auth_pwd=auth_pwd, debug=False)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), pkg, auth_pwd=auth_pwd, debug=True)
        #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform,userid))                
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
        #invalidate friend card details without platform as part of url.
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=platform)
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=platform)
        #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,userid,auth_pwd,usrplatform,uniq_id))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
        #invalidate friend card details without platform as part of url.
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=platform)
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=platform)

    response = current_app.make_response(jsonify(uniq_id=user._id, pkg=pkg))
    response.status_code = 204
    return response


#--------------------------------------------------------------------------------------#
@routes.route('/users/<uniq_id>/apps/<pkg>/like', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
def get_user_app_like_uncache(uniq_id, pkg):
    return get_user_app_like(uniq_id, pkg)

@cache.memoize(BALI_CACHE_TIME)
def get_user_app_like(uniq_id=None, pkg=None):
    user = User.load(uniq_id)
    if not user:
        abort(404)
    if not pkg:
        abort(400)
    pkgs = user.apps_liked
    #d(pkg)
    #d(pkgs)
    if pkg in pkgs:
        return current_app.make_response(jsonify(uniq_id=user._id, pkg=pkg, like=True))
    else:
        abort(404)


@routes.route('/users/<uniq_id>/apps/<pkg>/like', methods=['POST', 'PUT', ])
@requires_auth
def update_users_app_like(uniq_id, pkg):
    user = User.load(uniq_id)    
    if not user:
        abort(404)
    if not pkg:
        abort(400)
    
    if not pkg in user.apps_liked:
        #d(user.apps_liked)
        #d(pkg)
        user.apps_liked.append(pkg)
        user.update()
        #d(user.apps_liked)
    # Update Apps table with like information
    app = App.load(pkg)
    if not app:
        app = App()
        app._id = pkg
        app.update()
    if app and not uniq_id in app.liked:
        #d(app.liked)
        #d(uniq_id)
        if not app.liked:
            app.liked = []
        app.liked.append(uniq_id)
        app.update()
        #d(app.liked)

    device = ','.join([link['href'] for link in user.links if link['rel'] == 'device'])
    device_obj = Device.load(device)    
    if not device_obj:
        abort(400)

    usrplatform = device_obj.get_platform()

    cache.delete_memoized(get_user_profile,uniq_id)
    cache.delete_memoized(get_user_app_like,uniq_id, pkg)
    cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), pkg, auth_pwd=auth_pwd, debug=False)
    cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), pkg, auth_pwd=auth_pwd, debug=True)
    #current_app.logger.debug("%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    #invalidate friend card details without platform as part of url.
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=usrplatform)
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=usrplatform)
    
    all_appuvr_fb_friends = user.fb_friends()
    for userid in all_appuvr_fb_friends:
        friend = User.load(userid)
        if friend is None:
            abort(404)
        friend_device = ','.join([link['href'] for link in friend.links if link['rel'] == 'device'])
        friend_device_obj = Device.load(friend_device)
        platform = friend_device_obj.get_platform()

        cache.delete_memoized(get_user_apps_friends_in_common_likes, unicode(userid), pkg)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), pkg, auth_pwd=auth_pwd, debug=False)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), pkg, auth_pwd=auth_pwd, debug=True)
        #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform,userid))                
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
        #invalidate friend card details without platform as part of url.
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=platform)
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=platform)
        #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,userid,auth_pwd,usrplatform,uniq_id))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
        #invalidate friend card details without platform as part of url.
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=platform)
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=platform)
    
    response = current_app.make_response(jsonify(id=user._id, pkg=pkg, like=True))
    response.status_code = 201
    response.headers['Location']=url_for('.get_user_app_like_uncache',uniq_id=user._id, pkg=pkg, _external=True)
    #cache.delete_memoized(get_user_app_like,uniq_id=uniq_id, pkg=pkg)
    return response


@routes.route('/users/<uniq_id>/apps/<pkg>/like', methods=['DELETE', ])
@requires_auth
def delete_user_app_like(uniq_id, pkg):
    user = User.load(uniq_id)    
    if not user:
        abort(404)
    if not pkg:
        abort(400)
    
    if pkg in user.apps_liked:
        user.apps_liked.remove(pkg)
    user.update()
    # Update Apps table with like information
    app = App.load(pkg)
    if not app:
        app = App()
        app._id = pkg
        app.update()
    if app and uniq_id in app.liked:
        app.liked.remove(uniq_id)
        app.update()

    device = ','.join([link['href'] for link in user.links if link['rel'] == 'device'])
    device_obj = Device.load(device)   
    if not device_obj:
        abort(400)

    usrplatform = device_obj.get_platform()

    cache.delete_memoized(get_user_profile,uniq_id)
    cache.delete_memoized(get_user_app_like,uniq_id,pkg)
    cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), pkg, auth_pwd=auth_pwd, debug=False)
    cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), pkg, auth_pwd=auth_pwd, debug=True)
    #current_app.logger.debug("%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    #invalidate friend card details without platform as part of url.
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=usrplatform)
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=usrplatform)
    
    all_appuvr_fb_friends = user.fb_friends()
    for userid in all_appuvr_fb_friends:
        friend = User.load(userid)
        if friend is None:
            abort(404)
        friend_device = ','.join([link['href'] for link in friend.links if link['rel'] == 'device'])
        friend_device_obj = Device.load(friend_device)
        platform = friend_device_obj.get_platform()

        cache.delete_memoized(get_user_apps_friends_in_common_likes, unicode(userid), pkg)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), pkg, auth_pwd=auth_pwd, debug=False)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), pkg, auth_pwd=auth_pwd, debug=True)
        #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform,userid))                
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
        #invalidate friend card details without platform as part of url.
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=platform)
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=platform)
        #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,userid,auth_pwd,usrplatform,uniq_id))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
        #invalidate friend card details without platform as part of url.
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=platform)
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=platform)
    
    response = current_app.make_response(jsonify(uniq_id=user._id, pkg=pkg))
    response.status_code = 204
    #cache.delete_memoized(get_user_app_like,uniq_id=uniq_id, pkg=pkg)
    return response


@routes.route('/users/<uniq_id>/apps/<pkg>/dislike', methods=['GET',])
@support_jsonp
@support_etags
@requires_auth
def get_user_app_dislike_uncache(uniq_id, pkg):
    return get_user_app_dislike(uniq_id, pkg)

@cache.memoize(BALI_CACHE_TIME)
def get_user_app_dislike(uniq_id=None, pkg=None):
    user = User.load(uniq_id)
    if not user:
        abort(404)
    if not pkg:
        abort(400)
    pkgs = user.apps_disliked
    #d(pkg)
    #d(pkgs)
    if pkg in pkgs:
        return current_app.make_response(jsonify(uniq_id=user._id, pkg=pkg, dislike=True))
    else:
        abort(404)

@routes.route('/users/<uniq_id>/apps/<pkg>/dislike', methods=['POST', 'PUT', ])
@requires_auth
def update_users_app_dislike(uniq_id, pkg):
    user = User.load(uniq_id)    
    if not user:
        abort(404)
    if not pkg:
        abort(400)

    if not pkg in user.apps_disliked:
        user.apps_disliked.append(pkg)
        user.update()
    # Update Apps table with dislike information
    app = App.load(pkg)
    if not app:
        app = App()
        app._id = pkg
        app.update()
    if app and not uniq_id in app.disliked:
        if not app.disliked:
            app.disliked = []
        app.disliked.append(uniq_id)
        app.update()

    device = ','.join([link['href'] for link in user.links if link['rel'] == 'device'])
    device_obj = Device.load(device)
    if not device_obj:
        abort(400)
    usrplatform = device_obj.get_platform()

    cache.delete_memoized(get_user_profile,uniq_id)
    cache.delete_memoized(get_user_app_dislike,uniq_id, pkg)
    cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), pkg, auth_pwd=auth_pwd, debug=False)
    cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), pkg, auth_pwd=auth_pwd, debug=True)
    #current_app.logger.debug("%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    #invalidate friend card details without platform as part of url.
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=usrplatform)
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=usrplatform)

    all_appuvr_fb_friends = user.fb_friends()
    for userid in all_appuvr_fb_friends:
        friend = User.load(userid)
        if friend is None:
            abort(404)
        friend_device = ','.join([link['href'] for link in friend.links if link['rel'] == 'device'])
        friend_device_obj = Device.load(friend_device)
        platform = friend_device_obj.get_platform()

        cache.delete_memoized(get_user_apps_friends_in_common_likes, unicode(userid), pkg)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), pkg, auth_pwd=auth_pwd, debug=False)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), pkg, auth_pwd=auth_pwd, debug=True)
        #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform,userid))                
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
        #invalidate friend card details without platform as part of url.
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=platform)
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=platform)
        #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,userid,auth_pwd,usrplatform,uniq_id))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
        #invalidate friend card details without platform as part of url.
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=platform)
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=platform)
    
    response = current_app.make_response(jsonify(id=user._id, pkg=pkg, dislike=True))
    response.status_code = 201
    response.headers['Location']=url_for('.get_user_app_dislike_uncache',uniq_id=user._id, pkg=pkg, _external=True)
    #cache.delete_memoized(get_user_app_dislike,uniq_id=uniq_id, pkg=pkg)
    return response

@routes.route('/users/<uniq_id>/apps/<pkg>/dislike', methods=['DELETE', ])
@requires_auth
def delete_user_app_dislike(uniq_id, pkg):
    user = User.load(uniq_id)    
    if not user:
        abort(404)
    if not pkg:
        abort(400)
    
    if pkg in user.apps_disliked:
        user.apps_disliked.remove(pkg)
    user.update()
    # Update Apps table with dislike information
    app = App.load(pkg)
    if not app:
        app = App()
        app._id = pkg
        app.update()
    if app and uniq_id in app.disliked:
        app.disliked.remove(uniq_id)
        app.update()

    device = ','.join([link['href'] for link in user.links if link['rel'] == 'device'])
    device_obj = Device.load(device)

    if not device_obj:
        abort(400)

    usrplatform = device_obj.get_platform()

    cache.delete_memoized(get_user_profile,uniq_id)
    cache.delete_memoized(get_user_app_dislike,uniq_id, pkg)
    cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), pkg, auth_pwd=auth_pwd, debug=False)
    cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), pkg, auth_pwd=auth_pwd, debug=True)
    #current_app.logger.debug("%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
    #invalidate friend card details without platform as part of url.
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=False, platform=usrplatform)
    cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", None, auth_pwd=auth_pwd, debug=True, platform=usrplatform)

    all_appuvr_fb_friends = user.fb_friends()
    for userid in all_appuvr_fb_friends:
        friend = User.load(userid)
        if friend is None:
            abort(404)
        friend_device = ','.join([link['href'] for link in friend.links if link['rel'] == 'device'])
        friend_device_obj = Device.load(friend_device)
        platform = friend_device_obj.get_platform()

        cache.delete_memoized(get_user_apps_friends_in_common_likes, unicode(userid), pkg)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), pkg, auth_pwd=auth_pwd, debug=False)
        cache.delete_memoized(fetch_app_card, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), pkg, auth_pwd=auth_pwd, debug=True)
        #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,uniq_id,auth_pwd,usrplatform,userid))                
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=unicode(usrplatform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=unicode(usrplatform))
        #invalidate friend card details without platform as part of url.
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=False, platform=platform)
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, uniq_id, "udid", friend=unicode(userid), auth_pwd=auth_pwd, debug=True, platform=platform)
        #current_app.logger.debug("%s:%s:%s:%s:%s"%(APPLUVR_VIEW_SERVER,userid,auth_pwd,usrplatform,uniq_id))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=unicode(platform))
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=unicode(platform))
        #invalidate friend card details without platform as part of url.
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=False, platform=platform)
        cache.delete_memoized(fetch_friend_card, APPLUVR_VIEW_SERVER, unicode(userid), "udid", friend=uniq_id, auth_pwd=auth_pwd, debug=True, platform=platform)

    response = current_app.make_response(jsonify(uniq_id=user._id, pkg=pkg))
    response.status_code = 204
    #cache.delete_memoized(get_user_app_dislike,uniq_id=uniq_id, pkg=pkg)
    return response


@routes.route('/users/<uniq_id>/block', methods=['GET', ])
@support_jsonp
@requires_auth
def get_users_blocked_list(uniq_id):
    user = User.load(uniq_id)
    if not user:
        abort(404)
    return jsonify(data=dict(blocked_friends=user.blocked_friends(),blocking_friends=user.blocking_friends()))

@routes.route('/advisors/<uniq_id>/block', methods=['POST', 'PUT', ])
@requires_auth
def update_advisors_blocked_list(uniq_id):
    user = User.load(uniq_id)
    if not user:
        abort(404)

    args = MultiDict(request.json) if request.json else request.form
    form = UserDisallowForm(args)
    if not form.validate_on_submit():
        return make_400(form.errors)
    blocked_friends = user.only_blocked_friends() 
    #blocked_advisors = user.only_blocked_advisors() 
    blocked_friends.append(form.blocked_friends.data)  
    #all_blocked_friends =  blocked_friends + blocked_advisors
    all_blocked_friends =  blocked_friends 
    perms = UserDisallow.load('perms.'+uniq_id)
    if not perms:
        perms = UserDisallow(me = uniq_id, blocked_friends = ','.join(all_blocked_friends))
        perms.me = uniq_id
        perms._id = 'perms.'+uniq_id
    # load up the args
    for key in args:
        if key == 'blocked_friends':
           perms['blocked_friends'] = ','.join(all_blocked_friends)
        else:
            perms[key] = args[key]
    # Commit to database
    perms.update()
    # Put together response
    response = current_app.make_response(jsonify(data=perms.toDict()))
    response.status_code = 201
    #cache.delete_memoized(get_users_blocked_list,uniq_id=uniq_id)
    #cache.delete_memoized(get_user_fb_friends,id=uniq_id)
    #cache.delete_memoized(get_user_friends_apps,id=uniq_id)
       
    return response

@routes.route('/friends/<uniq_id>/block', methods=['POST', 'PUT', ])
@requires_auth
def update_friends_blocked_list(uniq_id):
    user = User.load(uniq_id)
    if not user:
        abort(404)

    device = ','.join([link['href'] for link in user.links if link['rel'] == 'device'])
    device_obj = Device.load(device)
    if not device_obj:
        abort(404)

    usrplatform = device_obj.get_platform()
    
    cache.delete_memoized(get_cached_user_only_friends_recent, uniq_id, 'True')
    cache.delete_memoized(get_cached_user_only_friends_recent, uniq_id, 'False') 
    cache.delete_memoized(get_cached_user_only_friends_apps, uniq_id, usrplatform)   
    cache.delete_memoized(get_only_new_friends_apps_notification, uniq_id, unicode(device))      
    cache.delete_memoized(get_only_new_friends_notification, uniq_id, unicode(device))
    cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, block=False, debug=False)
    cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, block=True, debug=True)
    cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, block=False, debug=True)
    cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, uniq_id, unicode(device), auth_pwd=auth_pwd, block=True, debug=False)

    all_appuvr_fb_friends = user.fb_friends(False)
    for userid in all_appuvr_fb_friends:
        friend = User.load(userid)
        if friend is None:
            abort(404)
        friend_device = ','.join([link['href'] for link in friend.links if link['rel'] == 'device'])
        friend_device_obj = Device.load(friend_device)
        platform = friend_device_obj.get_platform()

        cache.delete_memoized(get_cached_user_only_friends_recent, unicode(userid), 'True')
        cache.delete_memoized(get_cached_user_only_friends_recent, unicode(userid), 'False') 
        cache.delete_memoized(get_cached_user_only_friends_apps, unicode(userid), platform)   
        cache.delete_memoized(get_only_new_friends_apps_notification, unicode(userid), unicode(friend_device))      
        cache.delete_memoized(get_only_new_friends_notification, unicode(userid), unicode(friend_device)) 
        cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), auth_pwd=auth_pwd, block=False, debug=False)
        cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), auth_pwd=auth_pwd, block=True, debug=True)
        cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), auth_pwd=auth_pwd, block=False, debug=True)
        cache.delete_memoized(fetch_only_friends, APPLUVR_VIEW_SERVER, unicode(userid), unicode(friend_device), auth_pwd=auth_pwd, block=True, debug=False)

    args = MultiDict(request.json) if request.json else request.form
    form = UserDisallowForm(args)
    if not form.validate_on_submit():
        return make_400(form.errors)

    blocked_advisors = user.only_blocked_advisors()
    #blocked_friends = user.only_blocked_friends()     
    blocked_advisors.append(form.blocked_friends.data)
    #all_blocked_friends =  blocked_advisors +  blocked_friends
    all_blocked_friends =  blocked_advisors
    perms = UserDisallow.load('perms.'+uniq_id)   
    if not perms:
        perms = UserDisallow(me = uniq_id, blocked_friends = ','.join(all_blocked_friends))
        perms.me = uniq_id
        perms._id = 'perms.'+uniq_id
    # load up the args
    for key in args:
        if key == 'blocked_friends':
           perms['blocked_friends'] = ','.join(all_blocked_friends)
        else:
            perms[key] = args[key]
    # Commit to database
    perms.update()
    # Put together response
    response = current_app.make_response(jsonify(data=perms.toDict()))
    response.status_code = 201
    #cache.delete_memoized(get_users_blocked_list,uniq_id=uniq_id)
    #cache.delete_memoized(get_user_fb_friends,id=uniq_id)
    #cache.delete_memoized(get_user_friends_apps,id=uniq_id)
    return response


@routes.route('/users/<uniq_id>/block', methods=['POST', 'PUT', ])
@requires_auth
def update_users_blocked_list(uniq_id):
    user = User.load(uniq_id)
    if not user:
        abort(404)

    args = MultiDict(request.json) if request.json else request.form
    form = UserDisallowForm(args)
    if not form.validate_on_submit():
        return make_400(form.errors)
    perms = UserDisallow.load('perms.'+uniq_id)
    if not perms:
        perms = UserDisallow()
        perms.me = uniq_id
        perms._id = 'perms.'+uniq_id
    # load up the args
    for key in args:
        perms[key] = args[key]
    # Commit to database
    perms.update()
    # Put together response
    response = current_app.make_response(jsonify(data=perms.toDict()))
    response.status_code = 201
    #cache.delete_memoized(get_users_blocked_list,uniq_id=uniq_id)
    #cache.delete_memoized(get_user_fb_friends,id=uniq_id)
    #cache.delete_memoized(get_user_friends_apps,id=uniq_id) 

    return response

#--------------------------------------------------------------------------------------#

@routes.route('/platform/settings',methods=['GET'])
@print_timing
@support_jsonp
@support_etags
@requires_auth
@cache.memoize(60)
def get_all_settings():
    return jsonify(data=[setting.toDict() for setting in Settings.view('settings/all_settings')])  #.all_settings()])

@routes.route('/platform/settings/<key>',methods=['GET'])
@print_timing
@support_jsonp
@support_etags
@requires_auth
@cache.memoize(60)
def get_setting(key):
    setting = Settings.load(key)
    if not setting:
        abort(404)
    return jsonify(setting.toDict())

@routes.route('/platform/settings/<key>', methods=['POST', 'PUT'])
@print_timing
@requires_auth
def update_settings(key):
    args = MultiDict(request.json) if request.json else request.form
    if not args['value']:
        abort(400)
    setting = Settings.load(key)
    if not setting:
        setting = Settings(key=key, value=args['value'])
        setting._id = key
    else:
        for k in args:
            setting[k] = args[k]
    setting.update()
    response = current_app.make_response(jsonify(key=key,value=setting.value))
    response.status_code = 201
    response.headers['Location']=url_for('.get_setting',key=key, _external=True)
    #cache.delete_memoized(get_setting,key=key)
    #cache.delete_memoized(carousel_setting)
    return response

@routes.route('/platform/settings/<key>',methods=['DELETE'])
def get_setting_key(key):
    setting = Settings.load(key)
    if not setting:
        abort(404)
    couch.delete(setting)
    response = current_app.make_response(jsonify(setting=key))
    response.status_code = 204
    #cache.delete_memoized(get_setting,key=key)
    return response

# Version number
@routes.route('/platform/version',methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@cache.memoize(60)
def ver():
    from appluvr import __version__
    return jsonify(version=str(__version__))

# About
@routes.route('/platform/about', methods=['GET',])
@support_jsonp
@support_etags
@cache.memoize(FULL_DAY)
def about_platform():
    import platform
    from appluvr import __version__
    return jsonify(appluvr=dict(version=str(__version__), routes=repr(current_app.url_map)),python=dict(version=platform.python_version(), implementation=platform.python_implementation()), server=dict(node=platform.node(),version=platform.version()) )


@routes.route('/platform/db', methods=['GET',])
def get_db_info():
    return jsonify(**couch.info())

@routes.route('/platform/db/compact', methods=['POST',])
def get_db_compact():
    return jsonify(status=couch.compact())

#--------------------------------------------------------------------------------------#

@routes.route('/rel/<rel>/<id>/', methods=['GET',])
@print_timing
@support_jsonp
@support_etags
@cache.memoize(60)
def get_rel_href(rel, id):
    if rel is None or id is None:
        abort(400)
    return url_map(rel, id)

import random

@routes.route('/test-cache/<int:num>', methods=['GET',])
@cache.memoize(60)
def zcache(num):
    return str(num + random.randrange(1,10))

# Echo test
@routes.route("/echo/<str>", methods=['GET', 'POST'])
@print_timing
@test_decorator
def echo(str='abc'):
    return request.data

@routes.route('/test-no-cache1/<int:num>', methods=['GET',])
def zncache(num):
    return str(num + random.randrange(1,10))

@routes.route('/', defaults={'path': ''})
@routes.route('/<path:path>')
def catch_all(path):
    return 'The resource you are trying to access at path: %s is not available.' % path


#--------------------------------------------------------------------------------------#
