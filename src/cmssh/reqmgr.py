#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
CMS RequestManager plugin
"""
__author__ = "Valentin Kuznetsov"

# system modules
import os
import json

# cmssh modules
from   cmssh.iprint import print_info
from   cmssh.url_utils import get_data_and_close
from   cmssh.auth_utils import PEMMGR, working_pem, HTTPSClientAuthHandler

def reqmgr(dataset):
    "Retrieve information from CMS ReqMgr data-service"
    url  = 'https://cmsweb.cern.ch/reqmgr/rest/configIDs' + dataset
    cert = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
    configs = []
    with working_pem(PEMMGR.pem) as key:
        with get_data_and_close(url, key, cert) as data:
            stream = data.read()
            try:
                jsondict = json.loads(stream)
            except Exception as _exc:
                jsondict = eval(stream, { "__builtins__": None }, {})
            for key, val in jsondict.items():
                for item in val:
                    configs.append(item)
    if  configs:
        print_info('Found configuration %s files:' % len(configs))
        for rec in configs:
            print rec
    else:
        print_info('No configuration files is found')
