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
    
    def __init__(self, flag0:int, pSettings:dict, diag:int, pw:pointWatch, pins:dict, runSimple:int):
        super().__init__()
        self.on = False
        self.flag0 = flag0
        self.mode = 1
        self.diag = diag
<<<<<<< Updated upstream
=======
        self.turningDown = False
        self.resetPointVars()
>>>>>>> Stashed changes
        # store burstScale, burstLength, zero, critTimeOn, critTimeOff
        for s,val in pSettings.items():
            setattr(self, s, val)
        self.signals = channelWatchSignals()
        self.pw = pw     # now we can access the distances
        self.runSimple = runSimple
        
    def resetPointVars(self):
        '''reset the variables that must reset with each new point'''
        self.ended = False  # indicates we are in the shutoff at the end of the line
        self.started = False # indicates we are in the early turnon at the beginning of the line
        self.changedBy = None # indicates whether the status was changed by the point or by the flag
        
    def determineTrust(self) -> None:
        '''determine if this flag is hooked up to the arduino. if it is, we can trust its timing. if not, the flag is coming from sb3.exe and might be lying'''
        self.trustFlag = False
        for flag1, pin in pins:
            if flag1==self.flag0+1:
                self.trustFlag = True
                
        
    def diagHeader(self) -> str:
        return '\t'.join(['flag0:on mode', 'state|'])
    
    def diagPosRow(self, flag:int) -> str:
        flagOn0 = flagOn(self.flag, flag0)
        return '\t'.join([f'{flag0}:{flagOn0}', f'{cw.mode}', f'{cw.state}|'])
    
    #---------------------------------------
    # actions
    
    @pyqtSlot() 
    def turnOn(self) -> None:
        '''turn the pressure on to the burst pressure, or snap a picture'''
        self.on=True
        if self.mode == 1:
            # turn pressure on to burst pressure
            self.signals.goToPressure.emit(self.burstScale)
            self.turningDown = True
        elif self.mode == 2:
            # snap pictures
            self.signals.snap.emit()         
     
    @pyqtSlot(float) 
    def turnDown(self) -> None:
        '''turn the pressure down, given a distance from the last point'''
        led = self.pw.d.led
        if self.mode==1 and self.on:
            if led>self.bl:
                scale = 1
                self.turningDown = False   # stop turning down, met burst length
            else:
                scale = 1 + (self.burstScale-1)*(1-led/self.bl)
            self.signals.goToPressure.emit(scale)
            self.signals.printStatus.emit('turning down')
     
    @pyqtSlot() 
    def turnOff(self) -> None:
        '''turn the pressure off'''
        if self.mode == 1:
            self.signals.zeroChannel.emit(False)
            self.on=False
            self.turningDown = False
            
    #------------------------------------
    # each new point
            
    def afterCol(self) -> str:
        return f'p{self.flag0}_after'
    
    def beforeCol(self) -> str:
        return f'p{self.flag0}_before'
    
    @pyqtSlot(float) 
    def updateSpeed(self, speed:float) -> None:
        '''send new extrusion speed to fluigent'''
<<<<<<< Updated upstream
        self.signals.updateSpeed.emit(speed)
=======
        t = self.pointWatch.d.target
        if t[self.beforeCol()]<0 and t[self.afterCol()]>0:
            # negative value in before flag indicates that this is a special row
            speed = float(t[self.afterCol()])
            self.signals.updateSpeed.emit(speed)
            if self.on:
                # if pressure is on, go to that pressure
                self.signals.goToPressure.emit(1)
                
    def stateChange(self, s):
        '''get the state of this flag at the beginning of the line'''
        pt = getattr(self.pw.d, s)
        return {'before':pt[self.beforeCol()], 'after':pt[self.afterCol()]}                
                
    def defineStateCamera(self) -> None:
        '''define the state for a camera action'''
        b = self.stateChange('target')
        self.on = False
        if b['before']==0 and b['after']==1:
            # snap camera at point
            self.state = 4
        else:
            # do nothing at point
            self.state = 0
            
            
    def defineBurst(self) -> None:
        '''define the burst length'''
        if self.burstLength['units']=='mm':
            # burstlength is a length
            self.bl = self.burstLength['value']
        else:
            # burst length is a time. calculate length from speed
            self.bl = self.burstLength['value']*self.pw.d.target['speed']
            
    def defineStateFluigentTurnOn(self) -> None:
        '''define the state where the flag is turning on at this step'''
        sn = self.stateChange('next')
>>>>>>> Stashed changes
        
        if sn['before']==1 and sn['after']==0 and self.pw.d.zeroMove('next'):
            # turn on, then immediately turn off. don't actually extrude pressure
            self.state = 0
        else:
            # turn on within crit distance of point
            self.state=1
            if self.critTimeOn['units']=='s':
                # calculate crit distance based on speed
                self.critDistance = abs(self.critTimeOn['value'])*self.pw.d.target['speed']
            elif self.critTimeOn['units']=='mm':
                # already know crit distance
                self.critDistance = abs(self.critTimeOn['value'])
            self.critDistance = max(self.zeroDist, self.critDistance)  
                # revert to zero distance if smaller than zero distance
            if self.pw.d.tld<abs(self.critDistance)*2:
                # small move, revert to zero distance
                self.critDistance = self.zeroDist
                
    def defineStateFluigentTurnOff(self) -> None:
        '''define the state where the flag is turning off at this step'''
        # turn off after crit distance of point
        if ln['before']==1 and ln['after']==0 and self.pw.d.zeroMove('next'):
            # in this and last step, we turn on, then immediately turn off. don't actually extrude pressure
            self.state = 0
        else:
            self.state = 5
            if self.critTimeOff['units']=='s':
                # calculate 
                if 'speed' in self.pw.d.next:
                    speed = self.pw.d.next['speed']
                else:
                    speed = self.pw.d.target['speed']
                self.critDistance = self.critTimeOff['value']*speed
            else:
                self.critDistance = self.critTimeOff['value']
            self.critDistance = np.sign(self.critDistance)*max(self.zeroDist, abs(self.critDistance))

            if self.pw.d.tld<abs(self.critDistance)*2:
                # small move, revert to zero distance
                self.critDistance = np.sign(self.critDistance)*self.zeroDist
            
    def defineStateFluigent(self) -> None:
        '''define the state for a fluigent action''' 
        # get the burst length
        self.defineBurst()   
        
        # get the state and the crit distance
        t = self.stateChange('target')
        if t['before']==0 and t['after']==1:
            self.defineStateFluigentTurnOn()
        elif t['before']==1 and t['after']==0:
            self.defineStateFluigentTurnOff()
        else:
            # do nothing at point
            self.state = 0
        
    def defineState(self) -> None:
        '''determine when to turn on, turn off''' 
        self.resetPointVars()
        if self.mode==2:
            # camera
            self.defineStateCamera()
        elif self.mode==1:
            # fluigent
<<<<<<< Updated upstream
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
=======
            self.defineStateFluigent()
>>>>>>> Stashed changes
        
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

        
    def assessSnap(self, flagOn0:bool, diagStr:str) -> None:
        '''snap camera at the point. we already did the trustworthy flag check'''
        if flagOn0 and not self.on:
            if self.pw.estAtTarget() and self.pw.readAtTarget():
                self.getSadd('SNAP', {'Read and est at target':True}, diagStr)
                self.turnOn()
                self.changedBy = 'point'
        
    def assessTurnOn(self, flagOn0:bool, diagStr:str) -> bool:
        '''turn on fluigent at the point. '''
        # allow point timings to turn pressure on        
        zeroMove = self.cw.zeroMove()
        withinCrit = self.cw.estWithinCrit(self.critDistance)
        if zeroMove or withinCrit:
            self.getSadd('ON', {'Est at crit':withinCrit, 'Zero move':zeroMove}, diagStr)
            self.turnOn()
            self.changedBy = 'point'
            if withinCrit and not self.cw.estAtTarget():
                self.started = True

        
    def assessTurnOff(self, flagOn0:bool, d:dict, diagStr:str) -> bool:
        '''turn off fluigent at point'''
        zeroMove = self.cw.zeroMove()
        withinCrit = self.cw.estWithinCrit(self.critDistance)
        if zeroMove or withinCrit:
            self.getSadd('ON', {'Est at crit':withinCrit, 'Zero move':zeroMove}, diagStr)
            self.turnOff()
            self.changedBy = 'point'
            self.ende = True

            
    def assessTrusted(self, flagOn0:bool) -> None:
        # reset the point timing based on the flag
        if flagOn0:
            if not self.on or self.changedBy=='point':
                # if the point turned on pressure early, and the flag is now on, tell pointWatch accurate timing 
                self.pw.flagReset(self.flag0, True) 
                self.changedBy = 'flag'
            if not self.on and not self.ended:
                # flag is on, but pressure is not on 
                # and isn't at the end of the line
                self.getSadd('ON ', {'Flag on':True}, diagStr)
                self.turnOn()
                self.changedBy = 'flag'
        else:
<<<<<<< Updated upstream
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
=======
            if self.on or self.changedBy=='point':
                # if the point turned on pressure early, and the flag is now on, tell pointWatch accurate timing 
                self.pw.flagReset(self.flag0, False) 
                self.changedBy = 'flag'
            if self.on and not self.started:
                # flag is on, but pressure is not on 
                # and isn't at the end of the line
                self.getSadd('OFF ', {'Flag off':True}, diagStr)
                self.turnOff()
                self.changedBy = 'flag'
            
>>>>>>> Stashed changes
        
    def assessPosition(self, sbFlag:int, diagStr:str) -> None:
        '''check the state and do actions if relevant
        trd distance from target to read point
        lrd distance from last to read point
        tld distance from last to target point
        ted distance from target to estimated point
        led distance from last to estimated point
        sbFlag full flag value
        possible states are 0,1,4,5'''
        if self.runSimple==1:
            self.assessPositionSimple(sbFlag)
            return
        
        flagOn0 = flagOn(sbFlag, self.flag0)
<<<<<<< Updated upstream
=======
            
        if self.trustFlag:
            self.assessTrusted(flagOn0)
>>>>>>> Stashed changes
        
        # turn down from burst
        if self.turningDown:
            # bring down pressure from burst pressure
            self.turnDown()

        if self.runSimple==1 or (self.runSimple==2 and self.trustFlag):
            # trust the flag, ignore points
            return
            
        if self.state==0:
            # no change
            return
        elif self.state==4:
            # snap camera at point
            return self.assessSnap(flagOn0, diagStr)
        elif self.state==1:
            # turn on within crit distance of point or if we've started on the next line
            return self.assessTurnOn(flagOn0, diagStr)
        elif self.state==5:
            # turn off at end
            return self.assessTurnOff(flagOn0, diagStr)
                
<<<<<<< Updated upstream
        return readyForNextPoint
=======
        return
    
    def assessPositionSimple(self, sbFlag:int) -> None:
        '''only react to flags'''
        flagOn0 = flagOn(sbFlag, self.flag0)
        if flagOn0:
            if not self.on:
                # flag is on, but pressure is not on
                self.turnOn()
            elif self.turningDown:
                # flag is on, and pressure is on, and we're still in the burst zone
                self.turnDown() 
        else:
            if self.on:
                self.turnOff()
>>>>>>> Stashed changes


    @pyqtSlot() 
    def close(self) -> None:
        '''close the channel watch, send messages to object'''
        if self.mode==2:
            self.signals.finished.emit()
        elif self.mode==1:
            self.signals.zeroChannel.emit(True)