#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
File: ttt.py
Author: Valentin Kuznetsov <vkuznet@gmail.com>
Description: 
"""

# system modules
import os
import sys
import urllib
import urllib2

import re
import xml.etree.cElementTree as ET

# cmssh modules
from   cmssh.url_utils import get_data
from   cmssh.cms_objects import File, Block, Dataset

URL = 'http://cmsdbsprod.cern.ch/cms_dbs_prod_global/servlet/DBSServlet'

def adjust_value(value):
    """
    Change null value to None.
    """
    pat_float   = re.compile(r'(^[-]?\d+\.\d*$|^\d*\.{1,1}\d+$)')
    pat_integer = re.compile(r'(^[0-9-]$|^[0-9-][0-9]*$)')
    if  isinstance(value, str):
        if  value == 'null' or value == '(null)':
            return None
        elif pat_float.match(value):
            return float(value)
        elif pat_integer.match(value):
            return int(value)
        else:
            return value
    else:
        return value

def dict_helper(idict, notations):
    """
    Create new dict for provided notations/dict. Perform implicit conversion
    of data types, e.g. if we got '123', convert it to integer. The conversion
    is done based on adjust_value function.
    """
    child_dict = {}
    for kkk, vvv in idict.iteritems():
        child_dict[notations.get(kkk, kkk)] = adjust_value(vvv)
    return child_dict

def get_children(elem, event, row, key, notations):
    """
    xml_parser helper function. It gets recursively information about
    children for given element tag. Information is stored into provided
    row for given key. The change of notations can be applied during
    parsing step by using provided notations dictionary.
    """
    for child in elem.getchildren():
        child_key  = child.tag
        child_data = child.attrib
        if  not child_data:
            child_dict = adjust_value(child.text)
        else:
            child_dict = dict_helper(child_data, notations)

        if  isinstance(row[key], dict) and row[key].has_key(child_key):
            val = row[key][child_key]
            if  isinstance(val, list):
                val.append(child_dict)
                row[key][child_key] = val
            else:
                row[key][child_key] = [val] + [child_dict]
        else:
            if  child.getchildren(): # we got grand-children
                if  child_dict:
                    row[key][child_key] = child_dict
                else:
                    row[key][child_key] = {}
                if  isinstance(child_dict, dict):
                    newdict = {child_key: child_dict}
                else:
                    newdict = {child_key: {}}
                get_children(child, event, newdict, child_key, notations) 
                row[key][child_key] = newdict[child_key]
            else:
                if  not isinstance(row[key], dict):
                    row[key] = {}
                row[key][child_key] = child_dict
        if  event == 'end':
            child.clear()

def qlxml_parser(source, prim_key):
    "DBS2 QL XML parser"
    notations = {}
    context   = ET.iterparse(source, events=("start", "end"))

    root = None
    row = {}
    row[prim_key] = {}
    for item in context:
        event, elem = item
        key = elem.tag
        if key != 'row':
            continue
        if event == 'start' :
            root = elem
        if  event == 'end':
            row = {}
            row[prim_key] = {}
            get_children(elem, event, row, prim_key, notations)
            elem.clear()
            yield row
    if  root:
        root.clear()
    source.close()

def list_datasets(pattern):
    """Find sites"""
    query  = 'find dataset where dataset=%s' % pattern
    params = {"api":"executeQuery", "apiversion": "DBS_2_0_9", "query":query}
    data   = urllib2.urlopen(URL, urllib.urlencode(params))
    gen    = qlxml_parser(data, 'dataset')
    plist  = [Dataset(d['dataset']) for d in gen]
    return plist

def list_files(dataset, run=None):
    query  = 'find file where dataset=%s' % dataset
    if  run:
        query += ' and run=%s' % run
    params = {"api":"executeQuery", "apiversion": "DBS_2_0_9", "query":query}
    data   = urllib2.urlopen(URL, urllib.urlencode(params))
    gen    = qlxml_parser(data, 'file')
    files  = []
    for rec in gen:
        rec['logical_file_name'] = rec['file']['file']
        del rec['file']
        files.append(rec)
    plist  = [File(f) for f in files]
    return plist

def dataset_info(dataset):
    query  = 'find dataset.name, sum(block.size), count(block), sum(block.numfiles), sum(block.numevents), dataset.createdate where dataset=%s' % dataset
    params = {"api":"executeQuery", "apiversion": "DBS_2_0_9", "query":query}
    data   = urllib2.urlopen(URL, urllib.urlencode(params))
    rec    = [d for d in qlxml_parser(data, 'dataset')][0]
    rec['size'] = rec['dataset']['sum_block.size']
    rec['nblocks'] = rec['dataset']['count_block']
    rec['nfiles'] = rec['dataset']['sum_block.numfiles']
    rec['nevents'] = rec['dataset']['sum_block.numevents']
    rec['dataset'] = rec['dataset']['dataset.name']
    return Dataset(rec)

def block_info(block):
    query  = 'find block.name, block.size where block=%s' % block
    params = {"api":"executeQuery", "apiversion": "DBS_2_0_9", "query":query}
    data   = urllib2.urlopen(URL, urllib.urlencode(params))
    blk    = [b for b in qlxml_parser(data, 'block')][0]
    blk['block_name'] = blk['block']['block.name']
    blk['size'] = blk['block']['block.size']
    del blk['block']
    return Block(blk)

def file_info(lfn):
    query  = 'find file.name, file.size where file=%s' % lfn
    params = {"api":"executeQuery", "apiversion": "DBS_2_0_9", "query":query}
    data   = urllib2.urlopen(URL, urllib.urlencode(params))
    lfn    = [f for f in qlxml_parser(data, 'file')][0]
    lfn['logical_file_name'] = lfn['file']['file.name']
    lfn['size'] = lfn['file']['file.size']
    del lfn['file']
    return File(lfn)

def main():
    "Main function"
#    res = list_datasets("*Zee*")
    res = list_files("/Cosmics/CRUZET3-v1/RAW")
#    res = dataset_info("/EG/Run2010A-Dec4ReReco_v1/AOD")
#    res = block_info("/EG/Run2010A-Dec4ReReco_v1/AOD#f15ed71e-6491-4f73-a0e3-ac4248a6367d")
#    res = file_info('/store/relval/2008/3/28/RelVal-RelValFastSimZEE-1206666978/0000/4A6711A7-6FFC-DC11-B87F-001617C3B782.root')
    print "res", repr(res)

if __name__ == '__main__':
    main()


