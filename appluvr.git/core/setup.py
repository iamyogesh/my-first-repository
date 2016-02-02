import os
from setuptools import setup, find_packages, Extension
#import appluvr

here = os.path.abspath(os.path.dirname(__file__))
#README = open(os.path.join(here, 'index.rst')).read()
#CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()
_version_ = open(os.path.join(here, 'RELEASE-VERSION')).read().strip()

requires = [
    'Flask',
    'Flask-Cache>=0.4.0',
    'Flask-WTF',
    'Flask-Uploads',
    'CouchDB>=0.8',
    'Werkzeug>=0.6.2',
    'simplejson>=2.1.1',
    'virtualenv>=1.6.1',
    'requests',
    'ordereddict>=1.1',
    'wsgiref>=0.1.2',
    'Flask-Exceptional',
    'redis',
    'itsdangerous'
    ]

setup(name='appluvr',
      version=_version_,
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
      test_suite='appluvr',
      install_requires=requires,
      )
