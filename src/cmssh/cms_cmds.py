#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
Set of UNIX commands, e.g. ls, cp, supported in cmssh.
"""

# system modules
import os
import re
import glob
import traceback
import subprocess

# cmssh modules
from cmssh.iprint import print_red, print_blue, msg_red, msg_green, PrintManager
from cmssh.iprint import print_warning, print_error, print_success
from cmssh.filemover import copy_lfn, rm_lfn, mkdir, rmdir, list_se, dqueue
from cmssh.utils import list_results, check_os, exe_cmd, unsupported_linux
from cmssh.utils import osparameters
from cmssh.cmsfs import dataset_info, block_info, file_info, site_info, run_info
from cmssh.cmsfs import CMSFS, apply_filter, validate_dbs_instance
from cmssh.cms_urls import dbs_instances, tc_url
from cmssh.url_utils import get_data
from cmssh.results import ResultManager

# global scope
CMSMGR = CMSFS()
RESMGR = ResultManager()
PM     = PrintManager()

def options(arg):
    """Extract options from given arg string"""
    alist = arg.split()
    opts = []
    for par in arg.split():
        if  len(par) > 0 and par[0] == '-':
            opts.append(par)
    return opts

def execute(cmd, args=''):
    "Execute given command and its args in a shell"
    dyld = os.environ.get('DYLD_LIBRARY_PATH', None)
    if  dyld:
        os.environ['DYLD_LIBRARY_PATH'] = ''
    cmd_opts = '%s %s' % (cmd, args.strip())
    subprocess.call(cmd_opts, shell=True)
    if  dyld:
        os.environ['DYLD_LIBRARY_PATH'] = dyld

def execute_within_env(cmd, args=''):
    "Execute given command and its args in a shell"
    if  args.find("|") != -1:
        cmd_opts = '%s %s' % (cmd, args.strip())
        subprocess.call(cmd_opts, shell=True)
    else:
        cmd_opts = [cmd] + args.strip().split()
        subprocess.call(cmd_opts)

class Magic(object):
    def __init__(self, cmd):
        self.cmd = cmd
    def execute(self, args=''):
        "Execute given command and its args in a shell"
        execute(self.cmd, args)
    def execute_within_env(self, args=''):
        "Execute given command and its args in a shell"
        execute_within_env(self.cmd, args)

def cms_releases(_arg):
    """List available CMS releases"""
    arch = None
    platform = os.uname()[0]
    if  platform == 'Darwin':
        arch = 'osx'
    elif platform == 'Linux':
        arch = 'slc'
    else:
        raise Exception('Unsupported platform %s' % os.uname())

    active_releases = get_data(tc_url(), 'py_getActiveReleases')
    active = {}
    non_active = {}
    for rel in active_releases:
        args = {'release': rel}
        releases = get_data(tc_url(), 'py_getReleaseArchitectures', args)
        for item in releases:
            rel_arch = item[0]
            status   = item[1]
            if  rel_arch.find(arch) != -1:
                if  status:
                    active.setdefault(rel_arch, []).append(rel)
                else:
                    non_active.setdefault(rel_arch, []).append(rel)
    if  active:
        print "Supported releases for %s:" % platform.replace('Darwin', 'Mac OS X')
        for arch, releases in active.items():
            print '%s: %s' % (arch, ', '.join(releases))
    if  non_active:
        print "Un-supported releases for %s:" % platform.replace('Darwin', 'Mac OS X')
        for arch, releases in non_active.items():
            print '%s: %s' % (arch, ', '.join(releases))

    print "\nAvailable CMS releases for %s:" % os.environ['SCRAM_ARCH']
    cmd  = "apt-cache search CMSSW | grep CMSSW | grep -v -i fwlite"
    cmd += "| awk '{print $1}' | sed -e 's/cms+cmssw+//g' -e 's/cms+cmssw-patch+//g'"
    subprocess.call(cmd, shell=True)
    print "\nInstalled releases:"
    osname, osarch = osparameters()
    for idir in os.listdir(os.environ['VO_CMS_SW_DIR']):
        if  idir.find(osarch) != -1:
            rdir = os.path.join(os.environ['VO_CMS_SW_DIR'], '%s/cms/cmssw' % idir)
            if  os.path.isdir(rdir):
                for rel in os.listdir(rdir):
                    print '%s/%s' % (rel, idir)
#    rdir = os.path.join(os.environ['CMSSH_ROOT'], 'Releases')
#    if  os.path.isdir(rdir):
#        for rel in os.listdir(rdir):
#            print rel

def cms_root(arg):
    """
    Run ROOT command
    """
#    dyld_path = os.environ.get('DYLD_LIBRARY_PATH', None)
#    root_path = os.environ['DEFAULT_ROOT']
#    if  dyld_path:
#        os.environ['DYLD_LIBRARY_PATH'] = os.path.join(root_path, 'lib')
#    cmd_opts = '%s/root -l %s' % (os.path.join(root_path, 'bin'), arg.strip())
#    subprocess.call(cmd_opts, shell=True)
#    if  dyld_path:
#        os.environ['DYLD_LIBRARY_PATH'] = dyld_path
    cmd_opts = 'root -l %s' % arg.strip()
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
        PM.print_blue("Set debug level to %s" % arg)
        DEBUG.set(arg)
    else:
        PM.print_blue("Debug level is %s" % DEBUG.level)

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
    pat = '^CMSSW(_[0-9]){3}$|^CMSSW(_[0-9]){3}_patch[0-9]+$|^CMSSW(_[0-9]){3}_pre[0-9]+$'
    pat = re.compile(pat)
    if  not pat.match(rel):
        msg  = 'Fail to validate release name "%s"' % rel
        print_error(msg)
        msg  = 'Please check the you provide correct release name,'
        msg += ' e.g. CMSSW_X_Y_Z<_patchN>'
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
        print "\nInstalled releases:"
        dirs = os.listdir(os.path.join(os.environ['CMSSH_ROOT'], 'Releases'))
        for rel in dirs:
            print rel
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
        msg  = PM.msg_red('Unable to identify CMSSW environment, please run first: ')
        msg += PM.msg_blue('cmsrel <rel>\n')
        releases = os.listdir(os.environ['CMSSW_RELEASES'])
        msg += '\nInstalled releases: ' + PM.msg_green(', '.join(releases))
        print msg
        return
    cmd = "eval `scramv1 runtime -sh`; cmsRun"
    execute(cmd, arg)

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
    msg += PM.msg_green('find        ') \
        + ' search CMS meta-data (query DBS/Phedex/SiteDB)\n'
    msg += PM.msg_green('dbs_instance') \
        + ' show/set DBS instance, default is DBS global instance\n'
    msg += PM.msg_green('mkdir/rmdir ') \
        + ' mkdir/rmdir command, e.g. mkdir /path/foo or rmdir T3_US_Cornell:/store/user/foo\n'
    msg += PM.msg_green('ls          ') \
        + ' list file/LFN, e.g. ls local.file or ls /store/user/file.root\n'
    msg += PM.msg_green('rm          ') \
        + ' remove file/LFN, e.g. rm local.file or rm T3_US_Cornell:/store/user/file.root\n'
    msg += PM.msg_green('cp          ') \
        + ' copy file/LFN, e.g. cp local.file or cp /store/user/file.root .\n'
    msg += PM.msg_green('info        ') \
        + ' provides detailed info about given CMS entity, e.g. info run=160915\n'
    msg += PM.msg_green('dqueue      ') \
        + ' status of download queue, list files which are in progress.\n'
    msg += PM.msg_green('root        ') + ' invoke ROOT\n'
    msg += PM.msg_green('du          ') \
        + ' display disk usage for given site, e.g. du T3_US_Cornell\n'
    msg += '\nAvailable CMSSW commands (once you install any CMSSW release):\n'
    msg += PM.msg_green('releases    ') \
        + ' list available CMSSW releases\n'
    msg += PM.msg_green('install     ') \
        + ' install CMSSW release, e.g. install CMSSW_5_0_0\n'
    msg += PM.msg_green('cmsrel      ') \
        + ' switch to given CMSSW release and setup its environment\n'
    msg += PM.msg_green('arch        ') \
        + ' show or switch to given CMSSW architecture\n'
    msg += PM.msg_green('scram       ') + ' CMSSW scram command\n'
    msg += PM.msg_green('cmsRun      ') \
        + ' cmsRun command for release in question\n'
    msg += '\nAvailable GRID commands: <cmd> either grid or voms\n'
    msg += PM.msg_green('<cmd>init    ') + ' setup your proxy (aka <cmd>-proxy-init)\n'
    msg += PM.msg_green('<cmd>info    ') + ' show your proxy info (aka <cmd>-proxy-info)\n'
    msg += '\nQuery results are accessible via %s function:\n' % PM.msg_blue('results()')
    msg += '   find dataset=/*Zee*\n'
    msg += '   for r in results(): print r, type(r)\n'
    msg += '\nHelp is accessible via ' + PM.msg_blue('cmshelp <command>\n')
    msg += '\nTo install python software use ' + \
                PM.msg_blue('pip <search|(un)install> <package>')
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
        pat_lfn = re.compile('.*\.root$')
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
    cmssh mkdir command creates directory on local filesystem or remove CMS storage element.
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
    opts = options(arg)
    if  opts:
        arg = arg.strip().replace(''.join(opts), '').strip()
    if  os.path.exists(arg) or not arg:
        prc = subprocess.Popen("ls " + " " + ''.join(opts) + " " + arg, shell=True)
        sts = os.waitpid(prc.pid, 0)[1]
    else:
        pat_site = re.compile('^(site=)?T[0-9]_[A-Z]+(_)[A-Z]+')
        pat_dataset = re.compile('^(dataset=)?/.*/.*/.*')
        pat_block = re.compile('^(block=)?/.*/.*/.*#.*')
        pat_lfn = re.compile('^(file=)?/.*\.root$')
        pat_run = re.compile('^(run=)?[1-9][0-9]{5,8}$')
        pat_se = re.compile('^(site=)?T[0-3]_.*:/.*')
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
        else:
            raise Exception('Unsupported input')
        RESMGR.assign(res)
        list_results(res, debug=True)

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
    pat = re.compile('T[0-3].*:/.*')
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
    "Return status of LFN in transfer (the download queue)"
    if  arg and arg != 'list':
        print_red("Wrong argument '%s', please use 'list'" % arg)
        return
    dqueue(arg)

def cms_architectures():
    "Return list of supported CMS architectures"
    # TODO: I need to replace py_getReleaseArchitectures
    # with new API which will return list of all architectures
    args  = {'release':'CMSSW_6_0_X'}
    res   = get_data(tc_url(), 'py_getReleaseArchitectures', args)
    archs = [r[0] for r in res] \
        + ['osx106_amd64_gcc421', 'osx106_amd64_gcc461', 'osx106_amd64_gcc462']
    return list(set(archs))

def cms_arch(arg=None):
    "Show and set CMSSW architecture"
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
    else:
        cms_archs = cms_architectures()
        if  arg not in cms_archs:
            msg  = 'Wrong architecture, please choose from the following list\n'
            msg += ', '.join(cms_archs)
            raise Exception(msg)
        print "Switch to SCRAM_ARCH=%s" % arg
        os.environ['SCRAM_ARCH'] = arg

def results():
    """Return results from recent query"""
    return RESMGR
