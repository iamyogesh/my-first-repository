from appluvr import couchdb
#from flaskext.couchdb import *
from couchdbkit.schema import *
from couchdbkit import *
from appluvr.utils.misc import url_map
from werkzeug import LocalProxy
import time
from flask import current_app

spit = LocalProxy(lambda: current_app.logger.debug)


"""
.. autoclass:: LinkedDocument
"""
class LinkedDocument(couchdb.Document):
    doc_type = 'linked'
    # Track last modified time for all entities
    last_modified = IntegerProperty(default=None)
    # Track first created time for all entities
    first_created = IntegerProperty(default=None)
    links = ListProperty()

    def toDict(self):
        retval = dict(links=self.get_links(), _id = self._id, first_created=self.first_created, last_modified=self.last_modified)
        #import pdb; pdb.set_trace()
        return retval

    def get_links(self):
        #return [ (dict(rel=link.rel, href=link.href)) for link in self.links if link['href'] != '__stale__']
        #return [ (dict(link=url_map(link.rel,link.href), rel=link.rel, href=link.href)) for link in self.links if link['href'] != '__stale__']
        #import pdb; pdb.set_trace()
        return [ (dict(rel=link.get('rel'), href=link.get('href'))) for link in self.links if link.get('href') != '__stale__']

    def add_link(self, rel, uniq_id):
        assert(uniq_id)
        if not uniq_id in [link['href'] for link in self.links if link['rel'] == rel]:
            print self.links
            self.links.append(rel=rel,href=uniq_id)
            print self.links

    def del_link(self, uniq_id):
        assert(uniq_id)
        update = False
        for index, link in enumerate(self.links):
            if link['href'] == uniq_id:
                spit(link["rel"] +" link href " + uniq_id + " at index " + str(index) + " of " + str(len(self.links))) 
                link['href'] = None
                link['rel'] = '_stale_'
                update = True
        self.store() if update == True else False

    @classmethod
    def load(cls, id):
        try:
            return cls.get(id)
        except:
            return None

    def update(self):
        if self.first_created is None:
           self.first_created = int(time.time())
        self.last_modified = int(time.time())
        self.store()

    def __repr__(self):
        return '<LinkedDocument>'

__all__ = ['LinkedDocument']
