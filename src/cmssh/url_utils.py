#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
URL utils
"""

# system modules
import os
import json
import urllib
import urllib2
import subprocess
from contextlib import contextmanager

# cmssh modules
from cmssh.iprint import print_info
from cmssh.auth_utils import PEMMGR, working_pem
from cmssh.auth_utils import get_key_cert, HTTPSClientAuthHandler

def get_data(url, kwargs=None, headers=None,
        verbose=None, decoder='json', post=False):
    "Retrive data"
    ckey = None
    cert = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
    with working_pem(PEMMGR.pem) as ckey:
        return get_data_helper(url, kwargs, headers,
                verbose, decoder, post, ckey, cert)

def get_data_helper(url, kwargs=None, headers=None,
        verbose=None, decoder='json', post=False, ckey=None, cert=None):
    """Retrieve data helper function"""
    if  url.find('https') != -1:
        if  not ckey and not cert:
            ckey, cert = get_key_cert()
    else:
        ckey = None
        cert = None
    if  kwargs:
        params = kwargs
    else:
        params = {}
    if  url.find('/datasets') != -1: # DBS3 use case
        params.update({'dataset_access_type':'PRODUCTION', 'detail':'True'})
    encoded_data = urllib.urlencode(params, doseq=True)
    if  not post:
        url = url + '?' + encoded_data
    if  verbose:
        print "Request:", url, encoded_data, headers, ckey, cert
    req = urllib2.Request(url)
    if  headers:
        for key, val in headers.items():
            req.add_header(key, val)
    else:
        headers = {'Accept':'application/json;text/json'}
    if  cert:
        handler = HTTPSClientAuthHandler(ckey, cert)
        opener  = urllib2.build_opener(handler)
        urllib2.install_opener(opener)
    if  post:
        print "POST", req, url, encoded_data, params
        res = urllib2.urlopen(req, json.dumps(params))
    else:
        res = urllib2.urlopen(req)
    if  decoder == 'json':
        data = json.load(res)
    else:
        data = res.read()
    return data

def send_email(to_user, from_user, title, ticket):
    "Send email about user ticket"
    # we will use mail unix command for that
    cmd = 'echo "User: %s\nTicket:\n%s" | mail -s "cmssh gist %s" %s'\
        % (from_user, ticket, title, to_user)
    subprocess.call(cmd, shell=True)

@contextmanager
def get_data_and_close(url, ckey=None, cert=None, headers={'Accept':'*/*'}):
    "Context Manager to read data from given URL"
    if  not ckey and not cert:
        ckey, cert = get_key_cert()
    req = urllib2.Request(url)
    if  headers:
        for key, val in headers.items():
            req.add_header(key, val)

    handler = HTTPSClientAuthHandler(ckey, cert)
    opener  = urllib2.build_opener(handler)
    urllib2.install_opener(opener)
    data    = urllib2.urlopen(req)
    try:
        yield data
    finally:
        data.close()
