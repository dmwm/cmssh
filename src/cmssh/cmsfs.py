#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
CMSFS is a file-system on top of routefs to access CMS meta-data
"""

import os
import json
import routes
from   types import GeneratorType, InstanceType
from   cmssh.url_utils import get_data
from   cmssh.cms_objects import Run, File, Block, Dataset, Site, User
from   cmssh.ddict import DotDict, convert_dot_notation

def rowdict(columns, row):
    """Convert given row list into dict with column keys"""
    robj = {}
    for key, val in zip(columns, row):
        robj.setdefault(key, val)
    return robj
    
def sitedb_parser(data):
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

def find_sites(url, method, params):
    data = get_data(url, method, params)
    sites = []
    for files in data['phedex']['block']:
        for fdict in files['file']:
            for replica in fdict['replica']:
                sites.append(Site(replica))
    return sites

def apply_filter(flt, gen):
    """Apply given filter to a given set of results"""
    flt_func, flt_name = flt.split()
    if  isinstance(gen, list) or isinstance(gen, GeneratorType):
        if  flt_func == 'grep':
            for row in gen:
                att = flt_name.split('.')[-1]
                if  row.data.has_key(att):
                    yield row.data[att]
        elif flt_func == 'count':
            res = 0
            for row in gen:
                att = flt_name.split('.')[-1]
                if  row.data.has_key(att):
                    res += 1
        elif flt_func == 'sum':
            res = 0
            for row in gen:
                att = flt_name.split('.')[-1]
                if  row.data.has_key(att):
                    res += float(row.data[att])
            yield res
        else:
            for row in gen:
                yield row
    else:
        yield gen

class CMSFS(object):
    def __init__(self, *args, **kwargs):
        super(CMSFS, self).__init__(*args, **kwargs)
        self.primary_datasets = {}
        self.map = self.make_map()

    def make_map(self):
        rmp = routes.Mapper()
        rmp.connect('run={run:\d+}', controller='list_runs')
        rmp.connect('dataset={dataset:/.*?}', controller='list_datasets')
        rmp.connect('file dataset={dataset:/.*?}', controller='list_files')
        rmp.connect('site dataset={dataset:/.*?}', \
               controller='list_sites4dataset')
        rmp.connect('site file={filename:/.*.root?}', \
               controller='list_sites4file')
        rmp.connect('{sitename:T[0-3].*?}', controller='list_du4site')
        rmp.connect('site={sitename:T[0-3].*?}', controller='list_sites')
        rmp.connect('block site={sitename:T[0-3].*?}', \
               controller='list_block4site')
        rmp.connect('user={username:.*?}', controller='list_user')
        return rmp

    def lookup(self, obj):
        """
        Find the filesystem entry object for a given obj
        """
        match = self.map.match(obj)
        if  match is None:
            print "Match not found"
            return []
        controller = match.pop('controller')
        result = getattr(self, controller)(**match)
        return result

    def dataset(self, path):
        """
        Dataset access method
        """
        return self.lookup(path)

    def list_datasets(self, **kwargs):
        """
        Controller to get DBS datasets
        """
        url = 'http://localhost:8989/dbs/DBSReader'
        method = 'datasets'
        params = {'dataset':kwargs['dataset']}
        data = get_data(url, method, params)
        plist = [Dataset(d) for d in data]
        return plist

    def list_runs(self, **kwargs):
        """
        Controller to get runs
        """
        url = 'http://cms-conddb.cern.ch'
        method = 'getLumi'
        params = {'Runs':kwargs.get('run'), 'lumiType':'delivered'}
        data = get_data(url, method, params)
        plist = [Run(d) for d in data]
        return plist

    def list_files(self, **kwargs):
        """
        Controller to get files
        """
#        print "list_files kwargs", kwargs
        url = 'http://localhost:8989/dbs/DBSReader'
        method = 'files'
        params = {'dataset': kwargs['dataset'], 'detail': 'True'}
        data = get_data(url, method, params)
        plist = [File(f) for f in data]
        return plist

    def list_sites4dataset(self, **kwargs):
        """
        Controller to get sites for given dataset
        """
#        print "list_sites4dataset kwargs", kwargs
        url = 'https://cmsweb.cern.ch/phedex/datasvc/json/prod'
        method = 'fileReplicas'
        params = {'dataset': kwargs['dataset']}
        return find_sites(url, method, params)

    def list_sites4file(self, **kwargs):
        """
        Controller to get sites for given file
        """
#        print "list_sites4file kwargs", kwargs
        url = 'https://cmsweb.cern.ch/phedex/datasvc/json/prod'
        method = 'fileReplicas'
        params = {'lfn': kwargs['filename']}
        return find_sites(url, method, params)

    def list_sites(self, **kwargs):
        """
        Controller to get site info
        """
#        print "list_sites kwargs", kwargs
        url = 'https://cmsweb.cern.ch/phedex/datasvc/json/prod'
        method = 'nodeusage'
        params = {'node': kwargs['sitename']}
        data = get_data(url, method, params)
#        for node in data['phedex']['node']:
#            yield node
        plist = [Site(s) for s in data['phedex']['node']]
        return plist

    def list_block4site(self, **kwargs):
        """
        Controller to get site info
        """
#        print "list_block4site kwargs", kwargs
        url = 'https://cmsweb.cern.ch/phedex/datasvc/json/prod'
        method = 'blockreplicasummary'
        params = {'node': kwargs['sitename']}
        data = get_data(url, method, params)
#        for node in data['phedex']['block']:
#            yield node['name']
        plist = [Block(b) for b in data['phedex']['block']]
        return plist

    def list_du4site(self, **kwargs):
        """
        Controller to get site info
        """
#        print "list_du4site kwargs", kwargs
        url = 'https://cmsweb.cern.ch/phedex/datasvc/json/prod'
        method = 'blockreplicas'
        site = kwargs['sitename']
        params = {'node': site}
        data = get_data(url, method, params)
        nfiles = 0
        nblocks = 0
        size = 0
        for row in data['phedex']['block']:
            nblocks += 1
            nfiles += int(row['files'])
            for rep in row['replica']:
                if  rep['node'] == site:
                    size += long(rep['bytes'])
        return dict(nblocks=nblocks, nfiles=nfiles, totalsize=size)

    def list_user(self, **kwargs):
        """
        Controller to get site info
        """
#        print "list_block4site kwargs", kwargs
        url = 'https://cmsweb.cern.ch/sitedb/data/prod'
        method = 'people'
        params = {}
        cert = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
        ckey = os.path.join(os.environ['HOME'], '.globus/userkey.pem')
        data = get_data(url, method, params, ckey, cert)
        qname = kwargs['username']
        users = []
        for row in sitedb_parser(data):
            username = row.get('username', None)
            forename = row.get('forename', None)
            surname  = row.get('surname', None)
            email    = row.get('email', None)
            if  username and qname.find(username) != -1 or \
                forename and qname.find(forename) != -1 or \
                surname and qname.find(surname) != -1 or \
                email and qname.find(email) != -1:
#                yield dict(user=row)
                users.append(row)
        return [User(u) for u in users]
