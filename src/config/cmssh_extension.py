#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
#pylint: disable-msg=E1101,C0103,R0902

# system modules
import os
import sys
import stat
import time
import thread
import traceback
from   types import GeneratorType, ModuleType

# change name space
import __builtin__
builtin_reload = __builtin__.reload
del __builtin__.reload

# ipython modules
import IPython
from   IPython import release

# cmssh modules
import cmssh
from   cmssh.iprint import PrintManager, print_error, print_warning, print_info
from   cmssh.debug import DebugManager
from   cmssh.cms_cmds import dbs_instance, Magic, cms_find, cms_du
from   cmssh.cms_cmds import cms_ls, cms_cp, verbose, cms_dqueue, cmscrab
from   cmssh.cms_cmds import cms_rm, cms_rmdir, cms_mkdir, cms_root, cms_xrdcp
from   cmssh.cms_cmds import cms_install, cms_releases, cms_info, debug_http
from   cmssh.cms_cmds import cmsrel, cmsrun, cms_help, cms_arch, cms_vomsinit
from   cmssh.cms_cmds import cms_help_msg, results, cms_apt, cms_das, cms_das_json
from   cmssh.cms_cmds import github_issues

class ShellName(object):
    def __init__(self):
        """Hold information about the shell"""
        self.prompt   = "cms-sh"
        self.name     = 'cmsHelp'
        self.dict     = {}
        self.funcList = []

def reload_module(arg):
    """
    Reload given python module, i.e. you can modify any python code
    and reload it directly into your current shell.
    Examples:
        Let's say you edit cmssh/utils.py file and add some functionality
        Just invoke the following command and this functionality will be
        added into your current session.

        cmssh> reload_module cmssh.utils
    """
    for key, val in sys.modules.items():
        if  key.find(arg) != -1:
            if  isinstance(val, ModuleType):
                print_info('reload %s' % key)
                builtin_reload(val)

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
        print_info("Available commands within %s sub-shell:" % prompt)
    if  funcList:
        if  not funcList.count('_exit'):
            funcList.append('_exit')
        for func in funcList:
            print_info("%s %s" % (" "*10, func))
            if  not ID.funcList.count(func):
                ID.funcList.append(func)
    else:
        ID.funcList = funcList

def set_prompt(in1):
    """Define shell prompt"""
    ip = get_ipython()
    prompt = '%s|\#> ' % in1
    ip.prompt_manager.width = len(prompt)-1
    ip.prompt_manager.in_template = prompt


#
# load managers
#
try:
    DEBUG    = DebugManager()
    ID       = ShellName()
except:
    traceback.print_exc()

# list of cms-sh magic functions
cmsMagicList = [ \
    ('reload', reload_module),
    # generic commands, we use Magic class and its execute function
    ('cvs', Magic('cvs').execute),
    ('svn', Magic('svn').execute),
    ('ssh', Magic('ssh').subprocess),
    ('kinit', Magic('kinit').subprocess),
    ('klist', Magic('klist').execute),
    ('kdestroy', Magic('kdestroy').execute),
    ('git', Magic('git').execute),
    ('echo', Magic('echo').execute),
    ('grep', Magic('grep').execute),
    ('tail', Magic('tail').execute),
    ('tar', Magic('tar').execute),
    ('zip', Magic('zip').execute),
    ('chmod', Magic('chmod').execute),
    ('vim', Magic('vim').subprocess),
    ('python', Magic('python').execute),
    ('env', Magic('env').execute),
    ('pip', Magic('pip').subprocess),
    # CMS commands
    ('cmsenv', Magic('eval `scramv1 runtime -sh`').execute),
    ('scram', Magic('scramv1').execute),
    ('vomsinit', cms_vomsinit),
    ('vomsinfo', Magic('voms-proxy-info').execute),
    # specific commands whose execution depends on conditions
    ('crab', cmscrab),
    ('das', cms_das),
    ('das_json', cms_das_json),
    ('apt', cms_apt),
    ('xrdcp', cms_xrdcp),
    ('root', cms_root),
    ('find', cms_find),
    ('du', cms_du),
    ('ls', cms_ls),
    ('info', cms_info),
    ('rm', cms_rm),
    ('mkdir', cms_mkdir),
    ('rmdir', cms_rmdir),
    ('cp', cms_cp),
    ('dqueue', cms_dqueue),
    ('verbose', verbose),
    ('debug_http', debug_http),
    ('install', cms_install),
    ('releases', cms_releases),
    ('dbs_instance', dbs_instance),
    ('cmsrel', cmsrel),
    ('cmsRun', cmsrun),
    ('cmsrun', cmsrun),
    ('cmshelp', cms_help),
    ('arch', cms_arch),
    ('tickets', github_issues),
    ('ticket', github_issues),
]
if  os.environ.get('CMSSH_EOS', 0):
    eos = '/afs/cern.ch/project/eos/installation/cms/bin/eos.select'
    cmsMagicList.append(('eos', Magic(eos).execute))

def check_0400(kfile):
    "Check 0400 permission of given file"
    mode = os.stat(kfile).st_mode
    cond = bool(mode & stat.S_IRUSR) and not bool(mode & stat.S_IWUSR) \
            and not bool(mode & stat.S_IXUSR) \
            and not bool(mode & stat.S_IRWXO) \
            and not bool(mode & stat.S_IRWXG)
    return cond

def check_0600(kfile):
    "Check 0600 permission of given file"
    mode = os.stat(kfile).st_mode
    cond = bool(mode & stat.S_IRUSR) and not bool(mode & stat.S_IXUSR) \
            and not bool(mode & stat.S_IRWXO) \
            and not bool(mode & stat.S_IRWXG)
    return cond

def test_key_cert():
    """Test user key/cert file and their permissions"""
    kfile = os.path.join(os.environ['HOME'], '.globus/userkey.pem')
    cfile = os.path.join(os.environ['HOME'], '.globus/usercert.pem')
    if  os.path.isfile(kfile):
        if  not (check_0600(kfile) or check_0400(kfile)):
            msg = "File %s has weak permission settings, try" % kfile
            print_warning(msg)
            print "chmod 0400 %s" % kfile
    else:
        print_error("File %s does not exists, grid/cp commands will not work" % kfile)
    if  os.path.isfile(cfile):
        if  not (check_0600(cfile) or check_0400(cfile)):
            msg = "File %s has weak permission settings, try" % cfile
            print_warning(msg)
            print "chmod 0600 %s" % cfile
    else:
        msg = "File %s does not exists, grid/cp commands will not work" % cfile
        print_error(msg)

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
        if  hasattr(ip, 'register_magic_function'): # ipython 0.13 and above
            magic_kind = 'line'
            func = m[1]
            name = m[0]
            ip.register_magic_function(func, magic_kind, name)
        else: # ipython 0.12 and below
            setattr(ip, magic_name, m[1])

    # import required modules for the shell
    ip.ex("from cmssh.cms_cmds import results, cms_vomsinit")
    ip.ex("from cmssh.auth_utils import PEMMGR, read_pem")
    ip.ex("read_pem()")
    ip.ex("cms_vomsinit()")

    # Set cmssh prompt
    prompt = 'cms-sh'
    ip.prompt_manager.in_template = '%s|\#> ' % prompt
    print cms_help_msg()
    
    # check existance and permission of key/cert 
    test_key_cert()

def load_ipython_extension(ipython):
    """Load custom extensions"""
    # The ``ipython`` argument is the currently active
    # :class:`InteractiveShell` instance that can be used in any way.
    # This allows you do to things like register new magics, plugins or
    # aliases.
    main(ipython)
