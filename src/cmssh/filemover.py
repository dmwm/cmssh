#!/usr/bin/env python

# system modules
import os
import re
import sys
import time
import json
import types
import urllib
import urllib2
import datetime
import traceback
from   subprocess import Popen, PIPE

# for DBS2 XML parsing
import xml.etree.ElementTree as ET

# cmssh modules
from cmssh.utils import size_format
from cmssh.ddict import DotDict
from cmssh.cmsfs import CMSFS
from cmssh.url_utils import get_data
from cmssh.cms_objects import File, Block, Dataset

def phedex_url(api=''):
    """Return Phedex URL for given API name"""
    return 'https://cmsweb.cern.ch/phedex/datasvc/json/prod/%s' % api

def dbs_url(api=''):
    """Return DBS URL for given API name"""
    return 'https://cmsweb.cern.ch/dbs/DBSReader/%s' % api

def check_permission(dst, verbose=None):
    """
    Check permission to write to given destination area
    """
#    if  not verbose: sys.stdout.write('.')
    if  verbose:
        print "Check permission to write to %s" % dst
    cmd    = 'srm-mkdir %s' % dst
    pipe   = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE, close_fds=True)
    (child_stdout, child_stderr) = (pipe.stdout, pipe.stderr)
    stdout = child_stdout.read()
    stderr = child_stderr.read()
    if  stderr.find('command not found') != -1:
        print 'Unable to find srm-ls tool'
        print help
        sys.exit(1)
    if  stdout.find('SRM-DIR: directory not created') != -1 or\
        stdout.find('SRM_FAILURE') != -1:
        msg = "Unable to access %s:" % dst
        print msg
        print "-" * len(msg)
        print
        print stdout
        sys.exit(1)

def check_software(softlist):
    """
    Perform the check that Grid middleware is installed on a node
    """
    help     = 'Please run with --help for more options'
    for cmd in softlist:
        pipe   = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE, close_fds=True)
        (child_stdout, child_stderr) = (pipe.stdout, pipe.stderr)
        stdout = child_stdout.read()
        stderr = child_stderr.read()
        if  not stdout:
            print 'Unable to find %s' % cmd
            print help
            sys.exit(1)

def check_proxy():
    """
    Perform validity of the proxy
    """
    # check valid proxy
    cmd    = 'grid-proxy-info'
    pipe   = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE, close_fds=True)
    (child_stdout, child_stderr) = (pipe.stdout, pipe.stderr)
    stdout = child_stdout.read()
    stderr = child_stderr.read()
    if  stderr.find('command not found') != -1:
        print 'Unable to find grid-proxy-info tool'
        print help
        sys.exit(1)
    for line in stdout.split('\n'):
        if  line.find('timeleft') != -1 and line.split()[-1] == '0:00:00':
            print '\nYour proxy has been expired, renew proxy ...'
            os.system('grid-proxy-init')

def parser(data):
    """Parser DBS2 listFiles output"""
    elem  = ET.fromstring(data)
    for i in elem:
        if  i.tag == 'file':
            yield i.attrib['lfn']

def parse_srmls(data):
    """Parse srm-ls XML output"""
    data = data.split('<?xml version="1.0" encoding="UTF-8"?>')
    data = '<?xml version="1.0" encoding="UTF-8"?>' + data[-1]
    elem  = ET.fromstring(data)
    for i in elem:
        if  i.tag == 'file' and i.attrib.has_key('size'):
            return i.attrib['size']

def lfns(run=None, dataset=None):
    """
    Get lfns list for provided run/dataset
    """
    url  = 'http://cmsdbsprod.cern.ch/cms_dbs_prod_global/servlet/DBSServlet'
    api  = 'files' # DBS3
    api  = 'listFiles' # DBS2 
    args = dict(data_tier_list='', analysis_dataset_name='',
                  processed_dataset='', detail='False',
                  retrive_list='', block_name='', path='',
                  run_number='', primay_dataset='',
                  other_details='False')
    params = {'user_type': 'NORMAL', 'apiversion': 'DBS_2_0_9', 'api': api}
    if  run:
        args['run_number'] = run
    if  dataset:
        args['path'] = dataset
    params.update(args)
    data = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
    result = data.read()
    for row in parser(result):
        yield row

#    json_dict = json.load(data) # JSON is only for DBS3
#    print json_dict

def get_username(verbose=None):
    """
    Get user name from provided DN
    """
#    if  not verbose: sys.stdout.write('.')
    # get DN from grid-proxy-info
    cmd    = 'grid-proxy-info'
    pipe   = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE, close_fds=True)
    (child_stdout, child_stderr) = (pipe.stdout, pipe.stderr)
    stdout = child_stdout.read()
    stderr = child_stderr.read()
    if  stderr.find('command not found') != -1:
        raise Exception(stderr)
    userdn = None 
    try:
        for line in stdout.split('\n'):
            if  line.find('issuer') != -1:
                issuer, userdn = line.split(' : ')
    except:
        raise Exception('Unable to parse grid-proxy-info:\n%s' % stdout)
    if  verbose:
        print "userdn :", userdn
    if  not userdn:
        raise Exception('Unable to determine your DN, please run grid-proxy-init')
    url    = 'https://cmsweb.cern.ch/sitedb/json/index/dnUserName'
    params = {'dn': userdn}
    data   = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
    result = eval(data.read()) # for some reason SiteDB is not shipped JSON properly
    return result['user']

def nodes(select=True):
    """
    Yield list of Phedex nodes, I only select T2 and below
    """
    url    = phedex_url('nodes')
    params = {}
    data   = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
    result = json.load(data)
    pat    = re.compile('^T[0-1]_[A-Z]+(_)[A-Z]+')
    lnodes = []
    for row in result['phedex']['node']:
        if  select and pat.match(row['name']):
            continue
        msg = "%s, SE: %s, description %s/%s" \
        % (row['name'], row['se'], row['technology'], row['kind'])
        lnodes.append(msg)
    lnodes.sort()
    for row in lnodes:
        print row

def resolve_srm_path(node, verbose=None):
    """
    Use TFC phedex API to resolve srm path for given node
    """
#    if  not verbose: sys.stdout.write('.')
    url    = phedex_url('tfc')
    params = {'node':node}
    data   = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
    result = json.load(data)
    for row in result['phedex']['storage-mapping']['array']:
        if  row['protocol'] == 'srmv2' and row['element_name'] == 'lfn-to-pfn':
            yield (row['result'], row['path-match'])

def get_pfns(lfnobj, verbose=None):
    """
    Look-up LFN in Phedex and get corresponding list of PFNs
    """
    lfn = lfnobj.logical_file_name
#    if  not verbose: sys.stdout.write('.')
    pfnlist   = []
    params    = {'se':'*', 'lfn':lfn}
    url       = phedex_url('fileReplicas')
    data      = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
    json_dict = json.load(data)
    ddict     = DotDict(json_dict)
    if  not json_dict['phedex']['block']:
        msg  = "LFN: %s\n" % lfn
        msg += 'No replicas found\n'
        msg += str(json_dict)
        print msg
        return pfnlist
    selist = []
    for fname in ddict.get('phedex.block.file'):
        for replica in fname['replica']:
            cmsname = replica['node']
            se      = replica['se']
            selist.append(se)
            if  not verbose:
                print "found LFN on node=%s, se=%s" % (cmsname, se)
            if  cmsname.count('T0', 0, 2) == 1:
                continue # skip T0's
            # query Phedex for PFN
            url    = phedex_url('lfn2pfn')
            params = {'protocol':'srmv2', 'lfn':lfn, 'node':cmsname}
            data   = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
            result = json.load(data)
            try:
                for item in result['phedex']['mapping']:
                    pfn = item['pfn']
                    if  pfn not in pfnlist:
                        pfnlist.append(pfn)
            except:
                msg = "Fail to look-up PFNs in Phedex\n" + str(result)
                print msg
                continue
    lfnobj.assign('se', selist)
    return pfnlist

def list_dataset(dataset, verbose=None):
    """List dataset"""
    url = dbs_url('')
    params = {'dataset': dataset, 'detail':'True'}
    result = get_data(url, 'datasets', params, verbose)
    return [Dataset(r) for r in result]

def list_block(block, verbose=None):
    """List block"""
    url = dbs_url()
    params = {'block_name': block, 'detail':'True'}
    result = get_data(url, 'blocks', params, verbose)
    return [Block(r) for r in result]

def list_file(lfn, verbose=None):
    """List file"""
    url = dbs_url()
    params = {'logical_file_name': lfn, 'detail':'True'}
    result = get_data(url, 'files', params, verbose)
    return [File(r) for r in result]

def srmls(dst, verbose=None):
    """list files at given destination"""
    site = dst
    pat = re.compile('^T[0-9]_[A-Z]+(_)[A-Z]+')
    if  pat.match(dst):
        url       = phedex_url('blockReplicas')
        params    = {'node': dst}
        data      = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
        json_dict = json.load(data)
        totfiles  = 0
        totblocks = 0
        totsize   = 0
        for row in json_dict['phedex']['block']:
            totfiles += long(row['files'])
            totblocks += 1
            for rep in row['replica']:
                if  rep['node'] == dst:
                    totsize += long(rep['bytes'])
            print row['name']
        print "Total number of blocks:", totblocks
        print "Total number of files :", totfiles
        return totsize

def srmcp(srmcmd, lfn, dst, verbose=None):
    """
    Look-up LFN in Phedex and construct srmcp command for further processing
    """
#    if  not verbose: sys.stdout.write('.')
    pat = re.compile('^T[0-9]_[A-Z]+(_)[A-Z]+')
    if  pat.match(dst):
        dst_split = dst.split(':')
        dst = dst_split[0]
        if  len(dst_split) > 1:
            local_path = dst_split[1]
        else:
            local_path = '/store/user/%s' % get_username(verbose)
        for srm_path, lfn_match in resolve_srm_path(dst, verbose):
            lfn_pat = re.compile(lfn_match)
            if  lfn_pat.match(lfn):
                srm_path = srm_path.replace('\?', '?').replace('$1', local_path)
                if  verbose:
                    print "Resolve %s into %s" % (dst, srm_path)
                dst = srm_path
        check_permission(dst, verbose)
    else:
        if  not dst.find('file:///') != -1:
            dst = 'file:///%s' % dst
    pfnlist   = []
    params    = {'se':'*', 'lfn':lfn}
    url       = phedex_url('fileReplicas')
    data      = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
    json_dict = json.load(data)
    ddict     = DotDict(json_dict)
    if  verbose:
        print "Look-up LFN:"
        print lfn
    if  not json_dict['phedex']['block']:
        msg  = "LFN: %s\n" % lfn
        msg += 'No replicas found\n'
        msg += str(json_dict)
        raise Exception(msg)
    for fname in ddict.get('phedex.block.file'):
        for replica in fname['replica']:
            cmsname = replica['node']
            se      = replica['se']
            if  verbose:
                print "found LFN on node=%s, se=%s" % (cmsname, se)
            if  cmsname.count('T0', 0, 2) == 1:
                continue # skip T0's
            # query Phedex for PFN
            url    = phedex_url('lfn2pfn')
            params = {'protocol':'srmv2', 'lfn':lfn, 'node':cmsname}
            data   = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
            result = json.load(data)
            try:
                for item in result['phedex']['mapping']:
                    pfn = item['pfn']
                    if  pfn not in pfnlist:
                        pfnlist.append(pfn)
            except:
                msg = "Fail to look-up PFNs in Phedex\n" + str(result)
                print msg
                continue
    if  verbose > 1:
        print "PFN list:"
        for pfn in pfnlist:
            print pfn

    # finally let's create srmcp commands for each found pfn
    for item in pfnlist:
        file = item.split("/")[-1]
        cmd = "%s %s %s/%s -pushmode -statuswaittime 30" % (srmcmd, item, dst, file)
        yield cmd

def get_size(cmd, verbose=None):
    """
    Execute srm-ls <surl> command and retrieve file size information
    """
#    if  not verbose: sys.stdout.write('.')
    pipe  = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE, close_fds=True)
    (child_stdout, child_stderr) = (pipe.stdout, pipe.stderr)
    stdout = child_stdout.read()
    stderr = child_stderr.read()
    if  stderr.find('command not found') != -1:
        print 'Unable to find srm-ls tool'
        print help
        sys.exit(1)
    orig_size = None
    if  cmd.find('file:///') != -1: # srm-ls returns XML
        orig_size = parse_srmls(stdout)
    else:
        for line in stdout.split('\n'):
            if  line.find('Bytes') != -1:
                orig_size = line.replace('\n', '').split('=')[-1]
    return orig_size

def check_file(src, dst, verbose):
    """
    Check if file is transfered and return dst, dst_size upon success.
    """
#    if  not verbose: sys.stdout.write('.')
    # find file size from replica
    rcmd  = 'srm-ls %s' % src
    orig_size = get_size(rcmd, verbose)
    if  verbose:
        print "At %s, file size %s" % (src, orig_size)

    # find file size from destination (if any)
    rcmd  = 'srm-ls %s' % dst
    dst_size = get_size(rcmd, verbose)
    if  verbose:
        print "At %s, file size %s" % (dst, dst_size)

    if  orig_size == dst_size:
        return (dst, dst_size)
    return False

def execute(lfn, cmd, verbose):
    """
    Execute given srm-copy command, but also check if file is in place at dst
    cmd = srm-copy <from> <to> <options>
    """
    slist  = cmd.split()
    src    = slist[1]
    dst    = slist[2]
    status = check_file(src, dst, verbose) 
    if  status:
        return status
    else:
        os.system(cmd) # execute given command
    status = check_file(src, dst, verbose) # check again since SRM may fail
    return status
    
def check_allowance(verbose):
    """
    Check if user is allowed to perform srm-copy command.
    We send request to FileMover server, who response with ok/fail.
    """
#    if  not verbose: sys.stdout.write('.')
    url  = filemover_url() + '/allow'
    args = {'userdn': get_username()}
    if  verbose:
        print "check_allowance", url, args
    data = urllib2.urlopen(url, urllib.urlencode(args, doseq=True))
    return data.read()
    
def add_request(lfn, src, dst, verbose):
    """
    Send request to FileMover server to add information abotu src/dst request.
    """
#    if  not verbose: sys.stdout.write('.')
    url  = filemover_url() + '/record'
    date = '%s' % datetime.date.today()
    args = {'userdn':get_username(), 'src':src, 'dst':dst, 'date':date, 'lfn':lfn}
    if  verbose:
        print "add_request", url, args
    data = urllib2.urlopen(url, urllib.urlencode(args, doseq=True))
    return data.read()
    
class FileMover(object):
    def __init__(self):
        self.instance = "Instance at %d" % self.__hash__()
        self.cmsfs = CMSFS()
        check_proxy()
    def copy(self, lfn, dst, verbose=0):
        """Copy lfn to destination"""
        for cmd in srmcp("srm-copy", lfn, dst, verbose):
            if  cmd:
                status = execute(lfn, cmd, verbose)
                if  status:
                    dst, dst_size = status
                    print "\nDone, file located at %s (%s)" \
                        % (dst, size_format(dst_size))
                    break
    def list(self, arg, verbose=0):
        """List function"""
        pat_site = re.compile('^T[0-9]_[A-Z]+(_)[A-Z]+')
        pat_dataset = re.compile('^/.*/.*/.*')
        pat_block = re.compile('^/.*/.*/.*#.*')
        pat_lfn = re.compile('^/.*\.root$')
        if  pat_site.match(arg):
            return srmls(arg)
        elif pat_lfn.match(arg):
            lfn = list_file(arg)[0]
            pfnlist = get_pfns(lfn, verbose)
            lfn.assign('pfn', pfnlist)
            return lfn
        elif pat_block.match(arg):
            return list_block(arg)
        elif pat_dataset.match(arg):
            return list_dataset(arg)
        else:
            raise Exception('Unsupported input')

FM_SINGLETON = FileMover()
def copy_lfn(lfn, dst, verbose=0):
    """Copy lfn to destination"""
    FM_SINGLETON.copy(lfn, dst, verbose)

def list_lfn(lfn, verbose=0):
    """List lfn info"""
    return FM_SINGLETON.list(lfn, verbose)

