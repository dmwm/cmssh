#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
URL utils
"""

import os
import json
import httplib
import urllib
import urllib2

class HTTPSClientAuthHandler(urllib2.HTTPSHandler):
    """
    Simple HTTPS client authentication class based on provided 
    key/ca information
    """
    def __init__(self, key=None, cert=None, level=0):
        if  level:
            urllib2.HTTPSHandler.__init__(self, debuglevel=1)
        else:
            urllib2.HTTPSHandler.__init__(self)
        self.key = key
        self.cert = cert

    def https_open(self, req):
        """Open request method"""
        #Rather than pass in a reference to a connection class, we pass in
        # a reference to a function which, for all intents and purposes,
        # will behave as a constructor
        return self.do_open(self.get_connection, req)

    def get_connection(self, host, timeout=300):
        """Connection method"""
        if  self.key:
            return httplib.HTTPSConnection(host, key_file=self.key,
                                                cert_file=self.cert)
        return httplib.HTTPSConnection(host)

def get_data(url, method, kwargs, ckey=None, cert=None, verbose=None):
    """Retrieve data"""
    url = os.path.join(url, method)
    if  kwargs:
        params = kwargs
    else:
        params = {}
    if  method == 'datasets':
        params.update({'dataset_access_type':'PRODUCTION', 'detail':'True'})
    url = url + '?' + urllib.urlencode(params, doseq=True)
#    print "\n### URL", url
    req = urllib2.Request(url)
    headers = {'Accept':'application/json;text/json'}
    if  headers:
        for key, val in headers.items():
            req.add_header(key, val)
    if  ckey and cert:
        handler = HTTPSClientAuthHandler(ckey, cert, verbose)
        opener  = urllib2.build_opener(handler)
        urllib2.install_opener(opener)
    res  = urllib2.urlopen(req)
    data = json.load(res)
    return data

