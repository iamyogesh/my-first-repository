from flask import Flask, g, json, request, jsonify
from werkzeug import LocalProxy
from flaskext.script import Manager
from workerd import delayable
import requests
from werkzeug.datastructures import MultiDict
import urllib


app = Flask(__name__)
manager = Manager(app)

auth_user = 'tablet'
auth_pwd = 'aspirin'

d = LocalProxy(lambda: app.logger.debug)
e = LocalProxy(lambda: app.logger.error)
w = LocalProxy(lambda: app.logger.warning)

#-------------------------------------------------------------------------------#
@delayable
def clear_all_users_black_list(server, auth_pwd=auth_pwd, debug=False):
    """
    Stub for blocking blacklist API
    """
    app.debug = debug 
    
    black_listed_apps= get_blacklisted_apps(server)
    target1 = '%sapi/users' % (server)
    r = requests.get(target1, auth=(auth_user,auth_pwd))    
    if r.status_code == 200:
        users = [(user.get('uniq_id'),[x.get('href') for x in user.get('links') if x.get('rel') == 'device']) for user in r.json.get('data')]
        for user, devices in users:
            for device in devices:
                print user, device
                _clear_user_black_list(server, user, device, black_listed_apps, auth_pwd, debug)
    else:
        print 'Worker error - unable to fetch list of users'


@delayable
def clear_user_black_list(server, user, device, auth_pwd=auth_pwd, debug=False):
    """
    Stub for blocking blacklist API
    """
    app.debug = debug 

    black_listed_apps= get_blacklisted_apps(server)
    _clear_user_black_list(server, user, device, black_listed_apps, auth_pwd, debug)
    

def _clear_user_black_list(server, user, device, black_listed_apps, auth_pwd=auth_pwd, debug=False):
    apps_of_user = get_user_apps(server,user, device) 
    print 'User Apps: ',  apps_of_user
    print "==================================================================="
    filtered_user_apps = remove_blacklist_app(apps_of_user, black_listed_apps,user,server,device)
    print 'Filtered Apps: ',filtered_user_apps
    #return filtered_user_apps
              
       
def remove_blacklist_app(apps_of_user, black_listed_apps,user, server, device): 
    apps_to_remove= [user_app for user_app in apps_of_user if user_app.get('package_name',None) in black_listed_apps]
    if len(apps_to_remove) > 0:
        print "apps to remove:", apps_to_remove 
    else:
        print "no apps to remove - user is clean"
        return
    for black_app in apps_to_remove:
        apps_of_user.remove(black_app)
    print "------------------------",apps_of_user
    if len(apps_of_user) > 0:
        data_to_post= {'apps':apps_of_user , 'live':'0'}     
        target4 = '%sviews/users/%s/devices/%s/apps' % (server, user, device)
        updated_user_apps= post_filtered_apps(target4, data_to_post)
        return updated_user_apps
    else:
        target3 = '%sviews/users/%s/devices/%s/apps' % (server,user, device)       
        updated_user_apps= delete_apps(target3)
        return updated_user_apps
        
   
def post_filtered_apps(url, mydata):
    r=requests.get(url,auth=(auth_user,auth_pwd)) 
    if r.status_code == 200:
        final_data=json.dumps(mydata.get('apps'))
        post_data= requests.post(url, data=dict(apps=final_data,live=0), auth=(auth_user,auth_pwd))
        print post_data.status_code         
        return post_data.content
    else:
        print 'URL Error:',r.status_code
 
    
def delete_apps(url):
    r=requests.get(url,auth=(auth_user,auth_pwd)) 
    if r.status_code == 200:        
        delete_data= requests.delete(url,auth=(auth_user,auth_pwd)) 
        return delete_data.status_code       
    else:
        print 'URL Error:',r.status_code 

def get_blacklisted_apps(server):   
    black_list=[]
    target1 = '%sapi/apps/blacklist' % (server)
    r1 = requests.get(target1, auth=(auth_user,auth_pwd))
    if r1.status_code == 200:
        list_of_black_apps=json.loads(r1.content).get('blacklisted_apps')
        if len(list_of_black_apps) == 0:
            d("No blacklisted package ids are present")  
            return black_list
        else:
            blacklist_apps = [pkg.get('package_name') for pkg in list_of_black_apps]
            return blacklist_apps      
    else:
        e('Worker failed with error code: %s' % r1.status_code)
        return black_list
      
      
def get_user_apps(server,user, device): 
    """
    Stub for getting user apps
    """  
    apps_of_user=[]   
    apps=[]
    target1 = '%sviews/users/%s/devices/%s/apps' % (server,user, device)
    r1 = requests.get(target1, auth=(auth_user,auth_pwd))
    if r1.status_code == 200:
        all_pkg_names=json.loads(r1.content).get('data',None)
        if len(all_pkg_names) == 0:
            return apps
        else:
            return all_pkg_names
    else:
        e('Worker failed with error code: %s' % r1.status_code)
        return apps
    
#-----------------------------------------------------------------------#                    
@manager.command
def clear_user(server, user, device, auth_pwd=auth_pwd, debug=False):
    return clear_user_black_list(server, user, device, auth_pwd=auth_pwd, debug=debug)

@manager.command
def clear_all_users(server, auth_pwd=auth_pwd, debug=False):
    return clear_all_users_black_list(server, auth_pwd=auth_pwd, debug=debug)

#---------------------------------------------------------------------------#                
if __name__ == '__main__':
    manager.run()
   
