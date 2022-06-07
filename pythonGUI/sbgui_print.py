#!/usr/bin/env python
'''Shopbot GUI Shopbot functions'''

# 
from PyQt5 import QtCore, QtGui
import PyQt5.QtWidgets as qtw
import os, sys
import winreg
import subprocess
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import csv
import re
import time
import win32gui, win32api, win32con
import pandas as pd

# local packages
import Fluigent.SDK as fgt
from config import cfg
from sbgui_general import *
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(currentdir)
sys.path.append(parentdir)
sys.path.append(os.path.join(parentdir, 'SBP_files'))  # add python folder
from sbpRead import *


##################################################  

def ppdist(p1:List[float], p2:List[float]) -> float:
    '''distance between two points'''
    try:
        return np.sqrt((p1[0]-p2[0])**2+(p1[1]-p2[1])**2+(p1[2]-p2[2])**2)
    except ValueError:
        return 0

class channelWatch:
    '''a tool for watching changes in state'''
    
    def __init__(self, csvfile:str, num:int, critTimeOn:float, critTimeOff:float, zero:float, sbWin):
        
        # state codes: 
        # 0 = no change at point
        # 1 = turn on when within critical distance of point
        # 2 = go to state 3 when flag is off
        # 3 = turn off when past critical distance of point
        # 4 = snap when flag is on
        self.state = 0    
        self.num = num
        self.critTimeOn = critTimeOn
        self.zero = zero
        self.critTimeOff = critTimeOff
        self.targetPoint = ['','','']
        self.lastPoint = ['','','']
        self.sbWin = sbWin
        numChannels = len(sbWin.fluBox.pchannels)
        if num<numChannels:
            # this is a pressure channel
            self.pressure = True
            self.pChannel = sbWin.fluBox.pchannels[num]
            self.pressBox = self.pChannel.constBox
        else:
            # this is a camera channel
            self.pressure = False
            self.camBoxes = sbWin.camBoxes
        self.points = pd.read_csv(csvfile, index_col=0)
        self.currentIndex = 0
        self.readPoint()
        
    def readPoint(self) -> None:
        '''update the current state to reflect the next row'''
        if (self.currentIndex)>=len(self.points):
            # end of file
            return
        row = self.points.loc[self.currentIndex]
        self.currentIndex+=1
        if pd.isna(row['x']) or pd.isna(row['y']) or pd.isna(row['z']):
            # undefined points, skip
            if float(row[f'p{self.num}_before'])<0:
                # change the speed
                try:
                    speed = float(row[f'p{self.num}_after'])
                    if speed>0:
                        cali = self.sbWin.calibDialog.calibWidgets[self.num]
                        cali.updateSpeed(speed)   # update the speed in the calibration box
                        cali.plot.calcPressure()  # calculate the new pressure 
                        cali.copyPressure()       # store that pressure in the run box
                except:
                    pass
            self.readPoint()
            return
        self.lastPoint = self.targetPoint
        self.targetPoint = [float(row['x']), float(row['y']), float(row['z'])]
        if row[f'p{self.num}_before']==0 and row[f'p{self.num}_after']==1:
            # turn on at point
            if self.pressure:
                # turn on pressure before we hit the point
                self.state = 1
                self.critDistance = max(self.zero, self.critTimeOn*row['speed'])  # distance from point when we turn on
            else:
                # turn on camera with flag
                self.state = 4
                self.critDistance = self.zero
        elif row[f'p{self.num}_before']==1 and row[f'p{self.num}_after']==0:
            # turn off at point
            if self.pressure:
                # turn off pressure after we leave the point
                self.state = 5
                self.critDistance = max(self.zero, self.critTimeOff*row['speed'])  # distance from point when we turn on
            else:
                # turn off camera with flag
                self.state = 0
                self.critDistance = self.zero
        else:
            # no change in state
            self.state = 0
            self.critDistance = self.zero
          
    
            
    def dist(self, x:float, y:float, z:float) -> float:
        '''distance to the target point'''
        return ppdist([x,y,z], self.targetPoint)
        
    def lastDist(self, x:float, y:float, z:float) -> float:
        '''distance to the last target point'''
        return ppdist([x,y,z], self.lastPoint)
    
    def endPointDist(self) -> float:
        '''distance between the last point and target point'''
        return ppdist(self.targetPoint, self.lastPoint)
    
    def turnOn(self) -> None:
        '''turn the pressure on, or snap a picture'''
        if self.pressure:
            # turn pressure on
            self.pChannel.goToRunPressure()
        else:
            # snap pictures
            for camBox in self.camBoxes:
                if camBox.camObj.connected:
                    if camBox.camInclude.isChecked() and not camBox.camObj.recording:
                        camBox.cameraPic()
                        
    def turnOff(self) -> None:
        '''turn the pressure off'''
        if self.pressure:
            self.pChannel.zeroChannel(status=False)
            
    def printState(self) -> None:
        '''print the state of the print'''
        statecodes = {0:'No change at point', 1:'Turn on at point', 2:'Go to state 3 when flag is off', 3:'Turn off after point', 4:'snap picture when flag is on', 5:'Go to state 2 when flag is on'}
        logging.info(f'{self.state}:{statecodes[self.state]}. {self.targetPoint}')
        
                
    def checkPoint(self, sbFlag:int, x:float, y:float, z:float) -> bool:
        '''check if we need a change in pressure or a change in state, make changes
        return True if the run may be over, False if not'''
        # state codes: 

        if self.state==0:
            # 0 = no change at point
            if self.dist(x,y,z)<self.critDistance:
                self.readPoint()
                return True
        elif self.state==1:
            # 1 = turn on when within critical distance of point
            if self.dist(x,y,z)<self.critDistance:
                self.turnOn()
                self.readPoint()
                return False
        elif self.state==5:
            # 5 = wait for the flag to turn on, then go to state 2
            if sbFlag%2**(self.num+1)==2**self.num:
                # flag is on
                self.state=2
                return False
        elif self.state==2:
            # 2 = wait for the flag to turn off, then go to state 3
            if sbFlag>0 and not sbFlag%2**(self.num+1)==2**self.num:
                # flag is off
                self.state=3
                return False
        elif self.state==3:
            # 3 = turn off when past critical distance of point
            dist = self.dist(x,y,z)
            lastdist = self.lastDist(x,y,z)
            endPointDist = self.endPointDist()
            if dist>self.critDistance and (dist+lastdist)>(endPointDist+self.zero):
                # point must not be on line between the two endpoints and must be greater than critDistance past endpoint
                print(self.dist(x,y,z), self.critDistance, [x,y,z], self.targetPoint, self.lastPoint, sbFlag)
                self.turnOff()
                self.readPoint()
                return True
        elif self.state==4:
            # 4 = snap when flag is on
            if sbFlag%2**(self.num+1)==2**self.num:
                self.turnOn()
                self.readPoint()
                return True
                
        
        
    
            
class SBPtimings:
    '''a tool for triggering changes in state
    numChannels is the number of pressure channels available
    critTimeOn: turn on flow this many seconds before you hit the corner
    critTimeOff: turn off flow this many seconds after you leave the corner
    zero: mm margin of error to be "at the point"
    '''

    def __init__(self, sbpfile:str, sbWin, critTimeOn:float=0.1, critTimeOff:float=0, zero:float=0.1):
        if not sbpfile.endswith('.sbp'):
            raise ValueError('Input to SBPtimings must be an SBP file')
        self.sbpfile = sbpfile
        self.csvfile = self.sbpfile.replace('.sbp', '.csv')
        if not os.path.exists(self.csvfile):
            sp = SBPPoints(sbpfile)
            sp.export()
            sp = pd.read_csv(self.csvfile, index_col=0)
        else:
            sp = pd.read_csv(self.csvfile, index_col=0)

        self.channels =[]
        for key in sp:
            if key.startswith('p') and key.endswith('_before'):
                channel = int(key[1])
                self.channels.append(channelWatch(self.csvfile, channel, critTimeOn, critTimeOff, zero, sbWin))
        
    def check(self, sbFlag:int, x:float, y:float, z:float) -> bool:
        '''update status of channels based on position and flags
        return True if the run may be over, False if not'''
        allowEnd = True
        
        for c in self.channels:
            o = c.checkPoint(sbFlag, x, y, z)
            if not o:
                allowEnd = False
        return allowEnd
    