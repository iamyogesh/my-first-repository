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
    for dir in ['dev']:
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
    with cd('/home/web/appluvr/v1'):
        run('supervisorctl stop v1')
        run('/home/web/appluvr/v1/env/bin/python /home/web/appluvr/v1/env/bin/easy_install --upgrade  /tmp/%s-py2.6.egg' % dist)
        run('supervisorctl start v1')

def upload():
    dist = env.dist
    put('dist/%s-py2.6.egg' % dist, '/tmp/%s-py2.6.egg' %dist)
    run('cp /tmp/%s-py2.6.egg /home/canarys/.docs/builds' %dist)
    print 'http://182.71.252.172/builds/%s' % dist

def sdist():
    dist = env.dist
    local('python setup.py sdist', capture=False)
    #put('dist/%s.tar.gz' % dist, '/tmp/%s.tar.gz' %dist)
    #run('cp /tmp/%s.tar.gz /home/canarys/.docs/builds' %dist)
    #print 'http://182.71.252.172/builds/%s.tar.gz' % dist


def download():
    dist = env.dist
    with cd('/home/web/appluvr/v1'):
        run('wget http://182.71.252.172/builds/%s-py2.6.egg' %dist)

def docs():
    local('python setup.py build_sphinx')
    local('cd build/sphinx/html && zip -r /tmp/foo.zip .')
    put('/tmp/foo.zip','/tmp/foo.zip')
    with cd('/home/canarys/.docs/docs'):
        run('unzip -o /tmp/foo.zip')
        run('rm /tmp/foo.zip')
    local('rm /tmp/foo.zip')

def status():
    run('supervisorctl status')

def cloudant_create(app_name):
    cloudant_config = local('heroku config -s --app %s | grep CLOUDANT' % app_name, capture=True)
    appluvr_db = 'vz-appluvr-db'
    if cloudant_config:
        cloudant_db = cloudant_config.split('=')[1]
        print 'Found couchdb configured at %s ' % cloudant_db
        print 'Creating design documents'
        from couchdbkit import *
        COUCHDB_SERVER = cloudant_db
        COUCHDB_DATABASE = appluvr_db
        server = Server(COUCHDB_SERVER)
        db = server.get_or_create_db(COUCHDB_DATABASE)
        from couchdbkit.designer import push
        models = ['app','user','device','comment','interest','settings','promoapp','user_disallow', 'reports']
        [push('_design/%s' % model, db) for model in models]
        replicate_cmd = 'curl http://localhost:5984/_replicate -H \'Content-Type: application/json\' -d \'{ "source": "vz-appluvr-experts", "target": "%s/%s" }\'' % (cloudant_db, appluvr_db)
        print 'Replicating experts with command $%s ' % replicate_cmd
        local(replicate_cmd)
    else:
        print 'Unable to read cloudant config'

def db_create(server, database):
    print 'Creating design documents'
    from couchdbkit import *
    COUCHDB_SERVER = server
    COUCHDB_DATABASE = database
    _server = Server(COUCHDB_SERVER)
    db = _server.get_or_create_db(COUCHDB_DATABASE)
    from couchdbkit.designer import push
    models = ['app','user','device','comment','interest','settings','promoapp','user_disallow','reports','app_packs','deal','notification','widgets']
    [push('_design/%s' % model, db) for model in models]
    #replicate_cmd = 'curl http://localhost:5984/_replicate -H \'Content-Type: application/json\' -d \'{ "source": "vz-appluvr-experts", "target": "%s/%s" }\'' % (server, database)
    #print 'Replicating experts with command $%s ' % replicate_cmd
    #local(replicate_cmd)
