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
    def __init__(self, ckey=None, cert=None):
#        urllib2.HTTPSHandler.__init__(self, debuglevel=1)
        urllib2.HTTPSHandler.__init__(self)
        self.ckey = ckey
        self.cert = cert

    def https_open(self, req):
        """Open request method"""
        #Rather than pass in a reference to a connection class, we pass in
        # a reference to a function which, for all intents and purposes,
        # will behave as a constructor
        return self.do_open(self.get_connection, req)

    def get_connection(self, host, timeout=300):
        """Connection method"""
        if  self.ckey:
            return httplib.HTTPSConnection(host, key_file=self.ckey,
                                                cert_file=self.cert)
        return httplib.HTTPSConnection(host)

def get_data(url, method, kwargs, headers=None, verbose=None):
    """Retrieve data"""
    if  url.find('https') != -1:
        ckey, cert = get_key_cert()
    else:
        ckey = None
        cert = None
    url = os.path.join(url, method)
    if  kwargs:
        params = kwargs
    else:
        params = {}
    if  method == 'datasets':
        params.update({'dataset_access_type':'PRODUCTION', 'detail':'True'})
    url = url + '?' + urllib.urlencode(params, doseq=True)
    if  verbose:
        print "Request:", url, headers, ckey, cert
    req = urllib2.Request(url)
    if  headers:
        for key, val in headers.items():
            req.add_header(key, val)
    else:
        headers = {'Accept':'application/json;text/json'}
    if  ckey and cert:
        handler = HTTPSClientAuthHandler(ckey, cert)
        opener  = urllib2.build_opener(handler)
        urllib2.install_opener(opener)
    res  = urllib2.urlopen(req)
    data = json.load(res)
    return data

def get_key_cert():
    """
    Get user key/certificate
    """
    key  = None
    cert = None
    globus_key  = os.path.join(os.environ['HOME'], '.globus/userkey.pem')
    globus_cert = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
    if  os.path.isfile(globus_key):
        key  = globus_key
    if  os.path.isfile(globus_cert):
        cert  = globus_cert

    # First presendence to HOST Certificate, RARE
    if  os.environ.has_key('X509_HOST_CERT'):
        cert = os.environ['X509_HOST_CERT']
        key  = os.environ['X509_HOST_KEY']

    # Second preference to User Proxy, very common
    elif os.environ.has_key('X509_USER_PROXY'):
        cert = os.environ['X509_USER_PROXY']
        key  = cert

    # Third preference to User Cert/Proxy combinition
    elif os.environ.has_key('X509_USER_CERT'):
        cert = os.environ['X509_USER_CERT']
        key  = os.environ['X509_USER_KEY']

    # Worst case, look for cert at default location /tmp/x509up_u$uid
    elif not key or not cert:
        uid  = os.getuid()
        cert = '/tmp/x509up_u'+str(uid)
        key  = cert

    if  not os.path.exists(cert):
        raise Exception("Certificate PEM file %s not found" % key)
    if  not os.path.exists(key):
        raise Exception("Key PEM file %s not found" % key)

    return key, cert

