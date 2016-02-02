"""
Example Usage: 
    python  mig_data.py migrate http://anjuna.herokuapp.com/v2/ anil_kumble@tfbnw.net  dhoni@tfbnw.net -d
"""

import requests
from flask import Flask, json
from flaskext.script import Manager
from workerd import delayable

app = Flask(__name__)
manager = Manager(app)

auth_user = 'tablet'
auth_pwd = 'aspirin'

#---------------------------------------------------------------------
DEBUG=True
def info(str):
	if DEBUG:
		print str

@delayable
def main(server, fuser, luser, auth_pwd=auth_pwd, debug=False):
    migrate_data(server, fuser, luser, auth_pwd=auth_pwd, debug=False)   
  
def migrate_data(server, fuser, luser, auth_pwd=auth_pwd, debug=False):
    url='%sapi/users/%s/apps'%(server, fuser)
    r=requests.get(url,auth=(auth_user,auth_pwd)) 
    if r.status_code == 200:
        apps=json.loads(r.content).get('data')
        for app in apps:
            pkg=str(app.strip('[]')).replace("'", "") 
            url1='%sapi/users/%s/apps/%s/like'%(server, fuser, pkg)
            r1=requests.get(url1,auth=(auth_user,auth_pwd)) 
            url2='%sapi/users/%s/apps/%s/dislike'%(server, fuser, pkg )
            r2=requests.get(url2,auth=(auth_user,auth_pwd))
            if r1.status_code == 200:
                info(url1)
                info(r1.status_code)
                info(r1.read()) 
                url3='%sapi/users/%s/apps/%s/like'%(server, luser, pkg)
                post_function(url3, pkg)
            elif r2.status_code == 200:
                info(url2)
                info(r2.status_code)
                info(r2.read()) 
                url4='%sapi/users/%s/apps/%s/dislike'%(server, luser, pkg)
                post_function(url4, pkg)
            else:
                 pass

def post_function(url, pkg):
    r1=requests.get(url,auth=(auth_user,auth_pwd))
    info(url)
    data={"pkg":pkg}
    if r1.status_code == 200 or r1.status_code == 404:        
        post_data= requests.post(url,data,auth=(auth_user,auth_pwd))         
        info(post_data.status_code)
        info(post_data.read()) 
        info("===================================")
    else:
        print 'URL Error:',r1.status_code

@manager.command
def migrate(server, fuser, luser, auth_pwd=auth_pwd, debug=False):    
    return main(server, fuser, luser, auth_pwd, debug)

#---------------------------------------------------------------------
if __name__ == '__main__':
    manager.run()


