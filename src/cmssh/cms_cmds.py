#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
Set of UNIX commands, e.g. ls, cp, supported in cmssh.
"""

# system modules
import os
import re
import traceback
import subprocess

# cmssh modules
from cmssh.iprint import print_red, print_blue, PrintManager
from cmssh.filemover import copy_lfn, rm_lfn, mkdir, rmdir, list_se
from cmssh.utils import list_results
from cmssh.cmsfs import dataset_info, block_info, file_info, site_info
from cmssh.cmsfs import CMSFS, apply_filter
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

# main magic commands available in cms-sh
def cmd_cvs(arg):
    """cvs shell command"""
    arg = arg.strip()
    subprocess.call("cvs %s" % arg, shell=True)

def cmd_vim(arg):
    """vim shell command"""
    arg = arg.strip()
    subprocess.call("vim %s" % arg, shell=True)

def cmd_python(arg):
    """python shell command"""
    arg = arg.strip()
    subprocess.call("python %s" % arg, shell=True)
    
def grid_proxy_init(_arg):
    """grid-proxy-init shell command"""
    subprocess.call("grid-proxy-init")
    
def grid_proxy_info(_arg):
    """grid-proxy-info shell command"""
    subprocess.call("grid-proxy-info", shell=True)
    
def apt_get(arg):
    """apt-get shell command"""
    arg = arg.strip()
    subprocess.call("apt-get %s" % arg, shell=True)
    
def apt_cache(arg):
    """apt-cache shell command"""
    arg = arg.strip()
    subprocess.call("apt-cache %s" % arg, shell=True)

def releases(_arg):
    """releases shell command"""
    cmd  = "apt-cache search CMSSW | grep CMSSW | grep -v -i fwlite"
    cmd += "| awk '{print $1}' | sed -e 's/cms+cmssw+//g' -e 's/cms+cmssw-patch+//g'"
    subprocess.call(cmd, shell=True)

def cmssw_install(arg):
    """CMSSW install shell command"""
    arg = arg.strip()
    print "Searching for %s" % arg
    subprocess.call('apt-cache search %s | grep -v -i fwlite' % arg, shell=True)
    print "Installing %s" % arg
    if  arg.lower().find('patch') != -1:
        subprocess.call('apt-get install cms+cmssw-patch+%s' % arg, shell=True)
    else:
        subprocess.call('apt-get install cms+cmssw+%s' % arg, shell=True)

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
    cmssw_dir = os.environ.get('CMSSW_RELEASES', os.getcwd())
#    cmsenv = "eval `scramv1 runtime -sh`"
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
#    path = '/usr/lib:%s/%s/cms/cmssw/%s/external/%s/lib:' % (vdir, arch, rel, arch)
#    if  arch.find('osx') != -1:
#        os.environ['DYLD_LIBRARY_PATH'] = path + os.environ['DYLD_LIBRARY_PATH']
#    path = '%s/%s/cms/cmssw/%s/bin/%s:' % (vdir, arch, rel, arch)
#    os.environ['PATH'] = path + os.environ['PATH']
#    if  arch.find('osx') != -1:
#        cmd = "eval `scramv1 runtime -sh`; env | grep ^DYLD_FALLBACK_LIBRARY_PATH="
#    else:
#        cmd = "eval `scramv1 runtime -sh`; env | grep ^LD_LIBRARY_PATH="
#    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
#    key, val = proc.stdout.read().split('=')
#    os.environ[key] = val
    cmd = "eval `scramv1 runtime -sh`; env"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    for line in proc.stdout.read().split('\n'):
        if  line and line.find('=') != -1 and line[0] != '_':
            key, val = line.replace('\n', '').split('=')
            os.environ[key] = val
    path = '/usr/lib:%s/%s/cms/cmssw/%s/external/%s/lib:' % (vdir, arch, rel, arch)
    if  arch.find('osx') != -1:
        os.environ['DYLD_LIBRARY_PATH'] = path + os.environ['DYLD_LIBRARY_PATH']
    print "Setup and switch to %s" % os.getcwd()

def scram(arg):
    """scram CMSSW command"""
    arg = arg.strip()
    subprocess.call("scramv1 %s" % arg, shell=True)

def cmsrun(arg):
    """cmsRun CMSSW command"""
    arg = arg.strip()
    subprocess.call("cmsRun %s" % arg, shell=True)

def cmsenv(arg=None):
    """cmsenv CMSSW command"""
    arg = arg.strip()
    subprocess.call("eval `scramv1 runtime -sh`")

def cms_help_msg():
    """cmsHelp message"""
    msg  = '\nAvailable cmssh commands:\n'
    msg += PM.msg_green('find    ') \
        + ' search CMS meta-data (query DBS/Phedex/SiteDB)\n'
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
    msg += PM.msg_green('root    ') + ' invoke ROOT\n'
    msg += PM.msg_green('du      ') \
        + ' display disk usage for given site, e.g. du T3_US_Cornell\n'
    msg += PM.msg_green('releases') \
        + ' list available CMSSW releases\n'
    msg += PM.msg_green('install ') \
        + ' install CMSSW release, e.g. install CMSSW_5_0_0\n'
    msg += '\nAvailable CMSSW commands (once you install any CMSSW release):\n'
    msg += PM.msg_green('scram   ') + ' CMSSW scram command\n'
    msg += PM.msg_green('cmsrel  ') + ' setup CMSSW release environment\n'
    msg += PM.msg_green('cmsRun  ') \
        + ' cmsRun command for release in question\n'
    msg += '\nAvailable GRID commands:\n'
    msg += PM.msg_green('gpinit  ') + ' setup your proxy (aka grid-proxy-init)\n'
    msg += PM.msg_green('gpinfo  ') + ' show your proxy info (aka grid-proxy-info)\n'
    msg += '\nQuery results are accessible via %s function:\n' % PM.msg_blue('results()')
    msg += '   find dataset=/*Zee*\n'
    msg += '   for r in results(): print r, type(r)\n'
    msg += '\nHelp is accessible via ' + PM.msg_blue('cmsHelp') + ' command'
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
    if  os.path.exists(arg):
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

def cms_root(arg):
    """CMS root command"""
    arg = arg.strip()
    subprocess.call("root -l %s" % arg, shell=True)

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
        verbose = get_ipython().debug
    except:
        verbose = 0
    if  not arg:
        print_red("Usage: cp <options> source_file target_{file,directory}")
    if  os.path.exists(arg):
        prc = subprocess.Popen("cp " + arg, shell=True)
        sts = os.waitpid(prc.pid, 0)[1]
    else:
        try:
            src, dst = arg.split()
            if  dst == '.':
                dst = os.getcwd()
            status = copy_lfn(src, dst, verbose=verbose)
            print_blue("Status %s" % status)
        except:
            traceback.print_exc()
            print_red("Wrong argument '%s'" % arg)

def results():
    """Return RESMGR"""
    return RESMGR
