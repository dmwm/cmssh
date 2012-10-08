#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
CMS PREP plugin
"""
__author__ = "Valentin Kuznetsov"

# system modules
import os
import json
import urllib
import cookielib

# 3d party modules
from html2text import wrapwrite, html2text

# cmssh modules
from   cmssh.iprint import print_info
from   cmssh.auth_utils import PEMMGR, working_pem, get_data_sso
from   cmssh.auth_utils import parse_sso_output, create_https_opener

def prep(dataset):
    "Retrieve information from CMS ReqMgr data-service"
    dsn  = dataset.split('/')[1]
    purl= 'http://cms.cern.ch/iCMS/jsp/mcprod/admin/requestmanagement.jsp'
    args = {'dsn': dsn, 'campid':'any'}
    sso  = 'https://cms.cern.ch/test/env.cgi?url='
    url  = sso + purl + '?' + urllib.urlencode(args)
    cert = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
    data = ''
#    print "url", url
    with working_pem(PEMMGR.pem) as key:
        data   = get_data_sso(url, key, cert).read()
        params_dict, action = parse_sso_output(data)
        params = urllib.urlencode((params_dict))
#        print "params", params
#        print "action", action
        if  action:
            opener = create_https_opener(key, cert)
            fdesc  = opener.open(action, params)
            data   = fdesc.read()
            for row in data.split('\n'):
                if  row.find('setCookie') != -1:
                    ctup = row.split('(')[-1].replace('"', '').replace("'", '').split(',')[:2]
#                    print "key/val", ctup
            for hdl in opener.handlers:
                if  repr(hdl).find('urllib2.HTTPCookieProcessor') != -1:
                    for ccc in hdl.__dict__['cookiejar']:
                        cookie = cookielib.Cookie(\
                                port=None, port_specified=False, domain=ccc.domain,
                                domain_specified=False, domain_initial_dot=False,
                                path=ccc.path, path_specified=False, secure=None, expires=None,
                                discard=True, comment=None, comment_url=None, rest=None,
                                version=0, name=ctup[0], value=ctup[1])
                        hdl.__dict__['cookiejar'].set_cookie(cookie)
                        break
                        print hdl.__dict__['cookiejar']
#            print "\n### data", '\n'.join([r for r in data.split() if r])
            fdesc  = opener.open(purl + '?' + urllib.urlencode(args))
            data   = fdesc.read()
#    print "\n### data", data
    wrapwrite(html2text(data, ''))
