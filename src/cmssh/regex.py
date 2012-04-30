#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
File       : regex.py
Author     : Valentin Kuznetsov <vkuznet@gmail.com>
Description: Various regex patterns used by cmssh
"""

# system modules
import re

pat_release = re.compile(\
r'^(release=)?CMSSW(_[0-9]){3}$|(release=)?^CMSSW(_[0-9]){3}_patch[0-9]+$|^(release=)?CMSSW(_[0-9]){3}_pre[0-9]+$')
pat_lfn = re.compile('.*\.root$')
pat_site = re.compile('^(site=)?T[0-9]_[A-Z]+(_)[A-Z]+')
pat_dataset = re.compile('^(dataset=)?/.*/.*/.*')
pat_block = re.compile('^(block=)?/.*/.*/.*#.*')
pat_lfn = re.compile('^(file=)?/.*\.root$')
pat_run = re.compile('^(run=)?[1-9][0-9]{5,8}$')
pat_se = re.compile('^(site=)?T[0-3]_.*:/.*')
float_number_pattern = re.compile(r'(^[-]?\d+\.\d*$|^\d*\.{1,1}\d+$)')
int_number_pattern = re.compile(r'(^[0-9-]$|^[0-9-][0-9]*$)')
