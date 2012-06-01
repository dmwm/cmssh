#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
File: cmssw_utils.py
Author: Valentin Kuznetsov <vkuznet@gmail.com>
Description: CMSSW utilities
"""

# system modules
import os

def remote_script(user, rel, cmd='crab -status'):
    "Generate script to setup CMSSW release area"
    cert = ""
    fname = '/tmp/x509up_u%s' % os.getuid()
    with open(fname, 'r') as x509:
        cert = x509.read()
    script = """node=`uname -n`
uid=`id -u`
fname=/tmp/x509up_u$uid
echo "Launch job on $node, uid=$uid"
source /afs/cern.ch/cms/LCG/LCG-2/UI/cms_ui_env.sh
cat > $fname << EOF
%(cert)s
EOF
chmod og-rwx $fname
#voms-proxy-init -voms cms
voms-proxy-info
mkdir -p /tmp/%(user)s
cd /tmp/%(user)s
echo "Setup new scram area in $PWD"
scramv1 project CMSSW %(rel)s
cd %(rel)s/src
echo "Untar cmssh tarball"
tar xfz /tmp/%(user)s/cmssh.tar.gz
echo "Content of work area $PWD"
ls
eval `scramv1 runtime -sh`
echo "Build local stuff"
scram b
echo "Setup CRAB client environment"
source /afs/cern.ch/cms/ccs/wm/scripts/Crab/crab.sh
%(cmd)s
/bin/rm -f $fname
""" % dict(cert=cert, user=user, rel=rel, cmd=cmd)
    return script

def crabconfig():
    "Create CRAB2 cfg file"
    content = """# Example of CRAB cfg file, http://bit.ly/JRo4jS
[CRAB]
jobtype = cmssw
use_server = 1
scheduler = glidein

[CMSSW]
# mandatory parameters (replace with your settings)
datasetpath = /TT_TuneZ2_7TeV-mcatnlo/Fall11-PU_S6_START42_V14B-v1/AODSIM
pycfg_params = outputFile=myoutput.root
pset = /afs/cern.ch/work/v/valya/public/CMSSW_4_2_8/src/TopDilLikeSelection_cfg.py

total_number_of_events = -1
events_per_job = 30000
get_edm_output = 1

[USER]
# please fill out your email
#eMail = YOUR_EMAIL@DOMAIN.COM
copy_data = 1
storage_element = T1_US_FNAL_Buffer
thresholdLevel=95
check_user_remote_dir = 0

# if you want to publish your data use publish_data = 1 and provide
# suitable dataset name and DBS instance, otherwise leave as is
# and it will not be published
publish_data = 0
publish_data_name = MCTSusy_Skim_Mar2012
dbs_url_for_publication = https://cmsdbsprod.cern.ch:8443/cms_dbs_ph_analysis_01_writer/servlet/DBSServlet

[GRID]
#ce_black_list = T2_ES_IFCA
"""
    return content
def edmconfig(release, lfnlist, evtlist, ofname, prefix=None):
    """
    Generate EDM config file template.

    :Parameters:
      - `release`: CMSSW release name, e.g. CMSSW_5_0_0
      - `lfnlist`: list of LFN files
      - `evtlist`: list of events in a form of [(run, evt, lumi), ...]
      - `ofname` :  output file name
    """
    if  not lfnlist:
        return ''
    if  isinstance(lfnlist, list):
        newlist = []
        for lfn in lfnlist:
            if  os.path.isfile(lfn):
                lfn = 'file:///' + lfn
            newlist.append(lfn)
        lfnlist = newlist
    else:
        if  os.path.isfile(lfnlist):
            lfnlist = ['file:///%s' % lfnlist]
        else:
            lfnlist = [lfnlist]
    if  prefix:
        files = ','.join(["'%s/%s'" \
                % (prefix, f.split('/')[-1]) for f in lfnlist])
    else:
        files = str(lfnlist).replace('[', '').replace(']', '')
    events = ""
    for run, event, lumi in evtlist:
        events += "'%s:%s'," % (run, event)
    events = events[:-1] # to remove last comma
    if  release < 'CMSSW_1_6':
        return None, None # no support for that release series
    elif  release < 'CMSSW_2_1':
        config = """process PICKEVENTS =
{
    include "FWCore/MessageService/data/MessageLogger.cfi"
    replace MessageLogger.cerr.threshold = "WARNING"
    source = PoolSource {
        untracked vstring fileNames = { %s }
        untracked VEventID eventsToProcess= { %s }
    }
    module out = PoolOutputModule
    {
        untracked string fileName = '%s'
    }
    endpath outpath = { out }
}
""" % (files, events.replace("'",""), ofname)
    elif release < 'CMSSW_3_1_0':
        config = """import FWCore.ParameterSet.Config as cms

process = cms.Process("PICKEVENTS")

process.source = cms.Source("PoolSource",
    fileNames = cms.untracked.vstring( %s ), 
    eventsToProcess = cms.untracked.VEventID( %s )
)

process.Out = cms.OutputModule("PoolOutputModule",
    outputCommands = cms.untracked.vstring('keep *'),
    fileName = cms.untracked.string('%s')
)

process.e = cms.EndPath(process.Out)

process.maxEvents = cms.untracked.PSet(
    input = cms.untracked.int32(-1)
)
""" % (files, events, ofname)
    else:
        config = """import FWCore.ParameterSet.Config as cms

process = cms.Process("PICKEVENTS")

process.source = cms.Source("PoolSource",
    fileNames = cms.untracked.vstring( %s ), 
    eventsToProcess = cms.untracked.VEventRange( %s )
)

process.Out = cms.OutputModule("PoolOutputModule",
    outputCommands = cms.untracked.vstring('keep *'),
    fileName = cms.untracked.string('%s')
)

process.e = cms.EndPath(process.Out)

process.maxEvents = cms.untracked.PSet(
    input = cms.untracked.int32(-1)
)
""" % (files, events, ofname)
    config = '# %s\n\n%s' % (release, config)
    return config
