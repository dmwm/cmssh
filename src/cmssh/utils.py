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

def size_format(i):
    """
    Format file size utility, it converts file size into KB, MB, GB, TB, PB units
    """
    try:
        num = long(i)
    except:
        traceback.print_exc()
        return "N/A"
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

