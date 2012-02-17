#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
Common utilities
"""
import os
import re
import sys
import time
import types
import readline
import traceback
import subprocess
from   types import GeneratorType

from   cmssh.iprint import format_dict

def print_progress(progress, msg='Download in progress:'):
    "Print on stdout progress message"
    if  progress == 'N/A':
        sys.stdout.write("%s   \r" % msg )
    else:
        sys.stdout.write("%s %d%%   \r" % (msg, progress) )
    sys.stdout.flush()

def size_format(i):
    """
    Format file size utility, it converts file size into KB, MB, GB, TB, PB units
    """
    try:
        num = long(i)
    except:
#        traceback.print_exc()
        return None
    for x in ['','KB','MB','GB','TB','PB']:
        if num < 1024.:
            return "%3.1f%s" % (num, x)
        num /= 1024.

def whoami():
    # the way to get function name, see http://code.activestate.com/recipes/66062/
    return sys._getframe(1).f_code.co_name

def swap_dict(original_dict):
    """Swap key/value in dict"""
    return dict([(v, k) for (k, v) in original_dict.iteritems()])

class Completer:
    def __init__(self, words):
        self.words = words
        self.prefix = None
    def complete(self, prefix, index):
        if prefix != self.prefix:
            # we have a new prefix!
            # find all words that start with this prefix
            self.matching_words = [
                w for w in self.words if w.startswith(prefix)
                ]
            self.prefix = prefix
        try:
            return self.matching_words[index]
        except IndexError:
            return None

def list_results(res, debug):
    """List results"""
    if  not res:
        return
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
        if  not debug:
            print res
        else:
            print repr(res)

def execmd(cmd):
    """Execute given command in subprocess"""
    pipe = subprocess.Popen(cmd, shell=True, 
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    (child_stdout, child_stderr) = (pipe.stdout, pipe.stderr)
    stdout = child_stdout.read()
    stderr = child_stderr.read()
    return stdout, stderr

