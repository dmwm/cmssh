#!/usr/bin/env python

import os
import sys
from distutils.core import setup
sys.path.append(os.path.join(os.getcwd(), 'src'))
import cmssh

if sys.version_info < (2, 6):
    raise Exception("cmssh requires Python 2.6 or higher.")

def dirwalk(relativedir):
    """
    Walk a directory tree and look-up for __init__.py files.
    If found yield those dirs. Code based on
    http://code.activestate.com/recipes/105873-walk-a-directory-tree-using-a-generator/
    """
    dir = os.path.join(os.getcwd(), relativedir)
    for fname in os.listdir(dir):
        fullpath = os.path.join(dir, fname)
        if  os.path.isdir(fullpath) and not os.path.islink(fullpath):
            for subdir in dirwalk(fullpath):  # recurse into subdir
                yield subdir
        else:
            initdir, initfile = os.path.split(fullpath)
            if  initfile == '__init__.py':
                yield initdir

def find_packages(relativedir):
    """Find packages"""
    packages = [] 
    for dir in dirwalk(relativedir):
        package = dir.replace(os.getcwd() + '/', '')
        package = package.replace(relativedir + '/', '')
        package = package.replace('/', '.')
        packages.append(package)
    return packages

def main():
    """Main routine"""
    setup (
        name = "cmssh",
        version = "%s.%s" % (cmssh.__version__, cmssh.__revision__),
        description = "An interactive, programmable environment and shell for CMS",
        package_dir = {'cmssh':'src/cmssh'},
        data_files = [('config',['src/config/cmssh_extension.py','src/config/ipython_config.py'])],
        packages = find_packages('src'),
        long_description = "cmssh -- an interactive shell for CMS",
        classifiers = [
            'Environment :: Console',
            "Intended Audience :: Developers",
            'Intended Audience :: End Users/Desktop',
            'Intended Audience :: System Administrators',
            "License :: OSI Approved :: GNU License",
            'Operating System :: MacOS :: MacOS X',
            'Operating System :: Microsoft :: Windows',
            'Operating System :: POSIX',
            "Programming Language :: Python",
            "Topic :: Database :: Front-Ends",
        ],
        requires = ['python (>=2.6)', 'ipython (>=0.11)'],
        author = "Valentin Kuznetsov",
        author_email = "vkuznet@gmail.com",
        url = "https://twiki.cern.ch/twiki/bin/view/CMS/",
        license = "GNU License",
    )

if __name__ == '__main__':
    main()
