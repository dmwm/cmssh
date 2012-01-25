#!/usr/bin/env python

"""Filemover cli equivalent"""

# system modules
import os
import re
import sys
import json
import stat
import time
import thread
import urllib
import urllib2
import datetime

# for DBS2 XML parsing
import xml.etree.ElementTree as ET

# cmssh modules
from cmssh.iprint import print_red, print_blue
from cmssh.utils import size_format
from cmssh.ddict import DotDict
from cmssh.cms_urls import phedex_url
from cmssh.cms_objects import CMSObj
from cmssh.utils import execmd, print_progress

def file_size(ifile):
    "Return file size"
    if  os.path.isfile(ifile):
        return os.stat(ifile)[stat.ST_SIZE]
    return 0

def check_permission(dst, verbose=None):
    """
    Check permission to write to given destination area
    """
    if  verbose:
        print "Check permission to write to %s" % dst
    cmd    = 'srm-mkdir %s' % dst
    stdout, stderr = execmd(cmd)
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
        stdout, stderr = execmd(cmd)
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
    stdout, stderr = execmd(cmd)
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
#    url  = 'http://cmsdbsprod.cern.ch/cms_dbs_prod_global/servlet/DBSServlet'
#    api  = 'listFiles' # DBS2 
#    args = dict(data_tier_list='', analysis_dataset_name='',
#                  processed_dataset='', detail='False',
#                  retrive_list='', block_name='', path='',
#                  run_number='', primay_dataset='',
#                  other_details='False')
#    params = {'user_type': 'NORMAL', 'apiversion': 'DBS_2_0_9', 'api': api}
#    if  run:
#        args['run_number'] = run
#    if  dataset:
#        args['path'] = dataset
    url  = dbs_url()
    params = {'detail':'True'}
    api  = 'files' # DBS3
    if  run:
        args['minrun'] = run
        args['maxrun'] = run
    if  dataset:
        args['dataset'] = dataset
    params.update(args)
    data = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
#    result = data.read() # DBS2
#    for row in parser(result):
#        yield row

    json_dict = json.load(data) # JSON is only for DBS3
    for row in json_dict:
        yield row['logical_file_name']

def get_username(verbose=None):
    """
    Get user name from provided DN
    """
    # get DN from grid-proxy-info
    cmd    = 'grid-proxy-info'
    stdout, stderr = execmd(cmd)
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
        msg = 'Unable to determine your DN, please run grid-proxy-init'
        raise Exception(msg)
    # TODO: replace with new SiteDB
    url    = 'https://cmsweb.cern.ch/sitedb/json/index/dnUserName'
    params = {'dn': userdn}
    data   = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
    result = eval(data.read()) 
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
    url    = phedex_url('tfc')
    params = {'node':node}
    data   = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
    result = json.load(data)
    for row in result['phedex']['storage-mapping']['array']:
        if  row['protocol'] == 'srmv2' and row['element_name'] == 'lfn-to-pfn':
            yield (row['result'], row['path-match'])

def resolve_user_srm_path(node, ldir='/store/user', verbose=None):
    """
    Use TFC phedex API to resolve srm path for given node
    """
    url    = phedex_url('lfn2pfn')
    params = {'node':node, 'lfn':ldir, 'protocol': 'srmv2'}
    data   = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
    result = json.load(data)
    for row in result['phedex']['mapping']:
        yield row['pfn']

def get_pfns(lfn, verbose=None):
    """
    Look-up LFN in Phedex and get corresponding list of PFNs
    """
    pfnlist   = []
    params    = {'se':'*', 'lfn':lfn}
    url       = phedex_url('fileReplicas')
    data      = urllib2.urlopen(url, urllib.urlencode(params, doseq=True))
    json_dict = json.load(data)
    ddict     = DotDict(json_dict)
    if  not json_dict['phedex']['block']:
#        msg  = "LFN: %s\n" % lfn
#        msg += 'No replicas found\n'
#        msg += str(json_dict)
#        print msg
        return pfnlist
    selist = []
    for fname in ddict.get('phedex.block.file'):
        for replica in fname['replica']:
            cmsname = replica['node']
            se      = replica['se']
            if  se not in selist:
                selist.append(se)
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
    return pfnlist, selist

def srmcp(srmcmd, lfn, dst, verbose=None):
    """
    Look-up LFN in Phedex and construct srmcp command for further processing
    """
    pat = re.compile('^T[0-9]_[A-Z]+(_)[A-Z]+')
    if  pat.match(dst):
        dst_split = dst.split(':')
        dst = dst_split[0]
        if  len(dst_split) == 1: # copy to the node
            local_path = dst_split[1]
            for srm_path, lfn_match in resolve_srm_path(dst, verbose):
                lfn_pat = re.compile(lfn_match)
                if  lfn_pat.match(lfn):
                    srm_path = srm_path.replace('\?', '?').replace('$1', local_path)
                    if  verbose:
                        print "Resolve %s into %s" % (dst, srm_path)
                    dst = srm_path
        else:
            paths = [p for p in resolve_user_srm_path(dst, verbose=verbose)]
            dst = '%s/%s' % (paths[0], get_username())
        check_permission(dst, verbose)
    else:
        if  not dst.find('file:///') != -1:
            dst = 'file:///%s' % dst
    pfnlist   = []
    if  os.path.isfile(lfn) or lfn.find('file:///') != -1: # local file
        pfn = lfn.replace('file:///', '')
        if  pfn[0] != '/':
            pfn = 'file:///%s' % os.path.join(os.getcwd(), pfn)
        else:
            pfn = 'file:///%s' % pfn
        pfnlist   = [pfn]
    else:
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
        ifile = item.split("/")[-1]
        cmd = "%s %s %s/%s -pushmode -statuswaittime 30" \
                % (srmcmd, item, dst, ifile)
        yield cmd

def get_size(cmd, verbose=None):
    """
    Execute srm-ls <surl> command and retrieve file size information
    """
    if  cmd.find('file:///') != -1:
        return file_size(cmd.split('file:///')[-1])
    stdout, stderr = execmd(cmd)
    if  stderr.find('command not found') != -1:
        print 'Unable to find srm-ls tool'
        print help
        sys.exit(1)
    if  stderr:
        print_red(stderr)
    orig_size = 0
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
    # find file size from replica
    rcmd  = 'srm-ls %s' % src
    orig_size = get_size(rcmd, verbose)
    if  verbose:
        print "%s, size %s" % (src, orig_size)

    # find file size from destination (if any)
    rcmd  = 'srm-ls %s' % dst
    dst_size = get_size(rcmd, verbose)
    if  verbose:
        print "%s, size %s" % (dst, dst_size)

    if  orig_size == dst_size:
        return (dst, dst_size)
    return False

def execute(cmd, lfn, verbose):
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
#        os.system(cmd) # execute given command
        stdout, stderr = execmd(cmd)
        if  stderr:
            print_red(stderr)
        if  not stdout.find('SRM_SUCCESS') != -1:
            print stdout
    status = check_file(src, dst, verbose) # check again since SRM may fail
    return status
    
def check_allowance(verbose):
    """
    Check if user is allowed to perform srm-copy command.
    We send request to FileMover server, who response with ok/fail.
    """
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
    url  = filemover_url() + '/record'
    date = '%s' % datetime.date.today()
    args = {'userdn':get_username(), 'src':src,
                'dst':dst, 'date':date, 'lfn':lfn}
    if  verbose:
        print "add_request", url, args
    data = urllib2.urlopen(url, urllib.urlencode(args, doseq=True))
    return data.read()
    
class FileMover(object):
    def __init__(self):
        self.instance = "Instance at %d" % self.__hash__()
        check_proxy()

    def copy_via_xrdcp(self, lfn, dst, verbose=0):
        "Copy LFN to given destination via xrdcp command"
        if  not os.path.isdir(dst):
            msg = 'xrdcp only works with local destination'
            print_red(msg)
            return 'fail'
        cmd = 'xrdcp root://xrootd.unl.edu/%s %s' % (lfn, dst)
        stdout, stderr = execmd(cmd)
        if  stderr:
            print_red(stderr)
            return 'fail'
        return 'success'

    def copy(self, lfn, dst, verbose=0):
        """Copy LFN to given destination"""
        err = 'Unable to identify total size of the file,'
        err += ' GRID middleware fails.'
        for cmd in srmcp("srm-copy", lfn, dst, verbose):
            if  cmd:
                if  verbose:
                    status = execute(cmd, lfn, verbose)
                    if  status:
                        dst, dst_size = status
                        size = size_format(dst_size)
                        if  not size or not dst_size:
                            print_red(err)
                            print "Status of transfer:\n", status
                            return 'fail'
                        else:
                            print "\nDone, file located at %s (%s)" \
                                % (dst, size_format(dst_size))
                        break
                else:
                    arr = cmd.split() # srm-copy <sourceURL> <targetURL> <options>
                    pfn = arr[1] # sourceURL
                    ifile = arr[2] # targetURL
                    tot_size = float(get_size('srm-ls %s' % pfn))
                    if  tot_size:
                        print_progress(0)
                        thread.start_new_thread(execute, (cmd, lfn, verbose))
                        while True:
                            size = get_size('srm-ls %s' % ifile)
                            if  not size or size == 'null':
                                print_progress('N/A', 'Download in progress ...')
                            else:
                                progress = float(size)*100/tot_size
                                print_progress(progress)
                            if  progress == 100:
                                break
                            time.sleep(0.5)
                        print '' # to finish print_progress
                    else:
                        print_red(err)
                        return 'fail'
        return 'success'

    def list_lfn(self, lfn, verbose=0):
        """List LFN"""
        pat_lfn = re.compile('^/.*\.root$')
        if  pat_lfn.match(lfn):
            pfnlist, selist = get_pfns(arg, verbose)
            for pfn in pfnlist:
                cmd = "srm-ls %s" % pfn
                print '%s %s' % (lfn, get_size(cmd, verbose))

    def list_se(self, arg, verbose=0):
        """list content of given directory on SE"""
        try:
            node, ldir = arg.split(':')
        except:
            msg = 'Given argument "%s" does not represent SE:dir' % arg
            raise Exception(msg)
        cmd = 'srm-ls'
        dst = [r for r in resolve_user_srm_path(node, ldir)][0]
        cmd = "srm-ls %s" % dst
        if  verbose:
            print cmd
        stdout, stderr = execmd(cmd)
        if  stderr:
            print_red(stderr)
        output = []
        row = {}
        for line in stdout.split():
            if  line.find('SRM-CLIENT*SURL') != -1:
                if  row:
                    output.append(CMSObj(row))
                    row = {}
                row['data'] = line.replace('SRM-CLIENT*SURL=', '')
            if  line.find('SRM-CLIENT*FILETYPE') != -1:
                row['type'] = line.replace('SRM-CLIENT*FILETYPE=', '').lower()
            if  line.find('SRM-CLIENT*BYTES') != -1:
                row['bytes'] = long(line.replace('SRM-CLIENT*BYTES=', ''))
        if  row:
            output.append(CMSObj(row))
        return output

    def rm_lfn(self, arg, verbose=0):
        """Remove user lfn from a node"""
        try:
            node, lfn = arg.split(':')
        except:
            msg = 'Given argument "%s" does not represent SE:LFN' % arg
            raise Exception(msg)
        cmd = 'srm-rm'
        dst = [r for r in resolve_user_srm_path(node)][0]
        dst = dst.split('=')[0]
        if  dst[-1] != '=':
            dst += '=' 
        cmd = "%s %s" % (cmd, dst+lfn)
        if  verbose:
            print cmd
        stdout, stderr = execmd(cmd)
        if  stderr:
            print_red(stderr)
        if  stdout.find('SRM_SUCCESS') != -1:
            return 'success'
        else:
            print stdout

    def rmdir(self, path, verbose=0):
        """rmdir command"""
        spath = path.split(':')
        if  len(spath) == 1:
            node = spath[0]
            ldir = '/store/user'
        else:
            node = spath[0]
            ldir = spath[1]
        dst = [r for r in resolve_user_srm_path(node, ldir)][0]
        cmd = 'srm-rmdir %s' % dst
        print cmd
        stdout, stderr = execmd(cmd)
        if  stderr:
            print_red(stderr)
        if  stdout.find('SRM_SUCCESS') != -1:
            return 'success'
        else:
            print stdout

    def mkdir(self, path, verbose=0):
        """mkdir command"""
        spath = path.split(':')
        if  len(spath) == 1:
            node = spath[0]
            ldir = '/store/user'
        else:
            node = spath[0]
            ldir = spath[1]
        dst = [r for r in resolve_user_srm_path(node, ldir)][0]
        cmd = 'srm-mkdir %s' % dst
        print cmd
        stdout, stderr = execmd(cmd)
        if  stderr:
            print_red(stderr)
        if  stdout.find('SRM_SUCCESS') != -1:
            return 'success'
        else:
            print stdout

FM_SINGLETON = FileMover()
def copy_lfn(lfn, dst, verbose=0):
    """Copy lfn to destination"""
    status = FM_SINGLETON.copy(lfn, dst, verbose)
    if  status == 'fail':
        print_blue('Fallback to xrdcp method')
        FM_SINGLETON.copy_via_xrdcp(lfn, dst, verbose)
    return status

def list_lfn(lfn, verbose=0):
    """List lfn info"""
    return FM_SINGLETON.list_lfn(lfn, verbose)

def list_se(arg, verbose=0):
    """List SE content"""
    return FM_SINGLETON.list_se(arg, verbose)

def rm_lfn(lfn, verbose=0):
    """Remove lfn from destination"""
    return FM_SINGLETON.rm_lfn(lfn, verbose)

def mkdir(dst, verbose=0):
    """mkdir via srm-mkdir"""
    return FM_SINGLETON.mkdir(dst, verbose)

def rmdir(dst, verbose=0):
    """rmdir via srm-rmdir"""
    return FM_SINGLETON.rmdir(dst, verbose)
