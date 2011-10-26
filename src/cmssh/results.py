#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
#pylint: disable-msg=E1101,C0103,R0902,R0903
"""
ResultManager holds current data returned by cms-sh
"""

class ResultManager(object):
    """This class holds results of every command used in cms-sh"""
    def __init__(self, debug=0):
        self.debug = debug
        self.data = None
        self.type = None
        
    def assign(self, data):
        """Assign data to Result Manager"""
        self.data = data
        self.type = type(data)
        
    def __xattrs__(self, mode="default"):
        """data attributes"""
        return ("data")

    def __iter__(self):
        """local iterator"""
        return iter(self.data)
