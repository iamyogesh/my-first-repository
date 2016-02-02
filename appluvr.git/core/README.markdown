

Welcome to the Verizon AppLuvr - Core Backend
---------------------------------------------

The main application is in the source directory, and can be either run using run_server.py or configured with apache using the wsgi script provided.

The Makefile assists with creating an installable egg, generating auto docs using Sphinx and publishing changes to the servers.


Installation Requirements
-------------------------

* Python 2.6
* setuptools
* gunicorn
* gevent
* Flask
* easy_install
* virtualenv
* CouchDB

Database view installation needs to be done by hand using couchapp or the init script

The full list is in the requirements.txt

This module is not meant to be used standalone, but run in conjunction with the views module

Database
--------

All CouchDB views and list functions are located in the _design folder
