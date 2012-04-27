#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
#pylint: disable-msg=E1101,C0103,R0902,R0903
"""
ResultManager holds current data returned by cms-sh
"""

import types

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

    def __len__(self):
        """len operator"""
        if  isinstance(self.data, types.GeneratorType):
            return len([i for i in self.data])
        elif isinstance(self.data, list):
            return len(self.data)
        else:
             raise TypeError

    def __getitem__(self, idx):
        """getitem operator"""
        if  isinstance(self.data, types.GeneratorType):
            if  not idx:
                return self.data.next()
            for _ in range(0, idx-1):
                self.data.next()
            return self.data.next()
        elif isinstance(self.data, list):
            return self.data.__getitem__(idx)
        else:
             raise TypeError

# create an singleton instance which will be used through the code
RESMGR = ResultManager()
