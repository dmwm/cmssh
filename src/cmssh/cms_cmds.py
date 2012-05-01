#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
Set of UNIX commands, e.g. ls, cp, supported in cmssh.
"""

# system modules
import os
import re
import json
import glob
import pprint
import traceback
import subprocess

# cmssh modules
from cmssh.iprint import print_red, print_blue, msg_red, msg_green, msg_blue
from cmssh.iprint import print_warning, print_error, print_success
from cmssh.filemover import copy_lfn, rm_lfn, mkdir, rmdir, list_se, dqueue
from cmssh.utils import list_results, check_os, exe_cmd, unsupported_linux
from cmssh.utils import osparameters, check_voms_proxy
from cmssh.cmsfs import dataset_info, block_info, file_info, site_info, run_info
from cmssh.cmsfs import CMSMGR, apply_filter, validate_dbs_instance, release_info
from cmssh.cms_urls import dbs_instances, tc_url
from cmssh.das import get_data as das_get_data, das_client
from cmssh.url_utils import get_data
from cmssh.regex import pat_release, pat_site, pat_dataset, pat_block
from cmssh.regex import pat_lfn, pat_run, pat_se, pat_release
from cmssh.tagcollector import releases as tc_releases
from cmssh.tagcollector import architectures as tc_architectures
from cmssh.results import RESMGR
from cmssh.auth_utils import PEMMGR, working_pem

def options(arg):
    """Extract options from given arg string"""
    alist = arg.split()
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
        cmd_opts = '%s %s' % (self.cmd, args.strip())
        subprocess.call(cmd_opts.strip(), shell=True)

def installed_releases():
    "Print a list of releases installed on a system"
    osname, osarch = osparameters()
    releases = []
    for idir in os.listdir(os.environ['VO_CMS_SW_DIR']):
        if  idir.find(osarch) != -1:
            rdir = os.path.join(os.environ['VO_CMS_SW_DIR'], '%s/cms/cmssw' % idir)
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
    """List available CMS releases"""
    arch = None
    platform = os.uname()[0]
    if  platform == 'Darwin':
        arch = 'osx'
    elif platform == 'Linux':
        arch = 'slc'
    else:
        raise Exception('Unsupported platform %s' % os.uname())

    if  arg == 'all':
        for rel in tc_releases():
            print rel['release_name']
    installed_releases()

def pkg_init(pkg_dir):
    "Create CMS command to source pkg environment"
    pkg_dir  = '%s/%s/%s' \
        % (os.environ['VO_CMS_SW_DIR'], os.environ['SCRAM_ARCH'], pkg_dir)
    pkg_init = 'source `find %s -name init.sh | tail -1`;' % pkg_dir
    if  not os.path.isdir(pkg_dir):
        pkg_init = ''
    return pkg_init

def cms_root(arg):
    """
    Run ROOT command
    """
    pcre_init = pkg_init('external/pcre')
    gcc_init  = pkg_init('external/gcc')
    root_init = pkg_init('lcg/root')
    pkgs_init = '%s %s %s' % (pcre_init, gcc_init, root_init)
    cmd_opts  = '%s root -l %s' % (pkgs_init, arg.strip())
    subprocess.call(cmd_opts, shell=True)

def cms_xrdcp(arg):
    """
    Run ROOT xrdcp command
    """
    dyld_path = os.environ.get('DYLD_LIBRARY_PATH', None)
    root_path = os.environ['DEFAULT_ROOT']
    if  dyld_path:
        os.environ['DYLD_LIBRARY_PATH'] = os.path.join(root_path, 'lib')
    cmd_opts = '%s/xrdcp %s' % (os.path.join(root_path, 'bin'), arg.strip())
    subprocess.call(cmd_opts, shell=True)
    if  dyld_path:
        os.environ['DYLD_LIBRARY_PATH'] = dyld_path

def debug(arg):
    """
    debug shell command
    """
    arg = arg.strip()
    if  arg:
        print_blue("Set debug level to %s" % arg)
        DEBUG.set(arg)
    else:
        print_blue("Debug level is %s" % DEBUG.level)

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
    ip = get_ipython()
    if  arg == '':
        print "verbose", ip.debug
    else:
        if  arg == 0 or arg == '0':
            ip.debug = False
        else:
            ip.debug = True

# CMSSW commands
def bootstrap(arch):
    "Bootstrap new architecture"
    cmd = 'sh -x $VO_CMS_SW_DIR/bootstrap.sh setup -path $VO_CMS_SW_DIR -arch $SCRAM_ARCH'
    if  unsupported_linux():
        cmd += ' -unsupported_distribution_hack'
    sdir  = os.path.join(os.environ['CMSSH_ROOT'], 'CMSSW')
    debug = 0
    exe_cmd(sdir, cmd, debug, 'Bootstrap %s ...' % arch)
    cmd   = 'source `find $VO_CMS_SW_DIR/$SCRAM_ARCH/external/apt -name init.sh | tail -1`; '
    cmd  += 'apt-get install external+fakesystem+1.0; '
    cmd  += 'apt-get update; '
    exe_cmd(sdir, cmd, debug, 'Initialize %s apt repository ...' % arch)

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
        msg = '\n%s/%s is not installed within cmssh, proceed [y/N] ' \
                % (rel, arch)
        val = raw_input(msg)
        if  val.lower() == 'y' or val.lower() == 'yes':
            os.environ['SCRAM_ARCH'] = arch
            if  not os.path.isdir(os.path.join(os.environ['VO_CMS_SW_DIR'], arch)):
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
    apt_dir = os.path.join(os.environ['VO_CMS_SW_DIR'], '%s/external/apt' % arch)
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
    subprocess.call(cmd, shell=True)
    if  rel.lower().find('patch') != -1:
        print "Installing cms+cmssw-patch+%s ..." % rel
        cmd = 'source %s; apt-get install cms+cmssw-patch+%s' % (script, rel)
    else:
        print "Installing cms+cmssw+%s ..." % rel
        cmd = 'source %s; apt-get install cms+cmssw+%s' % (script, rel)
    subprocess.call(cmd, shell=True)
    print "Create user area for %s release ..." % rel
    cmsrel(rel)

def cmsrel(rel):
    """
    Switch to given CMSSW release
    """
    rel = rel.strip()
    if  not rel:
        print_red('Please specify release name')
        installed_releases()
        return

    # check if given release name is installed on user system
    rel_arch = None
    for arch in cms_architectures():
        rel_dir = '%s/cms/cmssw/%s' % (arch, rel)
        if  os.path.isdir(os.path.join(os.environ['VO_CMS_SW_DIR'], rel_dir)):
            rel_arch = arch
    if  not rel_arch:
        msg  = msg_red('Release %s is not yet installed on your system.\n' % rel)
        msg += 'Use ' + msg_green('releases') + ' command to list available releases.\n'
        msg += 'Use ' + msg_green('install %s' % rel) + ' command to install given release.'
        print msg
        return

    # set release architecture
    os.environ['SCRAM_ARCH'] = rel_arch

    # switch to given release
    cmssw_dir = os.environ.get('CMSSW_RELEASES', os.getcwd())
    if  not os.path.isdir(cmssw_dir):
        os.makedirs(cmssw_dir)
    if  os.path.isdir(os.path.join(cmssw_dir, rel + '/src')):
        os.chdir(os.path.join(cmssw_dir, rel + '/src'))
    else:
        os.chdir(cmssw_dir)
        subprocess.call("scramv1 project CMSSW %s" % rel, shell=True)
        os.chdir(os.path.join(rel, 'src'))
    print "%s is ready, cwd: %s" % (rel, os.getcwd())

def cmsrun(arg):
    """
    Execute CMSSW cmsRun command
    """
    vdir = os.environ.get('VO_CMS_SW_DIR', None)
    arch = os.environ.get('SCRAM_ARCH', None)
    if  not vdir or not arch:
        msg  = msg_red('Unable to identify CMSSW environment, please run first: ')
        msg += msg_blue('cmsrel <rel>\n')
        releases = os.listdir(os.environ['CMSSW_RELEASES'])
        msg += '\nInstalled releases: ' + msg_green(', '.join(releases))
        print msg
        return
    cmd = "eval `scramv1 runtime -sh`; cmsRun"
    cmd_opts = '%s %s' % (cmd, arg.strip())
    subprocess.call(cmd_opts, shell=True)

def dbs_instance(arg=None):
    """
    Set dbs instance
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
    msg += msg_green('mkdir/rmdir ') \
        + ' mkdir/rmdir command, e.g. mkdir /path/foo or rmdir T3_US_Cornell:/store/user/foo\n'
    msg += msg_green('ls          ') \
        + ' list file/LFN, e.g. ls local.file or ls /store/user/file.root\n'
    msg += msg_green('rm          ') \
        + ' remove file/LFN, e.g. rm local.file or rm T3_US_Cornell:/store/user/file.root\n'
    msg += msg_green('cp          ') \
        + ' copy file/LFN, e.g. cp local.file or cp /store/user/file.root .\n'
    msg += msg_green('info        ') \
        + ' provides detailed info about given CMS entity, e.g. info run=160915\n'
    msg += msg_green('das         ') \
        + ' query DAS\n'
    msg += msg_green('das_json    ') \
        + ' query DAS and return data in JSON format\n'
    msg += msg_green('dqueue      ') \
        + ' status of download queue, list files which are in progress.\n'
    msg += msg_green('root        ') + ' invoke ROOT\n'
    msg += msg_green('du          ') \
        + ' display disk usage for given site, e.g. du T3_US_Cornell\n'
    msg += '\nAvailable CMSSW commands (once you install any CMSSW release):\n'
    msg += msg_green('releases    ') \
        + ' list available CMSSW releases\n'
    msg += msg_green('install     ') \
        + ' install CMSSW release, e.g. install CMSSW_5_0_0\n'
    msg += msg_green('cmsrel      ') \
        + ' switch to given CMSSW release and setup its environment\n'
    msg += msg_green('arch        ') \
        + ' show or switch to given CMSSW architecture\n'
    msg += msg_green('scram       ') + ' CMSSW scram command\n'
    msg += msg_green('cmsRun      ') \
        + ' cmsRun command for release in question\n'
    msg += '\nAvailable GRID commands: <cmd> either grid or voms\n'
    msg += msg_green('vomsinit    ') + ' setup your proxy (aka voms-proxy-init)\n'
    msg += msg_green('vomsinfo    ') + ' show your proxy info (aka voms-proxy-info)\n'
    msg += '\nQuery results are accessible via %s function:\n' % msg_blue('results()')
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
        if  arg in ipython.lsmagic():
            doc = getattr(ipython, 'magic_%s' % arg).func_doc
        elif 'cms_%s' % arg in ipython.lsmagic():
            doc = getattr(ipython, 'magic_cms_%s' % arg).func_doc
        elif 'cms%s' % arg in ipython.lsmagic():
            doc = getattr(ipython, 'magic_cms%s' % arg).func_doc
        else:
            doc = 'Documentation is not available'
    else:
        doc = cms_help_msg()
    print doc

def cms_rm(arg):
    """
    CMS rm command works with local files/dirs and CMS storate elements.
    Examples:
        cmssh# rm local_file
        cmssh# rm -rf local_dir
        cmssh# rm T3_US_Cornell:/xrootdfs/cms/store/user/user_name/file.root
    """
    arg = arg.strip()
    try:
        verbose = get_ipython().debug
    except:
        verbose = 0
    if  not arg:
        print_red("Usage: rm <options> source_file")
    dst = arg.split()[-1]
    if  os.path.exists(dst) or len(glob.glob(dst)):
        prc = subprocess.Popen("rm " + arg, shell=True)
        sts = os.waitpid(prc.pid, 0)[1]
    else:
        if  pat_lfn.match(arg):
            status = rm_lfn(arg, verbose=verbose)
            print_blue("Status %s" % status)
        else:
            raise Exception('Not implemented yet')

def cms_rmdir(arg):
    """
    cmssh rmdir command removes directory from local file system or CMS storage element.
    Examples:
        cmssh# rmdir foo
        cmssh# rmdir T3_US_Cornell:/store/user/user_name/foo
    """
    arg = arg.strip()
    try:
        verbose = get_ipython().debug
    except:
        verbose = 0
    if  not arg:
        print_red("Usage: rmdir <options> dir")
    if  os.path.exists(arg):
        prc = subprocess.Popen("rmdir " + arg, shell=True)
        sts = os.waitpid(prc.pid, 0)[1]
    else:
        try:
            status = rmdir(arg, verbose=verbose)
            print_blue("Status %s" % status)
        except:
            traceback.print_exc()

def cms_mkdir(arg):
    """
    cmssh mkdir command creates directory on local filesystem or remote CMS storage element.
    Examples:
        cmssh# mkdir foo
        cmssh# mkdir T3_US_Cornell:/store/user/user_name/foo
    """
    arg = arg.strip()
    try:
        verbose = get_ipython().debug
    except:
        verbose = 0
    if  not arg:
        print_red("Usage: mkdir <options> dir")
    if  arg.find(':') == -1: # not a SE:dir pattern
        prc = subprocess.Popen("mkdir " + arg, shell=True)
        sts = os.waitpid(prc.pid, 0)[1]
    else:
        try:
            status = mkdir(arg, verbose=verbose)
            print_blue("Status %s" % status)
        except:
            traceback.print_exc()

def cms_ls(arg):
    """
    cmssh ls command lists local files/dirs or CMS storate elements.
    Examples:
        cmssh# ls local_file
        cmssh# ls -l local_file
        cmssh# rm T3_US_Cornell:/store/user/valya
    """
    arg = arg.strip()
    try:
        verbose = get_ipython().debug
    except:
        verbose = 0
    if  not arg:
        arg = '.'
    if  arg and arg[0] == '~':
        arg = os.path.join(os.environ['HOME'], arg.replace('~/', ''))
    orig_arg = arg
    opts = options(arg)
    path = '/'.join(arg.split('/')[:-1])
    if  opts:
        arg = arg.strip().replace(''.join(opts), '').strip()
    if  os.path.exists(arg) or not arg  or (path and os.path.exists(path)):
        prc = subprocess.Popen("ls " + " " + ''.join(opts) + " " + arg, shell=True)
        sts = os.waitpid(prc.pid, 0)[1]
    else:
        if  orig_arg.find('|') != -1:
            arg, flt = orig_arg.split('|', 1)
            arg = arg.strip()
        else:
            flt = None
        if  pat_se.match(arg):
            arg = arg.replace('site=', '')
            res = list_se(arg, verbose)
        elif  pat_site.match(arg):
            arg = arg.replace('site=', '')
            res = site_info(arg, verbose)
        elif pat_lfn.match(arg):
            arg = arg.replace('file=', '')
            res = file_info(arg, verbose)
        elif pat_block.match(arg):
            arg = arg.replace('block=', '')
            res = block_info(arg, verbose)
        elif pat_dataset.match(arg):
            arg = arg.replace('dataset=', '')
            res = dataset_info(arg, verbose)
        elif pat_run.match(arg):
            arg = arg.replace('run=', '')
            res = run_info(arg, verbose)
        elif pat_release.match(arg):
            arg = arg.replace('release=', '')
            res = release_info(arg, verbose)
        else:
            raise Exception('Unsupported input')
        RESMGR.assign(res)
        list_results(res, debug=True, flt=flt)

def cms_info(arg):
    """
    cmssh info command provides information for given meta-data entity, e.g.
    dataset, block, file, run.
    Examples:
        cmssh# info dataset=/a/b/c
        cmssh# info /a/b/c
        cmssh# info run=160915
    """
    cms_ls(arg)

def cms_cp(arg):
    """
    cmssh cp command copies local files/dirs to/from local files/dirs or CMS storate elements.
    Examples:
        cmssh# cp file1 file2
        cmssh# cp file.root T3_US_Cornell:/store/user/name
        cmssh# cp /store/mc/file.root T3_US_Cornell:/store/user/name
        cmssh# cp T3_US_Cornell:/store/user/name/file.root T3_US_Omaha
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
        print_red("Wrong argument(s) for, cp '%s'" % arg)
    try:
        verbose = get_ipython().debug
    except:
        verbose = 0
    if  not arg:
        print_red("Usage: cp <options> source_file target_{file,directory}")
    pat = pat_se
    if  os.path.exists(src) and not pat.match(dst):
        prc = subprocess.Popen("cp %s %s" % (src, dst), shell=True)
        sts = os.waitpid(prc.pid, 0)[1]
    else:
        try:
            status = copy_lfn(src, dst, verbose, background)
            print_blue("Status %s" % status)
        except:
            traceback.print_exc()
            print_red("Wrong argument '%s'" % arg)

def cms_dqueue(arg=None):
    "Return status of transfer queue. For detailed view please use list option."
    if  arg and arg != 'list':
        print_red("Wrong argument '%s', please use 'list'" % arg)
        return
    dqueue(arg)

def cms_architectures(arch_type=None):
    "Return list of CMSSW architectures (aka SCRAM_ARCH)"
    archs = [a for a in tc_architectures(arch_type)]
    return archs

def cms_arch(arg=None):
    """
    Show or set CMSSW architecture. Optional parameters either <all> or <list>
        arch      # show current and installed architecture(s)
        arch all  # show all known CMSSW architectures
        arch list # show all CMSSW architectures for given platform
    """
    if  not arg:
        print "Current architecture: %s" % os.environ['SCRAM_ARCH']
        archs = []
        for name in os.listdir(os.environ['VO_CMS_SW_DIR']):
            if  check_os(name):
                archs.append(name)
        if  archs:
            print '\nInstalled architectures:'
            for item in archs:
                print item
    elif arg == 'all' or arg == 'list':
        if  arg == 'all':
            print 'CMSSW architectures:'
        else:
            print 'CMSSW architectures for %s:' % os.uname()[0].replace('Darwin', 'OSX')
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
    subprocess.call(cmd, shell=True)

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
        cmd  = "voms-proxy-destroy; "
        cmd += "voms-proxy-init -voms cms:/cms -key %s -cert %s" % (key, cert)
        subprocess.call(cmd, shell=True)

def results():
    """Return results from recent query"""
    return RESMGR
