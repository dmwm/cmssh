#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
#pylint: disable-msg=E1101,C0103,R0902

# system modules
import os
import sys
import traceback
import subprocess
from   types import GeneratorType

# ipython modules
import IPython
from   IPython import release

import cmssh
from   cmssh.iprint import PrintManager, format_dict
from   cmssh.debug import DebugManager
from   cmssh.cmsfs import CMSFS, apply_filter
from   cmssh.cms_cmds import cms_ls, cms_cp

class ShellName(object):
    def __init__(self):
        """Hold information about the shell"""
        self.prompt   = "cms-sh"
        self.name     = 'cmsHelp'
        self.dict     = {}
        self.funcList = []

def unregister():
    """Unregister shell"""
    ID.prompt         = "cms-sh"
    ID.name           = "cms-sh"
    ID.dict[ID.name]  = []
    ID.funcList       = []

def register(prompt, name, funcList=[]):
    """Register shell"""
    set_prompt(prompt)
    ID.prompt = prompt
    ID.name   = name
    funcList.sort()
    ID.dict[name] = funcList
    if  funcList:
        PM.print_blue("Available commands within %s sub-shell:" % prompt)
    if  funcList:
        if  not funcList.count('_exit'):
            funcList.append('_exit')
        for func in funcList:
            PM.print_blue("%s %s" % (" "*10, func))
            if  not ID.funcList.count(func):
                ID.funcList.append(func)
    else:
        ID.funcList = funcList

def set_prompt(in1):
    """Define shell prompt"""
    if  in1 == "cms-sh":
        unregister()
    if  in1.find('|\#>') != -1:
        in1 = in1.replace('|\#>', '').strip()
    ip = get_ipython()
    ip.displayhook.prompt1.p_template = \
        '\C_LightBlue[\C_LightCyan%s\C_LightBlue]|\#> ' % in1

def get_prompt():
    """Get prompt name"""
    IP = __main__.__dict__['__IP'] 
    prompt = getattr(IP.outputcache, 'prompt1') 
    return IP.outputcache.prompt1.p_template

# main magic commands available in cms-sh
def cvs(arg):
    """cvs shell command"""
    subprocess.call("cvs %s" % arg, shell=True)
    
def grid_proxy_init(_arg):
    """grid-proxy-init shell command"""
    subprocess.call("grid-proxy-init")
    
def grid_proxy_info(_arg):
    """grid-proxy-info shell command"""
    subprocess.call("grid-proxy-info")
    
def apt_get(arg):
    """apt-get shell command"""
    subprocess.call("apt-get %s" % arg, shell=True)
    
def apt_cache(arg):
    """apt-cache shell command"""
    subprocess.call("apt-cache %s" % arg, shell=True)

def releases(_arg):
    """releases shell command"""
    cmd  = "apt-cache search CMSSW | grep CMSSW | grep -v -i fwlite"
    cmd += "| awk '{print $1}' | sed 's/cms+cmssw+//g'"
    subprocess.call(cmd, shell=True)

def cmssw_install(arg):
    """CMSSW install shell command"""
    print "Searching for %s" % arg
    subprocess.call('apt-cache search %s | grep -v -i fwlite' % arg, shell=True)
    print "Installing %s" % arg
    subprocess.call('apt-get install cms+cmssw+%s' % arg, shell=True)

def debug(arg):
    """debug shell command"""
    if  arg:
        PM.print_blue("Set debug level to %s" % arg)
        DEBUG.set(arg)
    else:
        PM.print_blue("Debug level is %s" % DEBUG.level)

def lookup(arg):
    """Perform CMSFS lookup for provided query"""
    debug = get_ipython().debug
    args  = arg.split('|')
    if  len(args) == 1: # no filter
        res = CMSMGR.lookup(arg)
    else:
        gen = CMSMGR.lookup(args[0].strip())
        for flt in args[1:]:
            res = apply_filter(flt.strip(), gen)
    if  isinstance(res, list) or isinstance(res, GeneratorType):
        for row in res:
            if  not debug:
                print row
            else:
                print repr(row)
    elif  isinstance(res, set):
        for row in list(res):
            if  not debug:
                print row
            else:
                print repr(row)
    elif isinstance(res, dict):
        print format_dict(res)
    else:
        print res

def verbose(arg):
    """Set/get verbosity level"""
    ip = get_ipython()
    if  arg == '':
        print "verbose", ip.debug
    else:
        if  arg == 0 or arg == '0':
            ip.debug = False
        else:
            ip.debug = True

#
# load managers
#
try:
    CMSMGR   = CMSFS()
    PM       = PrintManager()
    ARCH     = "slc4_ia32_gcc345"
    DEBUG    = DebugManager()
    ID       = ShellName()
except:
    traceback.print_exc()

# list of cms-sh magic functions
cmsMagicList = [ \
    ('debug', debug),
    ('cvs', cvs),
    ('find', lookup),
    ('du', lookup),
    ('ls', cms_ls),
    ('cp', cms_cp),
    ('verbose', verbose),
    ('apt-get', apt_get),
    ('apt-cache', apt_cache),
    ('install', cmssw_install),
    ('releases', releases),
    ('grid-proxy-init', grid_proxy_init),
]

#
# Main function
#
def main(ipython):
    """Define custom extentions"""
    # global IP API
    ip = ipython

    # load cms modules and expose them to the shell
    for m in cmsMagicList:
        magic_name = 'magic_%s' % m[0]
        setattr(ip, magic_name, m[1])

    # Set cmssh prompt
    prompt = 'cms-sh'
    ip.displayhook.prompt1.p_template = \
        '\C_LightBlue[\C_LightCyan%s\C_LightBlue]|\#> ' % prompt
    
    # define dbsh banner
    pyver  = sys.version.split('\n')[0]
    ipyver = release.version
    ver    = "%s.%s" % (cmssh.__version__, cmssh.__revision__)
    msg    = "Welcome to cmssh %s!\n[python %s, ipython %s]\n%s\n" \
            % (ver, pyver, ipyver ,os.uname()[3])
    msg   += '\nAvailable CMS commands:\n'
    msg   += PM.msg_green('find    ') + ' search CMS meta-data (query DBS/Phedex/SiteDB)\n'
    msg   += PM.msg_green('ls      ') + ' list LFNs, e.g. ls /store/user/file.root\n'
    msg   += PM.msg_green('cp      ') + ' copy LFNs, e.g. cp /store/user/file.root .\n'
    msg   += PM.msg_green('releases') + ' list available CMSSW releases\n'
    msg   += PM.msg_green('install ') + ' install CMSSW releases, e.g. install CMSSW_5_0_0\n'
    msg   += '\nAvailable GRID commands:\n'
    msg   += PM.msg_green('grid-proxy-init') + ' setup your proxy\n'
    msg   += PM.msg_green('grid-proxy-info') + ' show your proxy info\n'
    print msg

def load_ipython_extension(ipython):
    """Load custom extensions"""
    # The ``ipython`` argument is the currently active
    # :class:`InteractiveShell` instance that can be used in any way.
    # This allows you do to things like register new magics, plugins or
    # aliases.
    main(ipython)
