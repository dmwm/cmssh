#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
File       : sitedb.py
Author     : Valentin Kuznetsov <vkuznet@gmail.com>
Description: SiteDB module
"""

# system modules
import os
import sys
import json
import time
import urllib2

# cmssh modules
from   cmssh.url_utils import get_data_and_close
from   cmssh.auth_utils import PEMMGR, working_pem, HTTPSClientAuthHandler

def rowdict(columns, row):
    """Convert given row list into dict with column keys"""
    robj = {}
    for k,v in zip(columns, row):
        robj.setdefault(k,v)
    return robj

def parser(data):
    """SiteDB parser"""
    if  isinstance(data, str) or isinstance(data, unicode):
        data = json.loads(data)
    if  not isinstance(data, dict):
        raise Exception('Wrong data type')
    if  data.has_key('desc'):
        columns = data['desc']['columns']
        for row in data['result']:
            yield rowdict(columns, row)
    else:
        for row in data['result']:
            yield row

class SiteDBManager(object):
    "SiteDB manager"
    def __init__(self, url='https://cmsweb.cern.ch/sitedb/data/prod', threshold = 10800):
        self.resources = []
        self.names = []
        self.url = url
        self.mapping = {}
        self.timestamp = time.time()
        self.threshold = threshold # in sec, default 3 hours
        self.init()

    def init(self):
        "initialize SiteDB connection and retrieve all names"
        # get site names
        url = self.url + '/site-names'
        names = {}
        cert = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
        with working_pem(PEMMGR.pem) as key:
            with get_data_and_close(url, key, cert) as data:
                for row in parser(data.read()):
                    names[row['site_name']] = row['alias']
            # get site resources
            url = self.url + '/site-resources'
            with get_data_and_close(url, key, cert) as data:
                for row in parser(data.read()):
                    fqdn = row['fqdn']
                    for sename in row['fqdn'].split(','):
                        self.mapping[sename.strip()] = names[row['site_name']]

    def get_name(self, sename):
        "Retrieve CMS name for given SE"
        if  not sename:
            return None
        if  time.time() - self.timestamp > self.threshold:
            self.init() # refresh data from SiteDB
        return self.mapping.get(sename, None)
