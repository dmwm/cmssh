#!/usr/bin/env python

"""CMS URLs"""

def phedex_url(api=''):
    """Return Phedex URL for given API name"""
    return 'https://cmsweb.cern.ch/phedex/datasvc/json/prod/%s' % api

def dbs_url(api=''):
    """Return DBS URL for given API name"""
    return 'https://cmsweb.cern.ch/dbs/DBSReader/%s' % api

def conddb_url(api=''):
    """Return CondDB URL for given API name"""
    return 'http://cms-conddb.cern.ch/%s' % api

def sitedb_url(api=''):
    """Return SiteDB URL for given API name"""
    return 'https://cmsweb.cern.ch/sitedb/data/prod/%s' % api
