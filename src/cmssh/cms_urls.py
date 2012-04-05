#!/usr/bin/env python

"""CMS URLs"""

# system modules
import os

def phedex_url(api=''):
    """Return Phedex URL for given API name"""
    return 'https://cmsweb.cern.ch/phedex/datasvc/json/prod/%s' % api

def get_dbs_instance(url):
    "Get DBS instance from DBS URL"
    if  url.find('cmsweb') != -1: # DBS3
        return url.split('/')[4]
    elif url.find('cmsdbsprod') != -1: # DBS2
        return url.split('/')[3]
    else:
        msg = 'Unsupported DBS url=%s' % url
        raise Exception(msg)

def dbs_url(inst='global', api=''):
    """Return DBS URL for given API name"""
    # DBS3 settings
    url = 'https://cmsweb.cern.ch/dbs/prod/%s/DBSReader/%s' % (inst, api)
    # DBS2 settings
    if  inst.find('cms_dbs') != -1:
        url = 'http://cmsdbsprod.cern.ch/%s/servlet/DBSServlet' % inst
    if  os.environ.has_key('DBS_INSTANCE'):
        url.replace('global', os.environ['DBS_INSTANCE'])
    return url

def conddb_url(api=''):
    """Return CondDB URL for given API name"""
    return 'http://cms-conddb.cern.ch/%s' % api

def sitedb_url(api=''):
    """Return SiteDB URL for given API name"""
    return 'https://cmsweb.cern.ch/sitedb/data/prod/%s' % api

def dashboard_url(api=''):
    "Return Dashboard URL for given API name"
    url = 'http://dashb-cms-job.cern.ch/dashboard/request.py/%s' % api
    return url
