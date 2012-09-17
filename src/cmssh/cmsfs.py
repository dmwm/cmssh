#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
CMSFS is a file-system on top of routefs to access CMS meta-data
"""

# system modules
import os
import re
import json
import routes
import urllib
import urllib2
from   types import GeneratorType

# cmssh modules
from   cmssh.iprint import format_dict
from   cmssh.url_utils import get_data
from   cmssh.cms_objects import Run, File, Block, Dataset, Site, User, Job
from   cmssh.cms_objects import Release
from   cmssh.tagcollector import releases
from   cmssh.filemover import get_pfns, resolve_user_srm_path
from   cmssh.cms_urls import phedex_url, dbs_url, conddb_url, sitedb_url
from   cmssh.cms_urls import dashboard_url, dbs_instances
from   cmssh import dbs2
from   cmssh.runsum import runsum
from   cmssh.lumidb import lumidb

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
    """Find sites"""
    data = get_data(url, method, params)
    sites = {}
    for files in data['phedex']['block']:
        for fdict in files['file']:
            replicas = fdict['replica']
            for replica in replicas:
                node = replica.get('node', None)
                se = replica.get('se', None)
                if  sites.has_key(node):
                    if  se not in sites[node]:
                        sites[node] += [se]
                else:
                    sites[node] = [se]
    for key, val in sites.iteritems():
        yield Site({'node': key, 'se': val})

def apply_filter(flt, gen):
    """Apply given filter to a given set of results"""
    arr = flt.split()
    if  len(arr) == 2:
        flt_func, flt_name = arr
        flt_opt = None
    elif len(arr) == 3:
        flt_func, flt_opt, flt_name = arr
    elif len(arr) > 3:
        raise NotImplementedError
    else:
        flt_func = arr[0]
        flt_name = None
    if  isinstance(gen, list) or isinstance(gen, GeneratorType):
        if  flt_func == 'grep' and flt_name:
            for row in gen:
                rrr = repr(row)
                if  flt_opt:
                    if  flt_opt == '-i':
                        if  rrr.lower().find(flt_name.lower()) != -1:
                            yield row
                    elif flt_opt == '-v':
                        if  rrr.find(flt_name) == -1:
                            yield row
                    elif flt_opt == '-iv' or flt_opt == '-vi':
                        if  rrr.lower().find(flt_name.lower()) == -1:
                            yield row
                    else:
                        raise NotImplementedError
                else:
                    if  rrr.find(flt_name) != -1:
                        yield row
        elif flt_func == 'count' or flt_func == 'wc':
            res = 0
            for row in gen:
                res += 1
            yield res
        else:
            raise NotImplementedError
    else:
        yield gen

def validate_dbs_instance(inst):
    "Validate DBS url"
    if  inst in dbs_instances():
        return True
    return False

class CMSFS(object):
    """CMS filesystem on top of CMS data-services"""
    def __init__(self, *args, **kwargs):
        super(CMSFS, self).__init__(*args, **kwargs)
        self.primary_datasets = {}
        self.map = self.make_map()

    def make_map(self):
        rmp = routes.Mapper()
        rmp.connect('run={run:\d+}', controller='list_runs')
        rmp.connect('dataset={dataset:.*?} status={status:.*?}', controller='list_datasets')
        rmp.connect('dataset={dataset:.*?}', controller='list_datasets')
        rmp.connect('file run={run:[0-9]+} dataset={dataset:/.*?}', controller='list_files')
        rmp.connect('file dataset={dataset:/.*?} run={run:[0-9]+}', controller='list_files')
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
        rmp.connect('job user={user:.*?}', controller='list_jobs')
        rmp.connect('job site={site:T[0-3].*?}', controller='list_jobs')
        rmp.connect('job', controller='list_jobs')
        rmp.connect('release', controller='list_releases')
        rmp.connect('releases', controller='list_releases')
        rmp.connect('release={name:CMSSW(_[0-9]){3}}', controller='list_releases')
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

    def list_releases(self, **kwargs):
        """
        Controller to get CMSSW release information
        """
        data  = releases(kwargs.get('name', None))
        plist = [Release(r) for r in data]
        return plist

    def list_datasets(self, **kwargs):
        """
        Controller to get DBS datasets
        """
        url = dbs_url()
        method = 'datasets'
        if  url.find('cmsdbsprod') != -1: # DBS2
            return dbs2.list_datasets(kwargs)
        params = {'dataset':kwargs['dataset']}
        if  kwargs['dataset'][0] == '*':
            kwargs['dataset'] = '/' + kwargs['dataset']
        data = get_data(url, method, kwargs)
        plist = [Dataset(d) for d in data]
        return plist

    def list_runs(self, **kwargs):
        """
        Controller to get runs
        """
        url = conddb_url()
        method = 'getLumi'
        run = kwargs.get('run')
        params = {'Runs':run, 'lumiType':'delivered'}
        data = get_data(url, method, params)
        plist = [Run(d) for d in data]
        return plist

    def list_files(self, **kwargs):
        """
        Controller to get files
        """
        url = dbs_url()
        run = kwargs.get('run', None)
        dataset = kwargs.get('dataset')
        if  url.find('cmsdbsprod') != -1: # DBS2
            return dbs2.list_files(dataset, run)
        method = 'files'
        params = {'dataset': dataset, 'detail': 'True'}
        if  run:
            params.update({'run_num': run})
        data = get_data(url, method, params)
        plist = [File(f) for f in data]
        return plist

    def list_sites4dataset(self, **kwargs):
        """
        Controller to get sites for given dataset
        """
#        print "list_sites4dataset kwargs", kwargs
        url = phedex_url()
        method = 'fileReplicas'
        params = {'dataset': kwargs['dataset']}
        return find_sites(url, method, params)

    def list_sites4file(self, **kwargs):
        """
        Controller to get sites for given file
        """
#        print "list_sites4file kwargs", kwargs
        url = phedex_url()
        method = 'fileReplicas'
        params = {'lfn': kwargs['filename']}
        return find_sites(url, method, params)

    def list_sites(self, **kwargs):
        """
        Controller to get site info
        """
#        print "list_sites kwargs", kwargs
        url = phedex_url()
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
        url = phedex_url()
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
        url = phedex_url()
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
        url = sitedb_url()
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

    def list_jobs(self, **kwargs):
        "Controller for jobs info"
#        print "list_jobs kwargs", kwargs
        url = dashboard_url()
        method = 'jobsummary-plot-or-table2' # JSON API (number 2 :)
        params = {
            'user': kwargs.get('user', ''),
            'site': kwargs.get('site', ''),
            'ce': '',
            'submissiontool': '',
            'dataset': kwargs.get('dataset', ''),
            'application': '',
            'rb': '',
            'activity': '',
            'grid': '',
            'date1': '',
            'date2': '',
            'jobtype': '',
            'tier': '',
            'check': 'submitted',
        }
        data = get_data(url, method, params)
        plist = [Job(r) for r in data['summaries']]
        return plist

def dataset_info(dataset, verbose=None):
    """Return dataset info"""
    url = dbs_url('')
    if  url.find('cmsdbsprod') != -1: # DBS2
        return dbs2.dataset_info(dataset, verbose)
    params = {'dataset': dataset, 'detail':'True'}
    result = get_data(url, 'datasets', params, verbose)
    res = [Dataset(r) for r in result]
    if  len(res) != 1:
        msg  = 'The %s dataset yield %s results' % (dataset, len(res))
        raise Exception(msg)
    return res[0]

def block_info(block, verbose=None):
    """Return block info"""
    url = dbs_url()
    if  url.find('cmsdbsprod') != -1: # DBS2
        return dbs2.block_info(block, verbose)
    params = {'block_name': block, 'detail':'True'}
    result = get_data(url, 'blocks', params, verbose)
    res = [Block(r) for r in result][0]
    if  len(res) != 1:
        msg  = 'The %s block yield %s results' % (block, len(res))
        raise Exception(msg)
    return res[0]

def file_info(lfn, verbose=None):
    """Return file info"""
    url = dbs_url()
    if  url.find('cmsdbsprod') != -1: # DBS2
        return dbs2.file_info(lfn, verbose)
    params = {'logical_file_name': lfn, 'detail':'True'}
    result = get_data(url, 'files', params, verbose)
    res = [File(r) for r in result]
    if  len(res) != 1:
        msg  = 'The %s LFN yield %s results' % (lfn, len(res))
        raise Exception(msg)
    lfnobj = res[0]
    try:
        pfnlist, selist = get_pfns(lfn, verbose)
        lfnobj.assign('pfn', pfnlist)
        lfnobj.assign('se', selist)
    except:
        lfnobj.assign('pfn', [])
        lfnobj.assign('se', [])
    return lfnobj

def site_info(dst, verbose=None):
    """list files at given destination"""
    url    = phedex_url()
    method = 'nodeusage'
    params = {'node': dst}
    data   = get_data(url, method, params)
    res    = [Site(s) for s in data['phedex']['node']]
    paths  = [r for r in resolve_user_srm_path(dst)]
    for site in res:
        site.assign('pfn_path', paths)
    for pdir in paths:
        site.assign('default_path', pdir.split('=')[-1])
    pat    = re.compile('^T[0-9]_[A-Z]+(_)[A-Z]+')
    if  pat.match(dst) and verbose:
        url       = phedex_url('blockReplicas')
        params    = {'node': dst}
        data      = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
        json_dict = json.load(data)
        totfiles  = 0
        totblocks = 0
        totsize   = 0
        print "Site %s has the following blocks:" % dst
        for row in json_dict['phedex']['block']:
            totfiles += long(row['files'])
            totblocks += 1
            for rep in row['replica']:
                if  rep['node'] == dst:
                    totsize += long(rep['bytes'])
            print row['name']
        print "Total number of blocks:", totblocks
        print "Total number of files :", totfiles
        return res
    return res

def run_info(run, verbose=None):
    """Return run info"""
    url = conddb_url()
    method = 'getLumi'
    params = {'Runs':run, 'lumiType':'delivered'}
    data = get_data(url, method, params)
    runinfo = [r for r in runsum(run)]
    runlumi = [r for r in data]
    plist = []
    for run in runinfo:
        for rec in runlumi:
            if  run['run'] == rec['Run']:
                run.update(rec)
        plist.append(Run(run))
    return plist

def release_info(release, rfilter=None):
    """Return release info"""
    data  = releases(release, rfilter)
    plist = [Release(r) for r in data]
    return plist

def run_lumi_info(dataset, verbose=None):
    "Return run-lumi info"
    try:
        data = json.loads(arg)
    except:
        data = arg # assume it is dataset
    url = dbs_url()
    run_lumi = {}
    if  url.find('cmsdbsprod') != -1: # DBS2
        if  isinstance(data, basestring):
            run_lumi = dbs2.run_lumi(data, verbose)
        elif isinstance(data, dict):
            for run, lumis in data.items():
                run_lumi[int(run)] = lumis
    else:
        run_lumi = {} # need to implement DBS3 call
    lumidb(run_lumi_dict=run_lumi, lumi_report=verbose)
    return []

# create instance of CMSFS class (singleton)
CMSMGR = CMSFS()
