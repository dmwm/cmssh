#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
Common utilities
"""

# system modules
import os
import re
import sys
import stat
import time
import shlex
import pydoc
import types
import readline
import traceback
import subprocess
import itertools
import functools
from   types import GeneratorType, InstanceType
from   cStringIO import StringIO
import xml.etree.cElementTree as ET
from   decorator import decorator

# cmssh modules
from   cmssh.iprint import format_dict, msg_green
from   cmssh.iprint import print_warning, print_error, print_info
from   cmssh.regex import float_number_pattern, int_number_pattern

def ranges(ilist):
    """
    Convert input list to list of ranges, see
    http://stackoverflow.com/questions/4628333/converting-a-list-of-integers-into-range-in-python
    """
    if  ilist:
        for _, bbb in itertools.groupby(enumerate(ilist), lambda (x, y): y - x):
            bbb = list(bbb)
            yield [bbb[0][1], bbb[-1][1]]

def touch(fname):
    "Emulate touch UNIX command"
    with open(fname, 'w') as fobj:
        fobj.write('')

def access2file(fname):
    "Check if given file name exists on a system and is accessible"
    if  not os.path.isfile(fname):
        msg = 'File %s does not exists' % fname
        print_error(msg)
        return False
    mode = os.stat(fname).st_mode
    if  not bool(mode & stat.S_IRUSR):
        msg = 'Unsufficient privileges to access %s' % fname
        print_error(msg)
        return False
    return True

def memoize(obj):
    "Keep things in cache"
    cache = obj.cache = {}
    @functools.wraps(obj)
    def memoizer(*args, **kwargs):
        if args not in cache:
            cache[args] = obj(*args, **kwargs)
        return cache[args]
    return memoizer

class working_dir(object):
    "ContextManager to switch for given directory"
    def __init__(self, new_dir, debug=None):
        self.ndir  = new_dir
        self.odir  = os.getcwd()
        self.debug = debug
    def __enter__(self):
        "Switch to new directory"
        if  self.ndir:
            if  self.debug:
                print "cd %s" % self.ndir
            os.chdir(self.ndir)
    def __exit__(self, exc_type, exc_val, exc_tb):
        "Switch to original directory"
        if  self.ndir:
            if  self.debug:
                print "cd %s" % self.odir
            os.chdir(self.odir)

def user_input(msg, default='N'):
    "Provide raw_input for given message and return True or False"
    if  default == 'y' or default == 'Y':
        msg += ' [Y/n] '
    else:
        msg += ' [y/N] '
    if  msg[0] != '\n':
        msg  = '\n' + msg
    uinput = raw_input(msg)
    if  (default == 'y' or default == 'Y') and not uinput:
        uinput = 'y'
    if  (default == 'n' or default == 'N') and not uinput:
        uinput = 'n'
    if  uinput.lower() == 'y' or uinput.lower() == 'yes':
        return True
    return False

def run(cmd, cdir=None, log=None, msg=None, debug=None, shell=False, call=False):
    "Run given command via subprocess call"
    if  msg:
        print msg
    cmd  = cmd.strip()
    kwds = {}
    if  shell or cmd.find(';') != -1 or cmd.find('&&') != -1 or \
        cmd.find('|') != -1:
        kwds = {'shell': True}
    else:
        if  isinstance(cmd, unicode):
            cmd = shlex.split(cmd.encode('ascii', 'ignore'))
        else:
            cmd = shlex.split(cmd)
    msg = 'execute cmd=%s, kwds=%s' % (cmd, kwds)
    if  debug:
        print_info(msg.capitalize())
    try:
        with working_dir(cdir):
            if  not call:
                kwds.update({'stdout':subprocess.PIPE,
                             'stderr':subprocess.PIPE,
                             'close_fds':True})
            if  log:
                with open(log, 'w') as logstream:
                    kwds.update({'stdout': logstream, 'stderr': logstream})
                    if  call:
                        subprocess.call(cmd, **kwds)
                        return
                    pipe = subprocess.Popen(cmd, **kwds)
            else:
                if  call:
                    subprocess.call(cmd, **kwds)
                    return
                pipe = subprocess.Popen(cmd, **kwds)
            (child_stdout, child_stderr) = (pipe.stdout, pipe.stderr)
            if  child_stdout:
                stdout = child_stdout.read()
            else:
                stdout = ''
            if  child_stderr:
                stderr = child_stderr.read()
            else:
                stderr = ''
            if  stderr:
                if  isinstance(cmd, list):
                    cmd_str = ' '.join(cmd)
                else:
                    cmd_str = cmd
                if  cmd_str.find('proxy') != -1: # proxy commands prints . to stderr
                    sss = stderr.replace(stderr[0], '')
                    if  not (stderr[0] == '.' and not len(sss)):
                        print_error(stderr)
                else:
                    print_error(stderr)
            print stdout
    except OSError as err:
        msg = 'OSError, fail to ' + msg + ', error=%s' % str(err)
        print_error(msg)
    except Exception as err:
        msg = 'Fail to ' + msg + ', error=%s' % str(err)
        print_error(msg)

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

class PrintProgress(object):
    def __init__(self, msg='Download in progress:', width=21, fill=' '):
        if  os.environ.has_key('CMSSH_NOTEBOOK'):
            self.return_char = ''
            init_msg = msg
            self.msg = '' # in notebook do not re-print
        else:
            self.return_char = '\r'
            init_msg = msg
            self.msg = init_msg
        self.width   = width
        self.fill    = fill
        self.print_msg(init_msg)
        self.init()

    def msg_format(self):
        return '%%%ds' % self.width

    def init(self, msg=None, fill=' '):
        "Init bar progress status"
        self.progress = set(['N/A']) # progress values
        if  msg:
            if  os.environ.has_key('CMSSH_NOTEBOOK'):
                if  msg == 'Download in progress:':
                    self.print_msg(msg)
                    self.msg   = ''
                    self.width = 0
            else:
                self.msg = msg
                self.width = len(self.msg)
                self.fill = fill

    def clear(self):
        "Clear bar progress status"
        print '' # to clear stdout
        self.init()

    def refresh(self, progress):
        "Update progress bar status"
        if  isinstance(progress, int) or isinstance(progress, float) or \
            isinstance(progress, long):
            progress = int(progress)
        if  progress in self.progress:
            return
        self.progress.add(progress)
        if  progress == 'N/A' or not progress:
            sys.stdout.write(self.return_char)
        else:
            msg = " %d%%" % progress
            msg = self.msg_format() % self.msg + msg + self.return_char
            sys.stdout.write(msg)
        sys.stdout.flush()

    def print_msg(self, msg):
        "Update progress bar with given message"
        if  os.environ.has_key('CMSSH_NOTEBOOK'):
            mmm = msg + '\n'
        else:
            mmm = self.msg_format() % (msg.ljust(self.width, self.fill) \
                    + self.return_char)
        sys.stdout.write(mmm)
        sys.stdout.flush()

def print_res_err(res, err):
    "Print res/err from remote command execution"
    if  isinstance(res, list):
        print "\n", '\n'.join(res)
    else:
        print "\n", res
    if  err:
        if  isinstance(err, list):
            msg = '\n'.join(err)
        else:
            msg = err
        print_warning(msg)

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
    "List results"
    if  not res:
        return
    gen = formatter_output(res, debug)
    out = '\n'.join([str(r) for r in gen])
    if  flt:
        out = '\n'.join(filter_output(out, flt))
    pager = os.environ.get('CMSSH_PAGER', None)
    if  pager and pager != '0':
        pydoc.pager(out)
    else:
        print out

def formatter_output(res, debug):
    "Formatter takes care of results representation"
    if  isinstance(res, list) or isinstance(res, GeneratorType):
        for row in res:
            if  not debug:
                yield row
            else:
                if  isinstance(row, basestring):
                    yield row
                else:
                    yield repr(row)
    elif  isinstance(res, set):
        for row in list(res):
            if  not debug:
                yield row
            else:
                if  isinstance(row, basestring):
                    yield row
                else:
                    yield repr(row)
    elif isinstance(res, dict):
        yield format_dict(res)
    else:
        if  not debug:
            yield res
        else:
            if  isinstance(res, basestring):
                yield res
            else:
                yield repr(res)

def filter_output(output, flt):
    "Filter given output"
    match = None
    if  flt:
        arr = flt.split()
        if  arr[0] == 'grep':
            match = ' '.join(arr[1:]).strip()
        else:
            raise NotImplementedError
    if  flt and match:
        arr = match.split()
        opt = None
        if  len(arr) == 1:
            match = arr[0]
        elif len(arr) == 2:
            opt, match = arr
        else:
            raise NotImplementedError
        for line in output.split('\n'):
            if  opt and opt == '-i':
                if  line.lower().find(match.lower()) != -1:
                    yield line
            elif  opt and opt == '-v':
                if  line.find(match) == -1:
                    yield line
            elif  opt and (opt == '-iv' or opt == '-vi'):
                if  line.lower().find(match.lower()) == -1:
                    yield line
            else:
                if  line.find(match) != -1:
                    yield line

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

def platform():
    "Return underlying platform"
    osname = os.uname()[0].lower()
    return osname.replace('darwin', 'osx')

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
    if  platform() == 'linux':
        redhat = '/etc/redhat-release'
        if  os.path.isfile(redhat):
            with open(redhat, 'r') as release:
                content = release.read()
                if  content.find('Scientific Linux') != -1 or \
                    content.find('Red Hat') != -1 or \
                    content.find('Fermi') != -1:
                    return True
    return False

def check_voms_proxy():
    "Check status of user VOMS proxy"
    cmd = 'voms-proxy-info -timeleft'
    out, err = execmd(cmd)
    if  err:
        print_error('Fail to check user proxy info')
        return

    if  int(out) < 3600: # time left is less then 1 hour
        msg  = 'Your VOMS proxy will expire in %s sec (< 1 hour). ' % out
        msg += 'Please run ' + msg_green('vomsinit') + ' command to renew it'
        print_warning(msg)

def get_kerberos_username():
    "Run klist in a shell and get a username from the principal"
    username = None
    cmd = 'klist | grep -i "Principal:"'
    stdout, _stderr = execmd(cmd)
    if  stdout:
        username = stdout.split()[-1].split('@')[0]
    return username

# set of utils for parsing DBS2 output
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

