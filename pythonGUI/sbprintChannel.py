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
    
    def __init__(self, flag0:int, pSettings:dict, diagStr, pw, pins:dict, runSimple:int):
        super().__init__()
        self.on = False
        self.flag0 = flag0
        self.mode = 0
        self.state = 0
        self.diagStr = diagStr
        self.turningDown = False
        self.resetPointVars()
        # store burstScale, burstLength, zero, critTimeOn, critTimeOff
        for s,val in pSettings.items():
            setattr(self, s, val)
        if self.runSimple==1:
            self.burstScale = 1  # do not burst if only tracking flags
        self.signals = channelWatchSignals()
        self.pw = pw     # now we can access the distances
        self.runSimple = runSimple
        self.determineTrust(pins)
        self.defineBurst()
        
    def resetPointVars(self):
        '''reset the variables that must reset with each new point'''
        self.ended = False  # indicates we are in the shutoff at the end of the line
        self.started = False # indicates we are in the early turnon at the beginning of the line
        self.changedBy = None # indicates whether the status was changed by the point or by the flag
        
    def determineTrust(self, pins:dict) -> None:
        '''determine if this flag is hooked up to the arduino. if it is, we can trust its timing. if not, the flag is coming from sb3.exe and might be lying'''
        self.trustFlag = False
        for flag1, pin in pins.items():
            if flag1==self.flag0+1:
                self.trustFlag = True
                
        
    def diagHeader(self) -> str:
        if self.mode==1 or self.mode==2:
            self.diagStr.addHeader(f'{self.flag0+1}:flg dev act on')
    
    def diagPosRow(self, sbflag:int) -> str:
        flagOn0 = flagOn(sbflag, self.flag0)
        s = f'{self.flag0+1}'
        if flagOn0:
            s = s + ':ON '
        else:
            s = s + ':OFF'
        s = s + ' '
        if self.mode==1:
            s = s + 'flu'
        elif self.mode==2:
            s = s + 'cam'
        else:
            # this is just a dummy flag, don't report values
            return
        s = s + ' '
        if self.state==0:
            s = s + 'non'
        elif self.state==1:
            s = s + 'on '
        elif self.state==4:
            s = s + 'sna'
        elif self.state==5:
            s = s + 'off'
        if self.on:
            s = s + ' ye'
        else:
            s = s + ' no'
        self.diagStr.addRow(s)
        
            
    @pyqtSlot(str, str)
    def emitStatus(self, sadd:str) -> None:
        '''print the status and emit it to the channel'''
        self.signals.printStatus.emit(sadd)
        self.diagStr.addStatus(sadd)
            
    def getSadd(self, change:str, d:dict) -> None:
        '''get a status string based on a dictionary of bools. change is a string to put at the front'''
        s = f'{self.flag0+1}: {change}'
        for key,val in d.items():
            if val:
                s = s + ' ' + key
        self.emitStatus(s)
    
    #---------------------------------------
    # actions
    
    @pyqtSlot() 
    def turnOn(self) -> None:
        '''turn the pressure on to the burst pressure, or snap a picture'''
        self.on=True
        self.ended = False
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
        if self.burstScale==1 or self.bl==0:
            self.turningDown = False
            return
        led = self.pw.d.led
        if self.mode==1 and self.on:
            if led>self.bl:
                scale = 1
                self.turningDown = False   # stop turning down, met burst length
                self.diagStr.addStatus(f'Done turning down')
            else:
                scale = 1 + (self.burstScale-1)*(1-led/self.bl)
            self.signals.goToPressure.emit(scale)
            
     
    @pyqtSlot() 
    def turnOff(self) -> None:
        '''turn the pressure off'''
        self.on = False
        self.started = False
        if self.mode == 1:
            self.signals.zeroChannel.emit(False)
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
        t = self.pw.d.target
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
        if not self.trustFlag:
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
            if 'speed' in self.pw.d.target:
                self.bl = self.burstLength['value']*self.pw.d.target['speed']
            else:
                self.bl = 0
            
    def defineStateFluigentTurnOn(self) -> None:
        '''define the state where the flag is turning on at this step'''
        sn = self.stateChange('next')
        
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
        ln = self.stateChange('last')
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
        # self.resetPointVars()
        if self.mode==2:
            # camera
            self.defineStateCamera()
        elif self.mode==1:
            # fluigent
            self.defineStateFluigent()
        else:
            # do nothing at point
            self.state = 0
            
    #----------------------

    def assessSnap(self, flagOn0:bool) -> None:
        '''snap camera at the point. we already did the trustworthy flag check'''
        if flagOn0 and not self.on:
            if self.pw.estAtTarget() and self.pw.readAtTarget():
                self.getSadd('SNAP', {'Read and est at target':True})
                self.turnOn()
                self.changedBy = 'point'
                self.started = True
        
    def assessTurnOn(self, flagOn0:bool) -> None:
        '''turn on fluigent at the point. '''
        # allow point timings to turn pressure on     
        if self.on:
            # already on
            return
        zeroMove = self.pw.zeroMove()
        withinCrit = self.pw.estWithinCrit(self.critDistance)
        if zeroMove or withinCrit:
            self.getSadd('ON', {'Est at crit':withinCrit, 'Zero move':zeroMove})
            self.turnOn()
            self.changedBy = 'point'
            self.started = True

        
    def assessTurnOff(self, flagOn0:bool) -> None:
        '''turn off fluigent at point'''
        if not self.on:
            # already off
            return
        zeroMove = self.pw.zeroMove()
        withinCrit = self.pw.estWithinCrit(self.critDistance)
        if zeroMove or withinCrit:
            self.getSadd('OFF', {'Est at crit':withinCrit, 'Zero move':zeroMove})
            self.turnOff()
            self.changedBy = 'point'
            self.ended = True

    def flagOnSadd(self) -> None:
        '''send out a message that the flag has turned on pressure or initiated the snap'''
        if self.mode==1:
            # fluigent
            self.getSadd('ON ', {'Flag on':True})
        else:
            self.getSadd('SNAP ', {'Flag on':True})
            
    def flagOffSadd(self) -> None:
        '''send out a message that the flag has turned off pressure or stopped the snap'''
        if self.mode==1:
            # fluigent
            self.getSadd('OFF ', {'Flag off':True})
        else:
            self.getSadd('SNOFF ', {'Flag off':True})
            
    def assessTrusted(self, flagOn0:bool) -> bool:
        ''' reset the point timing based on the flag. return true if the arduino changed the value '''
        resetFlag = False
        retval = False
        if flagOn0:
            # flag is on
            if self.on and self.changedBy=='point':
                # if the point turned on pressure early, and the flag is now on, tell pw accurate timing 
                resetFlag = True
                if self.changedBy=='point':
                    self.getSadd('RESET ', {'Flag on':True})
            if not self.on and not self.ended:
                # flag is on, but pressure is not on 
                # and isn't at the end of the line
                self.flagOnSadd()
                self.turnOn()
                self.changedBy = 'flag'
                self.started = False  # now we are in the real line, not the pre-flow
                retval = True
                resetFlag = True
            if resetFlag:
                self.pw.flagReset(self.flag0, True) 
                self.changedBy = 'flag'
                
        else:
            # flag is off
            if not self.on and self.changedBy=='point':
                # if the point turned off pressure early, and the flag is now off, tell pw accurate timing 
                resetFlag = True
                if self.changedBy=='point':
                    self.getSadd('RESET', {'Flag off':True})
            if self.on and not self.started:
                # flag is off, but pressure is on 
                # and isn't at the start of the line
                self.flagOffSadd()
                self.turnOff()
                self.changedBy = 'flag'
                self.ended = False   # now we are in the real line, not the pre-off
                retval = True
                resetFlag = True
            if resetFlag:
                self.pw.flagReset(self.flag0, False) 
                self.changedBy = 'flag'
        return retval
    
        
    def forceAction(self) -> bool:
        '''force the action if there is no trustworthy flag to force it'''
        if self.runSimple==1 or self.trustFlag:
            # don't let points boss us around, wait for flags
            return
        if self.state==4:
            # snap camera at point
            if not self.on:
                self.getSadd('SNAP', {'Forced':True})
                self.turnOn()
        elif self.state==1:
            # turn on within crit distance of point or if we've started on the next line
            if not self.on:
                self.getSadd('ON', {'Forced':True})
                self.turnOn()
        elif self.state==5:
            # turn off at end
            if self.on:
                self.getSadd('OFF', {'Forced':True})
                self.turnOff()
                
    def assessPositionSimple(self, sbFlag:int) -> None:
        '''only react to flags'''
        flagOn0 = flagOn(sbFlag, self.flag0)
        if flagOn0:
            if not self.on:
                # flag is on, but pressure is not on
                self.flagOnSadd()
                self.turnOn()
            elif self.turningDown:
                # flag is on, and pressure is on, and we're still in the burst zone
                self.turnDown() 
        else:
            if self.on:
                self.flagOffSadd()
                self.turnOff()
        
    def assessPosition(self, sbFlag:int) -> bool:
        '''check the state and do actions if relevant
        sbFlag full flag value
        possible states are 0,1,4,5'''
        if self.runSimple==1:
            self.assessPositionSimple(sbFlag)
            return
        
        flagOn0 = flagOn(sbFlag, self.flag0)
        if self.trustFlag:
            changed = self.assessTrusted(flagOn0)
            if changed:
                # don't change it again
                return True

        # turn down from burst
        if self.turningDown:
            # bring down pressure from burst pressure
            self.turnDown()

        if self.runSimple==1 or (self.runSimple==2 and self.trustFlag):
            # trust the flag, ignore points
            return False
            
        if self.state==4:
            # snap camera at point
            self.assessSnap(flagOn0)
        elif self.state==1:
            # turn on within crit distance of point or if we've started on the next line
            self.assessTurnOn(flagOn0)
        elif self.state==5:
            # turn off at end
            self.assessTurnOff(flagOn0)
        return False


    @pyqtSlot() 
    def close(self) -> None:
        '''close the channel watch, send messages to object'''
        if self.mode==2:
            self.signals.finished.emit()
        elif self.mode==1:
            self.signals.zeroChannel.emit(True)