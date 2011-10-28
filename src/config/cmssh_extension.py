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

# cmssh modules
import cmssh
from   cmssh.iprint import PrintManager
from   cmssh.debug import DebugManager
from   cmssh.cms_cmds import cvs, lookup, cms_ls, cms_cp, verbose
from   cmssh.cms_cmds import cms_rm, cms_rmdir, cms_mkdir, cms_root
from   cmssh.cms_cmds import apt_get, apt_cache, cmssw_install, releases
from   cmssh.cms_cmds import cmsrel, cmsrun, cmsenv, scram, cms_help
from   cmssh.cms_cmds import cms_help_msg, results
from   cmssh.cms_cmds import grid_proxy_init, grid_proxy_info

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

#
# load managers
#
try:
    PM       = PrintManager()
    DEBUG    = DebugManager()
    ID       = ShellName()
except:
    traceback.print_exc()

# list of cms-sh magic functions
cmsMagicList = [ \
    ('cvs', cvs),
    ('find', lookup),
    ('du', lookup),
    ('ls', cms_ls),
    ('rm', cms_rm),
    ('mkdir', cms_mkdir),
    ('rmdir', cms_rmdir),
    ('cp', cms_cp),
    ('root', cms_root),
    ('verbose', verbose),
    ('apt-get', apt_get),
    ('apt-cache', apt_cache),
    ('install', cmssw_install),
    ('releases', releases),
    ('cmsrel', cmsrel),
    ('cmsRun', cmsrun),
    ('cmsrun', cmsrun),
    ('cmsenv', cmsenv),
    ('scram', scram),
    ('cmsHelp', cms_help),
    ('grid-proxy-init', grid_proxy_init),
    ('grid-proxy-info', grid_proxy_info),
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

    # import required modules for the shell
    ip.ex("from cmssh.cms_cmds import results")

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
    msg   += cms_help_msg()
    print msg

def load_ipython_extension(ipython):
    """Load custom extensions"""
    # The ``ipython`` argument is the currently active
    # :class:`InteractiveShell` instance that can be used in any way.
    # This allows you do to things like register new magics, plugins or
    # aliases.
    main(ipython)
