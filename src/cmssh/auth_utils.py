#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
Set of auth utils:
- CERN SSO toolkit. Provides get_data method which allow
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
import tempfile
import traceback

# cmssh modules
from   cmssh.url_utils import HTTPSClientAuthHandler, get_key_cert
from   cmssh.utils import run

class _PEMMgr(object):
    "PEM content holder"
    def __init__(self):
        self.pem  = None # to be initialized at run time

# Singleton
PEMMGR = _PEMMgr()

def read_pem():
    "Create user key pem content"
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

def get_data(url, key, cert, debug=0):
    """
    Main routine to get data from data service behind CERN SSO.
    Return file-like descriptor object (similar to open).
    """
    # setup HTTP handlers
    cookie_handler = urllib2.HTTPCookieProcessor()
    https_handler  = HTTPSClientAuthHandler(key, cert)
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
    # Since XML form is not well-formed XML I'll parse it manually, urggg ...
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
