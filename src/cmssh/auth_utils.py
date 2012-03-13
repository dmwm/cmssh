#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
Set of auth utils:
- CERN SSO toolkit. Provides get_data method which allow
  to get data begind CERN SSO protected site.
- get user credential
"""
__author__ = "Valentin Kuznetsov"

import os
import time
import urllib
import urllib2
import httplib

def timestamp():
    """Construct timestamp used by Shibboleth"""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

class HTTPSClientAuthHandler(urllib2.HTTPSHandler):
    """
    Simple HTTPS client authentication class based on provided 
    key/ca information
    """
    def __init__(self, key=None, cert=None, level=0):
        urllib2.HTTPSHandler.__init__(self, debuglevel=level)
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

def get_data(url, key, cert, debug=0):
    """
    Main routine to get data from data service behind CERN SSO.
    Return file-like descriptor object (similar to open).
    """
    # setup HTTP handlers
    cookie_handler = urllib2.HTTPCookieProcessor()
    https_handler  = HTTPSClientAuthHandler(key, cert, debug)
    opener = urllib2.build_opener(cookie_handler, https_handler)
    urllib2.install_opener(opener)

    # send request to RunSummary, it set the _shibstate_ cookie which 
    # will be used for redirection
    fdesc  = opener.open(url)
    data   = fdesc.read()
    fdesc.close()

    # extract redirect parameters
    # Here is an example what should be sent to login.cern.ch via GET method
    # https://login.cern.ch/adfs/ls/auth/sslclient/?
    #    wa=wsignin1.0&
    #    wreply=https%3A%2F%2Fcmswbm.web.cern.ch%2FShibboleth.sso%2FADFS&
    #    wct=2012-03-13T20%3A21%3A51Z&
    #    wtrealm=https%3A%2F%2Fcmswbm.web.cern.ch%2FShibboleth.sso%2FADFS&
    #    wctx=cookie%3Ab6cd5965
    params = {}
    for line in data.split('\n'):
        if  line.find('Sign in using your Certificate</a>') != -1:
            args = line.split('href=')[-1].split('"')[1].\
                        replace('auth/sslclient/?', '')
            kwds = urllib.url2pathname(args).split('&amp;')
            params = dict([i.split('=') for i in kwds])
            break

    # now, request authentication at CERN login page
    params = urllib.urlencode(params, doseq=True)
    url    = 'https://login.cern.ch/adfs/ls/auth/sslclient/'
    fdesc  = opener.open(url+'?'+params)
    data   = fdesc.read()
    fdesc.close()

    # at this point it sends back the XML form to proceed since my client
    # doesn't support JavaScript and no auto-redirection happened
    # Since XML form is not well-formed XML I'll parsed manually, urggg ...
    param_dict = {}
    for item in data.split('<input '):
        if  item.find('name=') != -1 and item.find('value=') != -1:
            namelist = item.split('name="')
            key = namelist[1].split('"')[0]
            vallist = item.split('value="')
            val = vallist[1].split('"')[0]
            val = val.replace('&quot;', '"').replace('&lt;','<')
            param_dict[key] = val

    # now I'm ready to send my form to Shibboleth authentication
    # request to Shibboleth
    url    = 'https://cmswbm.web.cern.ch/Shibboleth.sso/ADFS'
    params = urllib.urlencode(param_dict)
    fdesc  = opener.open(url, params)
    return fdesc

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
