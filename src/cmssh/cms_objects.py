#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
#pylint: disable-msg=R0903

"""
CMS objects
"""
from   cmssh.iprint import format_dict

class CMSObj(object):
    """CMS object"""
    def __init__(self, data):
        super(CMSObj, self).__init__()
        self.data = data
    def __repr__(self):
        """CMSObj representation"""
        return format_dict(self.data)
    def __getattr__(self, name):
        """CMSObj attribute"""
        return self.data[name]
    def assign(self, key, val):
        """assign CMSObj attribute"""
        self.data[key] = val
    def __str__(self):
        """String representation"""
        return format_dict(self.data)

class Dataset(CMSObj):
    """DBS3 Dataset object"""
    def __init__(self, data):
        CMSObj.__init__(self, data)
    def __str__(self):
        """Dataset string representation"""
        return self.data['dataset']
        
class Run(CMSObj):
    """docstring for Run"""
    def __init__(self, data):
        CMSObj.__init__(self, data)
    def __str__(self):
        """Run string representation"""
        return str(self.data['Run'])

class File(CMSObj):
    """docstring for File"""
    def __init__(self, data):
        CMSObj.__init__(self, data)
    def __str__(self):
        """File string representation"""
        return self.data['logical_file_name']
        
class Block(CMSObj):
    """docstring for Block"""
    def __init__(self, data):
        CMSObj.__init__(self, data)
    def __str__(self):
        """Block string representation"""
        if  self.data.has_key('name'):
            return self.data['name']
        elif self.data.has_key('block_name'):
            return self.data['block_name']
        else:
            return self.data
        
class Site(CMSObj):
    """docstring for Site"""
    def __init__(self, data):
        CMSObj.__init__(self, data)
    def __str__(self):
        """Site string representation"""
        if  self.data.has_key('name'):
            return self.data['name']
        return self.data['node']

class User(CMSObj):
    """docstring for User"""
    def __init__(self, data):
        CMSObj.__init__(self, data)
    def __str__(self):
        """User string representation"""
        return self.data['username']

class Job(CMSObj):
    """docstring for User"""
    def __init__(self, data):
        CMSObj.__init__(self, data)
    def __str__(self):
        """User string representation"""
        return self.data['name']

