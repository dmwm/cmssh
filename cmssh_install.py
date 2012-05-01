#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
File       : cmssh_install.py
Author     : Valentin Kuznetsov [ vkuznet AT gmail DOT com ]
Description: cmssh installation script

Some useful URLs
http://www.globus.org/ftppub/gt5/5.0/5.0.4/installers/src/gt5.0.4-all-source-installer.tar.bz2
http://www.nikhef.nl/pub/projects/grid/gridwiki/index.php/Using_voms-proxy-init_on_an_OSX_(10.4_or_higher)_system
https://twiki.grid.iu.edu/bin/view/ReleaseDocumentation/VomsInstallGuide

"""

# system modules
import os
import re
import sys
import stat
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

if  os.uname()[0] == 'Darwin':
    DEF_SCRAM_ARCH = 'osx106_amd64_gcc421'
elif os.uname()[0] == 'Linux':
    if  os.uname()[-1] == 'x86_64':
        DEF_SCRAM_ARCH = 'slc5_amd64_gcc462'
    else:
        DEF_SCRAM_ARCH = 'slc5_ia32_gcc434'
    # test presence of readline
    readline = os.path.realpath('/usr/lib/libreadline.so')
    if  readline.find('so.5') == -1:
        msg  = 'cmssh on Linux requires readline5. Please verify that'
        msg += ' you have it installed on your system. So far we found\n'
        msg += '/usr/lib/libreadline.so -> %s' % readline
        raise Exception(msg)
else:
    print 'Unsupported platform'
    sys.exit(1)

# The 2.6.4 version of CMSSW python has bug in OpenSSL
# see https://hypernews.cern.ch/HyperNews/CMS/get/sw-develtools/1667/1.html
# We need to avoid it, otherwise usage of HTTPS will be broken
# So, the osx106_amd64_gcc462 has broken python 2.6.4
# the osx106_amd64_gcc461 has correct python 2.6.4, but broken 2.6.4-cmsX
# the osx106_amd64_gcc421 has corrent python 2.6.4, but it picks root 5.30.02
# which does not have pyROOT library
def find_root_package(apt, debug=None):
    """
    Find latest version of root package in CMSSW repository.
    For time being I veto all -cms packages due to bug in python w/ SSL.
    """
    cmd  = apt + 'apt-cache search root | grep "lcg+root" | grep -v toolfile '
    cmd += "| grep -v cms | tail -1 | awk '{print $1}'"
    if  debug:
        print cmd
    res  = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    root = res.stdout.read().replace('\n', '').strip()
    if  os.uname()[0] == 'Darwin': # OSX python has issues with SSL, will take fixed release
        root = 'lcg+root+5.30.02-cms4'
    return root

def matplotlib_package(apt, debug=None):
    """
    Find latest version of matplotlib package in CMSSW repository.
    """
    cmd  = apt + 'apt-cache search matplotlib | grep "matplotlib" | grep -v toolfile '
    cmd += "| grep -v cms | tail -1 | awk '{print $1}'"
    if  debug:
        print cmd
    res  = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    root = res.stdout.read().replace('\n', '').strip()
    if  os.uname()[0] == 'Darwin': # stay in sync w/ lcg+root on OSX
        root = 'external+py2-matplotlib+1.0.1-cms3'
    return root

def libpng_package(apt, debug=None):
    """
    Find latest version of libpng package in CMSSW repository.
    """
    cmd  = apt + 'apt-cache search matplotlib | grep "matplotlib" | grep -v toolfile '
    cmd += "| grep -v cms | tail -1 | awk '{print $1}'"
    if  debug:
        print cmd
    res  = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    root = res.stdout.read().replace('\n', '').strip()
    if  os.uname()[0] == 'Darwin': # stay in sync w/ lcg+root on OSX
        root = 'external+libpng+1.2.10'
    return root

def available_architectures():
    "Fetch CMSSW drivers"
    arch = os.uname()[0]
    pat1 = re.compile('.*-driver.txt</a>.*')
    pat2 = re.compile('^[osx,slc].*') 
    url  = 'http://cmsrep.cern.ch/cmssw/cms/'
    data = urllib2.urlopen(url)
    drivers = []
    for line in data.readlines():
        if  pat1.match(line):
            line = line.split('</a>')[0].split('">')[-1]
            if  pat2.match(line):
                if  arch == 'Linux' and line[:3] == 'slc':
                    yield line.replace('-driver.txt', '')
                elif arch == 'Darwin' and line[:3] == 'osx':
                    yield line.replace('-driver.txt', '')

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
        self.parser.add_option("--dev", action="store_true",
            dest="master", help="get cmssh code from development branch")
        drivers = ', '.join(available_architectures())
        self.parser.add_option("--arch", action="store",
            type="string", default=None, dest="arch",
            help="CMSSW architectures:\n%s, default %s" % (drivers, DEF_SCRAM_ARCH))
        self.parser.add_option("--cmssw", action="store",
            type="string", default=None, dest="cmssw",
            help="specify location of CMSSW install area")
        self.parser.add_option("--multi-user", action="store_true",
            default=False, dest="multi_user",
            help="install cmssh in multi-user environment")
        self.parser.add_option("--unsupported", action="store_true",
            dest="unsupported",
            help="enforce installation on unsupported platforms, e.g. Ubuntu")

    def get_opt(self):
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
    if  os.path.isfile(fname):
        with open(fname, 'r') as packages:
            for line in packages.readlines():
                if  url == line.replace('\n', ''):
                    return True
    return False

def add_url2packages(url, path):
    "Add url to packages file"
    with open(os.path.join(path, '.packages'), 'a') as packages:
        packages.write(url + '\n')

def get_file(url, fname, path, debug, check=True):
    """Fetch tarball from given url and store it as fname, untar it into given path"""
    os.chdir(path)
    with open(fname, 'w') as tar_file:
         tar_file.write(getdata(url, {}, debug))
    tar = tarfile.open(fname, 'r:gz')
    top_names = set([r.split('/')[0] for r in tar.getnames()])
    if  len(top_names) == 1:
        dir_name = top_names.pop()
        if  os.path.isdir(dir_name):
            try:
                os.removedirs(dir_name)
            except:
                pass
    tar.extractall(path)
    tar.close()
    add_url2packages(url, path)

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

def check_system(unsupported):
    "Check system requirements"
    # check presence of Java, required for GRID middleware
    if  not os.environ.has_key('JAVA_HOME'):
        print "JAVA_HOME environment is required to install GRID middleware tools"
        print "Please install Java and appropriately setup JAVA_HOME"
        print "For example, export JAVA_HOME=/usr"
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
            print msg
            sys.exit(1)

def main():
    mgr = MyOptionParser()
    opts, args = mgr.get_opt()

    platform = os.uname()[0]
    if  platform == 'Darwin':
        if  not os.environ.has_key('JAVA_HOME'):
            os.environ['JAVA_HOME'] = '/Library/Java/Home'
    elif platform == 'Linux':
        if  not os.environ.has_key('JAVA_HOME'):
            if  os.path.isfile('/usr/bin/java') or os.path.islink('/usr/bin/java'):
                os.environ['JAVA_HOME'] = '/usr'
            elif os.path.isfile('/usr/local/bin/java') or os.path.islink('/usr/local/bin/java'):
                os.environ['JAVA_HOME'] = '/usr/local'
            elif os.path.isfile('/opt/local/bin/java') or os.path.islink('/opt/local/bin/java'):
                os.environ['JAVA_HOME'] = '/opt/local'

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
    sysver = sys.version_info
    py_ver = '%s.%s' % (sysver[0], sysver[1])
    install_dir = '%s/install/lib/python%s/site-packages' % (path, py_ver)
    os.environ['PYTHONPATH'] = install_dir
    try:
        os.makedirs(install_dir)
    except:
        pass

    # setup platform and unsupported flag
    unsupported_linux = False
    if  os.uname()[3].find('Ubuntu') != -1 or opts.unsupported:
        unsupported_linux = True

    # setup system architecture
    parch = 'x86'
    arch  = opts.__dict__.get('arch', None)
    if  platform == 'Linux':
        if  unsupported_linux:
            ver = 'deb_5.0'
        else:
            ver = 'rhap_5'
        if  not arch:
            arch = DEF_SCRAM_ARCH
    elif platform == 'Darwin':
        ver  = 'macos_10.4'
        if  not arch:
            arch = DEF_SCRAM_ARCH
    else:
        print 'Unsupported OS "%s"' % platform
        sys.exit(1)
    if  not arch:
        print "Unsupported architecture"
        sys.exit(1)

    print 'Checking CMSSW ...'
    if  debug:
        print 'Probe architecture', arch
    os.chdir(path)
    os.environ['LANG'] = 'C'
    use_matplotlib = False
    sdir = '%s/CMSSW' % path

    if  opts.cmssw:
        # check if default architecture is present
        if  arch in os.listdir(opts.cmssw):
            os.symlink(opts.cmssw, sdir)
            os.environ['SCRAM_ARCH'] = arch
            os.environ['VO_CMS_SW_DIR'] = sdir
            if  os.path.isdir('%s/%s/external/py2-matplotlib' % (sdir, arch)):
                cmd = 'find $VO_CMS_SW_DIR/$SCRAM_ARCH/external/py2-matplotlib -name init.sh | tail -1'
                res = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
                mat = res.stdout.read().replace('\n', '').strip()
                if  mat.find('init.sh') != -1:
                    use_matplotlib = True
            if  debug:
                print 'Will use %s/%s' % (sdir, arch)
        else:
            print "Please supply via --arch the architecture from %s you wish to use"\
                % opts.cmssh 
            sys.exit(1)
    else: # do local CMSSW bootstrap
        try:
            os.makedirs(sdir)
        except:
            pass
        os.chdir(sdir)
        os.environ['VO_CMS_SW_DIR'] = sdir
        os.environ['SCRAM_ARCH'] = arch
        url  = 'http://cmsrep.cern.ch/cmssw/cms/bootstrap.sh'
        if  not is_installed(url, path):
            with open('bootstrap.sh', 'w') as bootstrap:
                 bootstrap.write(getdata(url, {}, debug))
            if  os.uname()[0].lower() == 'linux':
                os.rename('bootstrap.sh', 'b.sh')
                cmd = 'cat b.sh | sed "s,\$seed \$unsupportedSeeds,\$seed \$unsupportedSeeds libreadline5,g" > bootstrap.sh'
                res = subprocess.call(cmd, shell=True)
            os.chmod('bootstrap.sh', 0755)
            cmd  = 'sh -x $VO_CMS_SW_DIR/bootstrap.sh setup -path $VO_CMS_SW_DIR -arch $SCRAM_ARCH'
            if  unsupported_linux:
                cmd += ' -unsupported_distribution_hack'
            exe_cmd(sdir, cmd, debug, 'Bootstrap CMSSW')
            apt  = 'source `find $VO_CMS_SW_DIR/$SCRAM_ARCH/external/apt -name init.sh | tail -1`; '
            cmd  = apt
            cmd += 'apt-get install external+fakesystem+1.0; '
            cmd += 'apt-get update; '
            exe_cmd(sdir, cmd, debug, 'Init CMSSW apt repository')
            root = find_root_package(apt, debug)
            cmd  = apt + 'echo "Y" | apt-get install %s' % root
            exe_cmd(sdir, cmd, debug, 'Install %s' % root)
            root = libpng_package(apt, debug)
            cmd  = apt + 'echo "Y" | apt-get install %s' % root 
            exe_cmd(sdir, cmd, debug, 'Install libpng')
            root = matplotlib_package(apt, debug)
            cmd  = apt + 'echo "Y" | apt-get install %s' % root 
            exe_cmd(sdir, cmd, debug, 'Install matplotlib')
            use_matplotlib = True
            add_url2packages(url, path)

    # command to setup CMSSW python
    find_python = 'find $VO_CMS_SW_DIR/$SCRAM_ARCH/external/python -name init.sh | tail -1'
    res = subprocess.Popen(find_python, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cms_python_env = res.stdout.read().replace('\n', '').strip()
    if  not cms_python_env.find('init.sh') != -1:
        msg  = '\nUnable to locate python in:'
        msg += '\n%s/%s/external/python' % (os.environ['VO_CMS_SW_DIR'], os.environ['SCRAM_ARCH'])
        msg += '\nPlease check CMSSW area and/or choose another architecture\n'
        print msg
        sys.exit(1)
    pver     = '.'.join(cms_python_env.split('/')[-4].split('.')[0:2])
    cms_env  = 'source `%s`;' % find_python 
    if  debug:
        print "CMSSW python:", cms_python_env
        print "python version", pver

    print "Installing Globus"
    os.chdir(path)
    url = 'http://vdt.cs.wisc.edu/software/globus/4.0.8_VDT2.0.0gt4nbs/vdt_globus_essentials-VDT2.0.0-3-%s_%s.tar.gz' % (parch, ver)
    if  not is_installed(url, path):
        get_file(url, 'globus.tar.gz', path, debug)

    print "Installing Myproxy"
    url = 'http://vdt.cs.wisc.edu/software/myproxy/5.3_VDT-2.0.0/myproxy_client-5.3-%s_%s.tar.gz' % (parch, ver)
    if  not is_installed(url, path):
        get_file(url, 'myproxy_client.tar.gz', path, debug)
    url = 'http://vdt.cs.wisc.edu/software/myproxy/5.3_VDT-2.0.0/myproxy_essentials-5.3-%s_%s.tar.gz' % (parch, ver)
    if  not is_installed(url, path):
        get_file(url, 'myproxy_essentials.tar.gz', path, debug)

    print "Installing VOMS"
    url = 'http://vdt.cs.wisc.edu/software/voms/1.8.8-2p1-1/voms-client-1.8.8-2p1-%s_%s.tar.gz' % (parch, ver)
    if  not is_installed(url, path):
        get_file(url, 'voms-client.tar.gz', path, debug)
    url = 'http://vdt.cs.wisc.edu/software/voms/1.8.8-2p1-1/voms-essentials-1.8.8-2p1-%s_%s.tar.gz' % (parch, ver)
    if  not is_installed(url, path):
        get_file(url, 'voms-essentials.tar.gz', path, debug)

    print "Installing expat"
    ver = '2.0.1'
    url = 'http://sourceforge.net/projects/expat/files/expat/2.0.1/expat-%s.tar.gz/download?use_mirror=iweb' % ver
    if  not is_installed(url, path):
        get_file(url, 'expat-%s.tar.gz' % ver, path, debug)
        cmd = 'CFLAGS=-m32 ./configure --prefix=%s/install; make; make install' % path
        os.chdir(os.path.join(path, 'expat-%s' % ver))
        exe_cmd(os.path.join(path, 'expat-%s' % ver), cmd, debug)

    print "Installing PythonUtilities"
    url = "http://cmssw.cvs.cern.ch/cgi-bin/cmssw.cgi/CMSSW/FWCore/PythonUtilities.tar.gz?view=tar"
    if  not is_installed(url, path):
        get_file(url, 'PythonUtilities.tar.gz', path, debug)
        cmd = 'touch __init__.py; mv python/*.py .'
        exe_cmd(os.path.join(path, 'PythonUtilities'), cmd, debug)
        os.chdir(path)
        cmd = 'mkdir FWCore; touch FWCore/__init__.py; mv PythonUtilities FWCore'
        exe_cmd(path, cmd, debug)

#    print "Installing CRAB3"
#    ver = '3.0.6a'
#    url = 'http://cmsrep.cern.ch/cmssw/comp/SOURCES/slc5_amd64_gcc461/cms/crab-client3/%s/crabclient3.tar.gz' % ver
#    if  not is_installed(url, path):
#        get_file(url, 'crabclient3.tar.gz', path, debug)

#    print "Installing CRAB"
#    os.chdir(path)
#    crab_ver = 'CRAB_2_7_9'
#    url = 'http://cmsdoc.cern.ch/cms/ccs/wm/www/Crab/Docs/%s.tgz' % crab_ver
#    get_file(url, 'crab.tar.gz', path, debug)
#    cmd = 'cd %s; ./configure' % crab_ver
#    exe_cmd(path, cmd, debug)


    print "Installing WMCore"
    ver = '0.8.21'
    url = 'http://cmsrep.cern.ch/cmssw/comp/SOURCES/slc5_amd64_gcc461/cms/wmcore/%s/WMCORE.tar.gz' % ver
    if  not is_installed(url, path):
        get_file(url, 'wmcore.tar.gz', path, debug)

    print "Installing LCG info"
    url = 'http://vdt.cs.wisc.edu/software/lcg-infosites/2.6-2/lcg-infosites-2.6-2.tar.gz'
    if  not is_installed(url, path):
        get_file(url, 'lcg-infosites.tar.gz', path, debug)
    url = 'http://vdt.cs.wisc.edu/software/lcg-info//1.11.4-1/lcg-info-1.11.4-1.tar.gz'
    if  not is_installed(url, path):
        get_file(url, 'lcg-info.tar.gz', path, debug)

    print "Installing certificates"
    url = 'http://vdt.cs.wisc.edu/software/certificates/62/certificates-62-1.tar.gz'
    if  not is_installed(url, path):
        get_file(url, 'certificates.tar.gz', path, debug)

    print "Installing SRM client"
    ver = '2.2.1.3.19'
    url = 'http://vdt.cs.wisc.edu/software/srm-client-lbnl/%s/srmclient2-%s.tar.gz' \
        % (ver, ver)
    if  not is_installed(url, path):
        get_file(url, 'srmclient.tar.gz', path, debug)
        cmd  = cms_env + './configure --with-java-home=$JAVA_HOME --enable-clientonly'
        cmd += ' --with-globus-location=%s/globus' % path
        cmd += ' --with-cacert-path=%s/certificates' % path
        exe_cmd(os.path.join(path, 'srmclient2/setup'), cmd, debug)

    print "Installing pip"
    os.chdir(path)
    url = 'https://raw.github.com/pypa/virtualenv/master/virtualenv.py'
    if  not is_installed(url, path):
        with open('virtualenv.py', 'w') as fname:
            fname.write(getdata(url, {}, debug))
        cmd = cms_env + 'python %s/virtualenv.py %s/install' % (path, path)
        exe_cmd(path, cmd, debug)

    print "Installing IPython"
    cmd = cms_env + '%s/install/bin/pip install --upgrade ipython' % path
    exe_cmd(path, cmd, debug)

    print "Installing Routes"
    cmd = cms_env + '%s/install/bin/pip install --upgrade Routes' % path
    exe_cmd(path, cmd, debug)

    print "Installing decorator"
    cmd = cms_env + '%s/install/bin/pip install --upgrade decorator' % path
    exe_cmd(path, cmd, debug)

    print "Installing readline"
    ver = '6.2.2'
    url = 'http://pypi.python.org/packages/source/r/readline/readline-%s.tar.gz' % ver
    if  platform == 'Darwin' and not is_installed(url, path):
        get_file(url, 'readline.tar.gz', path, debug)
        cmd = """#!/bin/bash
export CMSSH_ROOT={path}
export VO_CMS_SW_DIR=$CMSSH_ROOT/CMSSW
export SCRAM_ARCH={arch}
export LANG="C"
source `find $VO_CMS_SW_DIR/$SCRAM_ARCH/external/python -name init.sh | tail -1`
idir={path}/install
mkdir -p $idir/lib/python{pver}/site-packages
export PYTHONPATH=$PYTHONPATH:$CMSSH_ROOT/install/lib/python{pver}/site-packages:$idir/lib/python{pver}/site-packages
python setup.py install --prefix=$idir
export CFLAGS='-arch x86_64'
export LDFLAGS='-arch x86_64'
cd readline
./configure CPPFLAGS='-DNEED_EXTERN_PC -fPIC'
make
cd -
python setup.py install --prefix=$idir
""".format(path=path, arch=arch, pver=pver)
#        rpath = '%s/install/lib/python2.6/site-packages' % path
#        cmd  = cms_env + 'mkdir -p %s; export PYTHONPATH=$PYTHONPATH:%s;' % (rpath, rpath)
#        cmd += 'python setup.py install --prefix=%s/install' % path
        exe_cmd(os.path.join(path, 'readline-%s' % ver), cmd, debug)

    print "Installing httplib2"
    cmd = cms_env + '%s/install/bin/pip install --upgrade httplib2' % path
    exe_cmd(path, cmd, debug)

    print "Installing paramiko"
    cmd = cms_env + '%s/install/bin/pip install --upgrade paramiko' % path
    exe_cmd(path, cmd, debug)

    print "Installing cmssh"
    os.chdir(path)
    try:
        cmd = 'rm -rf vkuznet-cmssh*; rm -rf cmssh'
        exe_cmd(path, cmd, debug)
    except:
        pass
    try:
        cmd = 'rm -rf .ipython'
        exe_cmd(path, cmd, debug)
    except:
        pass
    if  opts.master:
        url = 'http://github.com/vkuznet/cmssh/tarball/master/'
    else:
        url = 'http://github.com/vkuznet/cmssh/tarball/v0.21/'
    get_file(url, 'cmssh.tar.gz', path, debug, check=False)
    cmd = 'mv vkuznet-cmssh* %s/cmssh' % path
    exe_cmd(path, cmd, debug)

    print "Create matplotlibrc"
    os.chdir(path)
    ndir = os.path.join(os.getcwd(), 'install/lib/python%s/site-packages/matplotlib/mpl-data' % py_ver)
    try:
        os.makedirs(ndir)
    except:
        pass
    fin  = '%s/cmssh/src/config/matplotlibrc' % path
    fout = '%s/install/lib/python%s/site-packages/matplotlib/mpl-data/matplotlibrc' % (path, py_ver)
    with open(fout, 'w') as output:
        with open(fin, 'r') as config:
            for line in config.readlines():
                if  line.find('backend : MacOSX') != -1:
                    if  platform == 'Linux':
                        output.write('#backend : GTK')
                else:
                    output.write(line)

    print "Create configuration"
    os.chdir(path)
    with open('setup.sh', 'w') as setup:
        msg  = '#!/bin/bash\nexport CMSSH_ROOT=%s\n' % path
        msg += 'export VO_CMS_SW_DIR=$CMSSH_ROOT/CMSSW\n'
        msg += 'export SCRAM_ARCH=%s\n' % arch
        msg += 'export LANG="C"\n'
        if  not opts.multi_user:
            msg += 'export CMSSW_RELEASES=$CMSSH_ROOT/Releases\n'
        msg += 'if [ -f $VO_CMS_SW_DIR/cmsset_default.sh ]; then\n'
        msg += '   source $VO_CMS_SW_DIR/cmsset_default.sh\nfi\n'
        msg += 'export OLD_PATH=$PATH\n'
        msg += 'apt_init=`find $VO_CMS_SW_DIR/$SCRAM_ARCH/external/apt -name init.sh | tail -1`\n'
        msg += 'pcre_init=`find $VO_CMS_SW_DIR/$SCRAM_ARCH/external/pcre -name init.sh | tail -1`\n'
        msg += 'xz_init=`find $VO_CMS_SW_DIR/$SCRAM_ARCH/external/xz -name init.sh | tail -1`\n'
        msg += 'png_init=`find $VO_CMS_SW_DIR/$SCRAM_ARCH/external/libpng -name init.sh | tail -1`\n'
        msg += 'lapack_init=`find $VO_CMS_SW_DIR/$SCRAM_ARCH/external/lapack -name init.sh | tail -1`\n'
        msg += 'numpy_init=`find $VO_CMS_SW_DIR/$SCRAM_ARCH/external/py2-numpy -name init.sh | tail -1`\n'
        msg += 'matplotlib_init=`find $VO_CMS_SW_DIR/$SCRAM_ARCH/external/py2-matplotlib -name init.sh | tail -1`\n'
        msg += 'export PATH=/usr/bin:/bin:/usr/sbin:/sbin\n'
        msg += 'unset PYTHONPATH\n'
        msg += 'source $apt_init;\n'
        msg += 'source %s\n' % cms_python_env.replace(sdir, '$CMSSH_ROOT/CMSSW').replace(arch, '$SCRAM_ARCH')
        msg += 'source $xz_init;source $pcre_init;\n'
        msg += 'source $matplotlib_init;source $numpy_init;source $lapack_init;source $png_init\n'
        msg += 'export DYLD_LIBRARY_PATH=$CMSSH_ROOT/globus/lib:$CMSSH_ROOT/glite/lib:$CMSSH_ROOT/install/lib\n'
        msg += 'export LD_LIBRARY_PATH=$CMSSH_ROOT/globus/lib:$CMSSH_ROOT/glite/lib:$CMSSH_ROOT/install/lib:$LD_LIBRARY_PATH\n'
        msg += 'export PATH=$VO_CMS_SW_DIR/bin:$CMSSH_ROOT/install/bin:$PATH\n'
        msg += 'export PATH=$PATH:$CMSSH_ROOT/globus/bin\n'
        msg += 'export PATH=$PATH:$CMSSH_ROOT/glite/bin\n'
        msg += 'export PATH=$PATH:$CMSSH_ROOT/srmclient2/bin\n'
        msg += 'export PATH=$PATH:$CMSSH_ROOT/bin\n'
        msg += 'export PATH=$PATH:$CMSSH_ROOT/lcg/bin\n'
        msg += 'export PATH=$PATH:$CMSSH_ROOT/CRABClient/bin\n'
        msg += 'export PYTHONPATH=$CMSSH_ROOT/cmssh/src:$PYTHONPATH\n'
        msg += 'export PYTHONPATH=$ROOTSYS/lib:$PYTHONPATH\n'
        msg += 'export PYTHONPATH=$PYTHONPATH:$CMSSH_ROOT\n'
        msg += 'export PYTHONPATH=$PYTHONPATH:$CMSSH_ROOT/CRABClient/src/python\n'
        msg += 'export PYTHONPATH=$PYTHONPATH:$CMSSH_ROOT/WMCore/src/python\n'
        msg += 'export PYTHONPATH=$PWD/soft/install/lib/python%s/site-packages:$PYTHONPATH\n' % py_ver
        msg += 'export DBS_INSTANCE=cms_dbs_prod_global\n'
        msg += 'export LCG_GFAL_INFOSYS=lcg-bdii.cern.ch:2170\n'
        msg += 'export VOMS_USERCONF=$CMSSH_ROOT/glite/etc/vomses\n'
        msg += 'export VOMS_LOCATION=$CMSSH_ROOT/glite\n'
        msg += 'export MYPROXY_SERVER=myproxy.cern.ch\n'
        msg += 'export X509_CERT_DIR=$CMSSH_ROOT/certificates\n'
        msg += 'export GLOBUS_ERROR_VERBOSE=true\n'
        msg += 'export GLOBUS_OPTIONS=-Xmx512M\n'
        msg += 'export GLOBUS_TCP_PORT_RANGE=34000,35000\n'
        msg += 'export GLOBUS_PATH=$CMSSH_ROOT/globus\n'
        msg += 'export GLOBUS_LOCATION=$CMSSH_ROOT/globus\n'
        msg += 'export VOMS_PROXY_INFO_DONT_VERIFY_AC=anything_you_want\n'
        msg += 'export MATPLOTLIBRC=$CMSSH_ROOT/install/lib/python%s/site-packages/matplotlib/mpl-data\n' % py_ver
        if  debug:
            print "+++ write setup.sh"
        setup.write(msg)
    os.chmod('setup.sh', 0755)

    vomses = os.path.join(path, 'glite')
    print "Create vomses area"
    vdir = os.path.join(vomses, 'etc')
    try:
        os.makedirs(vdir)
    except:
        pass
    fname = os.path.join(vdir, 'vomses')
    with open(fname, 'w') as fds:
        msg = '"cms" "voms.fnal.gov" "15015" "/DC=org/DC=doegrids/OU=Services/CN=http/voms.fnal.gov" "cms"'
        fds.write(msg + '\n')
        msg = '"cms" "voms.cern.ch" "15002" "/DC=ch/DC=cern/OU=computers/CN=voms.cern.ch" "cms"'
        fds.write(msg + '\n')
        msg = '"cms" "lcg-voms.cern.ch" "15002" "/DC=ch/DC=cern/OU=computers/CN=lcg-voms.cern.ch" "cms"'
        fds.write(msg + '\n')
    os.chmod(fname, stat.S_IRUSR)

    print "Create cmssh"
    try:
        os.makedirs(os.path.join(path, 'bin'))
    except:
        pass
    with open(os.path.join(path, 'bin/cmssh'), 'w') as cmssh:
        msg  = '#!/bin/bash\n'
        msg += 'source %s/setup.sh\n' % path
        if  opts.multi_user:
            msg += 'ipdir="/tmp/$USER/.ipython"\nmkdir -p $ipdir\n'
        else:
            msg += 'ipdir="%s/.ipython"\nmkdir -p $ipdir\n' % path
        msg += """
soft_dir=%s
if [ ! -d $ipdir/extensions ]; then
    mkdir -p $ipdir/extensions
fi
if [ ! -d $ipdir/profile_cmssh ]; then
    mkdir -p $ipdir/profile_cmssh
fi
if [ ! -f $ipdir/extensions/cmssh_extension.py ]; then
    cp $soft_dir/cmssh/src/config/cmssh_extension.py $ipdir/extensions/
fi
if [ ! -f $ipdir/profile_cmssh/ipython_config.py ]; then
    cp $soft_dir/cmssh/src/config/ipython_config.py $ipdir/profile_cmssh/
fi
if [ ! -f $HOME/.globus/userkey.pem ]; then
    echo "You don't have $HOME/.globus/userkey.pem on this system"
    echo "Please install it to proceed"
    exit -1
fi
if [ ! -f $HOME/.globus/usercert.pem ]; then
    echo "You don't have $HOME/.globus/usercert.pem on this system"
    echo "Please install it to proceed"
    exit -1
fi
export IPYTHON_DIR=$ipdir
""" % path
        flags = '--no-banner'
        if  use_matplotlib:
            if  platform == 'Darwin':
                flags += ' --pylab=osx'
            else:
                flags += ' --pylab'
            flags += ' --InteractiveShellApp.pylab_import_all=False'
        msg += 'ipython %s --ipython-dir=$ipdir --profile=cmssh' % flags
        cmssh.write(msg)
    os.chmod('bin/cmssh', 0755)

    print "Clean-up ..."
    os.chdir(path)
    res = subprocess.call("rm *.tar.gz", shell=True)

    print "Congratulations, cmssh is available at %s/bin/cmssh" % path

if __name__ == '__main__':
    main()
