#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
Set of auth utils:
- CERN SSO toolkit. Provides get_data_sso method which allow
  to get data begind CERN SSO protected site.
- get user credential
"""
__author__ = "Valentin Kuznetsov"

# system modules
import os
import stat
import time
import urllib
import urllib2
import httplib
import tempfile
import traceback
import cookielib

# cmssh modules
from   cmssh.iprint import print_info
from   cmssh.utils import run

class HTTPSClientAuthHandler(urllib2.HTTPSHandler):
    """
    Simple HTTPS client authentication class based on provided
    key/ca information
    """
    def __init__(self, ckey=None, cert=None):
        if  int(os.environ.get('HTTPDEBUG', 0)):
            urllib2.HTTPSHandler.__init__(self, debuglevel=1)
        else:
            urllib2.HTTPSHandler.__init__(self)
        if  ckey != cert:
            self.ckey = ckey
            self.cert = cert
        else:
            self.cert = cert
            self.ckey = None

    def https_open(self, req):
        """Open request method"""
        #Rather than pass in a reference to a connection class, we pass in
        # a reference to a function which, for all intents and purposes,
        # will behave as a constructor
        return self.do_open(self.get_connection, req)

    def get_connection(self, host, timeout=300):
        """Connection method"""
        if  self.cert:
            return httplib.HTTPSConnection(host, key_file=self.ckey,
                                                cert_file=self.cert)
        return httplib.HTTPSConnection(host)

def create_https_opener(key, cert):
    "Create HTTPS url opener with cookie support"
    cookie_jar = cookielib.CookieJar()
    cookie_handler = urllib2.HTTPCookieProcessor(cookie_jar)
    https_handler  = HTTPSClientAuthHandler(key, cert)
    opener = urllib2.build_opener(cookie_handler, https_handler)
    agent = 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.6; en-US; rv:1.9.2.11) Gecko/20101012 Firefox/3.6.11'
    opener.addheaders = [('User-Agent', agent)]
    urllib2.install_opener(opener)
    return opener

class _PEMMgr(object):
    "PEM content holder"
    def __init__(self):
        self.pem  = None # to be initialized at run time

# Singleton
PEMMGR = _PEMMgr()

def read_pem():
    "Create user key pem content"
    try:
        read_pem_via_pyopenssl() # the most secure way to load user key
    except:
        read_pem_via_openssl() # fallback via openssl shell call

def read_pem_via_pyopenssl():
    "Create user key pem content via OpenSSL crypto module"
    from OpenSSL import crypto
    pkey = os.path.join(os.environ['HOME'], '.globus/userkey.pem')
    buf  = None
    with open(pkey, 'r') as key:
        buf = key.read()
    ckey = crypto.load_privatekey(crypto.FILETYPE_PEM, buf)
    PEMMGR.pem = crypto.dump_privatekey(crypto.FILETYPE_PEM, ckey)

def read_pem_via_openssl():
    """
    Create user key pem content via passless key (created by openssl).
    This function creates temporary file in user .globus area in order
    to load passless key.
    """
    globus_dir = os.path.join(os.environ['HOME'], '.globus')
    fname = os.path.join(globus_dir, 'cmssh.x509pk_u%s' % os.getuid())
    mode = stat.S_IRUSR
    try:
        cmd  = '/usr/bin/openssl rsa -in %s/.globus/userkey.pem -out %s' \
                % (os.environ['HOME'], fname)
        print # extra empty line before we read user key
        run(cmd)
        os.chmod(fname, mode)
        with open(fname, 'r') as userkey:
            PEMMGR.pem = userkey.read()
    except:
        traceback.print_exc()
    try:
        os.remove(fname)
    except:
        traceback.print_exc()

class working_pem(object):
    "ContextManager for temporary user key pem file"
    def __init__(self, pem):
        self.gdir = os.path.join(os.environ['HOME'], '.globus')
        self.pem  = pem
        self.name = None # runtime thing
    def __enter__(self):
        "Enter the runtime context related to this object"
        fobj = tempfile.mkstemp(prefix='cmssh', dir=self.gdir)
        self.name = fobj[-1]
        with open(self.name, 'w') as fname:
            fname.write(self.pem)
        return self.name
    def __exit__(self, exc_type, exc_val, exc_tb):
        "Exit the runtime context related to this object"
        os.remove(self.name)
        self.name = None

def timestamp():
    """Construct timestamp used by Shibboleth"""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def parse_sso_output(data):
    "Parse SSO XML output"
    # at this point SSO sends back the XML form to proceed since my client
    # doesn't support JavaScript and no auto-redirection happened
    # Since XML form is not well-formed XML I'll parse it manually, urggg ...
    param_dict = {}
    for item in data.split('<input '):
        if  item.find('name=') != -1 and item.find('value=') != -1:
            try:
                namelist = item.split('name="')
                key = namelist[1].split('"')[0]
            except:
                namelist = item.split('name=')
                key = namelist[1].split(' ')[0].strip()
            try:
                vallist = item.split('value="')
                val = vallist[1].split('"')[0]
            except:
                vallist = item.split('value=')
                val = vallist[1].split(' ')[0].strip()
            val = val.replace('&quot;', '"').replace('&lt;','<')
            param_dict[key] = val
        for key in ['action', 'ACTION']:
            if  item.find('%s=' % key) != -1:
                action = item.split("%s=" % key)[-1].split(" ")[0].split('"')[1]
                break
    return param_dict, action

def get_data_sso(url, key, cert, debug=0, redirect=None):
    """
    Main routine to get data from data service behind CERN SSO.
    Return file-like descriptor object (similar to open).
    For iCMS access we need to pass via environment checking, e.g.
    http://cms.cern.ch/iCMS/bla should be redirected to
    https://cms.cern.ch/test/env.cgi?url=http://cms.cern.ch/iCMS/bla
    """
    cern_env = 'https://cms.cern.ch/test/env.cgi?url='
    if  url.find('http://cms.cern.ch/iCMS') == 0 or\
        url.find('https://cms.cern.ch/iCMS') == 0:
        url   = cern_env + url
    orig_url  = url
    orig_args = url.split('?')[-1]
    # send request to url, it sets the _shibstate_ cookie which
    # will be used for redirection
    opener = create_https_opener(key, cert)
    fdesc  = opener.open(url)
    url    = fdesc.geturl()
    if  url.find('?') == -1:
        params = ''
    else:
        params = url.split('?')[-1] # redirect parameters
    if  int(os.environ.get('HTTPDEBUG', 0)):
        print_info('Response info')
        print fdesc.info()
        print fdesc.geturl()
    if  not params or params == orig_args:
        # if we did not receive new set of SSO parameters pass file
        # descriptor to upper level, e.g.
        # in case of CERN twiki it does not pass through SSO
        # therefore we just return file descriptor
        return fdesc
    fdesc.close()

    # now, request authentication at CERN login page
    url    = 'https://login.cern.ch/adfs/ls/auth/sslclient/'
    if  int(os.environ.get('HTTPDEBUG', 0)):
        print_info('CERN Login parameters')
        print url + '?' + params
    if  params:
        fdesc  = opener.open(url + '?' + params)
    else:
        fdesc  = opener.open(url)
    data   = fdesc.read()
    if  int(os.environ.get('HTTPDEBUG', 0)):
        print_info('Response info')
        print fdesc.info()
    fdesc.close()

    # at this point it sends back the XML form to proceed since my client
    # doesn't support JavaScript and no auto-redirection happened
    # Since XML form is not well-formed XML I'll parse it manually, urggg ...
    param_dict, action = parse_sso_output(data)

    # now I'm ready to send my form to Shibboleth authentication
    # request to Shibboleth
    if  action:
        url = action
    elif redirect:
        url = redirect
    else:
        url = orig_url
    params = urllib.urlencode(param_dict)
    if  int(os.environ.get('HTTPDEBUG', 0)):
        print_info('WBM parameters')
        print url + '?' + params
    fdesc  = opener.open(url, params)
    return fdesc

def get_key_cert():
    """
    Get user key/certificate
    """
    key  = None
    cert = None

    # Read user certificate chain from user globus area
    globus_key  = os.path.join(os.environ['HOME'], '.globus/userkey.pem')
    globus_cert = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
    if  os.path.isfile(globus_key):
        key  = globus_key
    if  os.path.isfile(globus_cert):
        cert  = globus_cert

    # look for cert at default location /tmp/x509up_u$uid
    if not key or not cert:
        uid  = os.getuid()
        cert = '/tmp/x509up_u'+str(uid)
        key  = cert

    # Second preference to User Proxy, very common
    elif os.environ.has_key('X509_USER_PROXY'):
        cert = os.environ['X509_USER_PROXY']
        key  = cert

    # Third preference to User Cert/Proxy combinition
    elif os.environ.has_key('X509_USER_CERT'):
        cert = os.environ['X509_USER_CERT']
        key  = os.environ['X509_USER_KEY']

    if  not os.path.exists(cert):
        raise Exception("Certificate PEM file %s not found" % key)
    if  not os.path.exists(key):
        raise Exception("Key PEM file %s not found" % key)

    if  key == cert: # key/cert in one file, e.g. /tmp/x509up_u<uid>
        key = None   # to handle correctly HTTPSHandler call

    return key, cert
