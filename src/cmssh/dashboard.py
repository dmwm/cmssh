#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
CMS dashboard plugin
"""
__author__ = "Valentin Kuznetsov"

# system modules
import os
import json
import urllib
import urllib2

# cmssh modules
from cmssh.cms_objects import Job

def jobsummary(idict):
    "Retrieve information from CMS dashboard"
    url = "http://dashb-cms-job.cern.ch/dashboard/request.py/jobsummary-plot-or-table2"
    params = {
        "user": "",
        "site": "",
        "ce": "",
        "submissiontool": "",
        "dataset": "",
        "application": "",
        "rb": "",
        "activity": "",
        "grid": "",
        "date1": "",
        "date2": "",
        "jobtype": "",
        "tier": "",
        "check": "submitted",
    }
    if  idict:
        params.update(idict)
    data = urllib2.urlopen(url + '?' + urllib.urlencode(params, doseq=True))
    res  = json.load(data)
    if  res.has_key('meta'):
        del res['meta']
    return [Job(r) for r in res['summaries']]
