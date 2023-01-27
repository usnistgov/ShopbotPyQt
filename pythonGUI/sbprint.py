#!/usr/bin/env python
'''Shopbot GUI functions for handling changes of state during a print'''

# external packages
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QMutex, QObject, QRunnable, QThread, QTimer
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget 
import os, sys
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import csv
import re
import win32gui, win32api, win32con
import time
import datetime

# local packages
from config import cfg
from general import *
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(currentdir)
sys.path.append(parentdir)
sys.path.append(os.path.join(parentdir, 'SBP_files'))  # add python folder
from sbpRead import *
from channelWatch import *
from printWatch import *

printDiag = False


##################################################  



    

class metaBox(QWidget):
    '''This opens a window that holds metadata about the run'''
    
    
    def __init__(self, parent, connect:bool=True):
        '''parent is the connectBox that this settings dialog belongs to. '''
        super().__init__(parent)  
        self.settingsBox = self
        self.parent = parent
        self.metaDict = {}
        if connect:
            self.connect()
    
    def connect(self):
        '''connect to metadata and create a tab for the settings box'''
        self.successLayout()
        
    def successLayout(self):
        '''create a tab for metadata'''
        self.metaBox = QWidget()
        self.bTitle = 'Metadata'
        layout = QVBoxLayout()
        # metadata
        labelStyle = 'font-weight:bold; color:#31698f'
        fLabel(layout, title='Metadata to save for each print in *_meta_*.csv:', style=labelStyle)
        self.metaTable = QTableWidget(30,3)
        self.metaTable.setColumnWidth(0, 200)
        self.metaTable.setColumnWidth(1, 200)
        self.metaTable.setColumnWidth(2, 200)
        self.metaTable.setMinimumHeight(400)
        self.metaTable.setMinimumWidth(620)
        newitem = QTableWidgetItem('property')
        self.metaTable.setItem(0, 0, newitem)
        newitem = QTableWidgetItem('value')
        self.metaTable.setItem(0, 1, newitem)
        newitem = QTableWidgetItem('units')
        self.metaTable.setItem(0, 2, newitem)
        self.loadConfig(cfg)   # load cfg data into table and fLineEdits
        self.metaTable.itemChanged.connect(self.changeMeta)
        layout.addWidget(self.metaTable)
        self.setLayout(layout)
        
    def changeMeta(self) -> None:
        '''update meta table'''
        for ii in range(self.metaTable.rowCount()):
            # iterate through rows and store them in the metadict
            name = self.metaTable.item(ii,0)
            if hasattr(name, 'text'):
                row = name.text()
                val = self.metaTable.item(ii,1)
                if hasattr(val, 'text'):
                    value = val.text()
                else:
                    value = ''
                un = self.metaTable.item(ii,2)
                if hasattr(un, 'text'):
                    units = un.text()
                else:
                    units = ''
                self.metaDict[row] = [value, units]
        
    def loadConfig(self, cfg1) -> None:
        '''load values from a config file'''
        if not 'meta' in cfg1:
            logging.error('No meta category in config file')
            return
        
        for ii,row in enumerate(cfg1.meta):
            try:
                value = str(cfg1.meta[row].value)
                units = str(cfg1.meta[row].units)
            except:
                logging.error(f'Missing data in {cfg1.meta[row]}')
            else:
                # store the value in the dictionary
                self.metaDict[row] = [value, units]
                
                # add the value to the row
                newitem = QTableWidgetItem(str(row))
                self.metaTable.setItem(ii+1, 0, newitem)
                newitem = QTableWidgetItem(value)
                self.metaTable.setItem(ii+1, 1, newitem)
                newitem = QTableWidgetItem(units)
                self.metaTable.setItem(ii+1, 2, newitem)
                
    def saveConfig(self, cfg1):
        '''save values to the config file'''
        meta = self.metaDict
        for key, value in meta.items():
            # store the dict value in the cfg box
            cfg1.meta[key].value = value[0]
            cfg1.meta[key].units = value[1]
        return cfg1
    
    def writeToTable(self, writer) -> None:
        '''write metatable values to a csv writer object'''
        # ad hoc metadata in settings
        for key,value in self.metaDict.items():
            writer.writerow([key, value[1], value[0]])
        
#----------------------------------------------------

class waitSignals(QObject):
    finished = pyqtSignal()
    stopHit = pyqtSignal()
    status = pyqtSignal(str, bool)
        
class waitForReady(QRunnable):
    '''waiting for the printer to be ready to print'''
    
    def __init__(self, dt:float, keys:QMutex):
        super(waitForReady,self).__init__()
        self.dt = dt # in ms
        self.keys = keys
        self.signals = waitSignals()
        
    @pyqtSlot()
    def run(self) -> None:
        '''check the shopbot status'''
        while True:
            self.keys.lock()
            ready = self.keys.SBisReady()
            running = self.keys.runningSBP
            self.keys.unlock()
            if ready or not running:
                self.signals.finished.emit()
                return
            else:
                time.sleep(self.dt/1000)  # loop every self.dt seconds
        
#-----------------------------------------------

class waitForStart(QRunnable):
    '''waiting for the printer to start printing'''
    
    def __init__(self, dt:float, keys:QMutex, runFlag1:int, channelsTriggered:list):
        super(waitForStart,self).__init__()
        self.dt = dt
        self.keys = keys
        self.runFlag1 = runFlag1
        self.channelsTriggered = channelsTriggered
        if len(self.channelsTriggered)==0:
            self.cf = 2**(self.runFlag1-1)
        else:
            self.cf = 2**(self.runFlag1-1) + 2**(self.channelsTriggered[0]) # the critical flag at which flow starts
        self.signals = waitSignals()
        self.spindleKilled = False
        self.spindleFound = False
      
    @pyqtSlot()
    def run(self):
        while True:
            if not self.spindleFound:
                out = self.killSpindlePopup()
            self.keys.lock()
            sbFlag = self.keys.getSBFlag()
            running = self.keys.runningSBP
            self.keys.unlock()
            self.updateStatus(f'Waiting to start file, Shopbot output flag = {sbFlag}, start at {self.cf}', False)
            if sbFlag==self.cf or not running:
                self.signals.finished.emit()
                return
            else:
                time.sleep(self.dt/1000)
            
    @pyqtSlot(str,bool)
    def updateStatus(self, status:str, log:bool):
        '''send a status update back to the GUI'''
        self.signals.status.emit(status, log)
            
    
    def killSpindlePopup(self) -> None:
        '''if we use output flag 1 (1-indexed), the shopbot thinks we are starting the router/spindle and triggers a popup. Because we do not have a router/spindle on this instrument, this popup is irrelevant. This function automatically checks if the window is open and closes the window'''
        hwndMain = win32gui.FindWindow(None, 'NOW STARTING ROUTER/SPINDLE !')
        if hwndMain>0:
            self.spindleFound = True
            time.sleep(self.dt/1000/2)
            self.killSpindle()
            
        return True
       
    @pyqtSlot()
    def killSpindle(self) -> None:
        '''actually kill the spindle'''
        hwndMain = win32gui.FindWindow(None, 'NOW STARTING ROUTER/SPINDLE !')
        if hwndMain>0:
            # disable the spindle warning
            try:
                # foreground the window
                hwndChild = win32gui.GetWindow(hwndMain, win32con.GW_CHILD)
                win32gui.SetForegroundWindow(hwndChild)   
            except Exception as e:
                self.signals.status.emit('Failed to disable spindle popup', True)
            else:
                # kill the window
                win32api.PostMessage( hwndChild, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)  
                self.spindleKilled = True

                
#----------------------------

class diagStr:
    '''holds a diagnostic string that describes the current time step'''
    
    def __init__(self, diag:int):
        self.row = ''
        self.status = ''
        self.header = ''
        self.diag = diag
        self.printi = 0
        
    def newRow(self):
        self.row = ''
        self.status = ''
        
    def addHeader(self, s) -> None:
        self.header = self.header +' | '+ s
        
    def addRow(self, s:str) -> None:
        self.row = self.row + ' | '+ s
        
    def addStatus(self, s:str) -> None:
        self.status = f'{self.status}, {s}'
        
    def printRow(self) -> None:
        if self.diag>2:
            # print every step
            print(f'{self.row}| {self.status}')
            self.printi+=1
        elif self.diag>1 and len(self.status)>0:
            print(f'{self.row}| {self.status}')
            self.printi+=1
        if (self.diag>1 and (self.printi>50)):
            print(self.header)
            self.printi = 0
            
    def printHeader(self) -> None:
        if self.diag>1:
            print(self.header)


    
class printLoopSignals(QObject):
    finished = pyqtSignal()   # print is done
    aborted = pyqtSignal()    # print was aborted from sbp app
    estimate = pyqtSignal(float,float,float)   # new estimated position
    target = pyqtSignal(float,float,float)      # send current target to GUI
    targetLine = pyqtSignal(int)   # send current target line to GUI
    status = pyqtSignal(str)
    
    
class printLoop(QObject):
    '''loop through this while prints are running
    dt is loop time in ms
    keys is an SBKeys object
    sbpfile is the name of the sbp file '''
    
    def __init__(self, dt:float, keys:QMutex, sbpfile:str, pSettings:dict, sbWin, sbRunFlag1:int):
        super(printLoop,self).__init__()
        self.dt = dt
        self.keys = keys    # holds windows registry keys
        self.signals = printLoopSignals()
        self.channelWatches = {}
        self.modes = []
        self.pSettings = pSettings
        self.tableDone = False
        self.runSimple = False
        self.printStarted = False
        self.waitingForLastRead = False
        self.diag = self.keys.diag
        self.diagStr = diagStr(self.diag)
        self.lastRead = 0 # last line read 
        self.runSimple = pSettings['runSimple']
        self.timeTaken = False
        self.sbWin = sbWin
        self.sbRunFlag1 = sbRunFlag1
        self.setUpPointWatch(pSettings, dt, sbpfile)
        self.assignFlags()
        
        
    def setUpPointWatch(self, pSettings:dict, dt:float, sbpfile:str) -> None:
        '''set up the point watch object'''
        self.pw = pointWatch(pSettings, dt, self.diagStr, self, self.runSimple)
        self.readKeys()   # intialize flag, loc
        
        self.pw.readCSV(sbpfile)

    @pyqtSlot()
    def assignFlags(self) -> None:
        '''for each flag in the points csv, assign behaviors using a dictionary of channelWatch objects'''
        
        # create channels
        for key in self.pw.points:
            if key.startswith('p') and key.endswith('_before'):
                # only take the before
                spl = re.split('p|_', key)
                flag0 = int(spl[1])   # 0-indexed
                if not flag0==self.sbRunFlag1-1:
                    self.channelWatches[flag0] = channelWatch(flag0, self.pSettings, self.diagStr, self.pw, self.keys.pins, self.runSimple)
                   
        self.defineHeader()
                    
        # assign behaviors to channels
        if hasattr(self.sbWin, 'fluBox') and hasattr(self.sbWin.fluBox, 'pchannels'):
            for channel in self.sbWin.fluBox.pchannels:
                flag0 = channel.flag1-1
                if flag0 in self.channelWatches:
                    cw = self.channelWatches[flag0]
                    # connect signals to fluigent functions and calibration functions
                    cw.mode = 1
                    self.modes.append(1)
                    cw.signals.goToPressure.connect(channel.goToRunPressure)
                    cw.signals.zeroChannel.connect(channel.zeroChannel)
                    cw.signals.printStatus.connect(channel.updatePrintStatus)
                    self.pw.signals.printStatus.connect(channel.updatePrintStatus)
                    if hasattr(self.sbWin, 'calibDialog'):
                        calibBox = self.sbWin.calibDialog.calibWidgets[channel.chanNum0]
                        cw.signals.updateSpeed.connect(calibBox.updateSpeedAndPressure)

        # assign behaviors to cameras
        if hasattr(self.sbWin, 'camBoxes'):
            fdict = self.sbWin.camBoxes.listFlags0()
            for flag0 in fdict:
                if flag0 in self.channelWatches:
                    cw = self.channelWatches[flag0]
                    cw.mode = 2
                    self.modes.append(2)
                    camBox = fdict[flag0]
                    # camBox.tempCheck()    # set the record checkbox to checked
                    # cw.signals.finished.connect(camBox.resetCheck)  # reset the checkbox when done
                    cw.signals.snap.connect(camBox.cameraPic)   # connect signal to snap function

        self.pw.findFirstPoint(list(self.channelWatches.keys()))

    
      
    #----------------------------------------

    def killSBP(self) -> None:
        '''kill the print'''
        # print('killing sbp')
        hwndMain = win32gui.FindWindow(None, 'ShopBotEASY')
        if hwndMain>0:
            # print('killing print')
            time.sleep(self.dt/1000/2)
            self.killPrint()

            
    def killPrint(self) -> None:
        '''kill the print'''
        hwndMain = win32gui.FindWindow(None, 'ShopBotEASY')
        hwndChild = win32gui.GetWindow(hwndMain, win32con.GW_CHILD)   # find the STOP HIT window
        win32gui.SetForegroundWindow(hwndChild)                       # bring the stop hit window to the front
        win32api.PostMessage( hwndChild, win32con.WM_KEYDOWN, win32con.VK_SPACE, 0) # close the stop hit window
        time.sleep(self.dt/1000/2)
        
    
    def stopHitPoint(self) -> bool:
        '''check if the stop was hit via the read point'''        
        if not self.runningSBP:
            # stop hit, end loop
            self.killSBP()
            return True
        
        if not self.printStarted:
            return False

        return self.pw.retracting() # check z
 
    
    def defineHeader(self):
        '''define the diagnostics print header'''
        headStr = ''
        for flag0,cw in self.channelWatches.items():
            cw.diagHeader()
        self.pw.diagHeader()
        self.diagStr.printHeader()
    
    def diagPosRow(self, newPoint:bool=False) -> None:
        '''get a row of diagnostic data'''
        if self.diag>1:
            for flag0, cw in self.channelWatches.items():
                cw.diagPosRow(self.sbFlag)
            self.pw.diagPosRow(self.sbFlag, newPoint)
        return


    #-------------------------------------
    
    def readKeys(self) -> None:
        '''initialize the flag and locations'''
        self.keys.lock()
        self.sbFlag = self.keys.getSBFlag()   # gets flag and sends signal back to GUI from keys
        self.pw.updateReadLoc(self.keys.getLoc())       # gets SB3 location and sends signal back to GUI from keys
        self.runningSBP = self.keys.runningSBP   # checks if the stop button has been hit
        self.pw.updateLastRead(self.keys.getLastRead())  # get the last line read into the shopbot. this is ahead of the line it is running
        newDiag = self.keys.diag                # logging mode           
        self.keys.unlock()
        
        # update diagnostic mode
        if not hasattr(self, 'diag') or not newDiag==self.diag:
            self.diag = newDiag
            self.diagStr.diag = newDiag
    
    @pyqtSlot()
    def updateState(self) -> None:
        '''get values from the keys'''
        self.readKeys()
        if not self.runSimple==1:
            est = self.pw.d.estimate
            self.signals.estimate.emit(est[0], est[1], est[2])  # update the estimate in the display
            # don't need to update the read point in display because flags.py already did it
            # determine if we can go onto the next point
        self.diagPosRow(newPoint=False)             # get diagnostic row

    
    #---------------------------------
    # each new point

    def updateSpeeds(self, targetPoint:pd.Series):
        '''update flow speeds'''
        for flag0, cw in self.channelWatches.items():
            cw.updateSpeed()

    def defineStates(self) -> None:
        ''''determine the state of the print, i.e. what we should watch for'''
        for flag0, cw in self.channelWatches.items():
            # for each channel, determine when to change state
            cw.defineState()
            
    def readPoint(self, letQueuedKill:bool=True) -> None:
        '''read a new point'''
        self.printi+=1
        t = self.pw.readPoint(letQueuedKill)   # get new target
        if len(t)==0:
            # print('read point rejected')
            # read point was rejected
            return
        if pd.isna(t['speed']):
            # this is just a speed step. adjust speeds and go to the next point
            self.updateSpeeds(t)
            if self.diag>1:
                print('Update speed')
            self.readPoint()
            return
        else:
            # this is a new point. update the channelWatches and update the gui
            self.signals.target.emit(*toXYZ(t))          # update gui
            self.signals.targetLine.emit(int(t['line']))
            self.defineStates()
            if self.diag>1:  
                self.diagPosRow(newPoint=True)
                
            
    #---------------------------------
    # each new time step
    
    def flagDone(self) -> bool:
        return self.sbFlag==0
    
    def printRow(self):
        '''print the table and status if in the right mode. return status to the shopbot box'''
        self.signals.status.emit(self.diagStr.status)
        self.diagStr.printRow()

    def evalState(self) -> bool:
        '''determine what to do about the channels'''
        # get keys and position, new estimate position
        
        self.diagStr.newRow()
        
        if not self.printStarted:
            # once we go below z=0, we've started printing
            if self.pw.printStarted():
                self.printStarted = True

        self.updateState()   # get status from sb3 and arduino, let pointWatch and distances recalculate 
        if self.runSimple==1 and self.flagDone():
            # print finished, end loop
            self.diagStr.addStatus('DONE flag off')
            self.diagStr.printRow()
            self.signals.status.emit(self.diagStr.status)
            return True

        tc = False
        for flag0, cw in self.channelWatches.items():
            # determine if each channel has reached the action
            trustChanged = cw.assessPosition(self.sbFlag)
            tc = tc or trustChanged
        
        if not trustChanged and self.pw.readyForNextPoint():
            # pointWatch says it's time for the next point
            for cw in self.channelWatches.values():
                # make any channels not attached to a trustworthy flag finish this move
                cw.forceAction()
            self.printRow()
            self.readPoint()
        else:
            self.printRow()
          
        
        return self.pw.tableDone

    #----------------------------
    
    @pyqtSlot()
    def run(self):
        while True:  
            # check for stop hit
            self.keys.lock()
            abort = self.keys.checkStop()
            self.keys.unlock()
            if abort:
                # stop hit on shopbot
                self.close()
                self.signals.aborted.emit()
                return
            
            killed = self.stopHitPoint()
            if killed:
                if self.pw.retracting():
                    # final withdrawal
                    time.sleep(1) # wait 1 second before stopping videos
                    self.close()
                    self.signals.finished.emit()
                else:
                    # stop hit on shopbot
                    self.close()
                    self.signals.aborted.emit()
                return
            
            # evaluate status
            done = self.evalState()
            if done:
                time.sleep(1) # wait 1 second before stopping videos
                self.close()
                self.signals.finished.emit()
                return
            
            time.sleep(self.dt/1000)
    
    def close(self):
        '''close all the channels'''
        for flag0,item in self.channelWatches.items():
            item.close()
    
