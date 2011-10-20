#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
#pylint: disable-msg=E1101,C0103,R0902,R0903
#Author:  Valentin Kuznetsov, 2008
"""
ResultManager holds current data returned by cms-sh
"""

try:
    from IPython.Extensions import ipipe
except ImportError:
    pass

class ResultManager(object):
    """
       This class holds results of every command used in cms-sh
    """
    def __init__(self, debug=0):
        self.debug = debug
        self.data = None
        self.type = None
        
    def set(self, data):
        """
           set data
        """
        self.data = data
        self.type = type(data)
        
    def __xattrs__(self, mode="default"):
        """
           attrbutes for data
        """
        return ("data")

    def __iter__(self):
        """
           local iterator data
        """
        return iter(self.data)
