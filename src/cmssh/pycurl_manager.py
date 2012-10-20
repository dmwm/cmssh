#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
#pylint: disable-msg=R0913,W0702,R0914,R0912,R0201
"""
File: pycurl_manager.py
Author: Valentin Kuznetsov <vkuznet@gmail.com>
Description: a basic wrapper around pycurl library.
The RequestHandler class provides basic APIs to get data
from a single resource or submit mutliple requests to
underlying data-services.

For CMS the primary usage would be access to DBS3 where
we need to fetch dataset details for a given dataset pattern.
This is broken into 2 APIs, datasets which returns list of
datasets and filesummaries which provides details about
given dataset. So we invoke 1 request to datasets API
followed by N requests to filesummaries API.
"""

import os
import sys
import stat
import urllib
import thread
import pycurl
import urllib
import urllib2
import tempfile
import traceback
import subprocess
from cmssh.auth_utils import PEMMGR, read_pem, working_pem, get_key_cert, HTTPSClientAuthHandler
try:
    import cStringIO as StringIO
except:
    import StringIO

class RequestHandler(object):
    """
    RequestHandler provides APIs to fetch single/multiple
    URL requests based on pycurl library
    """
    def __init__(self, config=None):
        super(RequestHandler, self).__init__()
        if  not config:
            config = {}
        self.nosignal = config.get('nosignal', 1)
        self.timeout = config.get('timeout', 300)
        self.connecttimeout = config.get('connecttimeout', 30)
        self.followlocation = config.get('followlocation', 1)
        self.maxredirs = config.get('maxredirs', 5)
        self.cache = {} # fill at run time

    def set_opts(self, curl, url, params, headers,
                 ckey=None, cert=None, post=None, doseq=True, verbose=None):
        """Set options for given curl object"""
        curl.setopt(pycurl.NOSIGNAL, self.nosignal)
        curl.setopt(pycurl.TIMEOUT, self.timeout)
        curl.setopt(pycurl.CONNECTTIMEOUT, self.connecttimeout)
        curl.setopt(pycurl.FOLLOWLOCATION, self.followlocation)
        curl.setopt(pycurl.MAXREDIRS, self.maxredirs)
        curl.setopt(pycurl.COOKIEJAR, '.cookie')
        curl.setopt(pycurl.COOKIEFILE, '.cookie')

        encoded_data = urllib.urlencode(params, doseq=doseq)
        if  not post:
            url = url + '?' + encoded_data
            curl.setopt(pycurl.POST, 0)
        if  post:
            curl.setopt(pycurl.POST, 1)
            curl.setopt(pycurl.POSTFIELDS, encoded_data)
        if  isinstance(url, str):
            curl.setopt(pycurl.URL, url)
        elif isinstance(url, unicode):
            curl.setopt(pycurl.URL, url.encode('ascii', 'ignore'))
        else:
            raise TypeError('Wrong type for url="%s", type="%s"' \
                % (url, type(url)))
        if  headers:
            curl.setopt(pycurl.HTTPHEADER, \
                    ["%s: %s" % (k, v) for k, v in headers.iteritems()])
        bbuf = StringIO.StringIO()
        hbuf = StringIO.StringIO()
        curl.setopt(pycurl.WRITEFUNCTION, bbuf.write)
        curl.setopt(pycurl.HEADERFUNCTION, hbuf.write)
        curl.setopt(pycurl.SSL_VERIFYPEER, False)
        if  ckey:
            curl.setopt(pycurl.SSLKEY, ckey)
        if  cert:
            curl.setopt(pycurl.SSLCERT, cert)
        if  verbose:
            curl.setopt(pycurl.VERBOSE, 1)
            if  isinstance(verbose, int) and verbose > 1:
                curl.setopt(pycurl.DEBUGFUNCTION, self.debug)
        return bbuf, hbuf

    def debug(self, debug_type, debug_msg):
        """Debug callback implementation"""
        print "debug(%d): %s" % (debug_type, debug_msg)

    def get_data(self, url, params, headers=None, post=None,
                ckey=None, cert=None, doseq=True, verbose=None):
        """Fetch data for given set of parameters"""
        if  self.cache.has_key(thread):
            curl = self.cache.get(thread)
        else:
            curl = pycurl.Curl()
            self.cache[thread] = curl
        bbuf, hbuf = self.set_opts(curl, url, params, headers,
                ckey, cert, post, doseq, verbose)
        curl.perform()
        bbuf.seek(0)# to use file description seek to the begining of the stream
        data = bbuf # leave StringIO object, which will serve as file descriptor
        hbuf.flush()
        return data
