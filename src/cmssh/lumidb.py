#!/usr/bin/env python
#pylint: disable-msg=C0103,C0322,C0324,C0301,R0914,R0912,R0915,W0612
# based on lumiCalc2.py script by Zhen Xie

"""
LumiDB module
"""

import sys
import coral
from RecoLuminosity.LumiDB import sessionManager
from RecoLuminosity.LumiDB import revisionDML, CommonUtil
from RecoLuminosity.LumiDB import lumiCalcAPI, lumiReport

def lumidb(run_lumi_dict, action='delivered', lumi_report=False):
    "Call lumidb to get luminosity numbers"
    actions  = ['overview', 'delivered', 'recorded', 'lumibyls', 'lumibylsXing']
    if  action not in actions:
        raise Exception('Unsupported action="%s", please check from %s' % (action, actions))
    beamModeChoices = ['stable']
    amodetagChoices = ['PROTPHYS', 'IONPHYS', 'PAPHYS' ]
    xingAlgoChoices = ['OCC1', 'OCC2', 'ET']

    #
    # parse arguments
    #  
    connect='frontier://LumiCalc/CMS_LUMI_PROD'
    authpath = None
    scalefactor = 1.0
    beamfluctuation = 0.2
    minbiasxsec = 69300.0 # minbias cross-secvtion in ub
    xingMinLum = 1e-03 # Minimum perbunch luminosity to print, default=1e-03/ub
    xingAlgo = 'OCC1'
    hltpath = None
    outputfile = None
    siteconfpath = None
    withoutNorm = False
    withoutCheckforupdate = False
    fillnum = None
    nowarning = True
    debug = False
    beamenergy = None
    amodetag = None
    reqrunmin=None
    reqfillmin=None
    reqtimemin=None
    reqrunmax=None
    reqfillmax=None
    reqtimemax=None
    timeFilter=[None,None]
    pbeammode = None
    iresults=[]
    reqTrg=False
    reqHlt=False
    svc = sessionManager.sessionManager(connect, authpath, siteconfpath, debugON=debug)
    session=svc.openSession(isReadOnly=True,
            cpp2sqltype=[('unsigned int', 'NUMBER(10)'), ('unsigned long long', 'NUMBER(20)')])

    ##############################################################
    # check run/ls list
    ##############################################################
    irunlsdict={}
    rruns=[]
    session.transaction().start(True)
    irunlsdict = run_lumi_dict
    iresults = []
    runlist=lumiCalcAPI.runList(session.nominalSchema(),
            fillnum, runmin=reqrunmin, runmax=reqrunmax,
            fillmin=reqfillmin, fillmax=reqfillmax,
            startT=reqtimemin, stopT=reqtimemax,
            l1keyPattern=None, hltkeyPattern=None,
            amodetag=amodetag, nominalEnergy=beamenergy,
            energyFlut=beamfluctuation,
            requiretrg=False, requirehlt=False)
    rruns = [val for val in runlist if val in irunlsdict.keys()]
    for selectedrun in irunlsdict.keys():#if there's further filter on the runlist,clean input dict
        if selectedrun not in rruns:
            del irunlsdict[selectedrun]
    ##############################################################
    # check datatag
    # #############################################################       
    datatagid, datatagname = revisionDML.currentDataTag(session.nominalSchema())
    dataidmap=revisionDML.dataIdsByTagId(\
            session.nominalSchema(), datatagid,
            runlist=rruns, withcomment=False)
    session.transaction().commit()
    if not dataidmap:
        print '[INFO] No qualified data found, do nothing'
        sys.exit(0)
                
    normvalueDict={}
    ##################
    # ls level       #
    ##################
    session.transaction().start(True)
    GrunsummaryData=lumiCalcAPI.runsummaryMap(session.nominalSchema(),irunlsdict)
    if  action == 'delivered':
        result=lumiCalcAPI.deliveredLumiForIds(session.nominalSchema(),irunlsdict,dataidmap,runsummaryMap=GrunsummaryData,beamstatusfilter=pbeammode,timeFilter=timeFilter,normmap=normvalueDict,lumitype='HF')
        if  lumi_report:
            lumiReport.toScreenTotDelivered(result,iresults,scalefactor,irunlsdict=irunlsdict,noWarning=nowarning,toFile=outputfile)

        # result {run:[lumilsnum(0),cmslsnum(1),timestamp(2),beamstatus(3),beamenergy(4),deliveredlumi(5),calibratedlumierr(6),(bxidxlist,bxvalues,bxerrs)(7),(bxidx,b1intensities,b2intensities)(8),fillnum(9),pu(10)]}
        totlumi = 0
        for run, val in result.items():
            for llist in val:
                if  irunlsdict[run]:
                    if  llist[0] in irunlsdict[run]: # select only lumis from input run ls dict
                        totlumi += llist[5]
                else:
                    totlumi += llist[5]
        totlumival, lumiunit = CommonUtil.guessUnit(totlumi)
        print "Delivered luminosity %s (%s)" % (totlumival, lumiunit)
    if  action == 'overview':
        result=lumiCalcAPI.lumiForIds(session.nominalSchema(),irunlsdict,dataidmap,runsummaryMap=GrunsummaryData,beamstatusfilter=pbeammode,timeFilter=timeFilter,normmap=normvalueDict,lumitype='HF')
        lumiReport.toScreenOverview(result,iresults,scalefactor,irunlsdict=irunlsdict,noWarning=nowarning,toFile=outputfile)
    if  action == 'lumibyls':
        if not hltpath:
            result=lumiCalcAPI.lumiForIds(session.nominalSchema(),irunlsdict,dataidmap,runsummaryMap=GrunsummaryData,beamstatusfilter=pbeammode,timeFilter=timeFilter,normmap=normvalueDict,lumitype='HF',minbiasXsec=minbiasxsec)
            lumiReport.toScreenLumiByLS(result,iresults,scalefactor,irunlsdict=irunlsdict,noWarning=nowarning,toFile=outputfile)            
        else:
            hltname=hltpath
            hltpat=None
            if hltname=='*' or hltname=='all':
                hltname=None
            elif 1 in [c in hltname for c in '*?[]']: #is a fnmatch pattern
                hltpat=hltname
                hltname=None
            result=lumiCalcAPI.effectiveLumiForIds(session.nominalSchema(),irunlsdict,dataidmap,runsummaryMap=GrunsummaryData,beamstatusfilter=pbeammode,timeFilter=timeFilter,normmap=normvalueDict,hltpathname=hltname,hltpathpattern=hltpat,withBXInfo=False,bxAlgo=None,xingMinLum=xingMinLum,withBeamIntensity=False,lumitype='HF')
            lumiReport.toScreenLSEffective(result,iresults,scalefactor,irunlsdict=irunlsdict,noWarning=nowarning,toFile=outputfile)
    if  action == 'recorded':#recorded actually means effective because it needs to show all the hltpaths...
        hltname=hltpath
        hltpat=None
        if hltname is not None:
            if hltname=='*' or hltname=='all':
                hltname=None
            elif 1 in [c in hltname for c in '*?[]']: #is a fnmatch pattern
                hltpat=hltname
                hltname=None
        result=lumiCalcAPI.effectiveLumiForIds(session.nominalSchema(),irunlsdict,dataidmap,runsummaryMap=GrunsummaryData,beamstatusfilter=pbeammode,timeFilter=timeFilter,normmap=normvalueDict,hltpathname=hltname,hltpathpattern=hltpat,withBXInfo=False,bxAlgo=None,xingMinLum=xingMinLum,withBeamIntensity=False,lumitype='HF')
        lumiReport.toScreenTotEffective(result,iresults,scalefactor,irunlsdict=irunlsdict,noWarning=nowarning,toFile=outputfile)
    if  action == 'lumibylsXing':
        result=lumiCalcAPI.lumiForIds(session.nominalSchema(),irunlsdict,dataidmap,runsummaryMap=GrunsummaryData,beamstatusfilter=pbeammode,timeFilter=timeFilter,normmap=normvalueDict,withBXInfo=True,bxAlgo=xingAlgo,xingMinLum=xingMinLum,withBeamIntensity=False,lumitype='HF')
        outfile=outputfile
        if  not outfile:
            print '[WARNING] no output file given. lumibylsXing writes per-bunch lumi only to default file lumibylsXing.csv'
            outfile='lumibylsXing.csv'           
        lumiReport.toCSVLumiByLSXing(result,scalefactor,outfile,irunlsdict=irunlsdict,noWarning=nowarning)
    session.transaction().commit()
    del session
    del svc 

if __name__ == '__main__':
    lumidb(sys.argv[1])
