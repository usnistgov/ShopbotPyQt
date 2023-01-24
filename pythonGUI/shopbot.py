#!/usr/bin/env python
'''Shopbot GUI Shopbot functions'''

# external packages
from PyQt5.QtCore import QRunnable, QThread, QThreadPool, QTimer
from PyQt5.QtGui import QDoubleValidator, QIntValidator
from PyQt5.QtWidgets import QFormLayout, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget
import os, sys
import winreg
import subprocess
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import csv
import re
import time
import win32gui, win32api, win32con

# local packages
from config import cfg
from general import *
from sbprint import *
from flags import *
from sbList import *




##################################################  
  
class sbSettingsBox(QWidget):
    '''This opens a window that holds settings about logging for the shopbot.'''
    
    
    def __init__(self, sbBox:connectBox):
        '''sbBox is the connectBox that this settings dialog belongs to. '''
        
        super().__init__(sbBox)  
        self.sbBox = sbBox
        layout = QVBoxLayout()
        form = QFormLayout()
        objValidator2 = QIntValidator(0, 10000)
        w = 100
        
        
        self.diagGroup = fRadioGroup(None, '', 
                                          {0:'None', 1:'Just critical', 2:'All changes', 3:'All time steps'}, 
                                          {0:0, 1:1, 2:2, 3:3},
                                         self.sbBox.diag, col=False, headerRow=False,
                                          func=self.changeDiag)
        form.addRow("Log", self.diagGroup.layout)
        layout.addLayout(form)
        
        # SBP folder
        fLabel(layout, title='.SBP file folder', style=labelStyle())
        self.folderRow = fileSetOpenRow(width=500, title='Set SBP folder',
                                   initFolder=self.sbBox.sbpFolder, 
                                   tooltip='Open SBP folder',
                                  setFunc = self.setSBPFolder,
                                  openFunc = self.openSBPFolder,
                                       layout = layout)

        # display settings
        fLabel(layout, title='File queue', style=labelStyle())
        self.showFolderCheck = fCheckBox(layout, title='Show full path in file queue', 
                                         tooltip='Show folder name in the list of Shopbot files',
                                         checked=cfg.shopbot.showFolder, 
                                         func=self.sbBox.reformatFileList)
        
        # save settings
        fLabel(layout, title='Saving time series', style=labelStyle())
        self.savePosCheck = fCheckBox(layout, title='Save x,y,z in time series table during print', 
                                      checked=cfg.shopbot.includePositionInTable, 
                                      func=self.updateSavePos)
        self.saveFlagCheck = fCheckBox(layout, title='Save output flag in time series table during print', 
                                      checked=cfg.shopbot.includeFlagInTable, 
                                      func=self.updateSaveFlag)
        
        form1 = QFormLayout()
        self.saveFreq = fLineUnits(form1, title=f'Save data frequency', 
                                  text=str(cfg.shopbot.saveDt), 
                                  tooltip='During prints, save data every _ ms',
                                  validator=objValidator2,
                                   width=w,
                                 func = self.updateSaveFreq, units=['ms'], uinit='ms')
        layout.addLayout(form1)
        self.savePicMetaData = fCheckBox(layout, title='Save metadata and time series for prints without pressure', 
                                      checked=cfg.shopbot.savePicMetadata, 
                                      func=self.updateSavePicMetadata)

        # autoplay checkboxes
        self.autoPlayChecks = fRadioGroup(layout, 'When the print is done', 
                                          {0:'Automatically start the next file', 
                                           1:'Wait for the user to press play'}, 
                                          {0:True, 1:False},
                                         self.sbBox.autoPlay, col=True, headerRow=True,
                                          func=self.changeAutoPlay)

        # timing error
        fLabel(layout, title='SB3 timing error correction', style=labelStyle())
        fileForm = QFormLayout()
        objValidator = QDoubleValidator(0, 10, 2)
        
        self.burstScale = fLineEdit(fileForm, title='Burst pressure scaling (default=1)',
                                    text=str(cfg.shopbot.burstScale), 
                                    tooltip='When you first turn on pressure, turn it to this value times the target value before you turn it down to the target value',
                                   func=self.updateBurstScale,
                                   width=w)
        self.burstLength = fLineUnits(fileForm, title='Burst pressure decay length',
                                    text=str(cfg.shopbot.burstLength.value), 
                                    tooltip='After you turn on the pressure, decrease to the target pressure over this distance in mm or time in seconds',
                                   func=self.updateBurstLength,
                                   width=w, units=['mm', 's'], uinit=cfg.shopbot.burstLength.units)
        self.critTimeOn = fLineUnits(fileForm, title='Crit length on',
                                    text=str(cfg.shopbot.critTimeOn.value), 
                                    tooltip='Turn on the pressure this amount of time in s or length in mm before the flag is turned on',
                                   func=self.updateCritTimeOn,
                                   width=w, units=['mm', 's'], uinit=cfg.shopbot.critTimeOn.units)
        self.critTimeOff = fLineUnits(fileForm, title='Crit time off (s)', 
                                     text=str(cfg.shopbot.critTimeOff.value), 
                                     tooltip='Turn off the pressure this amount of time in s or length in mm before the flag is turned off',
                                    func=self.updateCritTimeOff,
                                   width=w, units=['mm', 's'], uinit=cfg.shopbot.critTimeOff.units)
        self.zeroDist = fLineUnits(fileForm, title=f'Zero distance', 
                                  text=str(cfg.shopbot.zeroDist), 
                                  tooltip='If we are within this distance from a point, we are considered to be at the point. \
                                  In other words, margin of error or tolerance on distance measurements.',
                                 func = self.updateZeroDist,
                                   width=w, units=[self.sbBox.units], uinit=self.sbBox.units)
        
        self.checkFreq = fLineUnits(fileForm, title=f'Check flag frequency', 
                                  text=str(cfg.shopbot.dt.value), 
                                  tooltip='Check the status of the shopbot every _ ms',
                                  validator=objValidator2,
                                   width=w, units=[cfg.shopbot.dt.units], uinit=cfg.shopbot.dt.units)
        self.runSimple = fRadioGroup(layout, 'Pressure strategy', 
                                          {0:'Track points, flow speeds, and flags', 
                                           1:'Only track flags'
                                          2:'Track points, but let arduino override critTimeOn and critTimeOff'}, 
                                          {0:0, 1:1, 2:2},
                                         self.sbBox.runSimple, col=True, headerRow=True,
                                          func=self.changeRunSimple)
    
        objValidator3 = QIntValidator(cfg.shopbot.flag1min,cfg.shopbot.flag1max)
        self.flag1Edit = fLineEdit(fileForm, title=f'Run flag ({cfg.shopbot.flag1min}-{cfg.shopbot.flag1max})',
                              text =str(cfg.shopbot.flag1),
                              tooltip = 'Flag that triggers the start of print',
                              validator = objValidator3,
                              func = self.updateFlag1,
                                   width=w)
        layout.addLayout(fileForm)
        layout.addStretch()
        self.setLayout(layout)
        
    def loadConfig(self, cfg1) -> None:
        '''load values from a config file'''
        for s in ['burstScale', 'burstLength', 'critTimeOn', 'critTimeOff', 'zeroDist']:
            getattr(self, s).loadConfig(cfg1.shopbot[s])
        self.checkFreq.loadConfig(cfg1.shopbot.dt)
        self.saveFreq.loadConfig(cfg1.shopbot.saveDt)

        
    def saveConfig(self, cfg1):
        '''save values to the config file. all of these values should have already been saved in the main shopbot window'''
        return cfg1
    
    def changeDiag(self, diagbutton):
        '''Change the diagnostics status on the camera, so we print out the messages we want.'''
        self.sbBox.updateDiag(self.diagGroup.value())
        logging.info(f'Changed logging mode on shopbot.')
        
    def getDt(self) -> float:
        dt = float(self.checkFreq.value()['value'])
        if dt<=0:
            dt = 100
            logging.error('Bad value in shopbot check flag frequency')
            if cfg.shopbot.dt>0:
                self.checkFreq.setText(str(cfg.shopbot.dt))
            else:
                self.checkFreq.setText(str(dt))
        return dt
        
    def changeAutoPlay(self) -> None:
        '''Change autoPlay settings'''
        if self.autoPlayChecks.value():
            self.sbBox.autoPlay = True
            self.sbBox.updateStatus('Turned on autoplay', True)
        else:
            self.sbBox.autoPlay = False
            self.sbBox.updateStatus('Turned off autoplay', True)
            
    def changeRunSimple(self) -> None:
        '''Change points tracking strategy'''
        val = self.runSimple.value()
        self.sbBox.runSimple = val
        if val==0:
            self.sbBox.updateStatus('Only tracking flags', True)
            self.critTimeOn.enable()
            self.critTimeOff.enable()
        elif val==1:
            self.sbBox.updateStatus('Tracking points and flags', True)
            self.critTimeOn.enable()
            self.critTimeOff.enable()
        elif val==2:
            self.sbBox.updateStatus('Tracking points and flags, no crit times', True)
            self.critTimeOn.disable()
            self.critTimeOff.disable()
            
    def updateSavePos(self) -> None:
        '''update whether to save position in table'''
        if self.savePosCheck.isChecked():
            self.sbBox.savePos=True
        else:
            self.sbBox.savePos=False
            
    def updateSavePicMetadata(self) -> None:
        '''update whether to save metadata even if pressure is never turned on'''
        if self.savePicMetadata.isChecked():
            self.sbBox.savePicMetadata=True
        else:
            self.sbBox.savePicMetadata=False
            
    def updateSaveFlag(self) -> None:
        '''update whether to save flag in table'''
        if self.saveFlagCheck.isChecked():
            self.sbBox.saveFlag=True
        else:
            self.sbBox.saveFlag=False
            
    def updateSaveFreq(self) -> float:
        '''update how often to save data during prints'''
        dt = float(self.saveFreq.value()['value'])
        if dt<=0:
            dt = 100
            logging.error('Bad value in shopbot check flag frequency')
            if cfg.shopbot.saveDt.value>0:
                self.saveFreq.setText(str(cfg.shopbot.saveDt.value))
            else:
                self.saveFreq.setText(str(dt))
        self.sbBox.saveFreq = dt

            
    def updateFlag1(self) -> None:
        '''update sbBox run flag'''
        newflag1 = int(self.flag1Edit.text())
        if newflag1==self.sbBox.runFlag1:
            # no change in flag
            return
        if self.sbBox.sbWin.flagTaken(newflag1-1):
            self.sbBox.updateStatus(f'{newflag1} is taken. Resetting shopbot flag.', True)
            self.flag1Edit.setText(str(self.sbBox.runFlag1)) # reset the flag if it's taken
        else:
            self.sbBox.updateStatus(f'Updated shopbot flag to {self.sbBox.runFlag1}.', True)
            self.sbBox.runFlag1=newflag1
            self.sbBox.sbWin.flagBox.labelFlags()
            
    def updateUnitsValues(self, var:str) -> None:
        d = getattr(self, var).value()
        d['value'] = float(d['value'])
        setattr(self.sbBox, var, d)
        self.sbBox.updateStatus(f'Updated {var} to {d['value']} {d['units']}', True)
        
    def updateCritTimeOn(self) -> None:
        '''update sbBox crit time on'''
        self.updateUnitsValues('critTimeOn')
        
    def updateCritTimeOff(self) -> None:
        '''update sbBox crit time on'''
        self.updateUnitsValues('critTimeOff')
        
    def updateZeroDist(self) -> None:
        '''update sbBox crit zero dist'''
        self.updateUnitsValues('zeroDist')
        
    def updateBurstScale(self) -> None:
        '''update the burst pressure scaling'''
        self.sbBox.burstScale = float(self.burstScale.text())
        self.sbBox.updateStatus(f'Updated burst scale to {self.sbBox.burstScale}', True)
        
    def updateBurstLength(self) -> None:
        '''update the burst pressure length'''
        self.updateUnitsValues('burstLength')

    def setSBPFolder(self) -> None:
        '''set the folder to save all the files we generate from the whole gui'''
        self.sbBox.sbpFolder = setFolder(self.sbBox.sbpFolder)        
        self.sbBox.updateStatus('Changed shopbot file folder to %s' % self.sbBox.sbpFolder, True)
        self.fsor.updateText(self.sbBox.sbpFolder)
            
    def openSBPFolder(self) -> None:
        '''Open the save folder in windows explorer'''
        openFolder(self.sbBox.sbpFolder)

        
            
###########################################


class sbBox(connectBox):
    '''Holds shopbot functions and GUI items'''
    
    
    ####################  
    ############## initialization functions
    
    
    def __init__(self, sbWin:QMainWindow, connect:bool=True):
        '''sbWin is the parent window that all of the widgets are in'''
        super(sbBox, self).__init__()
        self.bTitle = 'Shopbot'
        self.sbWin = sbWin
        self.runningSBP = False
        self.setTitle('Shopbot')
        self.loadConfigMain(cfg)
        
        if connect:
            self.connect()
   
    def connect(self):
        '''connect to the SB3 software'''
        self.keys = SBKeys(self.diag)
        self.keys.signals.status.connect(self.updateStatus)   # connect key status to GUI
        self.keys.signals.flag.connect(self.updateFlag)       # connect flag status to GUI
        self.keys.signals.pos.connect(self.updateXYZ)         # connect position status to GUI
        if hasattr(self.sbWin, 'flagBox'):
            self.flagBox = self.sbWin.flagBox    # adopt the parent's flagBox for shorter function calls
        if not self.keys.connected:
             self.failLayout()
        else:
            self.successLayout()
            self.updateLoc()
            
    def timeRow(self) -> List:
        '''get a list of values to collect for the time table'''
        if self.savePos:
            if hasattr(self, 'x') and hasattr(self, 'y') and hasattr(self, 'z'):
                out = [self.x, self.y, self.z]
            else:
                out = ['','','']
            if hasattr(self, 'xe') and hasattr(self, 'ye') and hasattr(self, 'ze'):
                out = out+[self.xe, self.ye, self.ze]
            else:
                out = out + ['','','']
            if hasattr(self, 'xt') and hasattr(self, 'yt') and hasattr(self, 'zt'):
                out = out+[self.xt, self.yt, self.zt]
            else:
                out = out + ['','','']
        else:
            out = []
        if self.saveFlag:
            if hasattr(self, 'keys'):
                if hasattr(self, 'sbFlag'):
                    out = out + [self.sbFlag]
                else:
                    self.keys.lock()
                    out = out + [self.keys.currentFlag]
                    self.keys.unlock()
            else:
                out = out + ['']
        return out
    
    def timeHeader(self) -> List:
        '''get a list of header values for the time table'''
        if self.savePos:
            out = ['x_disp(mm)', 'y_disp(mm)', 'z_disp(mm)', 'x_est(mm)', 'y_est(mm)', 'z_est(mm)', 'x_target(mm)', 'y_target(mm)', 'z_target(mm)']
        else:
            out = []
        if self.saveFlag:
            out = out + ['flag']
        return out
 
    #-------------
    # communicating with the shopbot
    
    def getLoc(self) -> None:
        '''get the location'''
        self.keys.lock()
        x = self.keys.getLoc()
        self.keys.unlock()
        if len(x)>0:
            self.x = x[0]
            self.y = x[1]
            self.z = x[2]
        
    def updateLoc(self) -> None:
        '''update the location in the status bar'''
        self.getLoc()
                    
    #-------------
    # handling configs
    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        cfg1.shopbot.flag1 = self.runFlag1 
        cfg1.shopbot.autoplay = self.autoPlay   
        cfg1.shopbot.sbpFolder = self.sbpFolder
        cfg1.shopbot.units = self.units
        cfg1.shopbot.includePositionInTable = self.savePos
        cfg1.shopbot.includeFlagInTable = self.saveFlag
        cfg1.shopbot.savePicMetadata = self.savePicMetadata
        for s in ['critTimeOn', 'critTimeOff', 'burstLength']:
            for s2 in ['value', 'units']:
                cfg1.shopbot[s][s2] = getattr(self, s)[s2]
        cfg1.shopbot.zeroDist = self.zeroDist
        cfg1.shopbot.dt = self.checkFreq
        cfg1.shopbot.burstScale = self.burstScale
        cfg1.shopbot.diag = self.diag
        if hasattr(self, 'settingsBox'):
            cfg1 = self.settingsBox.saveConfig(cfg1)
        if hasattr(self, 'sbList'):
            cfg1 = self.sbList.saveConfig(cfg1)
        return cfg1
    
    def loadConfigMain(self, cfg1):
        '''load settings to the main box'''
        self.runFlag1 = cfg1.shopbot.flag1   # 1-indexed
        self.autoPlay = cfg1.shopbot.autoplay 
        self.sbpFolder = checkPath(cfg1.shopbot.sbpFolder)
        self.units = cfg1.shopbot.units
        self.savePos = cfg1.shopbot.includePositionInTable
        self.saveFlag = cfg1.shopbot.includeFlagInTable
        self.savePicMetadata = cfg1.shopbot.savePicMetadata
        for s in ['critTimeOn', 'critTimeOff', 'burstLength']:
            setattr(self, s, {})
            for s2 in ['value', 'units']:
                 getattr(self, s)[s2] = cfg1.shopbot[s][s2]
        self.zeroDist=cfg1.shopbot.zeroDist
        self.checkFreq=cfg1.shopbot.dt
        self.burstScale = cfg1.shopbot.burstScale
        self.saveFreq = cfg1.shopbot.saveDt
        self.diag = cfg1.shopbot.diag
        
    
    def loadConfig(self, cfg1):
        '''load settings from a config Box object'''
        self.loadConfigMain(cfg1)
        self.sbList.loadConfig(cfg1)
        self.settingsBox.loadConfig(cfg1)
        
    def getRunFlag1(self) -> int:
        if hasattr(self, 'runFlag1'):
            return self.runFlag1
        else:
            return -1
        
    def updateFlag(self, sbFlag:int) -> None:
        '''update the flag display in the flagBox'''
        self.sbFlag = sbFlag
        if hasattr(self, 'flagBox'):
            self.flagBox.update(sbFlag)
        else:
            logging.debug('flagBox not initialized')
            
    def readAndUpdateFlag(self) -> None:
        if self.runningSBP:
            return
        if hasattr(self, 'keys'):
            self.keys.lock()
            sbflag = self.keys.getSBFlag()
            self.keys.unlock()
            self.updateFlag(sbFlag)
            
    def updateDiag(self, diag:int) -> None:
        '''update the logging mode'''
        self.diag = diag
        self.keys.lock()
        self.keys.diag = diag
        self.keys.unlock()

    #------------------------------
    
    # testing mode
    
    def testLayout(self, fluigent:bool=False) -> None:
        '''layout if we are testing some other component'''
        self.resetLayout()
        self.layout = QVBoxLayout()
        self.testMetaButt = fButton(self.layout, title='Test meta save'
                                    , tooltip='Test saving metadata about the print'
                                    , func=self.saveMeta)
        self.testTimeButt = fButton(self.layout, title='Test time series save'
                                    , tooltip='Test saving time series'
                                    , func=self.testTime)
        if fluigent:
            self.addFluBox(self.layout)
        self.setLayout(self.layout)
        
    
    def saveMeta(self) -> None:
        '''create a csv file that describes the run speeds'''
        self.sbWin.saveMetaData()
        
       
    def writeToTable(self, writer) -> None:
        '''write metadata values to the table'''
        sh = SBPHeader(self.sbpName()) 
        t1 = sh.table()
        for row in t1:
            writer.writerow(row)
        writer.writerow(['run_flag1', '', self.runFlag1])
        writer.writerow(['critTimeOn', self.critTimeOn.units, self.critTimeOn.value])
        writer.writerow(['critTimeOff', self.critTimeOff.units, self.critTimeOff.value])
        writer.writerow(['zeroDist', self.units, self.zeroDist])
        writer.writerow(['checkFreq', 'ms', self.checkFreq])
        writer.writerow(['burstScale', '', self.burstScale])
        writer.writerow(['burstLength', self.burstLength.units, self.burstLength.value])

    def testTime(self) -> None:
        '''create metadata file'''
        self.sbWin.initSaveTable()
        QTimer.singleShot(2000, self.sbWin.stopSaveTable())
        
    
    #----------------------------   

    def successLayout(self) -> None:
        '''layout if we found the sb3 files and windows registry keys'''
        
        swidth = 600
        self.settingsBox = sbSettingsBox(self)
        self.resetLayout()
        self.runButt = runButt(self, size=50)
        self.createStatus(swidth, height=70, status='Waiting for file ...')
        self.topBar = fHBoxLayout(self.runButt, self.status, spacing=10)
        self.sbList = sbpNameList(self)
        self.layout = fVBoxLayout(self.topBar, self.sbList)
        self.addFluBox(self.layout)
        self.setLayout(self.layout)
    
    def addFluBox(self, layout:QLayout) -> None:
        '''add the fluigent boxes to the shopbot box'''
        if hasattr(self.sbWin, 'fluBox'):
            self.sbWin.fluBox.addPrintButtRow(layout)
    
    def reformatFileList(self) -> None:
        if hasattr(self, 'sbList'):
            self.sbList.reformat()
        
    def updateRunButt(self) -> None:
        if hasattr(self, 'runButt'):
            self.runButt.update(self.runningSBP)
        
    def enableRunButt(self) -> None:
        if hasattr(self, 'runButt'):
            self.runButt.setEnabled(True)
            self.updateRunButt()
        
    def disableRunButt(self) -> None:
        if hasattr(self, 'runButt'):
            self.runButt.setEnabled(False)
            self.updateRunButt()
            
    #-------------
    # flagBox operations
        
    def flagTaken(self, flag0:int) -> bool:
        '''check if the flag is already occupied'''
        if hasattr(self, 'flagBox'):
            return self.flagBox.flagTaken(flag0)
        else:
            return False
    
    @pyqtSlot(float,float,float)   
    def updateXYZ(self, x:float, y:float, z:float) -> None:
        '''update the read xyz display'''
        self.x = x
        self.y = y
        self.z = z
        if hasattr(self, 'flagBox'):
            self.flagBox.updateXYZ(x,y,z)
            
    @pyqtSlot(float,float,float)
    def updateXYZest(self, x:float, y:float, z:float) -> None:
        '''update the estimated xyz display'''
        self.xe = x
        self.ye = y
        self.ze = z
        if hasattr(self, 'flagBox'):
            self.flagBox.updateXYZest(x,y,z)
            
    @pyqtSlot(float,float,float)
    def updateXYZt(self, x:float, y:float, z:float) -> None:
        '''update the target xyz display'''
        self.xt = x
        self.yt = y
        self.zt = z
        if hasattr(self, 'flagBox'):
            self.flagBox.updateXYZt(x,y,z)

    ####################            
    #### functions to start on run
    
    ### set up the run
    
    def sbpName(self) -> str:
        if hasattr(self, 'sbList'):
            return self.sbList.currentFile
        else:
            if self.connected:
                logging.error('Shopbot box does not have attribute sbList')
            return ''

    def getCritFlag(self) -> int:
        '''Identify which channels are triggered during the run. critFlag is a shopbot flag value that indicates that the run is done. We always set this to 0. If you want the video to shut off after the first flow is done, set this to 2^(cfg.shopbot.flag-1). We run this function at the beginning of the run to determine what flag will trigger the start of videos, etc.'''
        self.channelsTriggered = channelsTriggered(self.sbpName())
        
        if not self.runFlag1-1 in self.channelsTriggered:
            # abort run: no signal to run this file
            self.updateStatus(f'Missing flag in sbp file: {self.runFlag1}', True)
            raise ValueError('Missing flag in sbp file')
        if self.runFlag1-1 in self.channelsTriggered:
            self.channelsTriggered.remove(self.runFlag1-1)
        return 0
    
    def stopHit(self) -> None:
        '''if the stop button on the shopbot was hit, this gets run'''
        self.allowEnd=True
        self.updateStatus('SB3 Stop button pressed', True)
        self.triggerKill()
    
    
    ### start/stop

        
    #---------------------------
    # first, wait for the shopbot to be ready

    def runFile(self) -> None:
        '''runFile sends a file to the shopbot and tells the GUI to wait for next steps. first, check if the shopbot is ready'''
        self.runningSBP = True
        self.keys.lock()
        self.keys.runningSBP = True
        self.keys.unlock()
        self.updateRunButt()
        waitRunnable = waitForReady(self.settingsBox.getDt(), self.keys)
        waitRunnable.signals.finished.connect(self.runFileContinue)  # continue when ready to print
        QThreadPool.globalInstance().start(waitRunnable) 

            
    #---------------------------------------------------------
    


    @pyqtSlot()
    def runFileContinue(self) -> None:
        '''runFile sends a file to the shopbot and tells the GUI to wait for next steps. second, send the file over'''
        # check if the file exists
        if not os.path.exists(self.sbpName()):
            if self.sbpName()=='BREAK':
                self.updateStatus('Break point hit.', True)
            else:
                self.updateStatus(f'SBP file does not exist: {self.sbpName()}', True)
            self.runningSBP=False
            self.keys.lock()
            self.keys.runningSBP = False
            self.keys.unlock()
            self.updateRunButt()
            self.sbList.activateNext()
            return
        
#         self.abortButt.setEnabled(True)
        
        ''' allowEnd is a failsafe measure because when the shopbot starts running a file that changes output flags, it asks the user to allow spindle movement to start. While it is waiting for the user to hit ok, only flag 4 would be up, giving a flag value of 8. If critFlag=8 (i.e. we want to stop running after the first extrusion step), this means the GUI will think the file is done before it even starts. We create an extra trigger to say that if we're extruding, we have to wait for extrusion to start before we can let the tracking stop'''
        try:
            self.critFlag = self.getCritFlag()
        except ValueError:
            self.triggerKill()
            return
        if self.critFlag==0:
            self.allowEnd = True
        else:
            self.allowEnd = False
            
        self.updateStatus(f'Running SBP file {self.sbpName()}, critFlag = {self.critFlag}', True)

            
        self.stopPrintThread()  # stop any existing threads
        pSettings = {'critTimeOn':self.critTimeOn, 'zeroDist':self.zeroDist, 'critTimeOff':self.critTimeOff, 'burstScale':self.burstScale, 'burstLength':self.burstLength}
        self.printWorker = printLoop(self.settingsBox.getDt(), self.keys, self.sbpName(), pSettings, self.sbWin, self.runFlag1)   # create a worker to track the print
        self.printWorker.signals.aborted.connect(self.triggerKill)
        self.printWorker.signals.finished.connect(self.triggerEndOfPrint)
        self.printWorker.signals.estimate.connect(self.updateXYZest)
        self.printWorker.signals.target.connect(self.updateXYZt)

        # send the file to the shopbot via command line
        self.keys.lock()
        appl = self.keys.sb3File
        self.keys.unlock()
        arg = self.sbpName() + ', ,4, ,0,0,0"'
        subprocess.Popen([appl, arg])
        
        # create a thread that waits for the start of flow
        waitRunnable = waitForStart(self.settingsBox.getDt(), self.keys, self.runFlag1, self.channelsTriggered)
        waitRunnable.signals.finished.connect(self.triggerWatch)
        waitRunnable.signals.status.connect(self.updateStatus)
        QThreadPool.globalInstance().start(waitRunnable) 
 
            
            
    ### start videos and fluigent
    
    @pyqtSlot()
    def triggerWatch(self) -> None:
        '''start recording and start the timer to watch for changes in pressure'''
        
        if not self.runningSBP:
            return

        # start the cameras if any flow is triggered in the run
        if min(self.channelsTriggered)<len(self.sbWin.fluBox.pchannels):
            self.sbWin.camBoxes.startRecording()
        if self.savePicMetadata or (len(self.channelsTriggered)>0 and not self.channelsTriggered==[2]):
            # only save speeds and pressures if there is extrusion or if the checkbox is marked
            self.sbWin.saveMetaData()    # save metadata
            self.sbWin.initSaveTable()   # save table of pressures
            
            
        self.printThread = QThread()
        self.printWorker.moveToThread(self.printThread)
        self.printThread.started.connect(self.printWorker.run)
        self.printWorker.signals.finished.connect(self.printThread.quit)
        self.printWorker.signals.finished.connect(self.printWorker.deleteLater)
        self.printThread.finished.connect(self.printThread.deleteLater)
        self.printThread.start()
        
      
    def stopRunning(self) -> None:
        '''stop watching for changes in pressure, stop recording  '''
        self.keys.lock()
        self.keys.runningSBP = False
        self.keys.getSBFlag()  # update the flag readout
        self.keys.unlock()
        if self.runningSBP:
            QTimer.singleShot(1000, self.closeDevices)  # close devices after 1 second
            
    def closeDevices(self) -> None:
        '''stop all recording devices'''
        if hasattr(self.sbWin, 'fluBox'):
            self.sbWin.fluBox.resetAllChannels(-1) # turn off all channels
            
        if hasattr(self.sbWin, 'camBoxes'):
            self.sbWin.camBoxes.stopRecording()    # turn off cameras
            
        self.sbWin.writeSaveTable()     # save the pressure and xyz readings    

                
    def readyState(self):
        '''return to the ready state'''
        self.runningSBP = False   # we're no longer running a sbp file
        self.keys.lock()
        self.keys.runningSBP = False
        self.keys.unlock()
        self.updateRunButt()    
        self.updateStatus('Ready', False)
        
    @pyqtSlot()
    def triggerKill(self) -> None:
        '''the stop button was hit, so stop'''
        logging.info('Stop hit')
        self.stopRunning()
        self.readyState()
        
    @pyqtSlot()
    def triggerEndOfPrint(self) -> None:
        '''we finished the file, so stop and move onto the next one'''
        logging.info('File completed')
        self.stopRunning()
        self.sbList.activateNext() # activate the next sbp file in the list
        if self.autoPlay and self.sbList.sbpNumber()>0: # if we're in autoplay and we're not at the beginning of the list, play the next file
            self.updateStatus('Autoplay is on: Running next file.', True)
            QTimer.singleShot(2000, self.runFile) # wait 2 seconds, then call runFile
        else:
            self.readyState()


    #-----------------------------------------
    
    def stopPrintThread(self):
        '''stop the print thread'''
        for s in ['printThread']:
            if hasattr(self, s):
                o = getattr(self, s)
                if not sip.isdeleted(o) and o.isRunning():
                    o.quit()
    
    
    def close(self):
        '''this gets triggered when the whole window is closed'''
        self.stopPrintThread()

