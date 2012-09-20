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
import traceback

import re

# cmssh modules
from   cmssh.url_utils import get_data
from   cmssh.utils import qlxml_parser
from   cmssh.cms_objects import File, Block, Dataset
from   cmssh.filemover import get_pfns, resolve_user_srm_path, lfn2pfn
from   cmssh.cms_urls import dbs_url, dbs_instances
from   cmssh.iprint import print_error, print_warning
from   cmssh.regex import pat_dataset, pat_block, pat_lfn, pat_run

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
    data   = urllib2.urlopen(dbs_url(), urllib.urlencode(params))
    gen    = qlxml_parser(data, 'dataset')
    plist  = [Dataset(d['dataset']) for d in gen]
    return plist

def list_files(dataset, run=None):
    query  = 'find file where dataset=%s' % dataset
    if  run:
        query += ' and run=%s' % run
    params = {"api":"executeQuery", "apiversion": "DBS_2_0_9", "query":query}
    data   = urllib2.urlopen(dbs_url(), urllib.urlencode(params))
    gen    = qlxml_parser(data, 'file')
    files  = []
    for rec in gen:
        rec['logical_file_name'] = rec['file']['file']
        del rec['file']
        files.append(rec)
    plist  = [File(f) for f in files]
    return plist

def dataset_info(dataset, verbose=None):
    query  = 'find dataset.name, datatype, dataset.status, dataset.createdate, dataset.createby, dataset.moddate, dataset.modby, sum(block.size), count(block), sum(block.numfiles), sum(block.numevents) where dataset=%s' % dataset
    params = {"api":"executeQuery", "apiversion": "DBS_2_0_9", "query":query}
    data   = urllib2.urlopen(dbs_url(), urllib.urlencode(params))
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

def block_info(block, verbose=None):
    query  = 'find block.name, block.sizei, block.createdate, block.createby, block.moddate, block.modby where block=%s' % block
    params = {"api":"executeQuery", "apiversion": "DBS_2_0_9", "query":query}
    data   = urllib2.urlopen(dbs_url(), urllib.urlencode(params))
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
    query  = 'find file.name, file.numevents, file.size, file.createdate, file.createby, file.moddate, file.modby where file=%s' % lfn
    params = {"api":"executeQuery", "apiversion": "DBS_2_0_9", "query":query}
    default_instance = os.environ.get('DBS_INSTANCE')
    for inst in dbs_instances():
        os.environ['DBS_INSTANCE'] = inst
        data   = urllib2.urlopen(dbs_url(), urllib.urlencode(params))
        try:
            rec = [f for f in qlxml_parser(data, 'file')][0]
        except:
            continue
        rec['logical_file_name'] = rec['file']['file.name']
        rec['size'] = rec['file']['file.size']
        rec['nevents'] = rec['file']['file.numevents']
        rec['created'] = time.strftime("%Y-%m-%d %H:%M:%S GMT", time.gmtime(rec['file']['file.createdate']))
        rec['createdby'] = rec['file']['file.createby']
        rec['modified'] = time.strftime("%Y-%m-%d %H:%M:%S GMT", time.gmtime(rec['file']['file.moddate']))
        rec['modifiedby'] = rec['file']['file.modby']
        del rec['file']
        lfnobj = File(rec)
        try:
            pfnlist, selist = get_pfns(lfn, verbose)
            if  not selist:
                query = 'find site where file=%s' % lfn
                params.update({"query":query})
                data  = urllib2.urlopen(dbs_url(), urllib.urlencode(params))
                try:
                    rec = [f for f in qlxml_parser(data, 'site')][0]
                    sename = rec['site']['site']
                    selist = [sename]
                    pfnlist = lfn2pfn(lfn, sename)
                except:
                    pass
            lfnobj.assign('pfn', pfnlist)
            lfnobj.assign('se', selist)
        except:
            traceback.print_exc()
            lfnobj.assign('pfn', [])
            lfnobj.assign('se', [])
        os.environ['DBS_INSTANCE'] = default_instance
        lfnobj.assign('dbs_instance', inst)
        return lfnobj
    os.environ['DBS_INSTANCE'] = default_instance
    msg = 'Fail to look-up LFN in %s DBS instances' % dbs_instances()
    print_error(msg)

def run_lumi(arg, verbose=None):
    if pat_block.match(arg):
        query  = 'find run,lumi where block=%s' % arg
    elif  pat_lfn.match(arg):
        query  = 'find run,lumi where file=%s' % arg
    elif  pat_dataset.match(arg):
        query  = 'find run,lumi where dataset=%s' % arg
    elif  pat_run.match(arg):
        query  = 'find run,lumi where run=%s' % arg
    params = {"api":"executeQuery", "apiversion": "DBS_2_0_9", "query":query}
    data   = urllib2.urlopen(dbs_url(), urllib.urlencode(params))
    run_lumi = {}
    for row in qlxml_parser(data, 'run'):
        rec = row['run']
        run = rec['run']
        lumi = rec['lumi']
        if  run_lumi.has_key(run):
            run_lumi[run].append(lumi)
        else:
            run_lumi[run] = [lumi]
    for key, val in run_lumi.items():
        val.sort()
        run_lumi[key] = val
    return run_lumi

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


