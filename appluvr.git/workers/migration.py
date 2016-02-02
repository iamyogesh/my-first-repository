"""
Worker tasks to collate card data for a user

"""
from flask import Flask, g, json, request, jsonify
from werkzeug import LocalProxy
from flaskext.script import Manager
from workerd import delayable
import requests

app = Flask(__name__)
manager = Manager(app)

auth_user = 'tablet'
auth_pwd = 'aspirin'

d = LocalProxy(lambda: app.logger.debug)
e = LocalProxy(lambda: app.logger.error)
w = LocalProxy(lambda: app.logger.warning)

#-------------------------------------------------------------------------------#
@delayable
def fetch_app_comments(server1, server2, user, auth_pwd=auth_pwd, debug=False):
    """
    Stub for inserting app card details views
    """
    app.debug = debug
    url1='%susers' %(server1)
    r1=requests.get( url1, auth=(auth_user,auth_pwd))
    users=json.loads(r1.content).get('data')
    for emails in users:
        email=emails.get('uniq_id')
        target1='%s/%s/apps' % (url1,email)
        r2 = requests.get(target1, auth=(auth_user,auth_pwd))
        if r2.status_code == 200:        
            apps=json.loads(r2.content).get('data')
            for pkg in apps: 
                pkg_name=str(pkg.strip('[]')).replace("'","").replace('"','')
                target2='%s/%s/comment' % (target1, pkg_name)
                url2 = "%sapi/users/%s/apps/%s/comment" %(server2, user, pkg_name)
                r3 = requests.get(target2, auth=(auth_user,auth_pwd))
                if r3.status_code == 200:
                    comments=json.loads(r3.content).get('comment')
                    comm={"comment":comments}
                    r4=requests.get(url2,auth=(auth_user,auth_pwd)) 
                    if r4.status_code == 200:
                        post_data= requests.post(url2,comm,auth=(auth_user,auth_pwd))         
                        print post_data.status_code
                        print post_data.read()
                    else:
                        print 'URL Error:',r4.status_code
                else:
                    pass
        else:
            pass

#-----------------------------------------------------------------------#                    
@manager.command
def app_comments(server1, server2, user, auth_pwd=auth_pwd, debug=False):
    return fetch_app_comments(server1, server2, user, auth_pwd, debug) 
#---------------------------------------------------------------------------#                
if __name__ == '__main__':
    manager.run()
          


