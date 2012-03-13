#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
File: cmssw_utils.py
Author: Valentin Kuznetsov <vkuznet@gmail.com>
Description: CMSSW utilities
"""

# system modules
import os

def cmssw_rel(user, rel):
    "Generate script to setup CMSSW release area"
    script = """echo "Setup user proxy"
source /afs/cern.ch/cms/LCG/LCG-2/UI/cms_ui_env.sh
voms-proxy-init -voms cms
mkdir -p /tmp/%(user)s
cd /tmp/%(user)s
echo "Setup new scram area in $PWD"
scramv1 project CMSSW %(rel)s
cd %(rel)s
echo "Content of work area $PWD"
ls
eval `scramv1 runtime -sh`
echo "Setup CRAB client environment"
source /afs/cern.ch/cms/ccs/wm/scripts/Crab/crab.sh
""" % dict(user=user, rel=rel)
    return script

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
