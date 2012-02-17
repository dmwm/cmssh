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
from cmssh.filemover import copy_lfn, rm_lfn, mkdir, rmdir, list_se, dqueue
from cmssh.utils import list_results
from cmssh.cmsfs import dataset_info, block_info, file_info, site_info
from cmssh.cmsfs import CMSFS, apply_filter, validate_dbs_instance
from cmssh.cms_urls import dbs_url
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
    if  args.find("|") != -1:
        cmd_opts = '%s %s' % (cmd, args.strip())
        subprocess.call(cmd_opts, shell=True)
    else:
        cmd_opts = [cmd] + args.strip().split()
        subprocess.call(cmd_opts)
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

def releases(_arg):
    """releases shell command"""
    print "\nAvailable CMS releases:"
    cmd  = "apt-cache search CMSSW | grep CMSSW | grep -v -i fwlite"
    cmd += "| awk '{print $1}' | sed -e 's/cms+cmssw+//g' -e 's/cms+cmssw-patch+//g'"
    subprocess.call(cmd, shell=True)
    print "\nInstalled releases:"
    rdir = os.path.join(os.environ['CMSSH_ROOT'], 'Releases')
    if  os.path.isdir(rdir):
        for rel in os.listdir(rdir):
            print rel

def cmssw_install(arg):
    """CMSSW install shell command"""
    arg = arg.strip()
    print "Searching for %s" % arg
    subprocess.call('apt-cache search %s | grep -v -i fwlite' % arg, shell=True)
    if  arg.lower().find('patch') != -1:
        print "Installing cms+cmssw-patch+%s" % arg
        execute('apt-get', 'install cms+cmssw-patch+%s' % arg)
    else:
        print "Installing cms+cmssw+%s" % arg
        execute('apt-get', 'install cms+cmssw+%s' % arg)

def cms_root(arg):
    "Run ROOT command"
    dyld_path = os.environ.get('DYLD_LIBRARY_PATH', None)
    root_path = os.environ['DEFAULT_ROOT']
    if  dyld_path:
        os.environ['DYLD_LIBRARY_PATH'] = os.path.join(root_path, 'lib')
    cmd_opts = '%s/root -l %s' % (os.path.join(root_path, 'bin'), arg.strip())
    subprocess.call(cmd_opts, shell=True)
    if  dyld_path:
        os.environ['DYLD_LIBRARY_PATH'] = dyld_path

def cms_xrdcp(arg):
    "Run ROOT command"
    dyld_path = os.environ.get('DYLD_LIBRARY_PATH', None)
    root_path = os.environ['DEFAULT_ROOT']
    if  dyld_path:
        os.environ['DYLD_LIBRARY_PATH'] = os.path.join(root_path, 'lib')
    cmd_opts = '%s/xrdcp %s' % (os.path.join(root_path, 'bin'), arg.strip())
    subprocess.call(cmd_opts, shell=True)
    if  dyld_path:
        os.environ['DYLD_LIBRARY_PATH'] = dyld_path

def debug(arg):
    """debug shell command"""
    arg = arg.strip()
    if  arg:
        PM.print_blue("Set debug level to %s" % arg)
        DEBUG.set(arg)
    else:
        PM.print_blue("Debug level is %s" % DEBUG.level)

def lookup(arg):
    """Perform CMSFS lookup for provided query"""
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
    """Set/get verbosity level"""
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
def cmsrel(rel):
    """switch to given CMSSW release"""
    rel = rel.strip()
    if  not rel:
        print_red('Please specify release name')
        print "\nInstalled releases:"
        dirs = os.listdir(os.path.join(os.environ['CMSSH_ROOT'], 'Releases'))
        for rel in dirs:
            print rel
        return
    # check if given release name is installed on user system
    rel_dir = '%s/cms/cmssw/%s' % (os.environ['SCRAM_ARCH'], rel)
    if  not os.path.isdir(os.path.join(os.environ['VO_CMS_SW_DIR'], rel_dir)):
        msg  = msg_red('Release %s is not yet installed on your system.\n' % rel)
        msg += 'Use ' + msg_green('releases') + ' command to list available releases.\n'
        msg += 'Use ' + msg_green('install %s' % rel) + ' command to install given release.'
        print msg
        return
    cmssw_dir = os.environ.get('CMSSW_RELEASES', os.getcwd())
    if  not os.path.isdir(cmssw_dir):
        os.makedirs(cmssw_dir)
    if  os.path.isdir(os.path.join(cmssw_dir, rel + '/src')):
        os.chdir(os.path.join(cmssw_dir, rel + '/src'))
    else:
        os.chdir(cmssw_dir)
        subprocess.call("scramv1 project CMSSW %s" % rel, shell=True)
        os.chdir(os.path.join(rel, 'src'))
    vdir = os.environ['VO_CMS_SW_DIR']
    arch = os.environ['SCRAM_ARCH']
    cmd = "eval `scramv1 runtime -sh`; env"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    for line in proc.stdout.read().split('\n'):
        if  line and line.find('=') != -1 and line[0] != '_':
            key, val = line.replace('\n', '').split('=')
            os.environ[key] = val
    path = '%s/%s/cms/cmssw/%s/external/%s/lib:' % (vdir, arch, rel, arch)
    if  arch.find('osx') != -1:
        os.environ['DYLD_LIBRARY_PATH'] = path + os.environ['DYLD_LIBRARY_PATH']
    print "%s is ready, cwd: %s" % (rel, os.getcwd())

def cmsrun(arg):
    """cmsRun CMSSW command"""
    vdir = os.environ.get('VO_CMS_SW_DIR', None)
    arch = os.environ.get('SCRAM_ARCH', None)
    base = os.environ.get('CMSSW_RELEASE_BASE', None)
    if  not vdir or not arch or not base:
        msg  = PM.msg_red('Unable to identify CMSSW environment, please run first: ')
        msg += PM.msg_blue('cmsrel <rel>\n')
        releases = os.listdir(os.environ['CMSSW_RELEASES'])
        msg += '\nInstalled releases: ' + PM.msg_green(', '.join(releases))
        print msg
        return
    execute("cmsRun", arg)

def dbs_instance(arg=None):
    """set dbs instance"""
    arg = arg.strip()
    if  arg:
        if  validate_dbs_instance(arg):
            os.environ['DBS_INSTANCE'] = arg
            print "Switch to %s DBS instance" % arg
        else:
            print "Invalid DBS instance"
    else:
        msg  = "DBS3 instance is set to: %s" \
                % os.environ.get('DBS_INSTANCE', 'global')
        print msg

def cms_help_msg():
    """cmsHelp message"""
    msg  = '\nAvailable cmssh commands:\n'
    msg += PM.msg_green('find    ') \
        + ' search CMS meta-data (query DBS/Phedex/SiteDB)\n'
    msg += PM.msg_green('dbs_instance') \
        + ' show/set DBS instance, default is global\n'
    msg += PM.msg_green('mkdir   ') \
        + ' mkdir command, e.g. mkdir /path/foo or mkdir T3_US_Cornell:/store/user/foo\n'
    msg += PM.msg_green('rmdir   ') \
        + ' rmdir command, e.g. rmdir /path/foo or rmdir T3_US_Cornell:/store/user/foo\n'
    msg += PM.msg_green('ls      ') \
        + ' list file/LFN, e.g. ls local.file or ls /store/user/file.root\n'
    msg += PM.msg_green('rm      ') \
        + ' remove file/LFN, e.g. rm local.file or rm T3_US_Cornell:/store/user/file.root\n'
    msg += PM.msg_green('cp      ') \
        + ' copy file/LFN, e.g. cp local.file or cp /store/user/file.root .\n'
    msg += PM.msg_green('dqueue  ') \
        + ' status of download queue, list files which are in progress.\n'
    msg += PM.msg_green('root    ') + ' invoke ROOT\n'
    msg += PM.msg_green('du      ') \
        + ' display disk usage for given site, e.g. du T3_US_Cornell\n'
    msg += '\nAvailable CMSSW commands (once you install any CMSSW release):\n'
    msg += PM.msg_green('releases') \
        + ' list available CMSSW releases\n'
    msg += PM.msg_green('install ') \
        + ' install CMSSW release, e.g. install CMSSW_5_0_0\n'
    msg += PM.msg_green('scram   ') + ' CMSSW scram command\n'
    msg += PM.msg_green('cmsrel  ') + ' switch to given CMSSW release and setup its environment\n'
    msg += PM.msg_green('cmsRun  ') \
        + ' cmsRun command for release in question\n'
    msg += '\nAvailable GRID commands:\n'
    msg += PM.msg_green('gridinit') + ' setup your proxy (aka grid-proxy-init)\n'
    msg += PM.msg_green('gridinfo') + ' show your proxy info (aka grid-proxy-info)\n'
    msg += PM.msg_green('vomsinit') + ' setup your VOMS proxy (aka voms-proxy-init)\n'
    msg += PM.msg_green('vomsinfo') + ' show your VOMS proxy info (aka voms-proxy-info)\n'
    msg += '\nQuery results are accessible via %s function:\n' % PM.msg_blue('results()')
    msg += '   find dataset=/*Zee*\n'
    msg += '   for r in results(): print r, type(r)\n'
    msg += '\nHelp is accessible via ' + PM.msg_blue('cmshelp') + ' command'
    return msg

def cms_help(arg=None):
    """cmsHelp command"""
    print cms_help_msg()

def cms_rm(arg):
    """CMS rm command"""
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
    """CMS rmdir command"""
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
    """CMS mkdir command"""
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
    """CMS ls command"""
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
        pat_site = re.compile('^T[0-9]_[A-Z]+(_)[A-Z]+')
        pat_dataset = re.compile('^/.*/.*/.*')
        pat_block = re.compile('^/.*/.*/.*#.*')
        pat_lfn = re.compile('^/.*\.root$')
        pat_se = re.compile('^T[0-3]_.*:/.*')
        if  pat_se.match(arg):
            res = list_se(arg, verbose)
        elif  pat_site.match(arg):
            res = site_info(arg, verbose)
        elif pat_lfn.match(arg):
            res = file_info(arg, verbose)
        elif pat_block.match(arg):
            res = block_info(arg, verbose)
        elif pat_dataset.match(arg):
            res = dataset_info(arg, verbose)
        else:
            raise Exception('Unsupported input')
        RESMGR.assign(res)
        list_results(res, debug=True)

def cms_cp(arg):
    """CMS cp command"""
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

def download_queue(arg=None):
    "status of download queue"
    dqueue()

def results():
    """Return RESMGR"""
    return RESMGR
