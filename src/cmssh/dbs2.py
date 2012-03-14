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
import time
import urllib
import urllib2

import re
import xml.etree.cElementTree as ET

# cmssh modules
from   cmssh.url_utils import get_data
from   cmssh.cms_objects import File, Block, Dataset
from   cmssh.filemover import get_pfns, resolve_user_srm_path

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

def list_datasets(kwargs):
    """Find sites"""
    dataset = kwargs.pop('dataset')
#    query  = 'find dataset, dataset.createdate, dataset.createby, dataset.moddate, dataset.modby, datatype, dataset.status where dataset=%s' % dataset
    query  = 'find dataset where dataset=%s' % dataset
    if  kwargs.has_key('status'):
        kwargs['dataset.status'] = kwargs['status']
        del kwargs['status']
    else:
        kwargs['dataset.status'] = 'VALID'
    cond   = ''
    for key, val in kwargs.items():
        cond += ' and %s=%s' % (key, val)
    query += cond
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
    query  = 'find dataset.name, datatype, dataset.status, dataset.createdate, dataset.createby, dataset.moddate, dataset.modby, sum(block.size), count(block), sum(block.numfiles), sum(block.numevents) where dataset=%s' % dataset
    params = {"api":"executeQuery", "apiversion": "DBS_2_0_9", "query":query}
    data   = urllib2.urlopen(URL, urllib.urlencode(params))
    rec    = [d for d in qlxml_parser(data, 'dataset')][0]
    rec['size'] = rec['dataset']['sum_block.size']
    rec['nblocks'] = rec['dataset']['count_block']
    rec['nfiles'] = rec['dataset']['sum_block.numfiles']
    rec['nevents'] = rec['dataset']['sum_block.numevents']
    rec['created'] = time.strftime("%Y-%m-%d %H:%M:%S GMT", time.gmtime(rec['dataset']['dataset.createdate']))
    rec['createdby'] = rec['dataset']['dataset.createby']
    rec['modified'] = time.strftime("%Y-%m-%d %H:%M:%S GMT", time.gmtime(rec['dataset']['dataset.moddate']))
    rec['modifiedby'] = rec['dataset']['dataset.modby']
    rec['status'] = rec['dataset']['dataset.status']
    rec['datatype'] = rec['dataset']['datatype']
    rec['dataset'] = rec['dataset']['dataset.name']
    return Dataset(rec)

def block_info(block):
    query  = 'find block.name, block.sizei, block.createdate, block.createby, block.moddate, block.modby where block=%s' % block
    params = {"api":"executeQuery", "apiversion": "DBS_2_0_9", "query":query}
    data   = urllib2.urlopen(URL, urllib.urlencode(params))
    blk    = [b for b in qlxml_parser(data, 'block')][0]
    blk['block_name'] = blk['block']['block.name']
    blk['size'] = blk['block']['block.size']
    blk['created'] = time.strftime("%Y-%m-%d %H:%M:%S GMT", time.gmtime(blk['block']['block.createdate']))
    blk['createdby'] = blk['block']['block.createby']
    blk['modified'] = time.strftime("%Y-%m-%d %H:%M:%S GMT", time.gmtime(blk['block']['block.moddate']))
    blk['modifiedby'] = blk['block']['block.modby']
    del blk['block']
    return Block(blk)

def file_info(lfn, verbose=None):
    query  = 'find file.name, file.size, file.createdate, file.createby, file.moddate, file.modby where file=%s' % lfn
    params = {"api":"executeQuery", "apiversion": "DBS_2_0_9", "query":query}
    data   = urllib2.urlopen(URL, urllib.urlencode(params))
    rec    = [f for f in qlxml_parser(data, 'file')][0]
    rec['logical_file_name'] = rec['file']['file.name']
    rec['size'] = rec['file']['file.size']
    rec['created'] = time.strftime("%Y-%m-%d %H:%M:%S GMT", time.gmtime(rec['file']['file.createdate']))
    rec['createdby'] = rec['file']['file.createby']
    rec['modified'] = time.strftime("%Y-%m-%d %H:%M:%S GMT", time.gmtime(rec['file']['file.moddate']))
    rec['modifiedby'] = rec['file']['file.modby']
    del rec['file']
    lfnobj = File(rec)
    try:
        pfnlist, selist = get_pfns(lfn, verbose)
        lfnobj.assign('pfn', pfnlist)
        lfnobj.assign('se', selist)
    except:
        lfnobj.assign('pfn', [])
        lfnobj.assign('se', [])
    return lfnobj

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


