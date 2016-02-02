'''

Prefix file for common code

'''

from flask import current_app
from werkzeug import LocalProxy
import os

spit = LocalProxy(lambda: current_app.logger.debug)

FB_TOKEN=None
FB_ME = 'https://graph.facebook.com/me?access_token='
FB_WALL_POST = 'https://graph.facebook.com/%s/feed'
FB_FRIENDS = 'https://graph.facebook.com/me/friends?access_token='
FB_PROFILE_PICTURE = 'https://graph.facebook.com/me/picture?type=large&access_token='
FB_PUBLIC_PROFILE_PICTURE = 'https://graph.facebook.com/%s/picture?type=large'

APPO_USER=os.environ.get('APPO_USER','brandmobility')
APPO_PWD=os.environ.get('APPO_PWD','verizon')
APPO_BASE_URL=os.environ.get('APPO_BASE_URL','http://verizon.appolicious.com/api/verizon')
APPO_VERSION=os.environ.get('APPO_VERSION','/v3/')
APPO_BASIC_AUTH=(APPO_USER, APPO_PWD)
APPO_URL=APPO_BASE_URL+APPO_VERSION
APPO_APPS_FOR_YOU='recommendations'
APPO_HOT_APPS='hot_apps'
APPO_PROFILE='users/profile'
APPO_SEARCH_TRENDS='search_trends'
APPO_SEARCHES='searches'
APPO_BLACK='apps/blacklist'
MIXES_URL = os.environ.get('MIXES_URL', 'http://:beretyhusabu@rybaga.api.indexden.com')
MIXES_INDEX = os.environ.get('MIXES_INDEX', 'mix_search_dev')


''' 
Caching presets
'''

# Full day
FULL_DAY=86400
BALI_CACHE_TIME=14400
APPLVR_CACHE_APPO=FULL_DAY
ONE_HOUR=3600

default_carousel_settings = {
    "CarouselSettings" : {
        "My Apps" : 150,
        "Apps For You" : 40,
        "Hot Apps" : 40,
        "My Friends" : 40,
        "My Friends Apps" : 40,
        "Search Carousel Apps" : 120,
        "Mixes Carousel" : 40,
        "Featured Apps": 40,
        "Recommended Apps": 40,
        "Percentage for AFY": 100,
        "AttWidget":40
        }
}

