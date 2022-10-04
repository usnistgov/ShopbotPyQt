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
            ready = self.keys.waitForSBReady()
            running = self.keys.runningSBP
            self.keys.unlock()
            if ready or not running:
                self.signals.finished.emit()
                return
            else:
                time.sleep(self.dt/1000)  # loop every self.dt seconds
        
#-----------------------------------------------

# def checkStopHit(self) -> None:
#         '''this checks for a window that indicates that the stop has been hit, either on the SB3 software, or through an emergency stop. this function tells sb3 to quit printing and tells sbgui to kill this print '''
#         hwndMain = win32gui.FindWindow(None, 'PAUSED in Movement or File Action')
#         if hwndMain>0:
            
#         return
    
# def killStopHit(self) -> None:
#     '''kill the stop hit window'''
#     # trigger the end of print
#     hwndChild = win32gui.GetWindow(hwndMain, win32con.GW_CHILD)
#     win32gui.SetForegroundWindow(hwndChild)
#     win32api.PostMessage( hwndChild, win32con.WM_KEYDOWN, 0x51, 0)
    


class waitForStart(QRunnable):
    '''waiting for the printer to start printing'''
    
    def __init__(self, dt:float, keys:QMutex, runFlag1:int, channelsTriggered:list):
        super(waitForStart,self).__init__()
        self.dt = dt
        self.keys = keys
        self.runFlag1 = runFlag1
        self.channelsTriggered = channelsTriggered
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
            cf = 2**(self.runFlag1-1) + 2**(self.channelsTriggered[0]) # the critical flag at which flow starts
            self.updateStatus(f'Waiting to start file, Shopbot output flag = {sbFlag}, start at {cf}', False)
            if sbFlag==cf or not running:
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

    
class printLoopSignals(QObject):
    finished = pyqtSignal()   # print is done
    aborted = pyqtSignal()    # print was aborted from sbp app
    estimate = pyqtSignal(float,float,float)   # new estimated position
    target = pyqtSignal(float,float,float)      # send current target to GUI
    
    
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
        self.printStarted = False
        self.hitRead = False
        self.targetPoint = {}
        self.nextPoint = {}
        self.zeroDist = pSettings['zeroDist']
        self.timeTaken = False
        self.readKeys()   # intialize flag, loc
        self.lastPoint = {'x':self.readLoc[0], 'y':self.readLoc[1], 'z':self.readLoc[2]}
        self.readCSV(sbpfile)    # read points
        self.sbWin = sbWin
        self.sbRunFlag1 = sbRunFlag1
        self.assignFlags()

    @pyqtSlot()
    def assignFlags(self) -> None:
        '''for each flag in the points csv, assign behaviors using a dictionary of channelWatch objects'''
        
        # create channels
        for key in self.points:
            if key.startswith('p') and key.endswith('_before'):
                # only take the before
                spl = re.split('p|_', key)
                flag0 = int(spl[1])   # 0-indexed
                if not flag0==self.sbRunFlag1-1:
                    self.channelWatches[flag0] = channelWatch(flag0, self.pSettings, self.diag)
                   
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
                    camBox.tempCheck()    # set the record checkbox to checked
                    cw.signals.finished.connect(camBox.resetCheck)  # reset the checkbox when done
                    cw.signals.snap.connect(camBox.cameraPic)   # connect signal to snap function
       
        self.pointTime = datetime.datetime.now()
        self.changePoint = self.readLoc
        if len(self.points)>1:  
            on = False
            # find first flag change
            while not on and not self.tableDone:
                self.readPoint()
                for flag0 in self.channelWatches:
                    if self.targetPoint[f'p{flag0}_after']==1:
                        on = True
        else:
            self.readPoint()
            
    
      
    #----------------------------------------
            
#     def checkStopHit(self) -> bool:
#         '''this checks for a window that indicates that the stop has been hit, either on the SB3 software, or through an emergency stop. this function tells sb3 to quit printing and tells sbgui to kill this print '''
#         hwndMain = win32gui.FindWindow(None, 'PAUSED in Movement or File Action')
#         if hwndMain>0:
#             print(f'stop hit on sb3, {hwndMain}')
#             time.sleep(self.dt/2/1000)
#             self.killStopHit()
#             return True
#         else:
#             return False
    
#     def killStopHit(self) -> None:
#         '''kill the stop hit window'''
#         # trigger the end of print
#         hwndMain = win32gui.FindWindow(None, 'PAUSED in Movement or File Action')
#         hwndChild = win32gui.GetWindow(hwndMain, win32con.GW_CHILD)   # find the STOP HIT window
#         win32gui.SetForegroundWindow(hwndChild)                       # bring the stop hit window to the front
#         win32api.PostMessage( hwndChild, win32con.WM_KEYDOWN, 0x51, 0) # close the stop hit window
#         return
    

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
        # stopHit = False
        # while not stopHit:
        #     stopHit = self.checkStopHit()
    
        
    def readCSV(self, sbpfile:str):
        '''get list of points from the sbp file'''
        if not sbpfile.endswith('.sbp'):
            raise ValueError('Input to SBPtimings must be an SBP file')
        sbpfile = sbpfile
        csvfile = sbpfile.replace('.sbp', '.csv')
        if not os.path.exists(csvfile):
            sp = SBPPoints(sbpfile)
            sp.export()
            sp = pd.read_csv(csvfile, index_col=0)
        else:
            sp = pd.read_csv(csvfile, index_col=0)
        self.points = sp
        self.pointsi = -1
        self.printi = -1
        self.zmax = self.points[self.points.z<=0].z.max() + 2
        self.fillTable()    # fill empty entries with current position

        
    def naPoint(self, row) -> bool:
        '''determine if the point is not filled'''
        return pd.isna(row['x']) or pd.isna(row['y']) or pd.isna(row['z'])

    def fillTable(self) -> None:
        '''go through the top of the table and fill empty entries with the current position'''
        self.starti = 0
        for i,row in self.points.iterrows():
            if self.naPoint(self.points.loc[i]):
                for j,var in {0:'x', 1:'y', 2:'z'}.items():
                    if pd.isna(self.points.loc[i, var]):
                        self.points.loc[i, var] = self.readLoc[j]   # fill empty value
                        self.starti = i+2
            else:
                return

    def updateSpeeds(self, targetPoint:pd.Series):
        '''update flow speeds'''
        for flag0, cw in self.channelWatches.items():
            if targetPoint[f'p{flag0}_before']<0 and targetPoint[f'p{flag0}_after']>0:
                # change speed
                cw.updateSpeed(float(targetPoint[f'p{flag0}_after']))
           
    @pyqtSlot()
    def readPoint(self) -> None:
        '''read the next point from the points list'''
        self.lastTime = self.pointTime    # store the time when we got the last point
        self.pointTime = datetime.datetime.now()
        self.changePoint = self.readLoc
        self.timeTaken = False
        self.hitRead = False
        self.pointsi+=1
        self.printi+=1
        if self.pointsi>=0 and self.pointsi<len(self.points):
            targetPoint = self.points.iloc[self.pointsi] 
            if pd.isna(targetPoint['speed']):
                # this is just a speed step. adjust speeds and go to the next point
                self.updateSpeeds(targetPoint)
                if self.diag>1:
                    print('Update speed')
                self.readPoint()
                return
                
            # define last and next points
            if self.pointsi>0:
                self.lastPoint = self.targetPoint
            self.targetPoint = targetPoint 
            self.speed = float(self.targetPoint['speed'])
            self.speed0 = self.speed
            self.signals.target.emit(*toXYZ(self.targetPoint))          # update gui
            self.targetVec = ppVec(self.lastPoint, self.targetPoint)
            if len(self.points)>self.pointsi+1:
                self.nextPoint = self.points.iloc[self.pointsi+1]
                self.nextVec = ppVec(self.targetPoint, self.nextPoint)
            self.defineStates()
        else:
            self.tableDone = True
        if self.diag>1:  
            diagStr = self.diagPosRow({}, newPoint=True)
        if  (self.diag>1 and (self.printi>50)):
            print(self.headStr)
            self.printi = 0

        
            
    def defineStates(self) -> None:
        ''''determine the state of the print, i.e. what we should watch for'''
        for flag0, cw in self.channelWatches.items():
            # for each channel, determine when to change state
            cw.defineState(self.targetPoint, self.nextPoint, self.lastPoint)

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
                # if self.pointsi==len(self.points)-1:
                if self.targetPoint['z']>0:
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
    
    #-------------------------------------
    
    def readKeys(self) -> None:
        '''initialize the flag and locations'''
        self.keys.lock()
        self.flag = self.keys.getSBFlag()   # gets flag and sends signal back to GUI from keys
        self.readLoc = self.keys.getLoc()       # gets SB3 location and sends signal back to GUI from keys
        self.runningSBP = self.keys.runningSBP   # checks if the stop button has been hit
        newDiag = self.keys.diag                # logging mode           
        self.keys.unlock()
        
        # update diagnostic mode
        if not hasattr(self, 'diag') or not newDiag==self.diag:
            self.diag = newDiag
            for flag0, cw in self.channelWatches.items():
                cw.diag = newDiag
    
    def updateState(self) -> None:
        '''get values from the keys'''
        self.oldFlag = self.flag
        self.oldReadLoc = self.readLoc
        self.estimateLoc()
        self.readKeys()
        
    @pyqtSlot()
    def estimateLoc(self) -> None:
        '''estimate the current location based on time since hitting last point and translation speed'''
        
        if not self.timeTaken:
            self.estLoc = self.readLoc
        else:
            dnow = datetime.datetime.now()
            dt = (dnow - self.pointTime).total_seconds()   # time since we hit the last point
            if not ('speed' in self.targetPoint and 'x' in self.lastPoint) or self.speed==0:
                self.estLoc = self.readLoc
            else:
                pt = toXYZ(self.lastPoint, listOut=True)
                vec = self.targetVec
                distTraveled = self.speed*dt # distance traveled since we hit the last point
                self.estLoc = [pt[i]+distTraveled*vec[i] for i in range(3)]  # estimated position
        self.signals.estimate.emit(self.estLoc[0], self.estLoc[1], self.estLoc[2])
        
        
    def stopHitPoint(self) -> bool:
        '''check if the stop was hit via the read point'''
        if not hasattr(self, 'readLoc'):
            return False
        
        if not self.runningSBP:
            # stop hit, end loop
            self.killSBP()
            return True
        
        if not self.printStarted:
            return False

        if float(self.readLoc[2])>(self.zmax):
            # stop hit. retracting
            if self.diag>1:
                print(f'z above max, {self.readLoc[2]}, {self.zmax}, {self.pointsi}, {self.starti}')
            return True
        else:
            return False
        
    def getDistances(self) -> dict:
        '''get distances between points'''
        trd = ppDist(self.readLoc, self.targetPoint)   # distance between the read loc and the target point
        if 'x' in self.lastPoint:
            lrd = ppDist(self.readLoc, self.lastPoint)   # distance between the read loc and the last point
            tld = ppDist(self.lastPoint, self.targetPoint)  # distance between last point and target point
        else:
            lrd = 0
            tld = 0
         
        ted = ppDist(self.estLoc, self.targetPoint) # distance between the estimated loc and the target point
        led = ppDist(self.estLoc, self.lastPoint) # distance between estimated loc and last point
        return {'trd':trd, 'lrd':lrd, 'tld':tld, 'ted':ted, 'led':led}
    
    def defineHeader(self):
        '''define the diagnostics print header'''
        headStr = '\t'
        for flag0 in self.channelWatches:
            headStr = headStr + f'flag0:on mode\tstate|\t'
        headStr = headStr + f'xd\tyd\tzd|\txe\tye\tze|\txt\tyt\tzt|\tflag\tspeed\tstart\tend\ttrd\tlrd\ttld\tted\tled'
        self.headStr = headStr
        if self.diag>1:
            print(self.headStr)
    
    def diagPosRow(self, d:dict, newPoint:bool=False) -> str:
        '''get a row of diagnostic data'''

        if self.diag>1:
            diagStr = '\t'
            for flag0, cw in self.channelWatches.items():
                flagOn0 = flagOn(self.flag, flag0)
                diagStr = diagStr + f'{flag0}:{flagOn0}\t{cw.mode}\t{cw.state}|'
            if newPoint:
                diagStr = diagStr + f'p{self.pointsi}'
                diagStr = diagStr + f'\t \t \t \t \t \t '
                flag, speed, timeTaken, stopHit = ' ', ' ', ' ', ' '
                trd, lrd, tld, ted, led = ' ', ' ', ' ', ' ', ' '
            else:
                x,y,z = toXYZ(self.readLoc)
                xe,ye,ze = toXYZ(self.estLoc)
                diagStr = diagStr + f'\t{x:2.2f}\t{y:2.2f}\t{z:2.2f}|'
                diagStr = diagStr + f'\t{xe:2.2f}\t{ye:2.2f}\t{ze:2.2f}|'
                flag = self.flag
                speed = self.speed
                timeTaken = self.timeTaken
                stopHit = self.hitRead
                trd = d['trd']
                lrd = d['lrd']
                tld = d['tld']
                ted = d['ted']
                led = d['led']
            xt,yt,zt = toXYZ(self.targetPoint)
            
            diagStr = diagStr + f'\t{xt:2.2f}\t{yt:2.2f}\t{zt:2.2f}|'
            diagStr = diagStr + f'\t{flag}'
            if newPoint:
                diagStr = diagStr + '\t \t \t \t \t \t \t \t '
            else:
                diagStr = diagStr + f'\t{speed:2.2f}\t{timeTaken}\t{stopHit}'
                diagStr = diagStr + f'\t{trd:2.2f}\t{lrd:2.2f}\t{tld:2.2f}\t{ted:2.2f}\t{led:2.2f}'
        else:
            diagStr = ''
        if self.diag>2:
            print(diagStr)
            self.printi+=1
        return diagStr
    
    
    def evalAngle(self, d:dict) -> Tuple[bool, float]:
        '''evaluate whether the angle of travel agrees with the intended angle of travel'''
        if self.timeTaken and not 2 in self.modes:
            # determine if we've changed direction. don't do this for camera runs or if we haven't started moving yet
            readStepDist = ppDist(self.oldReadLoc, self.readLoc)   # distance traveled between this step and last step
            if readStepDist>self.zeroDist and self.timeTaken:
                vec = ppVec(self.oldReadLoc, self.readLoc)       # direction traveled during this step
                angle = np.arccos(np.dot(vec, self.targetVec))   # angle between traveled vec and target vec
                nextAngle = np.arccos(np.dot(vec, self.nextVec)) # angle between vec and next vec
            else:
                angle = 0
        else:
            angle = 0

        if angle>np.pi/4 and self.hitRead:
            # we've changed directions and already hit the read point
            return True, angle
        else:
            # we've changed directions to the new direction
            return (angle>np.pi/4 and angle<np.pi*3/4 and nextAngle<np.pi/16), angle
    
    def checkHitRead(self, d:dict):
        '''check if the read point has hit the target point'''
        if not self.hitRead:
            if d['trd']<self.zeroDist or d['lrd']+d['trd'] > d['tld']+self.zeroDist:
                self.hitRead = True    # indicate we've hit the read point and are ready to move on
                
    def checkTimeTaken(self, d:dict):
        '''check if the time has started to write estimate points'''
        if not self.timeTaken and d['lrd']>self.zeroDist:
            # reset the time when the stage actually starts moving
            self.pointTime = datetime.datetime.now()
            self.timeTaken = True
            
    def checkEstimate(self, d:dict, diagStr:str) -> str:
        '''check if the estimate position is at the right speed'''
        if d['led']>d['lrd'] and self.speed>0.8*self.speed0:
            # estimate has gone past read point: slow down estimate
            self.speed = 0.95*self.speed  
            if self.diag>2:
                diagStr = diagStr + f' Reduce speed to {self.speed:2.2f}'
        return diagStr

    def evalState(self) -> bool:
        '''determine what to do about the channels'''
        # get keys and position, new estimate position
        if not self.printStarted:
            # once we go below z=0, we've started printing
            if self.readLoc[2]<self.zmax:
                self.printStarted = True
        
        self.updateState()
        if self.flag==0:
            # print finished, end loop
            return True
        d = self.getDistances()                  # get distances between points
        self.checkHitRead(d)                     # check if the read point has hit the target
        self.checkTimeTaken(d)                   # check if we've started the line
        diagStr = self.diagPosRow(d)             # get diagnostic row
        diagStr = self.checkEstimate(d,diagStr)  # check estimate
        
        readyForNextPoint = {}
        ready = False
        force, angle = self.evalAngle(d)
        if force:
            ready = True
            for flag0 in self.channelWatches:
                readyForNextPoint[flag0] = False
        else:
            # still going in the same direction
            for flag0, cw in self.channelWatches.items():
                # determine if each channel has reached the action
                readyForNextPoint[flag0] = cw.assessPosition(d, self.flag, diagStr)
                if readyForNextPoint[flag0]:
                    ready = True
                
        if ready:
            # if only some of the channels have moved on, force the action for the rest of them
            for flag0, r0 in readyForNextPoint.items():
                if not r0:
                    self.channelWatches[flag0].forceAction(diagStr, angle)
            # move onto the next point
            self.readPoint()
            if self.tableDone:
                return True
            
        return False

    
    #----------------------------
    
    def close(self):
        '''close all the channels'''
        for flag0,item in self.channelWatches.items():
            item.close()
    
