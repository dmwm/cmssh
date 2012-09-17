#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
#pylint: disable-msg=W0702
"""
Set of UNIX commands, e.g. ls, cp, supported in cmssh.
"""

# system modules
import os
import re
import sys
import time
import json
import glob
import base64
import pprint
import traceback
import subprocess

# cmssh modules
from cmssh.iprint import msg_red, msg_green, msg_blue
from cmssh.iprint import print_warning, print_error, print_status, print_info
from cmssh.filemover import copy_lfn, rm_lfn, mkdir, rmdir, list_se, dqueue
from cmssh.utils import list_results, check_os, unsupported_linux
from cmssh.utils import osparameters, check_voms_proxy, run, user_input
from cmssh.cmsfs import dataset_info, block_info, file_info, site_info, run_info
from cmssh.cmsfs import CMSMGR, apply_filter, validate_dbs_instance
from cmssh.cmsfs import release_info, run_lumi_info
from cmssh.github import get_tickets, post_ticket
from cmssh.cms_urls import dbs_instances, tc_url
from cmssh.das import das_client
from cmssh.url_utils import get_data, send_email
from cmssh.regex import pat_release, pat_site, pat_dataset, pat_block
from cmssh.regex import pat_lfn, pat_run, pat_se
from cmssh.tagcollector import architectures as tc_architectures
from cmssh.results import RESMGR
from cmssh.auth_utils import PEMMGR, working_pem
from cmssh.cmssw_utils import crab_submit_remotely, crabconfig

def options(arg):
    """Extract options from given arg string"""
    opts = []
    for par in arg.split():
        if  len(par) > 0 and par[0] == '-':
            opts.append(par)
    return opts

class Magic(object):
    """
    Class to be used with ipython magic functions. It holds given
    command and provide a method to execute it in a shell
    """
    def __init__(self, cmd):
        self.cmd = cmd
    def execute(self, args=''):
        "Execute given command in a shell"
        cmd = '%s %s' % (self.cmd, args.strip())
        run(cmd)
    def subprocess(self, args=''):
        "Execute given command in a shell"
        cmd = '%s %s' % (self.cmd, args.strip())
        subprocess.call(cmd, shell=True)

def installed_releases():
    "Print a list of releases installed on a system"
    _osname, osarch = osparameters()
    releases = []
    for idir in os.listdir(os.environ['VO_CMS_SW_DIR']):
        if  idir.find(osarch) != -1:
            rdir = os.path.join(\
                os.environ['VO_CMS_SW_DIR'], '%s/cms/cmssw' % idir)
            if  os.path.isdir(rdir):
                for rel in os.listdir(rdir):
                    releases.append('%s/%s' % (rel, idir))
    if  releases:
        releases.sort()
        print "\nInstalled releases:"
        for rel in releases:
            print rel
    else:
        msg  = "\nYou don't have yet CMSSW release installed on your system."
        msg += "\nPlease use " + msg_green('install CMSSW_X_Y_Z') \
                + ' command to install one'
        print msg

def cms_releases(arg=None):
    """
    List available CMS releases. Optional parameters either <list> or <all>
    Examples:
        cmssh> releases      # show installed CMSSW releases
        cmssh> releases list # show available CMSSW releases
        cmssh> releases all  # show all known CMS releases, including online, tests, etc.
    """
    if  arg:
        res = release_info(release=None, rfilter=arg)
        RESMGR.assign(res)
        releases = [str(r) for r in res]
        releases = list(set(releases))
        releases.sort()
        for rel in releases:
            print rel
    installed_releases()

def pkg_init(pkg_dir):
    "Create CMS command to source pkg environment"
    pkg_dir  = '%s/%s/%s' \
        % (os.environ['VO_CMS_SW_DIR'], os.environ['SCRAM_ARCH'], pkg_dir)
    cmd = 'source `find %s -name init.sh | tail -1`;' % pkg_dir
    if  not os.path.isdir(pkg_dir):
        cmd = ''
    return cmd

def cms_root(arg):
    """
    Run ROOT command
    """
    pcre_init = pkg_init('external/pcre')
    gcc_init  = pkg_init('external/gcc')
    root_init = pkg_init('lcg/root')
    pkgs_init = '%s %s %s' % (pcre_init, gcc_init, root_init)
    cmd = '%s root -l %s' % (pkgs_init, arg.strip())
    run(cmd)

def cms_xrdcp(arg):
    """
    Run ROOT xrdcp command
    """
    dyld_path = os.environ.get('DYLD_LIBRARY_PATH', None)
    root_path = os.environ['DEFAULT_ROOT']
    if  dyld_path:
        os.environ['DYLD_LIBRARY_PATH'] = os.path.join(root_path, 'lib')
    cmd = '%s/xrdcp %s' % (os.path.join(root_path, 'bin'), arg.strip())
    run(cmd)
    if  dyld_path:
        os.environ['DYLD_LIBRARY_PATH'] = dyld_path

#def debug(arg):
#    """
#    debug shell command
#    """
#    arg = arg.strip()
#    if  arg:
#        print_info("Set debug level to %s" % arg)
#        DEBUG.set(arg)
#    else:
#        print_info("Debug level is %s" % DEBUG.level)

def debug_http(arg):
    """
    Show or set HTTP debug flag. Default is 0.
    """
    arg = arg.strip()
    if  arg:
        if  arg not in ['0', '1']:
            print_error('Please provide 0/1 for debug_http command')
            return
        print_info("Set HTTP debug level to %s" % arg)
        os.environ['HTTPDEBUG'] = arg
    else:
        print_info("HTTP debug level is %s" % os.environ.get('HTTPDEBUG', 0))

def cms_find(arg):
    """
    Perform lookup of given query in CMS data-services.
    """
    lookup(arg)

def cms_du(arg):
    """
    Disk utility cmssh command. Provides information about given CMS storage element.
    """
    lookup(arg)

def lookup(arg):
    """
    Perform lookup of given query in CMS data-services.
    """
    arg = arg.strip()
    debug = get_ipython().debug
    args  = arg.split('|')
    if  len(args) == 1: # no filter
        res = CMSMGR.lookup(arg)
    else:
        gen = CMSMGR.lookup(args[0].strip())
        for flt in args[1:]:
            res = apply_filter(flt.strip(), gen)
    RESMGR.assign(res)
    list_results(res, debug)

def verbose(arg):
    """
    Set/get verbosity level
    """
    arg = arg.strip()
    ipth = get_ipython()
    if  arg == '':
        print_info("Verbose level is %s" % ipth.debug)
    else:
        if  arg == 0 or arg == '0':
            ipth.debug = False
        else:
            ipth.debug = True

# CMSSW commands
def bootstrap(arch):
    "Bootstrap new architecture"
    swdir = os.environ['VO_CMS_SW_DIR']
    arch  = os.environ['SCRAM_ARCH']
    cmd = 'sh -x %s/bootstrap.sh setup -path %s -arch %s' % (swdir, swdir, arch)
    if  unsupported_linux():
        cmd += ' -unsupported_distribution_hack'
    sdir  = os.path.join(os.environ['CMSSH_ROOT'], 'CMSSW')
    debug = 0
    msg   = 'Bootstrap %s ...' % arch
    run(cmd, sdir, 'bootstrap.log', msg, debug)
    cmd   = 'source `find %s/%s/external/apt -name init.sh | tail -1`; ' \
                % (swdir, arch)
    cmd  += 'apt-get install external+fakesystem+1.0; '
    cmd  += 'apt-get update; '
    msg   = 'Initialize %s apt repository ...' % arch
    run(cmd, sdir, msg=msg, debug=debug)

def get_release_arch(rel):
    "Return architecture for given CMSSW release"
    args = {'release': rel}
    releases = get_data(tc_url(), 'py_getReleaseArchitectures', args)
    output = []
    for item in releases:
        rel_arch = item[0]
        status   = item[1]
        if  check_os(rel_arch):
            output.append((rel_arch, status))
    return output

def check_release_arch(rel):
    "Check release/architecture"
    # check if given release name is installed on user system
    rel_dir = '%s/cms/cmssw/%s' % (os.environ['SCRAM_ARCH'], rel)
    if  os.path.isdir(os.path.join(os.environ['VO_CMS_SW_DIR'], rel_dir)):
        return 'ok'

    output = []
    for arch, status in get_release_arch(rel):
        if  not status:
            msg = '%s release is not officially supported under %s' \
                % (rel, arch)
            print_warning(msg)
        if  arch != os.environ['SCRAM_ARCH']:
            msg = 'Your SCRAM_ARCH=%s, while found arch=%s' \
                % (os.environ['SCRAM_ARCH'], arch)
            print_warning(msg)
        msg = '\n%s/%s is not installed within cmssh, proceed' \
                % (rel, arch)
        if  user_input(msg, default='N'):
            os.environ['SCRAM_ARCH'] = arch
            if  not os.path.isdir(\
                os.path.join(os.environ['VO_CMS_SW_DIR'], arch)):
                bootstrap(arch)
            return 'ok'
        else:
            msg = '%s/%s rejected by user' % (rel, arch)
            output.append(msg)

    if  output:
        return ', '.join(output)

    osname, osarch = osparameters()
    if  osname == 'osx' and osarch == 'ia32':
        return 'OSX/ia32 is not supported in CMSSW'
    return 'no match'

def get_apt_init(arch):
    "Return proper apt init.sh for given architecture"
    apt_dir = os.path.join(\
        os.environ['VO_CMS_SW_DIR'], '%s/external/apt' % arch)
    dirs = os.listdir(apt_dir)
    dirs.sort()
    name = 'etc/profile.d/init.sh'
    script = os.path.join(os.path.join(apt_dir, dirs[-1]), name)
    return script

def cms_install(rel):
    """
    Install given CMSSW release
    """
    rel = rel.strip()
    pat = pat_release
    if  not pat.match(rel):
        msg  = 'Fail to validate release name "%s"' % rel
        print_error(msg)
        msg  = 'Please check the you provide correct release name,'
        msg += ' e.g. CMSSW_X_Y_Z<_patchN>'
        print msg
        return

    # check if we have stand-alone installation
    if  os.path.islink(os.environ['VO_CMS_SW_DIR']):
        msg  = '\nYou are not allowed to install new release, '
        msg += 'since cmssh was installed with system CMSSW install area'
        print msg
        return

    # check if given release/architecture is in place
    status = check_release_arch(rel)
    if  status != 'ok':
        msg = '\nCheck release architecture status: %s' % status
        print msg
        return

    print "Searching for %s" % rel
    script = get_apt_init(os.environ['SCRAM_ARCH'])
    cmd = 'source %s; apt-cache search %s | grep -v -i fwlite' % (script, rel)
    run(cmd)
    if  rel.lower().find('patch') != -1:
        print "Installing cms+cmssw-patch+%s ..." % rel
        cmd = 'source %s; apt-get install cms+cmssw-patch+%s' % (script, rel)
    else:
        print "Installing cms+cmssw+%s ..." % rel
        cmd = 'source %s; apt-get install cms+cmssw+%s' % (script, rel)
    subprocess.call(cmd, shell=True) # use subprocess due to apt-get interactive feature
    print "Create user area for %s release ..." % rel
    cmsrel(rel)

def cmsrel(rel):
    """
    Switch to given CMSSW release
    """
    rel = rel.strip()
    if  not rel:
        print_error('Please specify release name')
        installed_releases()
        return

    # check if given release name is installed on user system
    rel_arch = None
    for arch in cms_architectures():
        rel_dir = '%s/cms/cmssw/%s' % (arch, rel)
        if  os.path.isdir(os.path.join(os.environ['VO_CMS_SW_DIR'], rel_dir)):
            rel_arch = arch
            break
    if  not rel_arch:
        msg  = 'Release %s is not yet installed on your system.\n' % rel
        msg  = msg_red(msg)
        msg += 'Use ' + msg_green('releases')
        msg += ' command to list available releases.\n'
        msg += 'Use ' + msg_green('install %s' % rel)
        msg += ' command to install given release.'
        print msg
        return

    # set release architecture
    os.environ['SCRAM_ARCH'] = rel_arch

    # switch to given release
    cmssw_dir = os.environ.get('CMSSW_RELEASES', os.getcwd())
    if  not os.path.isdir(cmssw_dir):
        os.makedirs(cmssw_dir)
    os.environ['CMSSW_VERSION'] = rel
    os.environ['CMSSW_WORKAREA'] = os.path.join(cmssw_dir, rel)
    if  os.path.isdir(os.path.join(cmssw_dir, rel + '/src')):
        os.chdir(os.path.join(cmssw_dir, rel + '/src'))
    else:
        os.chdir(cmssw_dir)
        cmd = "scramv1 project CMSSW %s" % rel
        run(cmd)
        os.chdir(os.path.join(rel, 'src'))

    # set edm utils for given release
    ipython = get_ipython()
    rdir    = '%s/bin/%s' % (rel_dir, rel_arch)
    reldir  = os.path.join(os.environ['VO_CMS_SW_DIR'], rdir)
    for name in os.listdir(reldir):
        fname = os.path.join(reldir, name)
        if  name.find('edm') == 0 and os.path.isfile(fname):
            magic_name = 'magic_%s' % name
            cmd = "eval `scramv1 runtime -sh`; %s" % fname
            setattr(ipython, magic_name, Magic(cmd).execute)

    # final message
    print "%s is ready, cwd: %s" % (rel, os.getcwd())

def cmsexe(cmd):
    """
    Execute given command within CMSSW environment
    """
    vdir = os.environ.get('VO_CMS_SW_DIR', None)
    arch = os.environ.get('SCRAM_ARCH', None)
    if  not vdir or not arch:
        msg  = 'Unable to identify CMSSW environment, please run first: '
        msg  = msg_red(msg)
        msg += msg_blue('cmsrel <rel>\n')
        releases = os.listdir(os.environ['CMSSW_RELEASES'])
        msg += '\nInstalled releases: ' + msg_green(', '.join(releases))
        print msg
        return
    cmd = "eval `scramv1 runtime -sh`; %s" % cmd
    run(cmd)

def cmscrab(arg):
    """
    Execute CRAB command, help is available at
    https://twiki.cern.ch/twiki/bin/view/CMSPublic/SWGuideCrabFaq
    """
    msg = \
    'CRAB FAQ: https://twiki.cern.ch/twiki/bin/view/CMSPublic/SWGuideCrabFaq'
    print_info(msg)
    # check if release version and work area are set (should be set at cmsrel)
    rel = os.environ.get('CMSSW_VERSION', None)
    work_area = os.environ.get('CMSSW_WORKAREA', None)
    if  not rel or not work_area:
        msg  = 'In order to run crab command you must '
        msg += 'run ' + msg_blue('cmsrel') + ' command'
        print_error(msg)
        return
    # check existence of crab.cfg
    crab_dir = os.path.join(work_area, 'crab')
    crab_cfg = os.path.join(crab_dir, 'crab.cfg')
    if  not os.path.isdir(crab_dir):
        os.makedirs(crab_dir)
    os.chdir(crab_dir)
    if  not os.path.isfile(crab_cfg):
        msg = 'No crab.cfg file found in %s' % crab_dir
        print_warning(msg)
        msg = 'Would you like to create one'
        if  user_input(msg, default='N'):
            with open('crab.cfg', 'w') as config:
                config.write(crabconfig())
            msg  = 'Your crab.cfg has been created, please edit it '
            msg += 'appropriately and re-run crab command'
            print_info(msg)
            print "cwd:", os.getcwd()
        return
    if  os.uname()[0] == 'Darwin' and arg == '-submit':
        crab_submit_remotely(rel, work_area)
        return
    cmd = 'source $CRAB_ROOT/crab.sh; crab %s' % arg
    cmsexe(cmd)

def cmsrun(arg):
    """
    Execute CMSSW cmsRun command
    """
    cmd = 'cmsRun %s' % arg
    cmsexe(cmd)

def dbs_instance(arg=None):
    """
    Show or set dbs instance
    """
    arg = arg.strip()
    if  arg:
        if  validate_dbs_instance(arg):
            os.environ['DBS_INSTANCE'] = arg
            print "Switch to %s DBS instance" % arg
        else:
            print "Invalid DBS instance"
    else:
        msg  = "DBS instance is set to: %s" \
                % os.environ.get('DBS_INSTANCE', 'global')
        print msg
    print '\nAvailable DBS instances:'
    for inst in dbs_instances():
        print inst

def cms_help_msg():
    """cmsHelp message"""
    msg  = '\nAvailable cmssh commands:\n'
    msg += msg_green('find        ') \
        + ' search CMS meta-data (query DBS/Phedex/SiteDB)\n'
    msg += msg_green('dbs_instance') \
        + ' show/set DBS instance, default is DBS global instance\n'
    msg += msg_green('mkdir/rmdir ') + ' mkdir/rmdir command, ' \
        + 'e.g. mkdir /path/foo or rmdir T3_US_Cornell:/store/user/foo\n'
    msg += msg_green('ls          ') \
        + ' list file/LFN, e.g. ls local.file or ls /store/user/file.root\n'
    msg += msg_green('rm          ') + ' remove file/LFN, ' \
        + 'e.g. rm local.file or rm T3_US_Cornell:/store/user/file.root\n'
    msg += msg_green('cp          ') \
        + ' copy file/LFN, e.g. cp local.file or cp /store/user/file.root .\n'
    msg += msg_green('info        ') \
        + ' provides detailed info about given CMS entity, ' \
        + 'e.g. info run=160915\n'
    msg += msg_green('das         ') + ' query DAS service\n'
    msg += msg_green('das_json    ') \
        + ' query DAS and return data in JSON format\n'
    msg += msg_green('dqueue      ') \
        + ' status of download queue, list files which are in progress.\n'
    msg += msg_green('root        ') + ' invoke ROOT\n'
    msg += msg_green('du          ') \
        + ' display disk usage for given site, e.g. du T3_US_Cornell\n'
    msg += '\nAvailable CMSSW commands (once you install any CMSSW release):\n'
    msg += msg_green('releases    ') \
        + ' list available CMSSW releases, accepts <list|all> args\n'
    msg += msg_green('install     ') \
        + ' install CMSSW release, e.g. install CMSSW_5_0_0\n'
    msg += msg_green('cmsrel      ') \
        + ' switch to given CMSSW release and setup its environment\n'
    msg += msg_green('arch        ') \
        + ' show or switch to given CMSSW architecture, accept <list|all> args\n'
    msg += msg_green('scram       ') + ' CMSSW scram command\n'
    msg += msg_green('cmsRun      ') \
        + ' cmsRun command for release in question\n'
    msg += '\nAvailable GRID commands: <cmd> either grid or voms\n'
    msg += msg_green('vomsinit    ') \
        + ' setup your proxy (aka voms-proxy-init)\n'
    msg += msg_green('vomsinfo    ') \
        + ' show your proxy info (aka voms-proxy-info)\n'
    msg += '\nQuery results are accessible via %s function:\n' \
        % msg_blue('results()')
    msg += '   find dataset=/*Zee*\n'
    msg += '   for r in results(): print r, type(r)\n'
    msg += '\nHelp is accessible via ' + msg_blue('cmshelp <command>\n')
    msg += '\nTo install python software use ' + \
                msg_blue('pip <search|(un)install> <package>')
    return msg

def cms_help(arg=None):
    """
    cmshelp command
    """
    if  arg:
        ipython = get_ipython()
        if  arg[0] == '(' and arg[-1] == ')':
            arg = arg[1:-1]
        for case in [arg, 'cms_'+arg, 'cms'+arg]:
            func = ipython.find_magic(case)
            if  func:
                doc = func.func_doc
                break
            else:
                doc = 'Documentation is not available'
    else:
        doc = cms_help_msg()
    print doc

def cms_rm(arg):
    """
    CMS rm command works with local files/dirs and CMS storate elements.
    Examples:
        cmssh> rm local_file
        cmssh> rm -rf local_dir
        cmssh> rm T3_US_Cornell:/xrootdfs/cms/store/user/user_name/file.root
    """
    arg = arg.strip()
    try:
        debug = get_ipython().debug
    except:
        debug = 0
    if  not arg:
        print_error("Usage: rm <options> source_file")
    dst = arg.split()[-1]
    if  os.path.exists(dst) or len(glob.glob(dst)):
        cmd = "rm %s" % arg
        run(cmd)
    else:
        if  pat_lfn.match(arg.split(':')[-1]):
            status = rm_lfn(arg, verbose=debug)
            print_status(status)
        else:
            raise Exception('Not implemented yet')

def cms_rmdir(arg):
    """
    cmssh rmdir command removes directory from local file system or CMS storage element.
    Examples:
        cmssh> rmdir foo
        cmssh> rmdir T3_US_Cornell:/store/user/user_name/foo
    """
    arg = arg.strip()
    try:
        debug = get_ipython().debug
    except:
        debug = 0
    if  not arg:
        print_error("Usage: rmdir <options> dir")
    if  os.path.exists(arg):
        run("rmdir %s" % arg)
    else:
        try:
            status = rmdir(arg, verbose=debug)
            print_status(status)
        except:
            traceback.print_exc()

def cms_mkdir(arg):
    """
    cmssh mkdir command creates directory on local filesystem or remote CMS storage element.
    Examples:
        cmssh> mkdir foo
        cmssh> mkdir T3_US_Cornell:/store/user/user_name/foo
    """
    arg = arg.strip()
    try:
        debug = get_ipython().debug
    except:
        debug = 0
    if  not arg:
        print_error("Usage: mkdir <options> dir")
    if  arg.find(':') == -1: # not a SE:dir pattern
        run("mkdir %s" % arg)
    else:
        try:
            status = mkdir(arg, verbose=debug)
            print_status(status)
        except:
            traceback.print_exc()

def cms_ls(arg):
    """
    cmssh ls command lists local files/dirs/CMS storate elements or
    CMS entities (se, site, dataset, block, run, release, file).
    Examples:
        cmssh> ls local_file
        cmssh> ls -l local_file
        cmssh> ls T3_US_Cornell:/store/user/valya
        cmssh> ls run=160915
    """
    arg = arg.strip()
    res = []
    try:
        debug = get_ipython().debug
    except:
        debug = 0
    orig_arg = arg
    if  orig_arg.find('|') != -1:
        arg, flt = orig_arg.split('|', 1)
        arg = arg.strip()
    else:
        flt = None
    startswith = None
    entities = \
        ['se', 'site', 'lfn', 'dataset', 'block', 'run', 'release', 'file']
    for item in entities:
        if  arg.startswith(item + '='):
            startswith = item
    if  os.path.isfile(orig_arg) or os.path.isdir(orig_arg):
        cmd = 'ls ' + orig_arg
        run(cmd, shell=True)
    elif pat_se.match(arg):
        arg = arg.replace('site=', '')
        res = list_se(arg, debug)
    elif  pat_site.match(arg):
        arg = arg.replace('site=', '')
        res = site_info(arg, debug)
    elif pat_lfn.match(arg):
        arg = arg.replace('file=', '')
        res = file_info(arg, debug)
    elif pat_block.match(arg):
        arg = arg.replace('block=', '')
        res = block_info(arg, debug)
    elif pat_dataset.match(arg):
        arg = arg.replace('dataset=', '')
        res = dataset_info(arg, debug)
    elif pat_run.match(arg):
        arg = arg.replace('run=', '')
        res = run_info(arg, debug)
    elif pat_release.match(arg):
        arg = arg.replace('release=', '')
        res = release_info(arg, debug)
    elif startswith:
        msg = 'No pattern is allowed for %s look-up' % startswith
        print_error(msg)
    else:
        cmd = 'ls ' + orig_arg
        run(cmd, shell=True)
    if  res:
        RESMGR.assign(res)
        list_results(res, debug=True, flt=flt)

def cms_lumi(arg):
    "Return lumi info for given dataset"
    arg = arg.replace('dataset=', '')
    res = run_lumi_info(arg)

def cms_info(arg):
    """
    cmssh info command provides information for given meta-data entity, e.g.
    dataset, block, file, run.
    Examples:
        cmssh> info dataset=/a/b/c
        cmssh> info /a/b/c
        cmssh> info run=160915

    Please note: to enable access to RunSummary service please ensure that your
    usercert.pem is mapped at https://ca.cern.ch/ca/Certificates/MapCertificate.aspx
    """
    cms_ls(arg)

def cms_cp(arg):
    """
    cmssh cp command copies local files/dirs to/from local files/dirs or CMS storate elements.
    Examples:
        cmssh> cp file1 file2
        cmssh> cp file.root T3_US_Cornell:/store/user/name
        cmssh> cp /store/mc/file.root T3_US_Cornell:/store/user/name
        cmssh> cp T3_US_Cornell:/store/user/name/file.root T3_US_Omaha
    """
    check_voms_proxy()
    arg = arg.strip()
    try:
        src, dst = arg.split(' ', 1)
        if  dst.find('&') != -1:
            background = True
            dst = dst.replace('&', '').strip()
        else:
            background = False
        if  dst == '.':
            dst = os.getcwd()
    except:
        traceback.print_exc()
        return
    try:
        debug = get_ipython().debug
    except:
        debug = 0
    if  not arg:
        print_error("Usage: cp <options> source_file target_{file,directory}")
    pat = pat_se
    if  os.path.exists(src) and not pat.match(dst):
        run("cp %s %s" % (src, dst))
    else:
        try:
            status = copy_lfn(src, dst, debug, background)
            print_status(status)
        except:
            traceback.print_exc()

def cms_dqueue(arg=None):
    "Return status of transfer queue. For detailed view please use list option."
    if  arg and arg != 'list':
        print_error("Wrong argument '%s', please use 'list'" % arg)
        return
    dqueue(arg)

def cms_architectures(arch_type=None):
    "Return list of CMSSW architectures (aka SCRAM_ARCH)"
    archs = [a for a in tc_architectures(arch_type)]
    return archs

def cms_arch(arg=None):
    """
    Show or set CMSSW architecture. Optional parameters either <all> or <list>
    Examples:
        cmssh> arch      # show current and installed architecture(s)
        cmssh> arch all  # show all known CMSSW architectures
        cmssh> arch list # show all CMSSW architectures for given platform
    """
    if  not arg:
        print "Current architecture: %s" % os.environ['SCRAM_ARCH']
        archs = []
        for name in os.listdir(os.environ['VO_CMS_SW_DIR']):
            if  check_os(name) and name.find('.') == -1:
                archs.append(name)
        if  archs:
            print '\nInstalled architectures:'
            for item in archs:
                print item
    elif arg == 'all' or arg == 'list':
        if  arg == 'all':
            print 'CMSSW architectures:'
        else:
            print 'CMSSW architectures for %s:' \
                % os.uname()[0].replace('Darwin', 'OSX')
        for name in cms_architectures('all'):
            if  arg == 'all':
                print name
            else:
                if  check_os(name):
                    print name
    else:
        cms_archs = cms_architectures('all')
        if  arg not in cms_archs:
            msg  = 'Wrong architecture, please choose from the following list\n'
            msg += ', '.join(cms_archs)
            raise Exception(msg)
        print "Switch to SCRAM_ARCH=%s" % arg
        os.environ['SCRAM_ARCH'] = arg

def cms_apt(arg=''):
    "Execute apt commands"
    if  '-cache' in arg or '-get' in arg:
        cmd = 'apt%s' % arg
    else:
        msg = 'Not supported apt command'
        raise Exception(msg)
    run(cmd)

def cms_das(query):
    "Execute given query in CMS DAS data-service"
    host  = 'https://cmsweb.cern.ch'
    idx   = 0
    limit = 0
    debug = 0
    das_client(host, query, idx, limit, debug, 'plain')

def cms_das_json(query):
    "Execute given query in CMS DAS data-service"
    host  = 'https://cmsweb.cern.ch'
    idx   = 0
    limit = 0
    debug = 0
    res   = das_client(host, query, idx, limit, debug, 'json')
    RESMGR.assign([res])
    pprint.pprint(res)

def cms_vomsinit(_arg=None):
    "Execute voms-proxy-init command on behalf of the user"
    cert = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
    with working_pem(PEMMGR.pem) as key:
        run("voms-proxy-destroy")
        cmd = "voms-proxy-init -rfc -voms cms:/cms -key %s -cert %s" % (key, cert)
        run(cmd)

def github_issues(arg=None):
    """
    Retrieve information about cmssh tickets, e.g.
    Examples:
        cmssh> tickets     # list all cmssh tickets
        cmssh> ticket 14   # get details for given ticket id
        cmssh> ticket new  # post new ticket from cmssh
        # or post it at https://github.com/vkuznet/cmssh/issues/new
    """
    if  arg == 'new':
        msg  = 'You can post new ticket via web interface at\n'
        msg += 'https://github.com/vkuznet/cmssh/issues/new\n'
        msg += 'otherwise it will be posted as anonymous gist ticket'
        print_info(msg)
        if  not user_input('Proceed', default='N'):
            return
        email = raw_input('Your Email : ')
        if  not email:
            msg = "You did your email address"
            print_error(msg)
            return
        desc  = ''
        msg   = 'Type your problem, attach traceback, etc. Once done print '
        msg  += msg_blue('EOF') + ' and hit ' + msg_blue('Enter') + '\n' 
        print msg
        while True:
            try:
                uinput = raw_input()
                if  uinput.strip() == 'EOF':
                    break
                desc += uinput + '\n'
            except KeyboardInterrupt:
                break
        if  not desc:
            msg = "You did not provide bug description"
            print_error(msg)
            return
        if  not user_input('Send this ticket', default='N'):
            print_info('Aborting your action')
            return
        key   = 'cmssh-%s' % time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time()))
        files = {key: {'content': desc}}
        res   = post_ticket(key, files)
        if  res.has_key('html_url'):
            print_status('New gist ticket %s' % res['html_url'])
            title = 'cmssh gist %s' % res['html_url']
            if  isinstance(res, dict):
                ticket = pprint.pformat(res)
            else:
                ticket = res
            to_user = base64.decodestring('dmt1em5ldEBnbWFpbC5jb20=\n')
            send_email(to_user, email, title, ticket)
    else:
        res = get_tickets(arg)
        RESMGR.assign(res)
        pprint.pprint(res)

def demo(_arg=None):
    "Show cmssh demo file"
    root = os.environ.get('CMSSH_ROOT')
    path = os.path.join(root, 'cmssh/DEMO')
    with open(path, 'r') as demo_file:
        print demo_file.read()

def results():
    """Return results from recent query"""
    return RESMGR
