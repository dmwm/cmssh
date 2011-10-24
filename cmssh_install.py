#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
File: cmssh_install.py
Author: Valentin Kuznetsov [ vkuznet AT gmail DOT com ]
Description: cmssh installation script
"""

# system modules
import os
import sys
import time
import shutil
import urllib
import urllib2
import tarfile
import subprocess
import traceback

# local modules
from pprint import pformat
from optparse import OptionParser

# check system requirements
if sys.version_info < (2, 6):
    raise Exception("cmssh requires python 2.6 or higher")

class MyOptionParser:
    """option parser"""
    def __init__(self):
        self.parser = OptionParser()
        self.parser.add_option("-v", "--verbose", action="store", 
            type="int", default=0, dest="debug", 
            help="verbose output")
        self.parser.add_option("-d", "--dir", action="store",
            type="string", default=None,
            dest="install_dir", help="install directory")
        self.parser.add_option("-i", "--install", action="store_true",
            dest="install", help="install command")
        self.parser.add_option("--arch", action="store",
            type="string", default=None, dest="arch",
            help="CMSSW architecture")
        self.parser.add_option("--unsupported", action="store_true",
            dest="unsupported",
            help="enforce installation on unsupported Linux platforms, e.g. Ubuntu")
    def getOpt(self):
        """Returns parse list of options"""
        return self.parser.parse_args()

def getdata(url, params, verbose=0):
    """Invoke URL call and retrieve data for given url/params/headers"""
    encoded_data = urllib.urlencode(params)
    headers = {}
    if  verbose:
        print '+++ getdata url=%s' % url
    req = urllib2.Request(url)
    for key, val in headers.items():
        req.add_header(key, val)
    if  verbose > 1:
        handler = urllib2.HTTPHandler(debuglevel=1)
        opener  = urllib2.build_opener(handler)
        urllib2.install_opener(opener)
    data = urllib2.urlopen(req)
    return data.read()

def get_file(url, fname, path, debug):
    """Fetch tarball from given url and store it as fname, untar it into given path"""
    with open(fname, 'w') as tar_file:
         tar_file.write(getdata(url, {}, debug))
    tar = tarfile.open(fname, 'r:gz')
    tar.extractall(path)
    tar.close()

def exe_cmd(idir, cmd, debug):
    """Execute given command in a given dir"""
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

def main():
    mgr = MyOptionParser()
    opts, args = mgr.getOpt()

    if  not opts.install:
        print "Usage: cmssh_install.py --help"
        sys.exit(0)
    debug = opts.debug
    idir = opts.install_dir
    if  not idir:
        msg  = "Please specify the install area"
        msg += " (it should have enough space to hold CMSSW releases)"
        print msg
        sys.exit(0)
    arch = opts.arch

    # setup install area
    cwd = os.getcwd()
    path = os.path.join(os.getcwd(), 'soft')
    print "Clean-up %s" % path
    try:
        shutil.rmtree(path)
    except:
        traceback.print_exc()
        pass
    sysver = sys.version_info
    py_ver = '%s.%s' % (sysver[0], sysver[1])
    install_dir = '%s/install/lib/python%s/site-packages' % (path, py_ver)
    os.environ['PYTHONPATH'] = install_dir
    try:
        os.makedirs(install_dir)
    except:
        pass
    os.chdir(path)

    platform = os.uname()[0]
    unsupported_linux = False
    if  os.uname()[3].find('Ubuntu') != -1 or opts.unsupported:
        unsupported_linux = True

    print "Installing Globus"
    url_src = 'http://www.globus.org/ftppub/gt5/5.0/5.0.4/installers/src/gt5.0.4-all-source-installer.tar.bz2'
    parch = 'x86'
    if  platform == 'Linux':
        if  unsupported_linux:
            ver = 'deb_5.0'
        else:
            ver = 'rhap_5'
        if  not arch:
            arch = 'slc5_ia32_gcc434'
    elif platform == 'Darwin':
        ver  = 'macos_10.4'
        if  not arch:
            arch = 'osx106_amd64_gcc461'
    else:
        msg = 'Unsupported OS "%s"' % platform
        print msg
        sys.exit(1)
    url = 'http://vdt.cs.wisc.edu/software/globus/4.0.8_VDT2.0.0/vdt_globus_essentials-VDT2.0.0-%s_%s.tar.gz' % (parch, ver)
    get_file(url, 'globus.tar.gz', path, debug)

    print "Installing SRM client"
    url = 'http://vdt.cs.wisc.edu/software/srm-client-lbnl/2.2.1.3.19/srmclient2-2.2.1.3.19.tar.gz'
    get_file(url, 'srmclient.tar.gz', path, debug)
    cmd  = './configure --with-java-home=$JAVA_HOME --enable-clientonly'
    cmd += ' --with-globus-location=%s/globus' % path
    exe_cmd(os.path.join(path, 'srmclient2/setup'), cmd, debug)

    print "Installing IPython"
    os.chdir(path)
    url = 'http://archive.ipython.org/release/0.11/ipython-0.11.tar.gz'
    get_file(url, 'ipython.tar.gz', path, debug)
    cmd = 'python setup.py install --prefix=%s/install' % path
    exe_cmd(os.path.join(path, 'ipython-0.11'), cmd, debug)

    print "Installing Routes"
    os.chdir(path)
    url = 'http://peak.telecommunity.com/dist/ez_setup.py'
    with open('ez_setup.py', 'w') as ez_setup:
         ez_setup.write(getdata(url, {}, debug))
    url = 'http://pypi.python.org/packages/source/R/Routes/Routes-1.12.3.tar.gz'
    get_file(url, 'routes.tar.gz', path, debug)
    cmd = 'cp ../ez_setup.py .; python setup.py install --prefix=%s/install' % path
    exe_cmd(os.path.join(path, 'Routes-1.12.3'), cmd, debug)
    
    print "Installing cmssh"
    os.chdir(path)
    url = 'http://github.com/vkuznet/cmssh/tarball/master/'
    get_file(url, 'cmssh.tar.gz', path, debug)
    cmd = 'mv vkuznet-cmssh* %s/cmssh' % path
    exe_cmd(path, cmd, debug)

    print "Bootstrap CMSSW"
    sdir = '%s/CMSSW' % path 
    try:
        os.makedirs(sdir)
    except:
        pass
    os.chdir(sdir)
    url  = 'http://cmsrep.cern.ch/cmssw/cms/bootstrap.sh'
    with open('bootstrap.sh', 'w') as bootstrap:
         bootstrap.write(getdata(url, {}, debug))
    os.chmod('bootstrap.sh', 0755)
    os.environ['VO_CMS_SW_DIR'] = sdir
    os.environ['SCRAM_ARCH'] = arch
    os.environ['LANG'] = 'C'
    cmd  = 'sh -x $VO_CMS_SW_DIR/bootstrap.sh setup -path $VO_CMS_SW_DIR -arch $SCRAM_ARCH'
    if  unsupported_linux:
        cmd += ' -unsupported_distribution_hack'
    cmd += ';source $VO_CMS_SW_DIR/$SCRAM_ARCH/external/apt/*/profile.d/init.sh;'
    cmd += 'apt-get install external+fakesystem+1.0;'
    cmd += 'apt-get update'
    exe_cmd(sdir, cmd, debug)
    
    print "Create configuration"
    os.chdir(path)
    with open('setup.sh', 'w') as setup:
        msg  = '#!/bin/bash\nexport DYLD_LIBRARY_PATH=%s/globus/lib\n' % path
        msg += 'export LD_LIBRARY_PATH=%s/globus/lib\n' % path
        msg += 'export PATH=%s/globus/bin:$PATH\n' % path
        msg += 'export PATH=%s/srmclient2/bin:$PATH\n' % path
        msg += 'export PATH=%s/install/bin:$PATH\n' % path
        msg += 'export PATH=%s/bin:$PATH\n' % path
        msg += 'export PYTHONPATH=%s/cmssh/src\n' % path
        msg += 'export PYTHONPATH=$PYTHONPATH:$PWD/soft/install/lib/python%s/site-packages\n' % py_ver
        msg += 'export VO_CMS_SW_DIR=%s/CMSSW\n' % path 
        msg += 'export SCRAM_ARCH=%s\n' % arch
        msg += 'export LANG="C"\n'
        msg += 'export CMSSW_RELEASES=%s/Releases\n' % path
        msg += 'if [ -f $VO_CMS_SW_DIR/cmsset_default.sh ]; then\n'
        msg += '   source $VO_CMS_SW_DIR/cmsset_default.sh\nfi\n'
        msg += 'source $VO_CMS_SW_DIR/$SCRAM_ARCH/external/apt/*/etc/profile.d/init.sh\n'
        if  debug:
            print "+++ write setup.sh"
        setup.write(msg)
    os.chmod('setup.sh', 0755)

    print "Create cmssh"
    os.makedirs(os.path.join(path, 'bin'))
    with open(os.path.join(path, 'bin/cmssh'), 'w') as cmssh:
        msg  = '#!/bin/bash\n'
        msg += 'source %s/setup.sh\n' % path
        msg += 'ipdir="%s/.ipython"\nmkdir -p $ipdir\n' % path
        msg += """
soft_dir=%s
if [ ! -d $soft_dir/.ipython/extensions ]; then
    mkdir -p $soft_dir/.ipython/extensions
fi
if [ ! -d $soft_dir/.ipython/profile_cmssh ]; then
    mkdir -p $soft_dir/.ipython/profile_cmssh
fi
if [ ! -f $soft_dir/.ipython/extensions/cmssh_extension.py ]; then
    cp $soft_dir/cmssh/src/config/cmssh_extension.py $soft_dir/.ipython/extensions/
fi
if [ ! -f $soft_dir/.ipython/profile_cmssh/ipython_config.py ]; then
    cp $soft_dir/cmssh/src/config/ipython_config.py $soft_dir/.ipython/profile_cmssh/
fi
export IPYTHON_DIR=$ipdir
grid-proxy-init
ipython --no-banner --ipython-dir=$ipdir --profile=cmssh
""" % path
        cmssh.write(msg)
    os.chmod('bin/cmssh', 0755)

    print "Contratulations, cmssh is available at %s/bin/cmssh" % path

if __name__ == '__main__':
    main()
