import os
from setuptools import setup, find_packages, Extension
import appluvr_views

here = os.path.abspath(os.path.dirname(__file__))
#README = open(os.path.join(here, 'index.rst')).read()
#CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()

requires = [
    'Flask',
    'Flask-WTF',
    'Flask-CouchDB>=0.2.1',
    'CouchDB>=0.8',
    'Werkzeug>=0.6.2',
    'simplejson>=2.1.1',
    'virtualenv>=1.6.1',
    'requests',
    'ordereddict>=1.1',
    'wsgiref>=0.1.2',
    'pycrypto>=2.3',
    'python-memcached>=1.39',
    'Flask-Exceptional',
    'Beaker'
    ]

setup(name='appluvr_views',
      version=appluvr_views.__version__,
      description='App discovery app',
#      long_description=README,
      classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Web Environment",
        "Framework :: Flask",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
        "Programming Language :: JavaScript",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.6",
        "Topic :: Internet",
        ],
      author='Arvi',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='appluvr_views',
      install_requires=requires,
      )
