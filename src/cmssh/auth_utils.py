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
from   cmssh.iprint import print_info
from   cmssh.url_utils import get_key_cert, create_ssh_opener
from   cmssh.utils import run

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

def get_data(url, key, cert, debug=0):
    """
    Main routine to get data from data service behind CERN SSO.
    Return file-like descriptor object (similar to open).
    """
    # send request to RunSummary, it set the _shibstate_ cookie which 
    # will be used for redirection
    opener = create_ssh_opener(key, cert)
    fdesc  = opener.open(url)
    url    = fdesc.geturl()
    params = url.split('?')[-1] # redirect parameters
    if  int(os.environ.get('HTTPDEBUG', 0)):
        print_info('Response info')
        print fdesc.info()
        print fdesc.geturl()
    fdesc.close()

    # now, request authentication at CERN login page
    url    = 'https://login.cern.ch/adfs/ls/auth/sslclient/'
    if  int(os.environ.get('HTTPDEBUG', 0)):
        print_info('CERN Login parameters')
        print url + '?' + params
    fdesc  = opener.open(url + '?' + params)
    data   = fdesc.read()
    if  int(os.environ.get('HTTPDEBUG', 0)):
        print_info('Response info')
        print fdesc.info()
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
    if  int(os.environ.get('HTTPDEBUG', 0)):
        print_info('WBM parameters')
        print url + '?' + params
    fdesc  = opener.open(url, params)
    return fdesc
