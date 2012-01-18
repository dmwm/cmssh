#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
#pylint: disable-msg=E1101,C0103,R0902

# system modules
import os
import sys
import stat
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
from   cmssh.cms_cmds import dbs_instance, Magic
from   cmssh.cms_cmds import lookup, cms_ls, cms_cp, verbose
from   cmssh.cms_cmds import cms_rm, cms_rmdir, cms_mkdir
from   cmssh.cms_cmds import cmssw_install, releases
from   cmssh.cms_cmds import cmsrel, cmsrun, cms_help
from   cmssh.cms_cmds import cms_help_msg, results

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
    ip.prompt_manager.in_template = \
        '%s|\#> ' % in1

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
    # generic commands, we use Magic class and its execute function
    ('cvs', Magic('cvs').execute),
    ('svn', Magic('svn').execute),
    ('git', Magic('git').execute),
    ('chmod', Magic('chmod').execute),
    ('xrdcp', Magic('xrdcp').execute),
    ('root', Magic('root').execute),
    ('apt-get', Magic('apt-get').execute),
    ('apt-cache', Magic('apt-cache').execute),
    ('crab', Magic('crab').execute),
    ('cmsenv', Magic('eval `scramv1 runtime -sh`').execute),
    ('scram', Magic('scramv1').execute),
    ('gridinit', Magic('grid-proxy-init').execute),
    ('gridinfo', Magic('grid-proxy-info').execute),
    ('vomsinit', Magic('voms-proxy-init').execute),
    ('vomsinfo', Magic('voms-proxy-info').execute),
    ('vim', Magic('vim').execute),
    ('python', Magic('python').execute),
    ('env', Magic('env').execute),
    # specific commands whose execution depends on conditions
    ('find', lookup),
    ('du', lookup),
    ('ls', cms_ls),
    ('rm', cms_rm),
    ('mkdir', cms_mkdir),
    ('rmdir', cms_rmdir),
    ('cp', cms_cp),
    ('verbose', verbose),
    ('install', cmssw_install),
    ('releases', releases),
    ('dbs_instance', dbs_instance),
    ('cmsrel', cmsrel),
    ('cmsRun', cmsrun),
    ('cmsrun', cmsrun),
    ('cmsHelp', cms_help),
]

def test_key_cert():
    """Test user key/cert file and their permissions"""
    kfile = os.path.join(os.environ['HOME'], '.globus/userkey.pem')
    cfile = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
    if  os.path.isfile(kfile):
        mode = os.stat(kfile).st_mode
        cond = bool(mode & stat.S_IRUSR) and not bool(mode & stat.S_IWUSR) \
                and not bool(mode & stat.S_IXUSR) \
                and not bool(mode & stat.S_IRWXO) \
                and not bool(mode & stat.S_IRWXG)
        if  not cond:
            PM.print_red("File %s has wrong permission, try chmod 0400 %s" % (kfile, kfile))
    else:
        PM.print_red("File %s does not exists, grid/cp commands will not work" % kfile)
    if  os.path.isfile(cfile):
        mode = os.stat(cfile).st_mode
        cond = bool(mode & stat.S_IRUSR) and not bool(mode & stat.S_IXUSR) \
                and not bool(mode & stat.S_IRWXO) \
                and not bool(mode & stat.S_IRWXG)
        if  not cond:
            PM.print_red("File %s has wrong permission, try chmod 0600 %s" % (cfile, cfile))
    else:
        PM.print_red("File %s does not exists, grid/cp commands will not work" % cfile)

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
#    ip.displayhook.prompt1.p_template = \
#        '\C_LightBlue[\C_LightCyan%s\C_LightBlue]|\#> ' % prompt
    ip.prompt_manager.in_template = '%s|\#> ' % prompt
    
    # define dbsh banner
    pyver  = sys.version.split('\n')[0]
    ipyver = release.version
    ver    = "%s.%s" % (cmssh.__version__, cmssh.__revision__)
    msg    = "Welcome to cmssh %s!\n[python %s, ipython %s]\n%s\n" \
            % (ver, pyver, ipyver ,os.uname()[3])
    msg   += cms_help_msg()
    print msg

    # check existance and permission of key/cert 
    test_key_cert()

def load_ipython_extension(ipython):
    """Load custom extensions"""
    # The ``ipython`` argument is the currently active
    # :class:`InteractiveShell` instance that can be used in any way.
    # This allows you do to things like register new magics, plugins or
    # aliases.
    main(ipython)
