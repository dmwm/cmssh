#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
Read CERN HTML pages, protected by SSO mechanism
"""
__author__ = "Valentin Kuznetsov"

import os
from feedparser import _getCharacterEncoding as enc
from html2text import wrapwrite, html2text

from cmssh.auth_utils import get_data_sso, PEMMGR, working_pem

def read(url, debug=0):
    "Get run information from RunSummary data-service"
    key  = None
    cert = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
    with working_pem(PEMMGR.pem) as key:
        data = get_data_sso(url, key, cert, debug)
        html = data.read()
        encoding = enc(data.headers, html)[0]
        if  encoding == 'us-ascii':
            encoding = 'utf-8'
        print "html", type(html), encoding
        text = html.decode(encoding)
        wrapwrite(html2text(text, ''))
