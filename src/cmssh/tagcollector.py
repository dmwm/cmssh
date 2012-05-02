#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
CMS Tag Collector interface
"""

# system modules
import re

# cmssh modules
from cmssh.utils import Memoize
from cmssh.cms_urls import tc_url
from cmssh.url_utils import get_data
from cmssh.regex import pat_release

@Memoize(interval=3600)
def releases(rel_name=None, rfilter=None):
    "Return information about CMS releases"
    if  rel_name:
        if  not pat_release.match(rel_name):
            msg = 'Wrong CMSSW release name'
            raise ValueError(msg)
        args  = {'release_name': rel_name}
    else:
        args  = {}
    rel_info  = get_data(tc_url(), 'getReleasesInformation', args)
    columns   = rel_info['columns']
    pat = re.compile('CMSSW_[1-9]_[0-9]_X\.*')
    for key, val in rel_info['data'].iteritems():
        if rfilter == 'list':
            if  pat.match(key) or not key.find('CMSSW') != -1:
                continue
        row   = {}
        pairs = zip(columns['release_name'], val)
        for kkk, vvv in pairs:
            if  isinstance(kkk, basestring):
                row[kkk] = vvv
            elif isinstance(kkk, list):
                for item in vvv:
                    row.setdefault('architectures', []).append(dict(zip(kkk, item)))
        row['release_name'] = key
        yield row

def architectures(arch_type='production'):
    "Return list of CMSSW known architectures"
    if  not arch_type:
        arch_type = 'all'
    prod_arch = set()
    dev_arch  = set()
    for row in releases():
        for item in row['architectures']:
            if  item['is_production_architecture']:
                prod_arch.add(item['architecture_name'])
            else:
                dev_arch.add(item['architecture_name'])
    if  arch_type == 'production':
        arch_list = list(prod_arch)
    elif arch_type == 'development':
        arch_list = list(dev_arch)
    elif arch_type == 'all':
        arch_list = list(prod_arch | dev_arch)
    else:
        raise NotImplementedError
    arch_list.sort()
    return arch_list

if __name__ == '__main__':
    for r in releases():
        print r
