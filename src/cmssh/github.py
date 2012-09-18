#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
File       : github.py
Author     : Valentin Kuznetsov <vkuznet@gmail.com>
Description: Module to handle github issues
"""

# system modules
import json
import urllib2

# cmssh modules
from cmssh.cms_objects import Ticket
from cmssh.url_utils import get_data

def get_tickets(ticket=None, **kwds):
    """
    Retrieve information about cmssh tickets
    """
    res  = []
    url  = 'https://api.github.com'
    path = 'repos/vkuznet/cmssh/issues'
    if  ticket:
        path += '/%s' % ticket
    url += path
    res  = get_data(url, kwds)
    if  isinstance(res, dict):
        res = [res]
    res  = [Ticket(t) for t in res]
    return res

def post_ticket(title, files=None, public=True):
    """
    Post new ticket on github
    """
    if  not files:
        files = {}
    url  = 'https://api.github.com/gists'
    req  = urllib2.Request(url)
    data = dict(description=title, public=public, files=files)
    try:
        req.add_header("Content-Type", "application/json")
        res = urllib2.urlopen(req, json.dumps(data))
    except (IOError, urllib2.HTTPError) as err:
        raise RuntimeError("Error on url=%s e=%s" % (url, err))
    data = json.load(res)
    return data

def post_ticket_orig(kwds, auth):
    """
    Post new ticket on github
    """
    url  = 'https://api.github.com/gists'
    req  = urllib2.Request(url)
    req.add_header("Authorization", "Basic %s" % auth)
    try:
        req.add_header("Content-Type", "application/json")
        res = urllib2.urlopen(req, json.dumps(kwds))
    except (IOError, urllib2.HTTPError) as err:
        raise RuntimeError("Error on url=%s e=%s" % (url, err))
    data = json.load(res)
    return data
