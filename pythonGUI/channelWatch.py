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

#---------------------------------------------

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
    printStatus = pyqtSignal(str)
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
    
    @pyqtSlot() 
    def turnOn(self) -> None:
        '''turn the pressure on to the burst pressure, or snap a picture'''
        if self.mode == 1:
            # turn pressure on to burst pressure
            self.signals.goToPressure.emit(self.burstScale)
            self.on=True
            self.turningDown = True
        elif self.mode == 2:
            # snap pictures
            self.signals.snap.emit()
                
     
    @pyqtSlot(float) 
    def turnDown(self, l:float) -> None:
        '''turn the pressure down, given a distance from the last point'''
        if self.mode==1 and self.on:
            if l>self.burstLength:
                scale = 1
                self.turningDown = False   # stop turning down, met burst length
            else:
                scale = 1 + (self.burstScale-1)*(1-l/self.burstLength)
            self.signals.goToPressure.emit(scale)
     
    @pyqtSlot() 
    def turnOff(self) -> None:
        '''turn the pressure off'''
        if self.mode == 1:
            self.signals.zeroChannel.emit(False)
            self.on=False
            self.turningDown = False
    
    @pyqtSlot(float) 
    def updateSpeed(self, speed:float) -> None:
        '''send new extrusion speed to fluigent'''
        self.signals.updateSpeed.emit(speed)
        if self.on:
            # if pressure is on, go to that pressure
            self.signals.goToPressure.emit(1)
        
    def defineState(self, targetPoint:pd.Series, nextPoint:pd.Series, lastPoint:pd.Series) -> None:
        '''determine when to turn on, turn off'''
        before = targetPoint[f'p{self.flag0}_before']
        after = targetPoint[f'p{self.flag0}_after']
        self.hitRead = False
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
                    tld = ppDist(lastPoint, targetPoint)  # distance between last point and target point
                    if tld<abs(self.critDistance)*2:
                        self.critDistance = self.zeroDist
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
                    if tld<abs(self.critDistance):
                        self.critDistance = self.zeroDist
            else:
                # do nothing at point
                self.state = 0

    @pyqtSlot(str, float, float)          
    def forceAction(self, diagStr:str, angle:float) -> None:
        '''force the current action'''
        sadd = ''
        if self.state==4 or self.state==1:
            self.turnOn()
            sadd = sadd + 'ON'
        elif self.state==5:
            self.turnOff() 
            sadd = sadd + 'OFF'
        else:
            sadd = sadd + 'NONE'
        sadd = sadd + f' Force action: {angle:1.2f}'
        self.signals.printStatus.emit(sadd)
        diagStr = diagStr+' '+sadd
        if self.diag>=2:
            print(diagStr)
        
    @pyqtSlot(str, str)
    def emitStatus(self, diagStr:str, sadd:str) -> None:
        '''print the status and emit it to the channel'''
        self.signals.printStatus.emit(sadd)
        if self.diag>=2:   
            print(f'{diagStr} {sadd}')
            
    def getSadd(self, change:str, d:dict, diagStr:str) -> None:
        '''get a status string based on a dictionary of bools. change is a string to put at the front'''
        s = change
        for key,val in d.items():
            if val:
                s = s + ' ' + key
        self.emitStatus(diagStr, s)
            
        
    def assessNoChange(self, d:dict, diagStr:str) -> bool:
        '''assess status when there is no change in channels at the end of the move
        led distance from last to estimated point
        tld distance from last to target point
        '''
        pastTarget = d['led']>d['tld']
        zeroMove = d['tld']<self.zeroDist
        atTarget = d['ted']<self.zeroDist
        ratTarget = self.hitRead
        if zeroMove or atTarget or (pastTarget and ratTarget):
            self.getSadd('NONE', {'Zero move':zeroMove, 'Est at target':atTarget, 'Est past target and read at target':(pastTarget and ratTarget)}, diagStr)
            return True
        else:
            return False
        
    def assessSnap(self, flagOn0:bool, d:dict, diagStr:str) -> bool:
        '''snap camera at the point'''
        if flagOn0:
            atTarget = (d['trd']<self.zeroDist and d['ted']<self.zeroDist)
            pastTarget = d['led']>d['tld']
            if atTarget:
                self.getSadd('SNAP', {'Read and est at target':atTarget}, diagStr)
                self.turnOn()
                return True
            else:
                return False
        else:
            return False
        
    def assessTurnOn(self, d:dict, diagStr:str) -> bool:
        '''turn on fluigent at the point'''
        pastTarget = d['led']>d['tld']
        atTarget = d['ted']<self.critDistance
        ratTarget = self.hitRead
        if atTarget or (pastTarget and ratTarget):
            self.getSadd('ON', {'Est at crit':atTarget, 'Est past target and read at target':(pastTarget and ratTarget)}, diagStr)
            self.turnOn()
            return True
        else:
            return False
        
    def assessTurnOff(self, flagOn0:bool, d:dict, diagStr:str) -> bool:
        '''turn off fluigent at point'''
        if flagOn0:
            return False
    
        zeroMove = d['tld']<self.zeroDist
        if zeroMove:
            # no movement during this line
            self.getSadd('OFF', {'zero move':zeroMove}, diagStr)
            self.turnOff()
            return True
        
        if self.critDistance<0:
            # turn off before end of line
            pastTarget = d['led']>d['tld']
            atCrit = d['ted']<abs(self.critDistance)
            if atCrit and self.on:
                self.getSadd('OFF', {'est at crit':atCrit}, diagStr)
                self.turnOff()
            else:
                atTarget = d['ted']<self.zeroDist
                if atTarget:
                    self.getSadd('NONE', {'est at target':atTarget}, diagStr)
            return d['ted']<self.zeroDist
        else:
            # turn off after end of line
            atTarget = d['led']>d['tld']+self.critDistance
            radTarget = self.hitRead
            outsidePath = ((d['lrd']+d['trd'] > d['tld']+self.zeroDist) and d['trd']>self.critDistance and d['lrd']>self.zeroDist)
            if (atTarget and radTarget) or outsidePath:
                self.getSadd('OFF', {'est at target and hit read':(atTarget and radTarget), 'read outside path and read past crit':outsidePath}, diagStr)
                self.turnOff() 
                return True
            else:
                return False
        
    def assessPosition(self, d:dict, sbFlag:int, diagStr:str) -> None:
        '''check the state and do actions if relevant
        trd distance from target to read point
        lrd distance from last to read point
        tld distance from last to target point
        ted distance from target to estimated point
        led distance from last to estimated point
        sbFlag full flag value
        possible states are 0,1,4,5'''
        
        readyForNextPoint = False
        flagOn0 = flagOn(sbFlag, self.flag0)
        
        # turn down from burst
        if self.turningDown:
            # bring down pressure from burst pressure
            self.turnDown(d['ted'])
            self.signals.printStatus.emit('turning down')
                
        if not self.hitRead:
            if d['trd']<self.zeroDist or d['lrd']+d['trd'] > d['tld']+self.zeroDist:
                self.hitRead = True    # indicate we've hit the read point and are ready to move on
                self.signals.printStatus.emit('hit read')

        if self.state==0:
            # no change
            return self.assessNoChange(d, diagStr)
        else:
            # change
            if self.state==4:
                # snap camera at point
                return self.assessSnap(flagOn0, d, diagStr)
            elif self.state==1:
                # turn on within crit distance of point or if we've started on the next line
                return self.assessTurnOn(d, diagStr)
            elif self.state==5:
                # turn off at end
                return self.assessTurnOff(flagOn0, d, diagStr)
                
        return readyForNextPoint
    
    def assessPositionSimple(self, sbFlag:int) -> None:
        flagOn0 = flagOn(sbFlag, self.flag0)
        
        if flagOn0 is True:
            if self.on is True:
                return
            else:
                self.turnOn()
                return
        else:
            if self.on is True:
                self.turnOff()
                return
            else:
                return


    @pyqtSlot() 
    def close(self) -> None:
        '''close the channel watch, send messages to object'''
        if self.mode==2:
            self.signals.finished.emit()
        elif self.mode==1:
            self.signals.zeroChannel.emit(True)