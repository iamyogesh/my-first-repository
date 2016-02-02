from workerd import delayable
from flask import Flask, g, json, request, jsonify
from flaskext.script import Manager
import requests

app = Flask(__name__)
manager = Manager(app)

auth_pair = ('tablet','aspirin')

auth_user = 'tablet'
auth_pwd = 'aspirin'

@delayable
def post_profile(server, user, device, auth_pwd=auth_pwd, debug=False):
    return post(server, user, device, auth_pwd)

@manager.command
def post(server, user, device, auth_pwd=auth_pwd):
    target = '%sapi/users/%s/devices/%s/appo/profile' % (server,user, device)
    print '..posting %s' % target
    r = requests.post(target, auth=(auth_user, auth_pwd))
    if r.status_code ==200:
        print 'Appo profile post: SUCCESS'
    else:
        print r.status_code
        print r.content

@manager.command
def post_all(server):
    target = '%sapi/users' % server
    r = requests.get(target, auth=auth_pair)
    if r.status_code == 200:
        users = json.loads(r.content).get('data', None)
        for user in users:
            target = '%s/users/%s/appo/profile' % (server,user.get('uniq_id'))
            print '..posting %s' % target
            r = requests.post(target, auth=auth_pair)
            if r.status_code ==200:
                pass
            else:
                print r.status_code
                print r.content


if __name__ == '__main__':
    manager.run()
