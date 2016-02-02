from fabric.api import *

def dev():
    env.user = 'canarys'
    env.hosts = ['182.71.252.172']

def stg():
    env.user = 'web'
    env.hosts = ['107.6.69.201']

def prod():
    env.user = 'web'
    env.hosts = ['107.6.69.195', '107.6.69.196']

def pack():
    # create a new source distribution an egg
    local('python setup.py bdist_egg', capture=False)
    dist = local('python setup.py --fullname', capture=True).strip()
    local('zip -d dist/%s-py2.6.egg \*.py' % dist)

def getver():
    dist = local('python setup.py --fullname', capture=True).strip()
    env.dist = dist

def canarys():
    # figure out the release name and version
    dist = local('python setup.py --fullname', capture=True).strip()
    # upload the source tarball to the temporary folder on the server
    put('dist/%s-py2.6.egg' % dist, '/tmp/%s-py2.6.egg' %dist)
    for dir in ['v2']:
        with cd('/home/canarys/%s' % dir):
            run('/home/canarys/%s/env/bin/python /usr/local/bin/easy_install --upgrade /tmp/%s-py2.6.egg' %(dir,dist))
            run('supervisorctl restart %s' % dir)
    run('cp /tmp/%s-py2.6.egg /home/canarys/.docs/builds' %dist)
    run('rm /tmp/%s-py2.6.egg' %dist)

def deploy():
    # figure out the release name and version
    dist = local('python setup.py --fullname', capture=True).strip()
    # upload the source tarball to the temporary folder on the server
    put('dist/%s-py2.6.egg' % dist, '/tmp/%s-py2.6.egg' %dist)    
    with cd('/home/web/appluvr/v2'):
        run('supervisorctl stop v2')
        run('/home/web/appluvr/v2/env/bin/python /home/web/appluvr/v2/env/bin/easy_install --upgrade  /tmp/%s-py2.6.egg' % dist)
        run('supervisorctl start v2')

def upload():
    dist = env.dist
    put('dist/%s-py2.6.egg' % dist, '/tmp/%s-py2.6.egg' %dist)
    run('cp /tmp/%s-py2.6.egg /home/canarys/.docs/builds' %dist)

def download():
    dist = env.dist
    with cd('/home/web/appluvr/v2'):
        run('wget http://182.71.252.172/builds/%s-py2.6.egg' %dist)

def restart(app):
    run('supervisorctl restart %s' % app)

def status():
    run('supervisorctl status')

def heroku_delete(app_name):
    # blows away app!
    local('heroku apps:destroy --app %s --confirm %s' % (app_name, app_name))

def heroku_create(app_name):
    # Blows away and rebuild instance
    local('git branch -f %s HEAD' % app_name)
    local('git checkout %s' % app_name)
    local('heroku create %s --stack cedar --remote %s --addons blitz:250,cloudant:oxygen,redistogo:nano' % (app_name, app_name))
    local('heroku config:add APPLUVR_VIEW_SERVER=http://%s.herokuapp.com/v2/ --app %s' % (app_name, app_name))
    local('git push %s %s:master' % (app_name, app_name))
