

Welcome to the Verizon AppLuvr - Server Application Project Home
===================================================================

This project contains the 'views' of the AppLuvr REST API that are presented to the web, tablet and smartphone apps. This needs to be used in conjunction with the core Appluvr module.

Installation Requirements
-------------------------

* Python 2.6
* setuptools
* gunicorn
* gevent
* easy_install
* virtualenv
* CouchDB

Workers: Setup Steps
--------------------
Install `Python 2.6`:
    sudo apt-get update; apt-get install python2.6
Install `easy_install`:
    sudo apt-get install python-setuptools
Install `virtualenv`:
    easy_install virtualenv
Create a `virtualenv`:
    virtualenv --no-site-packages env
    source env/bin/activate
Install the package requirements using `pip`:
    pip install -r worker-requirements.txt
Run individual workers (example below):
   
    python build_carousel_views.py apps_for_you http://baadaami.herokuapp.com/v2/ 383935aaffff-ffff-935c-7554-00000000 00000000-4557-c539-ffff-ffffaa539383  -d


Web: Setup Steps
----------------

* Install Python 2.6.
* Create a virtualenv (virtualenv  --no-site-packages env)
* Install easy_install
* easy_install gunicorn
* pip install -r requirements.txt
* easy_install --upgrade appluvr.egg
* Modify parameters in the config.py as needed
* Modify .env parameters as needed
* Run gunicorn with the bootstrap file or using foreman
* Install gevent libraries as required by your OS

Developers
----------
Add a symlink to the precommit script so that all unit tests are run before a checkin
ln -sf ../../pre-commit.sh .git/hooks/pre-commit

Author: Arvi Krishnaswamy


