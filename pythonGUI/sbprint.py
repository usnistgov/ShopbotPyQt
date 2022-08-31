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
                


    
#---------------------------------------------
    
    
def flagOn(sbFlag:int, flag0:int) -> bool:
    '''test if the 0-indexed flag is on'''
    binary = bin(sbFlag)   # convert to binary
    if len(binary)<2+flag0+1:
        return False       # binary doesn't have enough digits
    else:
        return bool(int(binary[-(flag0+1)]))     # find value at index

        
class channelWatchSignals(QObject):
    goToPressure = pyqtSignal(float)  # send burst pressure to fluigent
    zeroChannel = pyqtSignal(bool)    # zero fluigent channel
    snap = pyqtSignal()       # tell camera to take a snapshot
    updateSpeed = pyqtSignal(float)   # send new extrusion speed to fluigent
    finished = pyqtSignal()
    
    
class channelWatch(QObject):
    '''holds functions for turning on and off pressure'''
    
    def __init__(self, flag0:int, pSettings:dict, diag:int):
        super().__init__()
        self.on = False
        self.flag0 = flag0
        self.mode = 1
        self.turningDown = False
        self.diag = diag
        # store burstScale, burstLength, zero, critTimeOn, critTimeOff
        for s,val in pSettings.items():
            setattr(self, s, val)
        self.signals = channelWatchSignals()
    
    def turnOn(self) -> None:
        '''turn the pressure on to the burst pressure, or snap a picture'''
        if self.mode == 1:
            # turn pressure on to burst pressure
            self.signals.goToPressure.emit(self.burstScale)
            self.on=True
            self.turningDown = True
            if self.diag>1:
                print('turn on')
        elif self.mode == 2:
            # snap pictures
            self.signals.snap.emit()
                
                
    def turnDown(self, l:float) -> None:
        '''turn the pressure down, given a distance from the last point'''
        if self.mode==1 and self.on:
            if l>self.burstLength:
                scale = 1
                self.turningDown = False   # stop turning down, met burst length
            else:
                scale = 1 + (self.burstScale-1)*(1-l/self.burstLength)
            self.signals.goToPressure.emit(scale)
            if self.diag>1:
                print(f'turn down {scale}')
                        
    def turnOff(self) -> None:
        '''turn the pressure off'''
        if self.mode == 1:
            self.signals.zeroChannel.emit(False)
            self.on=False
            self.turningDown = False
            if self.diag>1:
                print('turn off')
                
    def updateSpeed(self, speed:float) -> None:
        '''send new extrusion speed to fluigent'''
        self.signals.updateSpeed.emit(speed)
        
    def defineState(self, targetPoint:pd.Series, nextPoint:pd.Series, lastPoint:pd.Series) -> None:
        '''determine when to turn on, turn off'''
        before = targetPoint[f'p{self.flag0}_before']
        after = targetPoint[f'p{self.flag0}_after']
        if f'p{self.flag0}_before' in nextPoint:
            nbefore = nextPoint[f'p{self.flag0}_before']
            nafter = nextPoint[f'p{self.flag0}_after']
        else:
            nbefore = 0
            nafter = 0
        if f'p{self.flag0}_before' in lastPoint:
            lbefore = lastPoint[f'p{self.flag0}_before']
            lafter = lastPoint[f'p{self.flag0}_after']
        else:
            lbefore = 0
            nafter = 0
        
        if self.mode==2:
            # camera
            if before==0 and after==1:
                # snap camera at point
                self.state = 4
            else:
                # do nothing at point
                self.state = 0
        elif self.mode==1:
            # fluigent
            if before==0 and after==1:
                if nbefore==1 and nafter==0 and targetPoint['x']==nextPoint['x'] and targetPoint['y']==nextPoint['y'] and targetPoint['z']==nextPoint['z']:
                    # turn on, then turn off
                    self.state = 0
                else:
                    # turn on within crit distance of point
                    self.state=1
                    self.critDistance = max(self.zeroDist, abs(self.critTimeOn)*targetPoint['speed'])
            elif before==1 and after==0:
                # turn off after crit distance of point
                if lbefore==0 and lafter==1 and targetPoint['x']==lastPoint['x'] and targetPoint['y']==lastPoint['y'] and targetPoint['z']==lastPoint['z']:
                    self.state = 0
                else:
                    self.state = 5

                    if self.critTimeOff<0:
                        # turn off before crit distance of point
                        self.critDistance = -max(self.zeroDist, -self.critTimeOff*targetPoint['speed'])
                    else:
                        # turn off after crit distance of point
                        if 'speed' in nextPoint:
                            speed = nextPoint['speed']
                        else:
                            speed = targetPoint['speed']
                        self.critDistance = max(self.zeroDist, self.critTimeOff*speed)

                    # zero out crit distance for short moves
                    tld = ppDist(lastPoint, targetPoint)  # distance between last point and target point
                    if tld<abs(self.critDistance)*2:
                        self.critDistance = self.zeroDist
            else:
                # do nothing at point
                self.state = 0

                
    def forceAction(self) -> None:
        '''force the current action'''
        if self.state==4 or self.state==1:
            self.turnOn()
        elif self.state==5:
            self.turnOff()            
        
                
            
    def assessPosition(self, trd:float, lrd:float, tld:float, ted:float, led:float, sbFlag:int, diagStr:str) -> None:
        '''check the state and do actions if relevant
        trd distance from target to read point
        lrd distance from last to read point
        tld distance from last to target point
        ted distance from target to estimated point
        led distance from last to estimated point
        sbFlag full flag value'''
        
        readyForNextPoint = False
        flagOn0 = flagOn(sbFlag, self.flag0)
        
        # turn down from burst
        if self.turningDown:
            # bring down pressure from burst pressure
               self.turnDown(ted)
        
        if self.state==0:
            pastTarget = led>tld
            zeroMove = tld<self.zeroDist
            atTarget = ted<self.zeroDist
            ratTarget = trd<self.zeroDist
            outsidePath = ((lrd+trd > tld+self.zeroDist))
            if zeroMove or atTarget or (pastTarget and (ratTarget or outsidePath)):
                if self.diag>=2:
                    if zeroMove:
                        print(f'{diagStr} Zero move')
                    if atTarget:
                        print(f'{diagStr} Estimated point at target point')
                    if pastTarget and ratTarget:
                        print(f'{diagStr} Estimated point past target and read at target')
                readyForNextPoint = True
        else:
        
            if self.mode==2:
                # camera
                if self.state==4:
                    # snap camera at point
                    if flagOn0:
                        atTarget = (trd<self.zeroDist and ted<self.zeroDist)
                        pastTarget = led>tld
                        if atTarget:
                            if self.diag>=2:
                                if atTarget:
                                    print(f'{diagStr} Read point and estimated point at target point')
                                # if pastTarget:
                                #     print(f'{diagStr} Estimated point past target')
                            self.turnOn()
                            readyForNextPoint = True
            elif self.mode==1:
                # fluigent
                
                # assess state
                if self.state==1:
                    # turn on within crit distance of point or if we've started on the next line
                    pastTarget = led>tld
                    atTarget = ted<self.critDistance
                    outsidePath = lrd+trd > tld+self.zeroDist
                    if atTarget or outsidePath:
                        if self.diag>=2:
                            if ted<self.critDistance:
                                print(f'{diagStr} Estimated point at target')
                            if outsidePath:
                                print(f'{diagStr} Read point outside path')
                            if pastTarget:
                                print(f'{diagStr} Estimated point past target')
                        self.turnOn()
                        readyForNextPoint = True
                elif self.state==5:
                    # turn off at end

                    if not flagOn0:
                        if tld<self.zeroDist:
                            # no movement during this line
                            if self.diag>=2:
                                print(f'{diagStr} Zero move')
                            self.turnOff()
                            readyForNextPoint = True
                        else:
                            if self.critDistance<0:
                                # turn off before end of line
                                pastTarget = led>tld
                                atTarget = ted<-self.critDistance
                                if atTarget:
                                    if self.diag>=2:
                                        if atTarget:
                                            print(f'{diagStr} Estimated point at target')
                                        if pastTarget:
                                            print(f'{diagStr} Estimated point past target')
                                    self.turnOff()
                                    readyForNextPoint = True
                            else:
                                # turn off after end of line
                                atTarget = led>tld+self.critDistance
                                outsidePath = ((lrd+trd > tld+self.zeroDist) and trd>self.critDistance)
                                if atTarget or outsidePath:
                                    if self.diag>=2:
                                        if atTarget:
                                            print(f'{diagStr} Estimated point at target')
                                        if outsidePath:
                                            print(f'{diagStr} Read point outside path and read point past crit distance')
                                    self.turnOff() 
                                    readyForNextPoint = True
                
        return readyForNextPoint


        
    def close(self) -> None:
        '''close the channel watch, send messages to object'''
        if self.mode==2:
            self.signals.finished.emit()
        elif self.mode==1:
            self.signals.zeroChannel.emit(True)
            
#----------------------------

def toXYZ(p1:Union[pd.Series, List[float]], listOut:bool=False) -> Tuple[float]:
    '''convert the point or pandas series to x,y,z'''
    if type(p1) is list and len(p1)==3:
        x = p1[0]
        y = p1[1]
        z = p1[2]
    elif type(p1) is pd.Series or type(p1) is dict:
        if 'x' in p1:
            x = p1['x']
        else:
            x = np.nan
        if 'y' in p1:
            y = p1['y']
        else:
            y = np.nan
        if 'z' in p1:
            z = p1['z']
        else:
            z = np.nan
    else:
        raise ValueError('Unknown type given to toXYZ')
    if listOut:
        return x,y,z
    else:
        return [x,y,z]

def dxdydz(p1:Union[pd.Series, List[float]], p2:Union[pd.Series, List[float]]) -> Tuple[float]:
    '''convert the two points to their differences'''
    p1x, p1y, p1z = toXYZ(p1)
    p2x, p2y, p2z = toXYZ(p2)

    if pd.isna(p2x) or pd.isna(p1x):
        dx = 0
    else:
        dx = float(p2x)-float(p1x)
    if pd.isna(p2y) or pd.isna(p1y):
        dy = 0
    else:
        dy =  float(p2y)-float(p1y)
    if pd.isna(p2z) or pd.isna(p1z):
        dz = 0
    else:
        dz = float(p2z)-float(p1z)
    return dx,dy,dz

def ppDist(p1:Union[pd.Series, List[float]], p2:Union[pd.Series, List[float]]) -> float:
    '''distance between two points'''
    dx,dy,dz = dxdydz(p1, p2)
    return np.sqrt(dx**2+dy**2+dz**2)
    
def ppVec(p1:pd.Series, p2:pd.Series) -> Tuple[float]:
    '''get the normalized direction'''
    dx,dy,dz = dxdydz(p1, p2)
    dist =  np.sqrt(dx**2+dy**2+dz**2)
    if dist==0:
        return [0,0,0]
    else:
        return [dx/dist, dy/dist, dz/dist]
    
    
    
    
class printLoopSignals(QObject):
    finished = pyqtSignal()   # print is done
    aborted = pyqtSignal()    # print was aborted from sbp app
    estimate = pyqtSignal(float,float,float)   # new estimated position
    
    
class printLoop(QObject):
    '''loop through this while prints are running
    dt is loop time in ms
    keys is an SBKeys object
    sbpfile is the name of the sbp file '''
    
    def __init__(self, dt:float, keys:QMutex, sbpfile:str, pSettings:dict, sbWin, sbRunFlag1):
        super(printLoop,self).__init__()
        self.dt = dt
        self.keys = keys    # holds windows registry keys
        self.signals = printLoopSignals()
        self.channelWatches = {}
        self.modes = []
        self.pSettings = pSettings
        self.tableDone = False
        self.targetPoint = {}
        self.nextPoint = {}
        self.zeroDist = pSettings['zeroDist']
        self.trd = 10000
        self.lrd = 10000
        self.tld = 10000
        self.ted = 10000
        self.timeTaken = False
        self.readKeys()   # intialize flag, loc
        self.lastPoint = {'x':self.readLoc[0], 'y':self.readLoc[1], 'z':self.readLoc[2]}
        self.readCSV(sbpfile)    # read points
        self.assignFlags(sbWin, sbRunFlag1)


    def assignFlags(self, sbWin, sbRunFlag1:int) -> None:
        '''for each flag in the points csv, assign behaviors using a dictionary of channelWatch objects'''
        
        # create channels
        for key in self.points:
            if key.startswith('p') and key.endswith('_before'):
                # only take the before
                spl = re.split('p|_', key)
                flag0 = int(spl[1])   # 0-indexed
                if not flag0==sbRunFlag1-1:
                    self.channelWatches[flag0] = channelWatch(flag0, self.pSettings, self.diag)
                   
                    
        # assign behaviors to channels
        if hasattr(sbWin, 'fluBox') and hasattr(sbWin.fluBox, 'pchannels'):
            for channel in sbWin.fluBox.pchannels:
                flag0 = channel.flag1-1
                if flag0 in self.channelWatches:
                    cw = self.channelWatches[flag0]
                    # connect signals to fluigent functions and calibration functions
                    cw.mode = 1
                    self.modes.append(1)
                    cw.signals.goToPressure.connect(channel.goToRunPressure)
                    cw.signals.zeroChannel.connect(channel.zeroChannel)
                    if hasattr(sbWin, 'calibDialog'):
                        calibBox = sbWin.calibDialog.calibWidgets[channel.chanNum0]
                        cw.signals.updateSpeed.connect(calibBox.updateSpeedAndPressure)

        # assign behaviors to cameras
        if hasattr(sbWin, 'camBoxes'):
            fdict = sbWin.camBoxes.listFlags0()
            for flag0 in fdict:
                if flag0 in self.channelWatches:
                    cw = self.channelWatches[flag0]
                    cw.mode = 2
                    self.modes.append(2)
                    camBox = fdict[flag0]
                    camBox.tempCheck()    # set the record checkbox to checked
                    cw.signals.finished.connect(camBox.resetCheck)  # reset the checkbox when done
                    cw.signals.snap.connect(camBox.cameraPic)   # connect signal to snap function
       
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
        self.fillTable()    # fill empty entries with current position

        
    def naPoint(self, row) -> bool:
        '''determine if the point is not filled'''
        return pd.isna(row['x']) or pd.isna(row['y']) or pd.isna(row['z'])

    def fillTable(self) -> None:
        '''go through the top of the table and fill empty entries with the current position'''
        for i,row in self.points.iterrows():
            if self.naPoint(self.points.loc[i]):
                for j,var in {0:'x', 1:'y', 2:'z'}.items():
                    if pd.isna(self.points.loc[i, var]):
                        self.points.loc[i, var] = self.readLoc[j]   # fill empty value
            else:
                return

    def updateSpeeds(self, targetPoint:pd.Series):
        '''update flow speeds'''
        for flag0, cw in self.channelWatches.items():
            if targetPoint[f'p{flag0}_before']<0 and targetPoint[f'p{flag0}_after']>0:
                # change speed
                cw.updateSpeed(targetPoint[f'p{flag0}_after'])
                    
    def readPoint(self) -> None:
        '''read the next point from the points list'''
        self.pointTime = datetime.datetime.now()
        self.changePoint = self.readLoc
        self.timeTaken = False
        self.pointsi+=1
        if self.pointsi>=0 and self.pointsi<len(self.points):
            targetPoint = self.points.iloc[self.pointsi] 
            if pd.isna(targetPoint['speed']):
                # this is just a speed step. adjust speeds and go to the next point
                self.updateSpeeds(targetPoint)
                self.readPoint()
                return
                
            # define last and next points
            if self.pointsi>0:
                self.lastPoint = self.targetPoint
            self.targetPoint = targetPoint
            self.targetVec = ppVec(self.lastPoint, self.targetPoint)
            if len(self.points)>self.pointsi+1:
                self.nextPoint = self.points.iloc[self.pointsi+1]
                self.nextVec = ppVec(self.targetPoint, self.nextPoint)
            self.defineStates()
        else:
            self.tableDone = True
        if self.diag>1:  
            print(f'New point row {self.pointsi}')
        if  (self.diag>1 and (self.pointsi%100==0)):
            # print(f'flag0\ton\tmode\tstate\ttrd\tlrd\ttld\tted\tdone\tlrd+trd\ttld+0\tx\ty\tz')
            headStr = f'flag0\ton\tmode\tstate\tx\ty\tz|\txe\tye\tze|\txt\tyt\tzt|\tflag'
            if self.diag>2:
                 headStr = headStr + f'\ttrd\tlrd\ttld\tted\tled'
            print(headStr)

        
            
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
        

    def estimateLoc(self) -> None:
        '''estimate the current location based on time since hitting last point and translation speed'''
        
        if not self.timeTaken:
            self.estLoc = self.readLoc
        else:
            dnow = datetime.datetime.now()
            dt = (dnow - self.pointTime).total_seconds()   # time since we hit the last point
            if not ('speed' in self.targetPoint and 'x' in self.lastPoint):
                self.estLoc = self.readLoc
            else:
                pt = toXYZ(self.lastPoint, listOut=True)
                vec = self.targetVec
                speed = float(self.targetPoint['speed'])
                distTraveled = speed*dt # distance traveled since we hit the last point
                self.estLoc = [pt[i]+distTraveled*vec[i] for i in range(3)]  # estimated position
        self.signals.estimate.emit(self.estLoc[0], self.estLoc[1], self.estLoc[2])


    def evalState(self) -> bool:
        '''determine what to do about the channels'''
        # get keys and position, new estimate position
        self.updateState()
        if not self.runningSBP:
            # stop hit, end loop
            self.killSBP()
            return True
        if self.flag==0:
            # print finished, end loop
            return True
        
        trd = ppDist(self.readLoc, self.targetPoint)   # distance between the read loc and the target point
        if 'x' in self.lastPoint:
            lrd = ppDist(self.readLoc, self.lastPoint)   # distance between the read loc and the last point
            tld = ppDist(self.lastPoint, self.targetPoint)  # distance between last point and target point
        else:
            lrd = 0
            tld = 0
         
        ted = ppDist(self.estLoc, self.targetPoint) # distance between the estimated loc and the target point
        led = ppDist(self.estLoc, self.lastPoint) # distance between estimated loc and last point
        
        self.trd = trd
        self.lrd = lrd
        self.tld = tld
        self.ted = ted
        self.led = led
        
        if not self.timeTaken and self.lrd>self.zeroDist:
            # reset the time when the stage actually starts moving
            self.pointTime = datetime.datetime.now()
            self.timeTaken = True

        readyForNextPoint = {}
        ready = False
        
        if not 2 in self.modes:
            # determine if we've changed direction. don't do this for camera runs
            if ppDist(self.oldReadLoc, self.readLoc)>self.zeroDist:
                vec = ppVec(self.oldReadLoc, self.readLoc)
                angle = np.arccos(np.dot(vec, self.targetVec))
            else:
                angle = 0
        else:
            angle = 0
            
            
        if angle>np.pi/8:
            # changed direction
            ready = True
            for flag0 in self.channelWatches:
                readyForNextPoint[flag0] = False
        else:
        
            for flag0, cw in self.channelWatches.items():
                # determine if each channel has reached the action
                if self.diag>1:
                    # print(f'{self.flag0}\t{flagOn0}\t{self.mode}\t{self.state}\t
                    #     {trd:2.2f}\t{lrd:2.2f}\t{tld:2.2f}\t{ted:2.2f}\t{readyForNextPoint}\t
                    #     {(lrd+trd):2.2f}\t{(tld+self.zeroDist):2.2f}')
                    flagOn0 = flagOn(self.flag, cw.flag0)
                    x,y,z = toXYZ(self.readLoc)
                    xt,yt,zt = toXYZ(self.targetPoint)
                    xe,ye,ze = toXYZ(self.estLoc)
                    diagStr =  f'{cw.flag0}\t{flagOn0}\t{cw.mode}\t{cw.state}|'
                    diagStr = diagStr + f'\t{x:2.2f}\t{y:2.2f}\t{z:2.2f}|'
                    diagStr = diagStr + f'\t{xe:2.2f}\t{ye:2.2f}\t{ze:2.2f}|'
                    diagStr = diagStr + f'\t{xt:2.2f}\t{yt:2.2f}\t{zt:2.2f}|'
                    diagStr = diagStr + f'\t{self.flag}'
                else:
                    diagStr = ''
                if self.diag>2:
                    diagStr = diagStr + f'\t{trd:2.2f}\t{lrd:2.2f}\t{tld:2.2f}\t{ted:2.2f}\t{led:2.2f}'
                    print(diagStr)
                    diagStr = ''
                readyForNextPoint[flag0] = cw.assessPosition(trd, lrd, tld, ted, led, self.flag, diagStr)
                if readyForNextPoint[flag0]:
                    ready = True
                
                
        if ready:
            # if only some of the channels have moved on, force the action for the rest of them
            for flag0, r0 in readyForNextPoint.items():
                if not r0:
                    self.channelWatches[flag0].forceAction()
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
    
