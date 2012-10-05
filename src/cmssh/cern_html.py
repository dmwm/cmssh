#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
Read CERN HTML pages, protected by SSO mechanism
"""
__author__ = "Valentin Kuznetsov"

# system modules
import os
import pydoc
import urllib

# 3d party modules
from feedparser import _getCharacterEncoding as enc
from html2text import wrapwrite, html2text

# cmssh modules
from cmssh.auth_utils import get_data_sso, PEMMGR, working_pem
from cmssh.url_utils import get_data

def read(url, output=None, debug=0):
    "Get run information from RunSummary data-service"
    encoding = 'utf-8'
    key  = None
    cert = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
    if  os.path.isfile(url):
        with open(url, 'r') as stream:
            context = stream.read()
            try:
                pydoc.pager(context)
            except:
                print context
        return
    elif url.find('cmsweb.cern.ch') != -1:
        data = get_data(url, decoder=None)
        html = data
        encoding = None
    elif url.find('mcdb.cern.ch') != -1:
        data = urllib.urlopen(url)
        html = data.read()
        encoding = enc(data.headers, html)[0]
    elif url.find('cern.ch') == -1:
        data = urllib.urlopen(url)
        html = data.read()
        encoding = enc(data.headers, html)[0]
    else:
        with working_pem(PEMMGR.pem) as key:
            data = get_data_sso(url, key, cert, debug)
            html = data.read()
            encoding = enc(data.headers, html)[0]
    if  encoding == 'us-ascii':
        encoding = 'utf-8'
    if  html:
        if  encoding:
            text = html.decode(encoding)
            res  = html2text(text, '')
            if  output:
                with open(output, 'w') as stream:
                    stream.write(html)
            else:
                try:
                    pydoc.pager(res.encode('utf-8'))
                except:
                    wrapwrite(html2text(text, ''))
        else:
            if  output:
                with open(output, 'w') as stream:
                    stream.write(html)
            else:
                try:
                    pydoc.pager(html)
                except:
                    print html
