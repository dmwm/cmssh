#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
File: cmssh_install.py
Author: Valentin Kuznetsov [ vkuznet AT gmail DOT com ]
Description: cmssh installation script

Some useful URLs
http://www.globus.org/ftppub/gt5/5.0/5.0.4/installers/src/gt5.0.4-all-source-installer.tar.bz2
http://www.nikhef.nl/pub/projects/grid/gridwiki/index.php/Using_voms-proxy-init_on_an_OSX_(10.4_or_higher)_system
https://twiki.grid.iu.edu/bin/view/ReleaseDocumentation/VomsInstallGuide

"""

# system modules
import os
import sys
import time
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
#        self.parser.add_option("--update", action="store",
#            type="string", default=None, dest="update",
#            help="Update cmssh to newest version, including all dependencies")
        self.parser.add_option("--unsupported", action="store_true",
            dest="unsupported",
            help="enforce installation on unsupported Linux platforms, e.g. Ubuntu")
        self.parser.add_option("--no_cmssw", action="store_true",
            dest="no_cmssw",
            help="do not bootstrap CMSSW area")
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

def is_installed(url, path):
    "Check if already installed a package for given URL"
    fname = os.path.join(path, '.packages')
    with open(fname, 'r') as packages:
        for line in packages.readlines():
            if  url == line.replace('\n', ''):
                return True
    return False

def get_file(url, fname, path, debug):
    """Fetch tarball from given url and store it as fname, untar it into given path"""
    os.chdir(path)
    if  is_installed(url, path):
        return
    with open(fname, 'w') as tar_file:
         tar_file.write(getdata(url, {}, debug))
    tar = tarfile.open(fname, 'r:gz')
    tar.extractall(path)
    tar.close()
    # add url into list of installed packages
    with open(os.path.join(path, '.packages'), 'a') as packages:
        packages.write(url)

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

def check_system(unsupported):
    "Check system requirements"
    # check presence of Java, required for GRID middleware
    if  not os.environ.has_key('JAVA_HOME'):
        print "JAVA_HOME environment is required to install GRID middleware tools"
        print "Please install Java and appropriately setup JAVA_HOME"
        sys.exit(1)

    # check Ubuntu default shell
    platform = os.uname()[0]
    unsupported_linux = False
    if  os.uname()[3].find('Ubuntu') != -1 or unsupported:
        unsupported_linux = True
        if  os.readlink('/bin/sh') != 'bash':
            msg  = 'The /bin/sh is pointing to %s.\n'
            msg += 'For proper installation of CMSSW software\n'
            msg += 're-configure /bin/sh to point to /bin/bash.\n'
            msg += 'On Ubuntu, if you have /bin/sh -> /bin/dash, just do:\n'
            msg += 'sudo dpkg-reconfigure dash'
            sys.exit(1)

def main():
    mgr = MyOptionParser()
    opts, args = mgr.getOpt()

    if  not opts.install:
        print "Usage: cmssh_install.py --help"
        sys.exit(0)
    check_system(opts.unsupported)
    debug = opts.debug
    idir = opts.install_dir
    if  not idir:
        msg  = "Please specify the install area"
        msg += " (it should have enough space to hold CMSSW releases)"
        print msg
        sys.exit(0)
    arch   = opts.arch
    cwd    = os.getcwd()
    path   = os.path.join(os.getcwd(), 'soft')
    # setup install area
#    print "Clean-up %s" % path
#    try:
#        cmd = 'rm -rf %s' % path
#        retcode = subprocess.call(cmd, shell=True)
#        if  retcode < 0:
#            print >> sys.stderr, "Child was terminated by signal", -retcode
#    except OSError, err:
#        print >> sys.stderr, "Execution failed:", err
    sysver = sys.version_info
    py_ver = '%s.%s' % (sysver[0], sysver[1])
    install_dir = '%s/install/lib/python%s/site-packages' % (path, py_ver)
    os.environ['PYTHONPATH'] = install_dir
    try:
        os.makedirs(install_dir)
    except:
        pass

    print "Installing Globus"
    parch = 'x86'
    arch  = None
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
        print 'Unsupported OS "%s"' % platform
        sys.exit(1)
    if  not arch:
        print "Unsupported architecture"
        sys.exit(1)

    url = 'http://vdt.cs.wisc.edu/software/globus/4.0.8_VDT2.0.0gt4nbs/vdt_globus_essentials-VDT2.0.0-3-%s_%s.tar.gz' % (parch, ver)
    get_file(url, 'globus.tar.gz', path, debug)

    print "Installing Myproxy"
    url = 'http://vdt.cs.wisc.edu/software/myproxy/5.3_VDT-2.0.0/myproxy_client-5.3-%s_%s.tar.gz' % (parch, ver)
    get_file(url, 'myproxy_client.tar.gz', path, debug)
    url = 'http://vdt.cs.wisc.edu/software/myproxy/5.3_VDT-2.0.0/myproxy_essentials-5.3-%s_%s.tar.gz' % (parch, ver)
    get_file(url, 'myproxy_essentials.tar.gz', path, debug)

    print "Installing VOMS"
    url = 'http://vdt.cs.wisc.edu/software/voms/1.8.8-2p1/voms-client-1.8.8-2p1-%s_%s.tar.gz' % (parch, ver)
    get_file(url, 'voms-client.tar.gz', path, debug)
    url = 'http://vdt.cs.wisc.edu/software/voms/1.8.8-2p1/voms-essentials-1.8.8-2p1-%s_%s.tar.gz' % (parch, ver)
    get_file(url, 'voms-essentials.tar.gz', path, debug)

    print "Installing expat"
    ver = '2.0.1'
    url = 'http://sourceforge.net/projects/expat/files/expat/2.0.1/expat-%s.tar.gz/download?use_mirror=iweb' % ver
    get_file(url, 'expat-%s.tar.gz' % ver, path, debug)
    if  not is_installed(url, path):
        if platform == 'Darwin':
            cmd = 'CFLAGS=-m32 ./configure --prefix=%s/install; make; make install' % path
        else:
            cmd = './configure --prefix=%s/install; make; make install' % path
        os.chdir(os.path.join(path, 'expat-%s' % ver))
        exe_cmd(os.path.join(path, 'expat-%s' % ver), cmd, debug)

    print "Installing PythonUtilities"
    url = "http://cmssw.cvs.cern.ch/cgi-bin/cmssw.cgi/CMSSW/FWCore/PythonUtilities.tar.gz?view=tar"
    get_file(url, 'PythonUtilities.tar.gz', path, debug)
    if  not is_installed(url, path):
        cmd = 'touch __init__.py; mv python/*.py .'
        exe_cmd(os.path.join(path, 'PythonUtilities'), cmd, debug)
        os.chdir(path)
        cmd = 'mkdir FWCore; touch FWCore/__init__.py; mv PythonUtilities FWCore'
        exe_cmd(path, cmd, debug)

    print "Installing CRAB3"
    ver = '3.0.6a'
    url = 'http://cmsrep.cern.ch/cmssw/comp/SOURCES/slc5_amd64_gcc461/cms/crab-client3/%s/crabclient3.tar.gz' % ver
    get_file(url, 'crabclient3.tar.gz', path, debug)

    print "Installing WMCore"
    ver = '0.8.21'
    url = 'http://cmsrep.cern.ch/cmssw/comp/SOURCES/slc5_amd64_gcc461/cms/wmcore/%s/WMCORE.tar.gz' % ver
    get_file(url, 'wmcore.tar.gz', path, debug)

    print "Installing LCG info"
    url = 'http://vdt.cs.wisc.edu/software/lcg-infosites//2.6-2/lcg-infosites-2.6-2.tar.gz'
    get_file(url, 'lcg-infosites.tar.gz', path, debug)
    url = 'http://vdt.cs.wisc.edu/software/lcg-info//1.11.4-1/lcg-info-1.11.4-1.tar.gz'
    get_file(url, 'lcg-info.tar.gz', path, debug)

    print "Installing certificates"
    url = 'http://vdt.cs.wisc.edu/software/certificates/62/certificates-62-1.tar.gz'
    get_file(url, 'certificates.tar.gz', path, debug)

    print "Installing SRM client"
    ver = '2.2.1.3.19'
    url = 'http://vdt.cs.wisc.edu/software/srm-client-lbnl/%s/srmclient2-%s.tar.gz' \
        % (ver, ver)
    get_file(url, 'srmclient.tar.gz', path, debug)
    if  not is_installed(url, path):
        cmd  = './configure --with-java-home=$JAVA_HOME --enable-clientonly'
        cmd += ' --with-globus-location=%s/globus' % path
        cmd += ' --with-cacert-path=%s/certificates' % path
        exe_cmd(os.path.join(path, 'srmclient2/setup'), cmd, debug)

    print "Installing IPython"
    ver = '0.12'
    url = 'http://archive.ipython.org/release/%s/ipython-%s.tar.gz' % (ver, ver)
    get_file(url, 'ipython.tar.gz', path, debug)
    if  not is_installed(url, path):
        cmd = 'python setup.py install --prefix=%s/install' % path
        exe_cmd(os.path.join(path, 'ipython-%s' % ver), cmd, debug)

    print "Installing Routes"
    os.chdir(path)
    ver = '1.12.3'
    url = 'http://peak.telecommunity.com/dist/ez_setup.py'
    if  not is_installed(url, path):
        with open('ez_setup.py', 'w') as ez_setup:
             ez_setup.write(getdata(url, {}, debug))
    url = 'http://pypi.python.org/packages/source/R/Routes/Routes-%s.tar.gz' % ver
    get_file(url, 'routes.tar.gz', path, debug)
    if  not is_installed(url, path):
        cmd = 'cp ../ez_setup.py .; python setup.py install --prefix=%s/install' % path
        exe_cmd(os.path.join(path, 'Routes-%s' % ver), cmd, debug)
    
    print "Installing cmssh"
    url = 'http://github.com/vkuznet/cmssh/tarball/master/'
    get_file(url, 'cmssh.tar.gz', path, debug)
    if  not is_installed(url, path):
        cmd = 'mv vkuznet-cmssh* %s/cmssh' % path
        exe_cmd(path, cmd, debug)

    if  not opts.no_cmssw:
        print "Installing root"
        if  platform == 'Linux':
            url = 'ftp://root.cern.ch/root/root_v5.30.03.Linux-slc5-gcc4.3.tar.gz'
        elif platform == 'Darwin':
            url = 'ftp://root.cern.ch/root/root_v5.30.02.macosx106-x86_64-gcc-4.2.tar.gz'
        else:
            print 'Unsupported OS "%s"' % platform
            sys.exit(1)
        get_file(url, 'root.tar.gz', path, debug)

        print "Bootstrap CMSSW"
        sdir = '%s/CMSSW' % path
        try:
            os.makedirs(sdir)
        except:
            pass
        os.chdir(sdir)
        url  = 'http://cmsrep.cern.ch/cmssw/cms/bootstrap.sh'
        if  not is_installed(url, path):
            with open('bootstrap.sh', 'w') as bootstrap:
                 bootstrap.write(getdata(url, {}, debug))
            os.chmod('bootstrap.sh', 0755)
            os.environ['VO_CMS_SW_DIR'] = sdir
            os.environ['SCRAM_ARCH'] = arch
            os.environ['LANG'] = 'C'
            cmd  = 'sh -x $VO_CMS_SW_DIR/bootstrap.sh setup -path $VO_CMS_SW_DIR -arch $SCRAM_ARCH'
            if  unsupported_linux:
                cmd += ' -unsupported_distribution_hack'
            exe_cmd(sdir, cmd, debug)
            cmd  = 'source `find $VO_CMS_SW_DIR/$SCRAM_ARCH/external/apt -name init.sh`;'
            cmd += 'apt-get install external+fakesystem+1.0;'
            cmd += 'apt-get update'
            exe_cmd(sdir, cmd, debug)
    
#    print "Installing CRAB"
#    os.chdir(path)
#    crab_ver = 'CRAB_2_7_9'
#    url = 'http://cmsdoc.cern.ch/cms/ccs/wm/www/Crab/Docs/%s.tgz' % crab_ver
#    get_file(url, 'crab.tar.gz', path, debug)
#    cmd = 'cd %s; ./configure' % crab_ver
#    exe_cmd(path, cmd, debug)

    print "Create configuration"
    os.chdir(path)
    with open('setup.sh', 'w') as setup:
        msg  = '#!/bin/bash\nexport CMSSH_ROOT=%s\n' % path
        msg += 'export DYLD_LIBRARY_PATH=%s/globus/lib:%s/glite/lib:%s/install/lib:%s/root/lib\n' \
                % (path, path, path, path)
        msg += 'export LD_LIBRARY_PATH=%s/globus/lib:%s/glite/lib:%s/install/lib:%s/root/lib\n' \
                % (path, path, path, path)
        msg += 'export PATH=%s/globus/bin:$PATH\n' % path
        msg += 'export PATH=%s/glite/bin:$PATH\n' % path
        msg += 'export PATH=%s/srmclient2/bin:$PATH\n' % path
        msg += 'export PATH=%s/install/bin:$PATH\n' % path
        msg += 'export PATH=%s/bin:$PATH\n' % path
        msg += 'export PATH=%s/lcg/bin:$PATH\n' % path
        msg += 'export PATH=$PATH:%s/CRABClient/bin\n' % path
        msg += 'export PYTHONPATH=%s/cmssh/src\n' % path
        msg += 'export PYTHONPATH=$PYTHONPATH:%s\n' % path
        msg += 'export PYTHONPATH=$PYTHONPATH:%s/CRABClient/src/python\n' % path
        msg += 'export PYTHONPATH=$PYTHONPATH:%s/WMCore/src/python\n' % path
        msg += 'export PYTHONPATH=$PYTHONPATH:$PWD/soft/install/lib/python%s/site-packages\n' % py_ver
        if  not opts.no_cmssw:
            msg += 'export VO_CMS_SW_DIR=%s/CMSSW\n' % path
            msg += 'export SCRAM_ARCH=%s\n' % arch
            msg += 'export LANG="C"\n'
            msg += 'export CMSSW_RELEASES=%s/Releases\n' % path
            msg += 'if [ -f $VO_CMS_SW_DIR/cmsset_default.sh ]; then\n'
            msg += '   source $VO_CMS_SW_DIR/cmsset_default.sh\nfi\n'
            msg += 'source $VO_CMS_SW_DIR/$SCRAM_ARCH/external/apt/*/etc/profile.d/init.sh\n'
        msg += 'export DEFAULT_ROOT=%s/root\n' % path
        msg += 'export LCG_GFAL_INFOSYS=lcg-bdii.cern.ch:2170\n'
        msg += 'export VOMS_USERCONF=%s/glite/etc/vomses\n' % path
        msg += 'export VOMS_LOCATION=%s/glite\n' % path
        msg += 'export X509_CERT_DIR=%s/certificates\n' % path
        msg += 'export GLOBUS_ERROR_VERBOSE=true\n'
        msg += 'export GLOBUS_OPTIONS=-Xmx512M\n'
        msg += 'export GLOBUS_TCP_PORT_RANGE=34000,35000\n'
        msg += 'export GLOBUS_PATH=%s/globus\n' % path
        msg += 'export GLOBUS_LOCATION=%s/globus\n' % path
        msg += 'export VOMS_PROXY_INFO_DONT_VERIFY_AC=anything_you_want\n'
        if  debug:
            print "+++ write setup.sh"
        setup.write(msg)
    os.chmod('setup.sh', 0755)

    vomses = os.path.join(path, 'glite')
    print "Create vomses area"
    vdir = os.path.join(vomses, 'etc')
    os.makedirs(vdir)
    fname = os.path.join(vdir, 'vomses')
    with open(fname, 'w') as fds:
        msg = '"cms" "voms.fnal.gov" "15015" "/DC=org/DC=doegrids/OU=Services/CN=http/voms.fnal.gov" "cms"'
        fds.write(msg + '\n')
        msg = '"cms" "voms.cern.ch" "15002" "/DC=ch/DC=cern/OU=computers/CN=voms.cern.ch" "cms"'
        fds.write(msg + '\n')
        msg = '"cms" "lcg-voms.cern.ch" "15002" "/DC=ch/DC=cern/OU=computers/CN=lcg-voms.cern.ch" "cms"'
        fds.write(msg + '\n')

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
#grid-proxy-init
voms-proxy-init -voms cms:/cms -valid 24:00
ipython --no-banner --ipython-dir=$ipdir --profile=cmssh
""" % path
        cmssh.write(msg)
    os.chmod('bin/cmssh', 0755)

    print "Congratulations, cmssh is available at %s/bin/cmssh" % path

if __name__ == '__main__':
    main()
