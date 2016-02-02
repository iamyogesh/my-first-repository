# -*- coding: utf-8 -*-
from appluvr import d
from werkzeug import LocalProxy
from flask import current_app, json
from operator import itemgetter
d = LocalProxy(lambda: current_app.logger.debug)

all_promos = spam = {'com.lev.aaa': "fun, travel", 'com.lev.roadside': "travel", 'com.lev.sur': "fun, music", 'com.lev.mul' : "fun, food", 'com.lev.golf' : "fun, sport", 'com.lev.nfc' : 'shopping', 'com.lev.koi' : 'sports, education', 'com.lev.card' : 'shopping'}

my_interests = ['fun', 'music']

orig_list = ['com.'+str(i) for i in range(1,20)]

def itunesid_to_packagename(dict_in):
    str_json = json.dumps(dict_in)
    str_json = str_json.replace('itunes_id', 'package_name')
    return json.loads(str_json)


def inject_promos(orig_list, all_promos, my_interests, promo_order, afy_multiplier = 2, ha_multiplier = 2, carousel='hot_apps', my_apps=None):

    spam = all_promos
    eggs = {}
    filtered_packages = []

    d('Promos -> Interests list is ' + repr(spam))

    for key in spam:
        interests = spam[key] #.split(',')
        interests = [interest.strip() for interest in interests]
        for interest in interests:
            tmp = eggs.get(interest, [])
            tmp.append(str(key))
            eggs[interest] = tmp


    d('Interests -> Promos list is %s' % repr(eggs)) 
    if "" in my_interests: my_interests.remove("")
    d('Jon Does interests are %s' % repr(my_interests))

    promos = list(set([item for sublist in [eggs.get(interest,None) for interest in my_interests if eggs.get(interest)] for item in sublist])) if len(my_interests) else spam.keys() 
    #d('promolist -> %s'%promos)
    
    my_apps = [] if my_apps is None else my_apps
    orig_list_for_filter = itunesid_to_packagename(orig_list)
    orig_list_pkgs = [app.get('package_name') for app in orig_list_for_filter]   
    promos = list(set(promos)-set(my_apps))
    filtered_list_pkgs = list(set(orig_list_pkgs)-set(promos))

    for app in orig_list_for_filter:
        if app.get('package_name') in filtered_list_pkgs:
            filtered_packages.append(app)

    promos=[ promo for promo in promo_order if promo in promos] 
    d('Promos personalized for Jon Doe are %s' % repr(promos))

    afy = filtered_packages

    #print 'The 1 in k hot_apps multiplier is ' + repr(ha_multiplier)
    #print 'The 1 in k apps_for_you multiplier is ' + repr(afy_multiplier)

    if carousel is 'apps_for_you':

        #print 'Original apps_for_you feed is ' + repr(afy)
        [afy.insert((count+1)*afy_multiplier-1, dict(package_name=promo)) for count, promo in enumerate(promos)]
        #print 'Final apps_for_you feed is ' + repr(afy[0:19])
        return afy

    if carousel is 'hot_apps':

        ha =  filtered_packages
        #print 'Original hot_apps feed is ' + repr(ha)
        [ha.insert((count+1)*ha_multiplier-1, dict(package_name=promo)) for count, promo in enumerate(promos)]
        #print 'Final hots_apps feed is ' + repr(ha[0:19])
        return ha

    if carousel is 'featured_apps':
        fa =  filtered_packages
        [fa.insert((count+1)*ha_multiplier-1, dict(package_name=promo)) for count, promo in enumerate(promos)]         
        return fa

#inject_promos(orig_list, all_promos, my_interests)

''' Fixed order promo list from a static list of packages passed from settings
    Ticket #1911: Hot apps now calls this function to get the promolist till
    we have ordered promo lists in the future
'''

def inject_ha_promos(orig_list, all_promos, my_interests, afy_multiplier = 5, ha_multiplier = 2, carousel='hot_apps', my_apps=None):
    promos = all_promos
    my_apps = [] if my_apps is None else my_apps
    #d(orig_list)
    #orig_list_pkgs = [app.get('package_name') for app in orig_list]
    ordered_apps=[]
    [ordered_apps.append(app) for app in orig_list if app.get('package_name') not in promos]
    #reduced_promos = list(set(promos)-set(my_apps)-set(orig_list_pkgs))
    #[ordered_promos.append(promo) for promo in promos if promo in reduced_promos]
    d('Promos personalized for Jon Doe are %s' % repr(promos))

    afy = orig_list

    #print 'The 1 in k hot_apps multiplier is ' + repr(ha_multiplier)
    #print 'The 1 in k apps_for_you multiplier is ' + repr(afy_multiplier)

    if carousel is 'apps_for_you':

        #print 'Original apps_for_you feed is ' + repr(afy)

        [afy.insert((count+1)*afy_multiplier-1, dict(package_name=promo)) for count, promo in enumerate(promos)]

        #print 'Final apps_for_you feed is ' + repr(afy[0:19])

        return afy

    if carousel is 'hot_apps':

        ha =  ordered_apps

        #print 'Original hot_apps feed is ' + repr(ha)

        [ha.insert((count+1)*ha_multiplier-1, dict(package_name=promo)) for count, promo in enumerate(promos)]
        d('ha = %s'%ha)

        #print 'Final hots_apps feed is ' + repr(ha[0:19])

        return ha



"""
Sample Output
-------------
Promos -> Interests list is {'com.lev.aaa': 'fun, travel', 'com.lev.card': 'shopping', 'com.lev.nfc': 'shopping', 'com.lev.roadside': 'travel', 'com.lev.sur': 'fun, music', 'com.lev.koi': 'sports, education', 'com.lev.golf': 'fun, sport', 'com.lev.mul': 'fun, food'}
Interests -> Promos list is {'sport': ['com.lev.golf'], 'shopping': ['com.lev.card', 'com.lev.nfc'], 'food': ['com.lev.mul'], 'travel': ['com.lev.aaa', 'com.lev.roadside'], 'sports': ['com.lev.koi'], 'music': ['com.lev.sur'], 'fun': ['com.lev.aaa', 'com.lev.sur', 'com.lev.golf', 'com.lev.mul'], 'education': ['com.lev.koi']}
Jon Does interests are ['fun', 'music']
Promos personalized for Jon Doe are ['com.lev.aaa', 'com.lev.sur', 'com.lev.golf', 'com.lev.mul']
Original apps_for_you feed is ['com.1', 'com.2', 'com.3', 'com.4', 'com.5', 'com.6', 'com.7', 'com.8', 'com.9', 'com.10', 'com.11', 'com.12', 'com.13', 'com.14', 'com.15', 'com.16', 'com.17', 'com.18', 'com.19']
The 1 in k hot_apps multiplier is 4
The 1 in k apps_for_you multiplier is 5
Final apps_for_you feed is ['com.1', 'com.2', 'com.3', 'com.4', 'com.lev.aaa', 'com.5', 'com.6', 'com.7', 'com.8', 'com.lev.sur', 'com.9', 'com.10', 'com.11', 'com.12', 'com.lev.golf', 'com.13', 'com.14', 'com.15', 'com.16']
Original hot_apps feed is ['com.1', 'com.2', 'com.3', 'com.4', 'com.5', 'com.6', 'com.7', 'com.8', 'com.9', 'com.10', 'com.11', 'com.12', 'com.13', 'com.14', 'com.15', 'com.16', 'com.17', 'com.18', 'com.19']
Final hots_apps feed is ['com.1', 'com.2', 'com.3', 'com.lev.aaa', 'com.4', 'com.5', 'com.6', 'com.lev.card', 'com.7', 'com.8', 'com.9', 'com.lev.nfc', 'com.10', 'com.11', 'com.12', 'com.lev.roadside', 'com.13', 'com.14', 'com.15']
"""
