#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
RunSummary service
"""
__author__ = "Valentin Kuznetsov"

import os
import time
import urllib

from cmssh.utils import xml_parser
from cmssh.auth_utils import get_data_sso, PEMMGR, working_pem

def run_summary_url(url, params):
    """Construct Run Summary URL from provided parameters"""
    if  url[-1] == '/':
        url = url[:-1]
    if  url[-1] == '?':
        url = url[:-1]
    paramstr = ''
    for key, val in params.iteritems():
        if  isinstance(val, list):
            paramstr += '%s=%s&' % (key, urllib.quote(val))
        elif key.find('TIME') != -1:
            paramstr += '%s=%s&' % (key, urllib.quote(val))
        else:
            paramstr += '%s=%s&' % (key, val)
    return url + '?' + paramstr[:-1]

def convert_datetime(sec):
    """Convert seconds since epoch to date format used in RunSummary"""
    return time.strftime("%Y.%m.%d %H:%M:%S", time.gmtime(sec))

def runsum(run, debug=0):
    "Get run information from RunSummary data-service"
    url  = "https://cmswbm.web.cern.ch/cmswbm/cmsdb/servlet/RunSummary"
    args = {"DB":"cms_omds_lb", "FORMAT":"XML", "RUN": "%s" % run}
    url  = run_summary_url(url, args)
    key  = None
    cert = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
    with working_pem(PEMMGR.pem) as key:
        data = get_data_sso(url, key, cert, debug, read_wbm=True)
        for row in xml_parser(data, 'runInfo'):
            yield row['runInfo']
