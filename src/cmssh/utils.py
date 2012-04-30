#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
Common utilities
"""

# system modules
import os
import re
import sys
import time
import types
import readline
import traceback
import subprocess
from   types import GeneratorType, InstanceType
from   cStringIO import StringIO
import xml.etree.cElementTree as ET
from   decorator import decorator

# cmssh modules
from   cmssh.iprint import format_dict, print_warning, msg_green, print_error
from   cmssh.regex import float_number_pattern, int_number_pattern

class Memoize(object):
    def __init__(self, interval=1*60*60):
        self.interval = interval # cache expiration time, default 1h
        self.expire = time.time() + self.interval

    def __call__(self, func):
        "Wrap for decorator function call"
        return decorator(self.check_cache, func)

    def check_cache(self, func, *args):
        "Set/get results from cache"
        if  not hasattr(func, 'results'):
            func.results = {}
        if  time.time() > self.expire:
            func.results = {}
            self.expire = time.time() + self.interval
        if  args not in func.results:
            result = func(*args)
            if  isinstance(result, GeneratorType):
                result = [r for r in result]
            func.results[args] = result
        return func.results[args]

def print_progress(progress, msg='Download in progress:'):
    "Print on stdout progress message"
    if  progress == 'N/A':
        sys.stdout.write("%s   \r" % msg )
    else:
        sys.stdout.write("%s %d%%   \r" % (msg, progress) )
    sys.stdout.flush()

def size_format(i):
    """
    Format file size utility, it converts file size into KB, MB, GB, TB, PB units
    """
    try:
        num = long(i)
    except:
#        traceback.print_exc()
        return None
    for x in ['','KB','MB','GB','TB','PB']:
        if num < 1024.:
            return "%3.1f%s" % (num, x)
        num /= 1024.

def whoami():
    # the way to get function name, see http://code.activestate.com/recipes/66062/
    return sys._getframe(1).f_code.co_name

def swap_dict(original_dict):
    """Swap key/value in dict"""
    return dict([(v, k) for (k, v) in original_dict.iteritems()])

class Completer:
    def __init__(self, words):
        self.words = words
        self.prefix = None
    def complete(self, prefix, index):
        if prefix != self.prefix:
            # we have a new prefix!
            # find all words that start with this prefix
            self.matching_words = [
                w for w in self.words if w.startswith(prefix)
                ]
            self.prefix = prefix
        try:
            return self.matching_words[index]
        except IndexError:
            return None

def list_results(res, debug, flt=None):
    """List results"""

    old_stdout = sys.stdout
    match = None
    if  flt:
        arr = flt.split()
        if  arr[0] == 'grep':
            match = ' '.join(arr[1:]).strip()
        else:
            raise NotImplementedError
        sys.stdout = mystdout = StringIO()

    if  not res:
        return
    if  isinstance(res, list) or isinstance(res, GeneratorType):
        for row in res:
            if  not debug:
                print row
            else:
                print repr(row)
    elif  isinstance(res, set):
        for row in list(res):
            if  not debug:
                print row
            else:
                print repr(row)
    elif isinstance(res, dict):
        print format_dict(res)
    else:
        if  not debug:
            print res
        else:
            print repr(res)

    sys.stdout = old_stdout
    if  flt and match:
        arr = match.split()
        opt = None
        if  len(arr) == 1:
            match = arr[0]
        elif len(arr) == 2:
            opt, match = arr
        else:
            raise NotImplementedError
        output = mystdout.getvalue()
        for line in output.split('\n'):
            if  opt and opt == '-i':
                if  line.lower().find(match.lower()) != -1:
                    print line
            elif  opt and opt == '-v':
                if  line.find(match) == -1:
                    print line
            elif  opt and (opt == '-iv' or opt == '-vi'):
                if  line.lower().find(match.lower()) == -1:
                    print line
            else:
                if  line.find(match) != -1:
                    print line

def execmd(cmd):
    """Execute given command in subprocess"""
    pipe = subprocess.Popen(cmd, shell=True, 
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    (child_stdout, child_stderr) = (pipe.stdout, pipe.stderr)
    stdout = child_stdout.read()
    stderr = child_stderr.read()
    return stdout, stderr

def adjust_value(value):
    """
    Change null value to None.
    """
    pat_float   = float_number_pattern
    pat_integer = int_number_pattern
    if  isinstance(value, basestring):
        value = value.strip()
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

def xml_parser(source, prim_key, tags=None):
    """
    XML parser based on ElementTree module. To reduce memory footprint for
    large XML documents we use iterparse method to walk through provided
    source descriptor (a .read()/close()-supporting file-like object 
    containig XML source).

    The provided prim_key defines a tag to capture, while supplementary
    *tags* list defines additional tags which can be added to outgoing
    result. For instance, file object shipped from PhEDEx is enclosed
    into block one, so we want to capture block.name together with
    file object.
    """
    notations = {}
    sup       = {}
    try:
        context = ET.iterparse(source, events=("start", "end"))
    except IOError as exc: # given source is not parseable
        # try different data format, it can be an HTTP error
        try:
            if  isinstance(source, str):
                data = json.loads(source)
                yield data
        except:
            pass
        msg = 'XML parser, data stream is not parseable: %s' % str(exc)
        print_exc(msg)
        context = []
    root      = None
    for item in context:
        event, elem = item
        if  event == "start" and root is None:
            root = elem # the first element is root
        row = {}
        if  tags and not sup:
            for tag in tags:
                if  tag.find(".") != -1:
                    atag, attr = tag.split(".")
                    if  elem.tag == atag and elem.attrib.has_key(attr):
                        att_value = elem.attrib[attr]
                        if  isinstance(att_value, dict):
                            att_value = \
                                dict_helper(elem.attrib[attr], notations)
                        if  isinstance(att_value, str):
                            att_value = adjust_value(att_value)
                        sup[atag] = {attr:att_value}
                else:
                    if  elem.tag == tag:
                        sup[tag] = elem.attrib
        key = elem.tag
        if  key != prim_key:
            continue
        row[key] = dict_helper(elem.attrib, notations)
        row[key].update(sup)
        get_children(elem, event, row, key, notations)
        if  event == 'end':
            elem.clear()
            yield row
    if  root:
        root.clear()
    if  isinstance(source, InstanceType) or isinstance(source, file):
        source.close()

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

def osparameters():
    "Return OS parameters as expected in CMS, osx/slc and ia32/amd64"
    osname = os.uname()[0].replace('Darwin', 'osx').replace('Linux', 'slc5')
    osarch = os.uname()[-1].replace('x86_64', 'amd64')
    for intel in ['i386', 'i486', 'i586', 'i686']:
        osarch = osarch.replace(intel, 'ia32')
    return osname, osarch

def check_os(rel_arch):
    "Check that given release architecture fits underlying OS"
    osname, osarch = osparameters()
    if  rel_arch.find(osname) != -1 and rel_arch.find(osarch) != -1:
        return True
    return False

def unsupported_linux():
    "Check if underlying OS is unsupported Linux platform"
    if  os.uname()[0].lower() == 'linux':
        redhat = '/etc/redhat-release'
        if  os.path.isfile(redhat):
            with open(redhat, 'r') as release:
                content = release.read()
                if  content.find('Scientific Linux') != -1 or \
                    content.find('Red Hat') != -1 or \
                    content.find('Fermi') != -1:
                    return True
    return False

def exe_cmd(idir, cmd, debug, msg=None):
    """Execute given command in a given dir"""
    if  msg:
        print msg
    os.chdir(idir)
    if  debug:
        print "cd %s\n%s" % (os.getcwd(), cmd)
    with open('install.log', 'w') as logstream:
        try:
            retcode = subprocess.call(cmd, shell=True, stdout=logstream, stderr=logstream)
            if  retcode < 0:
                print >> sys.stderr, "Child was terminated by signal", -retcode
        except OSError, err:
            print >> sys.stderr, "Execution failed:", err

def check_voms_proxy():
    "Check status of user VOMS proxy"
    cmd = 'voms-proxy-info -timeleft'
    res = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = (res.stdout, res.stderr)
    err = stderr.read()
    if  err:
        print_error('Fail to check user proxy info')
        return

    out = int(stdout.read())
    if  out < 3600: # time left is less then 1 hour
        msg  = 'Your VOMS proxy will expire in %s sec (< 1 hour). ' % out
        msg += 'Please run ' + msg_green('vomsinit') + ' command to renew it'
        print_warning(msg)
