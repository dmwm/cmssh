#!/usr/bin/env python
#-*- coding: utf-8 -*-
#pylint: disable-msg=
"""
File       : srmls_parser.py
Author     : Valentin Kuznetsov <vkuznet@gmail.com>
Description: 
"""

# system modules
import os
import re
import sys

def permissions(dfield, ufield, gfield, ofield):
    "Return UNIX permission string"
    def helper(field):
        "Decompose field into dict"
        out  = 'r' if 'r' in field else '-'
        out += 'w' if 'w' in field else '-'
        out += 'x' if 'x' in field else '-'
        return out
    return dfield + helper(ufield) + helper(gfield) + helper(ofield)

#
# srmls paser/formater/printer implementation
#
def srmls_parser(stream):
    "srmls parser"
    pat = re.compile('\s*[0-9]*\s*/.*')
    row = {}
    uid = ''
    gid = ''
    user = ''
    group = ''
    world = ''
    for line in stream.split('\n'):
        line = line.replace('\n', '')
        if  pat.match(line): # new row
            if  row:
                yield row
                row = {}
            content = line.split()
            if  len(content) == 1: # it is directory
                row['name'] = content[0]
            elif len(content) == 2: # it is file
                row['size'] = content[0]
                row['name'] = content[1]
        for perm in ['user', 'group', 'world']:
            if  line.lower().find('%spermission' % perm) != -1:
                value = line.split()[-1].lower().replace('permissions', '')
                if  perm == 'user':
                    user = value
                if  perm == 'group':
                    group = value
                if  perm == 'world':
                    world = value
                if  perm == 'user':
                    uid = line.split()[1].replace('uid=', '').lower()
                elif perm == 'group':
                    gid = line.split()[1].replace('gid=', '').lower()
        if  uid:
            row['uid'] = uid
        if  gid:
            row['gid'] = gid
        if  user:
            row['user']  = user
        if  group:
            row['group'] = group
        if  world:
            row['world'] = world
        if  line.lower().find('modified') != -1:
            row['tstamp'] = line.split(':', 1)[-1]
        if  line.lower().find('type') != -1:
            row['ftype'] = line.split()[-1].lower()
    if  row:
        yield row

def srmls_printer(stream, dst=''):
    "srmls printer"
    rows = []
    size_of_size = 0
    for row in srmls_parser(stream):
        size   = row.get('size', 0)
        if  len(str(size)) > size_of_size:
            size_of_size = len(str(size))
        rows.append(row)
    for row in rows:
        name   = row.get('name').replace(dst, '')
        if  not name:
            name = '.'
        elif name == '/':
            name = '.'
        elif name[0] == '/':
            name = name[1:]
        size   = row.get('size', 0)
        if  len(str(size)) < size_of_size:
            size = str(size).rjust(size_of_size-len(str(size))+1, ' ')
        tstamp = row.get('tstamp', '')
        ftype  = 'd' if row.get('ftype', '') == 'directory' else '-'
        user   = row.get('user', 'r--')
        group  = row.get('group', 'r--')
        world  = row.get('world', 'r--')
        perm   = permissions(ftype, user, group, world)
        uid    = row.get('uid', '')
        gid    = row.get('gid', '')
        if  uid and gid:
            yield "%s %s %s %s %s %s" % (perm, uid, gid, size, tstamp, name)
        else:
            yield "%s %s %s %s" % (perm, size, tstamp, name)

#
# srm-ls paser/formater/printer implementation
#
def check_ls_fields(data):
    "Helper function to check ls fields"
    keys   = data.keys()
    mandatory_keys = ['filetype', 'surl', 'lastaccessed']
    if  set(keys) & set(mandatory_keys):
        return True
    return False

def srm_ls_format(arr, dst=''):
    "Perform ls format of input rows"
    output = []
    size   = 0 # total size
    lbytes = 1 # length of the bytes field
    luser  = 1 # length of the user field
    lgroup = 1 # length of the group field
    ufield = ''
    user   = ''
    ofield = ''
    group  = ''
    gfield = ''
    for row in arr:
        if  not check_ls_fields(row):
            continue
        if  row.has_key('ownerpermission'):
            ufield = row['ownerpermission']['mode']
            user   = row['ownerpermission']['userid']
        if  row.has_key('ownerpermission'):
            ofield = row['otherpermission']
        if  row.has_key('grouppermission'):
            group  = row['grouppermission']['groupid']
            gfield = row['grouppermission']['mode']
        date   = row['lastaccessed']
        dfield = 'd' if row['filetype'] == 'directory' else '-'
        mask   = permissions(dfield, ufield, gfield, ofield)
        date   = row['lastaccessed']
        name   = row['surl'].replace('//', '/').replace(dst, '')
        if  not name:
            name = '.'
        elif name[0] == '/':
            name = name[1:]
        size   = 0 if not row.has_key('bytes') else row['bytes']
        lbytes = len(str(size)) if len(str(size)) > lbytes else lbytes
        luser  = len(str(user)) if len(str(user)) > luser else luser
        lgroup = len(str(group)) if len(str(group)) > lgroup else lgroup
        fields = (name, mask, user, group, size, date)
        output.append(fields)
    output.sort()
    field_format = '%(mask)s %(user)s %(group)s %s %s %s'
    out = []
    for row in output:
        name, mask, user, group, size, date = row
        pad    = ' '*(lbytes-len(str(size))) if len(str(size)) < lbytes else ''
        size   = '%s%s' % (pad, size)
        pad    = ' '*(luser-len(str(user))) if len(str(user)) < luser else ''
        user   = '%s%s' % (pad, user)
        pad    = ' '*(lgroup-len(str(group))) if len(str(group)) < lgroup else ''
        group  = '%s%s' % (pad, group)
        fields = '%s %s %s %s %s %s' % (mask, user, group, size, date, name)
        out.append(fields)
    if  not out:
        return arr
    return out

def srm_ls_printer(stream, dst=''):
    "printer for srm-ls command"
    for row in srm_ls_format(srm_ls_parser(stream), dst):
        yield row

def srm_ls_parser(stream):
    "parser for srm-ls command"
    row = {}
    entities = ['file_status', 'filelocality', 'filetype', 'otherpermission']
    for line in stream.split('\n'):
        if  line.find('SRM-CLIENT*') == -1:
            continue
        if  line.find('SRM-CLIENT*REQUEST_STATUS') != -1:
            continue
        if  line.find('SRM-CLIENT*SURL') != -1:
            if  row:
                yield row
                row = {}
        key, val = line.split('=')
        key = key.replace('SRM-CLIENT*', '').lower()
        if  key == 'bytes':
            val = long(val)
        if  key in entities:
            val = val.lower()
        if  key.find('.') != -1:
            att, elem = key.split('.')
            if  not row.has_key(att) or not isinstance(row[att], dict):
                row[att] = {}
            row[att][elem] = val.lower()
        else:
            row[key] = val
    if  row:
        yield row

def test():
    with open('srmls.out', 'r') as stream:
        for line in srmls_printer(stream.read(), dst='/xrootdfs/cms/store/user/'):
            print line

if __name__ == '__main__':
    test()
