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
import pprint
from   types import GeneratorType

# cmssh modules
from   cmssh.iprint import format_dict, print_warning, print_error
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
from   cmssh.regex import pat_dataset, pat_block, pat_lfn, pat_run

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

def find_sites(url, params):
    """Find sites"""
    data = get_data(url, params)
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
        if  url.find('cmsdbsprod') != -1: # DBS2
            return dbs2.list_datasets(kwargs)
        url = dbs_url('datasets')
        params = {'dataset':kwargs['dataset']}
        if  kwargs['dataset'][0] == '*':
            kwargs['dataset'] = '/' + kwargs['dataset']
        data = get_data(url, kwargs)
        plist = [Dataset(d) for d in data]
        return plist

    def list_runs(self, **kwargs):
        """
        Controller to get runs
        """
        url = conddb_url('getLumi')
        run = kwargs.get('run')
        params = {'Runs':run, 'lumiType':'delivered'}
        data = get_data(url, params)
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
        url = dbs_url('files')
        params = {'dataset': dataset, 'detail': 'True'}
        if  run:
            params.update({'run_num': run})
        data = get_data(url, params)
        plist = [File(f) for f in data]
        return plist

    def list_sites4dataset(self, **kwargs):
        """
        Controller to get sites for given dataset
        """
        url = phedex_url('fileReplicas')
        params = {'dataset': kwargs['dataset']}
        return find_sites(url, params)

    def list_sites4file(self, **kwargs):
        """
        Controller to get sites for given file
        """
        url = phedex_url('fileReplicas')
        params = {'lfn': kwargs['filename']}
        return find_sites(url, params)

    def list_sites(self, **kwargs):
        """
        Controller to get site info
        """
        url = phedex_url('nodeusage')
        params = {'node': kwargs['sitename']}
        data = get_data(url, params)
        plist = [Site(s) for s in data['phedex']['node']]
        return plist

    def list_block4site(self, **kwargs):
        """
        Controller to get site info
        """
        url = phedex_url('blockreplicasummary')
        params = {'node': kwargs['sitename']}
        data = get_data(url, params)
        plist = [Block(b) for b in data['phedex']['block']]
        return plist

    def list_du4site(self, **kwargs):
        """
        Controller to get site info
        """
        url     = phedex_url('blockReplicas')
        site    = kwargs['sitename']
        params  = {'node': site}
        data    = get_data(url, params)
        nfiles  = 0
        nblocks = 0
        size    = 0
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
        url = sitedb_url('people')
        params = {}
        cert = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
        ckey = os.path.join(os.environ['HOME'], '.globus/userkey.pem')
        data = get_data(url, params)
        qname = kwargs['username'].lower()
        users = []
        for row in sitedb_parser(data):
            username = row.get('username', '').lower()
            forename = row.get('forename', '').lower()
            surname  = row.get('surname', '').lower()
            email    = row.get('email', '').lower()
            if  username and qname.find(username) != -1 or \
                forename and qname.find(forename) != -1 or \
                surname and qname.find(surname) != -1 or \
                email and qname.find(email) != -1:
                users.append(row)
        return [User(u) for u in users]

    def list_jobs(self, **kwargs):
        "Controller for jobs info"
        url = dashboard_url('jobsummary-plot-or-table2') # JSON API (number 2 :)
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
        data = get_data(url, params)
        plist = [Job(r) for r in data['summaries']]
        return plist

def dataset_info(dataset, verbose=None):
    """Return dataset info"""
    url = dbs_url()
    if  url.find('cmsdbsprod') != -1: # DBS2
        return dbs2.dataset_info(dataset, verbose)
    params = {'dataset': dataset, 'detail':'True'}
    result = get_data(dbs_url('datasets'), params, verbose)
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
    result = get_data(dbs_url('blocks'), params, verbose)
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
    result = get_data(dbs_url('files'), params, verbose)
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
    url    = phedex_url('nodeusage')
    params = {'node': dst}
    data   = get_data(url, params)
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
    url = conddb_url('getLumi')
    params = {'Runs':run, 'lumiType':'delivered'}
    data = get_data(url, params)
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

def run_lumi_subset(json_file, run_lumi):
    "Return subset of good run/lumis based on provided golden json file and run lumi dict"
    rdict = {}
    for key, lumi_ranges in json_file.items():
        for run, lumis in run_lumi.items():
            if  int(run) == int(key):
                all_lumis = (i for x in lumi_ranges for i in xrange(x[0], x[-1]+1))
                if  lumis:
                    rdict[run] = list(set(lumis) & set(all_lumis))
                else:
                    rdict[run] = list(set(all_lumis))
    return rdict

def run_lumi_golden_json():
    "Get run lumi dict from golden JSON file"
    fname = os.environ.get('CMS_JSON', None)
    if  os.path.isfile(fname):
        with open(fname, 'r') as json_file:
            try:
                cms_json = json.load(json_file)
                return fname, cms_json
            except:
                print_error('Unable to decode CMS JSON: %s' % fname)
                return fname, {}
    else:
        msg  = 'Unable to locate CMS JSON file'
        print_warning(msg)
        return None, {}

def parse_runlumis(filelumis):
    "Parse DBS3 output of filelumis API and return run-lumi dict"
    run_lumi = {}
    for row in filelumis:
        run  = row['run_num']
        lumi = row['lumi_section_num']
        run_lumi.setdefault(run, []).append(lumi)
    return run_lumi

def run_lumi_info(arg, verbose=None):
    "Return run-lumi info"
    try:
        data = json.loads(arg)
    except:
        if  isinstance(arg, basestring) and arg.find("{") != -1:
            data = eval(arg, { "__builtins__": None }, {})
        else:
            data = arg # assume it is dataset/file/block/run
    url = dbs_url()
    run_lumi = {}
    if  isinstance(data, dict): # we got run-lumi dict
        for run, lumis in data.items():
            run_lumi[int(run)] = lumis
    elif isinstance(data, int) or pat_run.match(str(data)): # we got run-number
        run_lumi[int(data)] = None
    else:
        if  url.find('cmsdbsprod') != -1: # DBS2
            run_lumi = dbs2.run_lumi(str(data), verbose)
        else:
            if  pat_dataset.match(data):
                params = {'dataset': data}
                result = get_data(dbs_url('files'), params, verbose)
                for row in result:
                    params = {'logical_file_name': row['logical_file_name']}
                    run_lumi = parse_runlumis(get_data(dbs_url('filelumis'), params, verbose))
            elif pat_block.match(data):
                params = {'block_name': data}
                run_lumi = parse_runlumis(get_data(dbs_url('files'), params, verbose))
            elif pat_lfn.match(data):
                params = {'logical_file_name': data}
                run_lumi = parse_runlumis(get_data(dbs_url('filelumis'), params, verbose))
    if  not run_lumi:
        print_error('Empty run-lumi list')
        return []
    totlumi, lumiunit = lumidb(run_lumi_dict=run_lumi, lumi_report=verbose)
    print "Delivered luminosity %s (%s)" % (totlumi, lumiunit)
    if  verbose:
        print "Input run lumi dict", pprint.pprint(run_lumi)
    golden_fname, golden_json = run_lumi_golden_json()
    if  golden_json:
        if  verbose:
            print "Intersect with CMS JSON:", golden_fname
        rdict = run_lumi_subset(golden_json, run_lumi)
        totlumi, lumiunit = lumidb(rdict, lumi_report=verbose)
        print "Delivered luminosity wrt CMS JSON: %s (%s)" % (totlumi, lumiunit)
        if  verbose:
            print "Intersected run lumi dict", pprint.pprint(rdict)
    return []

# create instance of CMSFS class (singleton)
CMSMGR = CMSFS()
