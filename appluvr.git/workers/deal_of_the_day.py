from appluvr_views import  cache
from flask import Flask, g, json, request, jsonify, current_app
from werkzeug import LocalProxy
from flaskext.script import Manager
from workerd import delayable
import requests
import os
from appluvr.models.user import *
from appluvr.models.deal import *
from build_carousel_views import get_current_deals
from appluvr.utils.misc import *
from appluvr.models.deal import *

app = Flask(__name__)
manager = Manager(app)

auth_user = 'tablet'
auth_pwd = os.environ.get('APPLUVR_PWD', 'aspirin')

w = LocalProxy(lambda: app.logger.warning)

#---------------------------------------------------------------------------#
@delayable
def fetch_deal_app(server, id, udid, platform, carrier, dealstatus, auth_pwd=auth_pwd, debug=True):
	"""
    Stub for fetching appo data with dealed info
    """
	dealed_app_data=get_current_deals(platform, carrier)
	current_app.logger.debug(dealed_app_data)		
	if dealstatus == 'True':
		seen_deals = []	
		dealseen = UserSeenDeal.load('deal.'+id)
		if not dealseen:
			dealseen = UserSeenDeal(uniq_id = id, seen_deal = seen_deals)
			dealseen._id = "deal."+id
		dealseen.update()
		deal_ids = [dealed_app.get('deal_id') for dealed_app in dealed_app_data]
		for dealed_app in dealed_app_data:
			if dealed_app.get('deal_id') not in dealseen.seen_deal:
				package_name=dealed_app.get('package_name',None)
				dealseen.seen_deal = dealseen.seen_deal + deal_ids
				dealseen.update()				
				url2 = '%sviews/apps/%s/details?platform=%s' %(server, package_name, platform)						
				r1 = requests.get(url2, auth=(auth_user,auth_pwd))				
				if r1.status_code == 200:			
					appo_data = json.loads(r1.content)
					return dict(deal=dealed_app,data=appo_data) 
				else:
					return dict(deal={},data={}) 
	else:		
		for dealed_app in dealed_app_data:
			package_name=dealed_app.get('package_name',None)
			url2 = '%sviews/apps/%s/details?platform=%s' %(server, package_name, platform)						
			r1 = requests.get(url2, auth=(auth_user,auth_pwd))
			if r1.status_code == 200:			
				appo_data = json.loads(r1.content)
				return dict(deal=dealed_app,data=appo_data) 
			else:
				return dict(deal={},data={}) 
		

@manager.command
def dealed_app(server, id, udid, platform, auth_pwd=auth_pwd, debug=True):
    return fetch_dealed_app(server, id, udid, platform, auth_pwd, debug)
#---------------------------------------------------------------------------#
if __name__ == '__main__':
    manager.run()
