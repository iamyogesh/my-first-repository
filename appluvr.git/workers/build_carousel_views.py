"""
Worker tasks to collate carousel data for a user

Example Usage:
    python build_carousel_views.py apps_for_you http://baadaami.herokuapp.com/v2/ brad_pttszvc_spirrison@tfbnw.net 321089201267890  -d

See list of available options:
    python build_carousel_views.py apps_for_you

"""
from appluvr_views import d, couch, couchdb, cache
from flask import Flask, g, json, request, jsonify, current_app
from werkzeug import LocalProxy
from flaskext.script import Manager
from workerd import delayable
from appo import post_profile
import requests
import grequests
import os
import fb
import random
from operator import itemgetter
from appluvr.models.device import Device
from appluvr.models.settings import *
from appluvr.models.user import User
from build_card_views import apps_details, app_separation, get_xmap_results_from_server
from appluvr_views.promo import *
from appluvr_views.prefix import *
from appluvr.models.deal import *
from appluvr.models.app import *
from appluvr.utils.misc import *

app = Flask(__name__)
manager = Manager(app)

auth_user = 'tablet'
auth_pwd = os.environ.get('APPLUVR_PWD', 'aspirin')


w = LocalProxy(lambda: app.logger.warning)

#-------------------------------------------------------------------------------#

def carousel_setting():
    ret = Settings.load('carousel_settings')
    if ret:
        cms_setting = eval(ret.value)
    else:
        cms_setting = {}
    retval = default_carousel_settings
    retval.update(cms_setting)
    return retval.get('CarouselSettings')

@delayable
def fetch_my_friends(server, user, device, auth_pwd=auth_pwd, debug=False):
    """
    Fetch list of friends/experts
    For each of the friends/experts, inject their full name and profile picture link
    """
    my_friends =  fb.my_friends_list(server, user, device, auth_pwd, debug , block=True)
    app.logger.debug(my_friends)
    return json.dumps(my_friends)

@delayable
def fetch_only_advisors(server, user, device, auth_pwd=auth_pwd, block=True ,debug=False):
    """
    Fetch list of experts
    For each of the experts, inject their full name and profile picture link
    """
    my_adviosrs =  fb.get_only_advisor_friends(server, user, device, auth_pwd, debug , block=block)
    app.logger.debug(my_adviosrs)
    my_adviosrs_data = my_adviosrs.get('data')

    target1='%sapi/users/%s/block'%(server,user)
    r1= requests.get(target1, auth=(auth_user,auth_pwd))
    blocked_friends = []
    advisors_list = [] 
    if r1.status_code == 200:        
        blocked_friends = json.loads(r1.content).get('data').get('blocked_friends', None)
    if len(my_adviosrs_data)>0:
      for advisor_dict in my_adviosrs_data:
        if advisor_dict.get('uniq_id') in blocked_friends:
          advisor_dict['block'] = True        
        else:
          advisor_dict['block'] = False         
        advisors_list.append(advisor_dict)
    return jsonify(count = len(advisors_list), data =  advisors_list)

@delayable
@cache.memoize(BALI_CACHE_TIME)
def fetch_only_friends(server, user, device, auth_pwd=auth_pwd, block=True, debug=False):
    """
    Fetch list of friends
    For each of the friends, inject their full name and profile picture link
    """
    my_only_friends =  fb.get_only_friends(server, user, device, auth_pwd, debug , block=block)
    my_friends_data = my_only_friends.get('data')

    target = '%sapi/users/%s/block'%(server,user)
    target1 = '%sviews/users/%s/devices/%s/only_mf/count/' %(server, user, device)   

    urls = [target,target1]
    qs=(grequests.get(url, auth=(auth_user, auth_pwd))for url in urls)
    rs=grequests.map(qs)

    only_new_friends = []
    only_old_friends = []
    updated_mf_carousels = []
    blocked_friends = []
    r1 = rs[0]  
    if r1.status_code == 200:        
        blocked_friends = json.loads(r1.content).get('data').get('blocked_friends', None)

    max_size = carousel_setting().get('My Friends')
    r = rs[1]
    if r .status_code == 200:
      new_friends = json.loads(r.content).get('data') 

      if len(my_friends_data)>0: 
        for  user_dict in my_friends_data:
          if user_dict.get('uniq_id') in blocked_friends:
            user_dict['block'] = True        
          else:
            user_dict['block'] = False         
          if user_dict.get('uniq_id') in new_friends:
            user_dict['new'] = True
          else:
            user_dict['new'] = False
          updated_mf_carousels.append(user_dict)
        [only_new_friends.append(doc) if doc.get('new') == True else only_old_friends.append(doc) for doc in updated_mf_carousels] 
        only_new_friends = sorted(only_new_friends, key=itemgetter('first_created'), reverse=True)
        only_old_friends = sorted(only_old_friends, key=itemgetter('first_created'), reverse=True)    
        updated_mf_carousels = only_new_friends + only_old_friends   
        updated_mf_carousels = updated_mf_carousels[:max_size]      
    return jsonify(count = len(updated_mf_carousels), data = updated_mf_carousels)

@delayable
def fetch_mfa(server, user, device, auth_pwd=auth_pwd, debug=False,platform='android'):
    """
    Fetches my friends apps
    """
    target = '%sviews/users/%s/fb/friends/apps?platform=%s' % (server, user, platform)
    r = requests.get(target, auth = (auth_user,auth_pwd))
    mfa = get_friends_apps(r, server, user, device, platform, auth_pwd=auth_pwd, debug=False)
    return mfa    

@delayable
@cache.memoize(BALI_CACHE_TIME)
def fetch_only_mfa(server, user, device, auth_pwd = auth_pwd, debug = False, platform = 'android'):
    """
    Fetches my friends apps
    """
    android_equivalent_apps=[]
    ios_equivalent_apps=[]
    target = '%sviews/users/%s/fb/only_friends/apps?platform=%s' % (server, user, platform)
    target1 = '%sviews/users/%s/devices/%s/only_mfa/count/' %(server, user, device)

    urls = [target,target1]
    qs=(grequests.get(url, auth=(auth_user, auth_pwd))for url in urls)
    rs=grequests.map(qs)

    updated_appo = [] 
    new_pkgs = []
    old_pkgs =[]
    new_dict = {}
    return_list = []

    max_size = carousel_setting().get('My Friends Apps')
    mfa = get_friends_apps(rs[0], server, user, device, platform, auth_pwd=auth_pwd, debug=False)   
    mfa_appo_data = json.loads(mfa).get('data')

    if rs[1].status_code == 200:
      friends_apps_data = json.loads(rs[1].content).get('data')  
      for apps in friends_apps_data:
        new_dict.update({apps.get('package_name'):apps})      
      new_friends_apps =  new_dict.keys()

      for  pkg_dict in mfa_appo_data:         
        if pkg_dict.get('package_name') in new_friends_apps:
          pkg_dict['new'] = True
          updated_appo.append(pkg_dict) 
        else:
          pkg_dict['new'] = False
          updated_appo.append(pkg_dict)          

      [new_pkgs.append(pkg) if pkg.get('new') == True else old_pkgs.append(pkg) for pkg in updated_appo]
      new_pkgs = sorted(new_pkgs, key=itemgetter('first_created'), reverse=True)
      old_pkgs = sorted(old_pkgs, key=itemgetter('first_created'), reverse=True)
      updated_appo =   new_pkgs + old_pkgs 

      for pkg in updated_appo:
        pkg_name = pkg.get('package_name')
        if pkg_name in new_friends_apps:
          pkg['first_name'] = new_dict.get(pkg_name).get('first_name')
          pkg['last_name'] = new_dict.get(pkg_name).get('last_name')
          pkg['name'] = new_dict.get(pkg_name).get('name')
          return_list.append(pkg)
        else:          
          return_list.append(pkg)

      return_list = return_list[:max_size]     
    return jsonify(count = len(return_list), data = return_list)

@delayable
def fetch_all_my_friends(server, user, device, auth_pwd=auth_pwd, debug=False ):
    """
    Fetch list of friends/experts
    For each of the friends/experts, inject blocked/unblocked friends and Advisor
    """
    target1='%sapi/users/%s/block'%(server,user)
    r1= requests.get(target1, auth=(auth_user,auth_pwd))
    if r1.status_code == 200:
        friends_detail=[]
        blocked_friends = json.loads(r1.content).get('data').get('blocked_friends', None)
        my_friends=fb.my_friends_list(server, user, device, auth_pwd, debug , block=False)
        for apps_data in my_friends.get('data', None):
            if apps_data.get('uniq_id') in blocked_friends:
                apps_data['blocked']=True
                friends_detail.append(apps_data)
            else:
                apps_data['blocked']=False
                friends_detail.append(apps_data)
        output= jsonify(count=len(friends_detail),data=friends_detail)
        return output
    else:
        app.logger.error('Worker failed with error code: %s' % r1.status_code)
        output = jsonify(count = len([]), data = [])
        return output            

def get_friends_apps(r, server, user, device, platform, auth_pwd=auth_pwd, debug=False):
    """
    Fetches my friends apps
    """
    app.debug = debug
    if r.status_code is 200:
        app_list = json.loads(r.content).get('data', None)
        if not len(app_list):
            return json.dumps(dict(data=app_list))
        app_pkgs = [x.get('package_name').replace('"','') for x in app_list]
        app_pkg_cs = ','.join(app_pkgs)
        target = '%sviews/apps/summary/?platform=%s' % (server,platform)
        payload = {'ids': app_pkg_cs}
        r1 = requests.post(target, auth=(auth_user, auth_pwd),data=payload)
        if r1.status_code == 200:
            app_summaries = json.loads(r1.content)
            if platform == 'android':
              consolidated = [dict(x.items()+app_summaries.get(x.get('package_name').replace('"','')).items()) for x in app_list if app_summaries.get(x.get('package_name').replace('"','')) is not None]
            else:
              consolidated = [dict(x.items()+app_summaries.get(x.get('package_name').replace('"','')).items()) for x in app_list if app_summaries.get(x.get('package_name').replace('"','')) is not None]
            output=json.dumps(dict(count = len(consolidated), data=consolidated))
        else:
            app.logger.error('Worker failed with error code: %s' % r1.status_code)
            output = json.dumps(dict(count = len([]), data = []))
    else:
        app.logger.error('Worker failed with error code: %s' % r.status_code)
        output = json.dumps(dict(count = len([]), data = []))
    return output

@delayable
def fetch_recos(prefix, server, user, device, auth_pwd=auth_pwd, debug=False,platform='android'):
    """
    Fetches recos, injects app summaries for promo apps
    """
    app.debug = debug
    pkg_names = []
    post_profile(server, user, device, auth_pwd)
    target = '%sviews/users/%s/devices/%s/%s?platform=%s' % (server, user, device, prefix,platform)
    r = requests.get(target, auth=(auth_user,auth_pwd))
    pkg_names = []
    if r.status_code == 200:
      pkg_list = json.loads(r.content).get('data', None)
      if len(pkg_list) == 0:
        app.logger.debug('No package ids are present')
      else:
        pkg_names = [pkg.get('package_name') for pkg in pkg_list if len(pkg) ==1]
      if len(pkg_names) == 0:
        return r.content
      promoapps = ",".join(pkg_names)
      url2 = '%sviews/apps/summary?ids=%s&platform=%s' % (server, promoapps,platform)
      s = requests.get(url2, auth=(auth_user, auth_pwd))
      if s.status_code == 200:
        promoapps_summary = json.loads(s.content)
        consolidated = [dict(x.items()+promoapps_summary.get(x.get('package_name')).items()) if promoapps_summary.get(x.get('package_name')) is not None and len(x)==1 else x for x in pkg_list]
        output=json.dumps(dict(data=consolidated, count=len(consolidated)))
      else:
        app.logger.error('Worker failed with error code: %s' % s.status_code)
        output = json.dumps(dict(count = len([]), data = []))
    else:
        app.logger.error('Worker failed with error code: %s' % r.status_code)
        output = json.dumps(dict(count = len([]), data = []))
    return output

@delayable
@cache.memoize(BALI_CACHE_TIME)
def fetch_my_apps(server, user, device, auth_pwd=auth_pwd, debug=False,platform='android'):
  """
  Stub for inserting my apps mash up
  """
  app.debug = debug
  target = '%sviews/users/%s/all_my_apps?platform=%s' % (server, user, platform)
  r = requests.get(target, auth=(auth_user,auth_pwd))
  if r.status_code is 200:
    myapps_detail={}
    app.logger.debug('Received %s bytes' % len(r.content))
    temp = json.loads(r.content)
    array = temp['data']
    if len(array)==0:
      app.logger.debug("No package ids are present")
      return r.content
    else:    
      pkg_names = ",".join(array)      
      payload = {"ids":pkg_names,"platform":platform}
      url2 = '%sviews/apps/summary/' % (server)
      temp1 = requests.post(url2, data = payload, auth = (auth_user,auth_pwd))
      app_details = json.loads(temp1.content)      
      if platform =='android':           
        for i in app_details:
          android_name = app_details[i].get('android_market').get('name', None)
          vcast_name = app_details[i].get('vcast_market').get('name', None)
          if android_name==None and vcast_name ==None:
            pass
          else:
            name = (android_name or vcast_name).upper()
            myapps_detail[name] = app_details[i] 
      else:        
        for i in app_details:
          itunes_name = app_details[i].get('itunes_market').get('name', None)
          if itunes_name==None :
            pass
          else:
            name = itunes_name.upper()
            myapps_detail[name] = app_details[i]

      obj=dict()
      obj['data']=myapps_detail
      obj['count']=len(myapps_detail)
      temp1=[]
      for k in sorted(obj['data'].iterkeys()):
        temp1.append(obj['data'][k])
      out=dict()
      out['data']=temp1
      out['count']=len(temp1)
      packageList = json.dumps(out)
      #app.logger.debug(packageList)
      return packageList
  else:
    app.logger.error('Worker failed with error code: %s' % r.status_code)
    return json.dumps(dict(count = len([]), data = []))

@delayable
def fetch_appdetails_for_fb_share(server, user, device, auth_pwd=auth_pwd):
    platform='ios'
    empty = {'count':0,'apps':[]}
    device_obj = Device.load(device)
    if not device_obj:
      return None
    fb_shared_apps = set(device_obj.apps_fb_shared)
    installed_apps = set(device_obj.apps_installed)
    fb_apps2share = [x for x in installed_apps if x not in fb_shared_apps]

    if fb_apps2share:
      pkg_names = ",".join(fb_apps2share)
      url2 = '%sviews/apps/summary/?ids=%s&platform=%s' % (server, pkg_names,platform)
      temp1 = requests.get(url2,auth=(auth_user,auth_pwd))
      app_details = json.loads(temp1.content)
      myapps_detail={}
      for i in app_details:
          itunes_name = app_details[i].get('itunes_market').get('name', None)
          if itunes_name==None :
              pass
          else:
              name = itunes_name.upper()
              myapps_detail[name] = app_details[i]
      obj=dict()
      obj['apps']=myapps_detail
      obj['count']=len(myapps_detail)
      temp1=[]
      for k in sorted(obj['apps'].iterkeys()):
          temp1.append(obj['apps'][k])
      out=dict()
      out['apps']=temp1
      out['count']=len(temp1)
      packageList = json.dumps(out)
    else:
      packageList = json.dumps(empty)
    return packageList

@delayable
def share_iosapps2fb(server, user, device, data, auth_pwd=auth_pwd):

  headers = {'content-type': 'application/json'}
  platform='ios'
  empty = {'count':0,'apps':[]}
  pkgs = map(str, data.get('pkgs'))
  message = data.get('message')
  apps_fb_share_status = data.get('fb_share',1)

  #Auto_share
  if apps_fb_share_status == 0:
    device_object=add_to_device(pkgs,apps_fb_share_status,device)
    return jsonify(fbstatus=200)
  #manual_share & Auto Share
  elif (apps_fb_share_status is 1) or (apps_fb_share_status is 2):  
    if message == '':
      message = "I just found some cool apps using AppLuvr!"
    if len(pkgs)>0:
      #get pkg name from itunesid
      result=get_app_summary(server,pkgs,platform)
      #Share the status to facebook
      app_names= result.get('apps')
      pkg_list=[singleapp.get('itunes_market').get('name', None)for singleapp in app_names]
      #Share the status to facebook
      output="%s\r\n%s"%(message,', '.join(pkg_list))
      data={"message":output} 
      post_url= '%sapi/users/%s/fb/feed'%(server,user)
      r=requests.post(post_url, data=json.dumps(data), headers=headers, auth=(auth_user,auth_pwd))
      fbstatus = r.status_code
      #Save shared apps to user's device
      if r.status_code==200:
        device_obj=add_to_device(pkgs,apps_fb_share_status,device)
      else:
        device_obj=add_to_device([],apps_fb_share_status,device)
        fbstatus=400
      return jsonify(fbstatus=fbstatus)
    else:
      device_obj=add_to_device([],apps_fb_share_status,device)
      return jsonify(fbstatus=202)

def add_to_device(pkgs,apps_fb_share_status,device):
  device_obj = Device.load(device)
  if not device_obj:
    return None
  if len(pkgs)>0: 
    device_obj.apps_fb_shared=list(set(device_obj.apps_fb_shared + pkgs))
    #Since auto sharing is not enabled, adding these too only 
    #if packgages are not empty
    #remove from if condition if auto FB share is to be 
    #enabled
    device_obj.apps_fb_share_status=str(apps_fb_share_status)
    device_obj.update()
  return apps_fb_share_status

def get_app_summary(server,packageList,platform):
  pkg_names = ",".join(packageList)
  url2 = '%sviews/apps/summary/?ids=%s&platform=%s' % (server, pkg_names,platform)
  temp1 = requests.get(url2,auth=(auth_user,auth_pwd))
  app_details = json.loads(temp1.content)
  myapps_detail={}
  for i in app_details:
    itunes_name = app_details[i].get('itunes_market').get('name', None)
    if itunes_name==None :
      pass
    else:
      name = itunes_name.upper()
      myapps_detail[name] = app_details[i]
  obj=dict()
  obj['apps']=myapps_detail
  obj['count']=len(myapps_detail)
  temp1=[]
  for k in sorted(obj['apps'].iterkeys()):
    temp1.append(obj['apps'][k])
  out=dict()
  out['apps']=temp1
  out['count']=len(temp1)
  return out

@delayable
def fetch_all_app_packs(server, user, device, auth_pwd=auth_pwd, debug=False):
  """
  stub to get all app packs.
  """
  output = []
  post_profile(server, user, device, auth_pwd)
  target = '%sapi/app_packs/get/active' %(server)
  r= requests.get(target, auth = (auth_user,auth_pwd))
  if r.status_code == 200:
    app_packs = json.loads(r.content).get('app_packs')
    app_packs_carrousel=[dict(user_name=details.get('user_name'),user_picurl= details.get('user_picurl'),app_pack_name= details.get('apppack_name'),app_pack_img= details.get('apppack_img'),app_pack_id = details.get('app_id'), apppack_square_img= details.get('apppack_square_img')) for details in app_packs]
    random.shuffle(app_packs_carrousel)
    return app_packs_carrousel
  else:
    app.logger.debug("%s : device doesn't has insatlled app packs." %device)
    return output

@delayable
def fetch_all_app_packs_by_user(server, user, device, auth_pwd=auth_pwd, debug=False):
  """
  stub to get all app packs created by user.
  """
  users = User.load(user)
  target = '%sapi/app_packs/get/all' %(server) 
  r = requests.get(target, auth = (auth_user,auth_pwd))
  if r.status_code == 200:
    all_app_packs = json.loads(r.content).get('app_packs')
    user_app_packs = [app_pack for app_pack in all_app_packs if users.fb_id == app_pack.get('fb_id')]
    return jsonify(dict(count=len(user_app_packs),data=user_app_packs))
  else:
    app.logger.debug(r.status_code)
    return None

def translate_appo_source(apps, platform):
  afy_output = [] 
  if len(apps)>0:
    for pkg in apps:      
      pkg.update({'appo_source': pkg.get('source')})
      if pkg.get('source') == 'collaborative_filtering':
        pkg.update({'source':'Popular with other AppLuvr users'})
      elif pkg.get('source') == 'hot_apps':      
        pkg.update({'hot_reason':'Trending'})
        del pkg['source']
      elif pkg.get('source') == 'editorial':
        pkg.update({'source':'Editor\'s Pick'})
      elif pkg.get('source') == 'popular':
        pkg.update({'source':'Popular with other AppLuvr users'})
      elif 'interest' in pkg.get('source'):
        pkg.update({'source': "You like %s"%pkg.get('source').split('|')[1]})
      else:
        pkg = pkg     

      afy_output.append(pkg)
  return afy_output

@delayable
#@cache.memoize(FULL_DAY)
def fetch_recommended_apps(server, user, device, platform, auth_pwd, debug=False):
  """carrousel for fetch recommended_apps
  """
  post_profile(server, user, device, auth_pwd)

  appo_returns = fetch_appo_data(server, user, device, platform, auth_pwd) 

  afy_percentage=carousel_setting().get('Percentage for AFY') if carousel_setting().get('Percentage for AFY') else 100
  ha_percentage=100-afy_percentage
  max_size_recommended=carousel_setting().get('Recommended Apps')

  afy_output = []
  ha_output = []
  afy_array = []
  ha_array = []
   
  afy_array = appo_returns.get('recommendations', [])
  if len(afy_array)>0:
    afy_percent=(afy_percentage * len(afy_array))/100
    afy_output=afy_array[:afy_percent]  

  ha_array = appo_returns.get('hot_apps', [])
  if len(ha_array)>0:
    ha_percent=(ha_percentage * len(ha_array))/100
    ha_output=ha_array[:ha_percent]

  recommended = []

  afy_output = translate_appo_source(afy_output, platform)

  if afy_percentage == 100:
    recommended_apps = afy_array
  elif ha_percentage == 100:
    recommended_apps = ha_array
  else:
    recommended_apps=afy_output+ha_output

  if len(recommended_apps) > 0:
    random.shuffle(recommended_apps)
    recommended=recommended_apps[:max_size_recommended]
  if platform == 'ios':
    recommended = itunesid_to_packagename(recommended)
  recommended_apps_output=json.dumps(dict(count=len(recommended),data=recommended))
  return recommended_apps_output

@cache.memoize(BALI_CACHE_TIME)
def fetch_appo_data(server, user, device, platform, auth_pwd):
  '''
  fetch apps from appo.
  '''
  device_obj = Device.load(device)
  userobj = User.load(user)

  odp_installed = device_obj.odp_installed if device_obj else False
  max_size_hot_apps = carousel_setting().get('Hot Apps')
  max_size_recommendation = carousel_setting().get('Apps For You')
  appo_id = userobj.appo_profile().get('uid') if userobj else False

  # Fetch 2x the target max size since we'll be filtering later
  hot_apps_carousel_max_size = 2*max_size_hot_apps if 2*max_size_hot_apps<=70 else 70    
  recommendation_carousel_max_size = 2*max_size_recommendation if 2*max_size_recommendation<=70 else 70

  hot_apps_url = "".join([APPO_BASE_URL, APPO_VERSION, APPO_HOT_APPS])
  recommendation_url = "".join([APPO_BASE_URL, APPO_VERSION, APPO_APPS_FOR_YOU])  
  urls = [[hot_apps_url,hot_apps_carousel_max_size],[recommendation_url, recommendation_carousel_max_size]]
  qs = (grequests.get(url[0], params=dict(uid = appo_id, max_size = url[1]), auth=APPO_BASIC_AUTH) for url in urls)
  rs = grequests.map(qs)

  if rs[1].status_code == 200:    
    afy_output = json.loads(rs[1].content).get('recommendations', [])
  else:
    afy_output = []

  if rs[0].status_code == 200 :
    ha_output= json.loads(rs[0].content).get('hot_apps', [])
  else:
    ha_output = [] 

  recommended_apps=afy_output+ha_output

  if platform == 'android':
    app_card_url = ['%sviews/cards/%s/%s/app/%s/' %(server,user,device,each_app.get('package_name')) for each_app in recommended_apps] 
    qs = (grequests.get(url, auth=(auth_user,auth_pwd)) for url in app_card_url)
    rs = grequests.map(qs)
    current_app.logger.debug(["app card status:%s" %r.status_code for r in rs])
  else:
    app_card_url = ['%sviews/cards/%s/%s/app/%s/' %(server,user,device,each_app.get('itunes_id')) for each_app in recommended_apps] 
    qs = (grequests.get(url, auth=(auth_user,auth_pwd)) for url in app_card_url)
    rs = grequests.map(qs)
    current_app.logger.debug(["app card status:%s" %r.status_code for r in rs])

  return {"recommendations":afy_output,"hot_apps":ha_output,"recos":recommended_apps}

def get_current_deals(platform, carrier): 
  if "verizon" in carrier.lower():
    dealcarrier = "Verizon"
  elif "att" in carrier.lower() or "at&t" in carrier.lower():
    dealcarrier = "ATT"
  else:
    dealcarrier = "BM"
  #Get current time round off to nearest minute with second as 0 AND round of minutes to 30 multiples
  current = list(time.localtime())
  current[5] = 0
  current[4] = round_off_numbers(current[4], 30)
  current = int(time.mktime(time.struct_time(tuple(current))))
  current_app.logger.debug("----> %s"%current)
  keys = [current, platform, dealcarrier]
  current_app.logger.debug("----> keys %s"%keys)
  deal = [deal.current_deal_toDict() for deal in Deal.view('deal/current_deal',  key = keys)]
  return deal

@delayable
def fetch_featured_carousel(APPLUVR_VIEW_SERVER, id, udid, max_size, platform, carrier, debug=False):

  """carrousel for fetch featured_apps
  """
  user = User.load(id)

  if not user:
    return jsonify(count = len([]), data = [])

  if "verizon" in carrier.lower():
    carrier_prefix = 'vz'
  elif "att" in carrier.lower() or "at&t" in carrier.lower():
    carrier_prefix = 'att'
  else:
    carrier_prefix = 'bm'

  deal = get_current_deals(platform, carrier)
  current_app.logger.debug("====> deal %s"%deal)

  url='%sapi/promoapps'%(APPLUVR_VIEW_SERVER)
  promo_response = requests.get(url, auth=(auth_user, auth_pwd))
  if promo_response.status_code==200:
    array=json.loads(promo_response.content).get('data', None) 
    array = [each for each in array if each.get('carrousel') == 'featured_apps' and platform == each.get('platform') and carrier == each.get('carrier') ]
    promo_apps_view="promoapp/%s_%s_featured_apps"%(carrier_prefix,platform)
    interests = [interest.strip() for interest in user.interests] if user.interests else []         
    promolist = dict([(row['key'],row['value']) for row in PromoApp.view(promo_apps_view)])    
    promo=get_promo_order(promolist)                
    promo_interests=promo.get('promo_interests') 
    promo_orders=promo.get('promo_orders') 
    promo_context_copy = promo.get('promo_context_copy') 
    deal_data ={}

    if deal:
      dod_pkg = [each.get('package_name', None)for each in deal]
      dod_pkg=dod_pkg[0]  
      current_app.logger.debug("===> %s"%dod_pkg)    
      if platform == 'android':
        target1 = '%sviews/apps/%s/details?platform=%s' % (APPLUVR_VIEW_SERVER, dod_pkg, platform) 
        r = requests.get(target1, auth = (auth_user,auth_pwd))          
        if r .status_code == 200:
          appo_data = apps_details(r)
          current_app.logger.debug("===> %s"%appo_data) 
          deal_data = dict(package_name = appo_data.get('package_name'), icon_url = appo_data.get('icon_url'), android_market = appo_data.get('android_market'), vcast_market = appo_data.get('vcast_market'), appo_category = appo_data.get('appo_category'), punchline = appo_data.get('punchline'), doc_type = 'deal', deal_title = deal[0].get('deal_title'))

    featured_apps = inject_promos(orig_list=[], all_promos=promo_interests, my_interests=interests, promo_order=promo_orders, carousel='featured_apps', my_apps=user.all_apps())
    promo_pkg = [pkg.get('package_name') for pkg in featured_apps]    
    data = app_summary(APPLUVR_VIEW_SERVER, promo_pkg, ",".join(promo_pkg), platform, promo_context_copy)
    current_app.logger.debug("===> %s"%deal_data)
    if len(deal_data)>0:          
        data.insert(0, deal_data)

    featured_apps_output=jsonify(count=len(data), data=data) 
  else:
    featured_apps_output = jsonify(count = len([]), data = [])
  return  featured_apps_output  

def get_promo_order(interests):    
    promo_orders=[]
    promo_interests={}
    orderd_promo_pkg=[]
    promo_context_copy = []
    null_priority_promo_pkgs = []
    for pkg in interests:                 
        promo_interests[pkg]=interests[pkg][0]
        promo_priority = interests[pkg][1]       
        if promo_priority == '' or  promo_priority==None:
            promo_pkgs={"pkg":pkg, "priority":promo_priority}
            null_priority_promo_pkgs.append(promo_pkgs)
        else:            
            promo_pkgs={"pkg":pkg, "priority":int(promo_priority)}            
            promo_orders.append(promo_pkgs) 
            new_list=sorted(promo_orders, key=itemgetter('priority'))
            orderd_promo_pkg=[pkgs.get('pkg', None) for pkgs in new_list]

        promo_contxt={"pkg":pkg, "context_copy":interests[pkg][2]}
        promo_context_copy.append(promo_contxt)
        promo_interests.update()
        null_priority_pkgs = [pkgs.get('pkg', None) for pkgs in null_priority_promo_pkgs] 
        orderd_promo_pkg=orderd_promo_pkg+null_priority_pkgs 
    return dict(promo_interests=promo_interests,promo_orders=orderd_promo_pkg,promo_context_copy = promo_context_copy)


def app_summary(APPLUVR_VIEW_SERVER, featured_pkg, featured_pkg_csv, platform, promoapps_list):

  featured_apps = []
  url3 = '%sapi/apps/summary?ids=%s&platform=%s'%(APPLUVR_VIEW_SERVER, featured_pkg_csv, platform)
  r = requests.get(url3, auth=(auth_user, auth_pwd))
  if r.status_code==200:
    app_summary = json.loads(r.content)
    for package in featured_pkg:
      if package in app_summary.keys():
        details = app_summary.get(package)
        context_copy = [promoapp.get('context_copy') for promoapp in promoapps_list if package == promoapp.get('pkg') ]
        details['context_copy'] = context_copy[0] if context_copy[0] else ''
        featured_apps.append(details)
        if platform == 'ios':
          featured_apps = itunesid_to_packagename(featured_apps)
  return featured_apps

@delayable
def fetch_att_widget_carousels(server, user, device, platform, auth_pwd, debug=False):  
  """
  carrousel for fetch Att_widget.
  """
  device_object = Device.load(device)
  user_object = User.load(user)
  if not user_object or not device_object:
    return None

  appo_data = []
  output = []
  afy_app_summary_list = []
  afy_multiplier = 2      
  usr_obj = user_object.apps()
  my_apps = usr_obj[0][1]  

  url1='%sapi/att/widget/active'%(server)
  r1 = requests.get(url1, auth = (auth_user,auth_pwd))
  if r1. status_code == 200:
    app_data = json.loads(r1.content).get('data') 

    source_url = "".join([APPO_BASE_URL, APPO_VERSION, APPO_APPS_FOR_YOU])
    max_size = carousel_setting().get('AttWidget') if carousel_setting().get('AttWidget') else 20
    odp_installed =  False
    appo_id = user_object.appo_profile().get('uid') if user else False   
    carousel_max_size = 2*max_size if 2*max_size<=70 else 70

    r = requests.get(source_url,params=dict(uid=appo_id,max_size=carousel_max_size,odp_installed=odp_installed), auth=APPO_BASIC_AUTH)
    if r.status_code == 200:
      obj = json.loads(r.content).get('recommendations')      
      [obj.remove(obj[index]) for index, apps in enumerate(obj) if apps.get('package_name') in my_apps]
      afy_app_summary_list = obj

    for index, doc in enumerate(app_data):  
      pkgs = [apps.get('pkg') for apps in doc.get('app_data')]      
      pkgs = list(set(pkgs)-set(my_apps))

      if len(pkgs)> 0:  
        app_summary =  get_all_widget_app_summary(server, pkgs, platform)        
            
        appo_data =[app_summary.get(pkg) for pkg in pkgs if pkg in app_summary.keys()]
        if doc.get('widget_type') == 'standard':
          output.append(dict(widget_type = doc.get('widget_type'), appo = appo_data))

        if doc.get('widget_type') == 'banner' or doc.get('widget_type') == 'group':
          output.append(dict(widget_type = doc.get('widget_type'),  promo_copy = doc.get('promo_copy'), appo = appo_data))

        if doc.get('widget_type') == 'billboard':
          image_url = ','.join([apps.get('image_url') for apps in doc.get('app_data')]) 
          output.append(dict(widget_type = doc.get('widget_type'), image_url = image_url, appo = appo_data))

    [output.insert((count)*afy_multiplier, dict(appo=afy_app, widget_type = 'standard')) for count, afy_app in enumerate(afy_app_summary_list)]
    output = output[:max_size]
  return jsonify(dict(count=len(output),data=output))

def get_all_widget_app_summary(server, pkgs, platform):
  app_summary = {}
  if len(pkgs)>0:
    url2 = '%sapi/apps/summary?ids=%s&platform=%s'%(server, ','.join(pkgs), platform)
    r2 = requests.get(url2, auth=(auth_user, auth_pwd))
    if r2.status_code==200:
      app_summary = json.loads(r2.content)
  return app_summary

@delayable
def fetch_carousel_counts(server, user, device, platform, auth_pwd, debug=False):
  output = dict()
  #target1 = '%sviews/carousels/%s/%s/%s/only_mfa/'%(server, user, device, platform)
  #target2 = '%sviews/carousels/%s/%s/%s/only_mf/'%(server, user, device, platform)
  target3 = '%sviews/carousels/%s/%s/%s/only_advisors/'%(server, user, device, platform)
  #target4 = '%sviews/carousels/%s/%s/%s/my_comments/'%(server, user, device, platform)
  #target5 = '%sviews/carousels/%s/%s/%s/my_apps/'%(server, user, device, platform)
  target6 = '%sviews/users/%s/devices/%s/only_mf/count/'%(server, user, device)
  target7 = '%sviews/users/%s/devices/%s/only_mfa/count/'%(server, user, device)
  urls = [target3,target6,target7]
  qs=(grequests.get(url, auth=(auth_user, auth_pwd))for url in urls)
  rs=grequests.map(qs)
  '''
  if rs[1].status_code==200:
    output['my_friends_count'] = len(json.loads(rs[1].content).get('data', {}))
  else:
    output['my_friends_count'] = 0
  if rs[0].status_code==200:
    output['my_friends_apps_count'] = len(json.loads(rs[0].content).get('data', {}))
  else:
    output['my_friends_apps_count'] = 0
  if rs[3].status_code==200:
    print json.loads(rs[3].content).get('data', {})
    output['my_comments_count'] = len(json.loads(rs[3].content).get('data', {}))
  else:
    output['my_comments_count'] = 0
  if rs[4].status_code==200:
    print json.loads(rs[3].content).get('data', {})
    output['my_apps_count'] = len(json.loads(rs[4].content).get('data', {}))
  else:
    output['my_apps_count'] = 0
    '''
  if rs[0].status_code==200:
    output['advisors'] = len(json.loads(rs[0].content).get('data', {}))
  else:
    output['advisors'] = 0
  if rs[1].status_code==200:
    output['new_friends_count'] = len(json.loads(rs[1].content).get('data', {}))
    new_friends= json.loads(rs[1].content).get('data', {})
    if len(new_friends)>0:
        target = '%sviews/carousels/%s/%s/%s/only_mf'% (server, user, device, platform)
        req = requests.get(target, auth=(auth_user, auth_pwd))
        if req.status_code==200:
            current_app.logger.debug("----> updated <------") 

  else:
    output['new_friends_count'] = 0
  if rs[2].status_code==200:
    output['new_friends_apps_count'] = len(json.loads(rs[2].content).get('data', {}))
  else:
    output['new_friends_apps_count'] = 0 
  return jsonify(data=output)

@delayable
def fetch_my_comments(APPLUVR_VIEW_SERVER, max_size, id, platform, debug=False):
  target1='%sviews/users/%s/comments'%(APPLUVR_VIEW_SERVER, id)  
  r=requests.get(target1, auth=(auth_user, auth_pwd))
  if r.status_code == 200:
    array=json.loads(r.content).get('data', None)
    pkg=[]
    comment=[]
    uniq_id=[]
    last_modified=[]
    for each in array:
      pkg.append(each.get('pkg', None))
      comment.append(each.get('comment', None))
      uniq_id.append(each.get('uniq_id', None))
      last_modified.append(each.get('last_modified', None))
    pkg_csv=",".join(pkg)
    my_comments_output=appo_details(APPLUVR_VIEW_SERVER, pkg, pkg_csv, comment, uniq_id, last_modified, platform)
    return json.dumps(dict(count=len(my_comments_output), data=my_comments_output))
  else:
    return json.dumps(dict(count=len([]), data=[]))

def appo_details(APPLUVR_VIEW_SERVER, pkg, pkg_csv, comment, uniq_id, last_modified, platform):
  target2 = '%sapi/apps/summary?ids=%s&platform=%s'%(APPLUVR_VIEW_SERVER, pkg_csv, platform)
  r=requests.get(target2, auth=(auth_user, auth_pwd))
  my_comments=[]
  if r.status_code==200:
    appo_details=[v for each in pkg for k,v in json.loads(r.content).items() if k==each]
    i=0
    for each_data in appo_details:
      each_data['comment']=comment[i]
      each_data['uniq_id']=uniq_id[i]
      each_data['last_modified']=last_modified[i]
      i=i+1
      my_comments.append(each_data)
  return my_comments

def fetch_device(server, sub_id):
  """
  stub to fetch device.
  """
  output = []
  target = '%sapi/subid/get/all' %(server)
  r = requests.get(target, auth = (auth_user,auth_pwd))
  if r.status_code == 200:
    docs = json.loads(r.content).get('data')
    output = ','.join([doc.get('udid') for doc in docs if sub_id == doc.get('ATT_subid')])
  return json.dumps(dict(device = output))

@delayable
def fetch_mixes_search_carousel(server, user, device, platform, query_term, debug=False):
  target1='%sapi/app_pack/index/query?query_term=%s'%(server, query_term)
  r1=requests.get(target1, auth=(auth_user, auth_pwd))
  output = []
  if r1.status_code ==200:
    data_array=json.loads(r1.content).get('data', None)
    docid_array = [each.get('docid') for each in data_array]   
    mixed_carousel_output = app_pack_details(server, user, device, platform, query_term, docid_array)
    return jsonify(dict(count = len(mixed_carousel_output), data = (mixed_carousel_output)))
  else:
    return jsonify(dict(count = len(output), data = (output)))

def app_pack_details(server, user, device, platform, query_term, docid_array):
  output=[]
  post_profile(server, user, device, auth_pwd)
  target = '%sapi/app_packs/get/all' %(server)
  r = requests.get(target, auth = (auth_user,auth_pwd))
  if r.status_code == 200:
    app_packs = json.loads(r.content).get('app_packs')
    app_packs_carrousel=[dict(user_name=details.get('user_name'),user_picurl= details.get('user_picurl'),app_pack_name= details.get('apppack_name'),app_pack_img= details.get('apppack_img'),app_pack_id = details.get('app_id')) for details in app_packs]
    random.shuffle(app_packs_carrousel)    
    output=[each for each in app_packs_carrousel if each.get('app_pack_id', None) in docid_array]
  return output

#-------------------------------------------------------------------------------#

@manager.command
def apps_for_you(server, user, device, auth_pwd=auth_pwd, debug=False):
    return fetch_recos('apps_for_you', server, user, device, auth_pwd, debug)

@manager.command
def hot_apps(server, user, device, auth_pwd=auth_pwd, debug=False):
    return fetch_recos('hot_apps', server, user, device, auth_pwd, debug)

@manager.command
def my_friends(server, user, device, auth_pwd=auth_pwd, debug=False):
    result = fetch_my_friends(server,user, device, auth_pwd=auth_pwd, debug=debug)
    #app.logger.debug(result)
    return json.dumps(result)

@manager.command
def only_my_friends(server, user, device, auth_pwd=auth_pwd, debug=False):
    result = fetch_only_friends(server,user, device, auth_pwd=auth_pwd, debug=debug)
    return json.dumps(result)

@manager.command
def my_friends_apps(server, user, device, auth_pwd=auth_pwd, debug=False):
    return fetch_mfa(server, user, device, platform, auth_pwd, debug)

@manager.command
def only_my_friends_apps(server, user, device, auth_pwd=auth_pwd, debug=False):
    return fetch_only_mfa(server, user, device, platform, auth_pwd, debug)

@manager.command
def only_my_advisors(server, user, device, auth_pwd=auth_pwd, debug=False):
    return fetch_only_advisors(server, user, device, auth_pwd, debug)

@manager.command
def my_apps(server, user, device, auth_pwd=auth_pwd, debug=False):
    """
    Fetch list of installed apps on the device
    Inject app summary
    """
    return fetch_my_apps(server, user, device, auth_pwd, debug)

@manager.command
def all_my_friends(server, user, device, auth_pwd=auth_pwd, debug=False):
    """
    Fetch list of installed apps on the device
    Inject app summary
    """
    return fetch_all_my_friends(server, user, device, auth_pwd=auth_pwd, debug=False)

@manager.command
def all_app_packs(server, user, device, auth_pwd=auth_pwd, debug=False):
    """
    Fetch list of installed app packs on the device.
    """
    return fetch_all_app_packs(server, user, device, auth_pwd=auth_pwd, debug=False)

@manager.command
def users_all_app_packs(server, user, device, auth_pwd=auth_pwd, debug=False):
    """
    Fetch list of app_packs created by user.
    """
    return fetch_all_app_packs_by_user(server, user, device, auth_pwd=auth_pwd, debug=False)

@manager.command
def recommended_apps(APPO_BASE_URL, APPO_VERSION, APPO_HOT_APPS, APPO_APPS_FOR_YOU, hot_apps_carousel_max_size, recommendation_carousel_max_size, appo_id, odp_installed, afy_percentage, ha_percentage, max_size_recommended, auth, debug=False):
    return fetch_recommended_apps(APPO_BASE_URL, APPO_VERSION, APPO_HOT_APPS, APPO_APPS_FOR_YOU, hot_apps_carousel_max_size, recommendation_carousel_max_size, appo_id, odp_installed, afy_percentage, ha_percentage, max_size_recommended, auth, debug)

@manager.command
def featured_carousel(APPLUVR_VIEW_SERVER, max_size, platform, debug=False):
    return fetch_featured_carousel(APPLUVR_VIEW_SERVER, max_size, platform, debug=False)

@manager.command
def my_comments(APPLUVR_VIEW_SERVER, max_size, id, platform, debug=False):
  return fetch_my_comments(APPLUVR_VIEW_SERVER, max_size, id, platform, debug=False)

@manager.command
def get_mixes_search_carousel(APPLUVR_VIEW_SERVER, query_term, debug=False):
  return fetch_mixed_carousel(APPLUVR_VIEW_SERVER, query_term, debug=False)


#-------------------------------------------------------------------------------#

if __name__ == '__main__':
    manager.run()
