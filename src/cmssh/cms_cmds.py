"""
Set of UNIX commands, e.g. ls, cp, supported in cmssh.
All commands have prefix cms_
"""

import os
import traceback
from subprocess import Popen
from cmssh.utils import size_format
from cmssh.iprint import print_red, print_blue
from cmssh.filemover import list_lfn, copy_lfn

def options(arg):
    """Extract options from given arg string"""
    alist = arg.split()
    opts = []
    for par in arg.split():
        if  len(par) > 0 and par[0] == '-':
            opts.append(par)
    return opts

def cms_ls(arg):
    """
    CMS ls command
    """
    try:
        verbose = get_ipython().debug
    except:
        verbose = 0
    if  not arg:
        arg = '.'
    opts = options(arg)
    if  opts:
        arg = arg.strip().replace(''.join(opts), '').strip()
    if  os.path.exists(arg):
        prc = Popen("ls" + " " + ''.join(opts) + " " + arg, shell=True)
        sts = os.waitpid(prc.pid, 0)[1]
    else:
        size = list_lfn(arg, verbose=verbose)
        msg = "File size=%s (%s bytes)" % (size_format(size), size)
        print_blue(msg)

def cms_cp(arg):
    """
    CMS cp command
    """
    try:
        verbose = get_ipython().debug
    except:
        verbose = 0
    if  not arg:
        print_red("Usage: cp <options> source_file target_{file,directory}")
    if  os.path.exists(arg):
        prc = Popen("cp " + arg, shell=True)
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
