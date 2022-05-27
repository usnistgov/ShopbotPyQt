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

class channelWatch:
    '''a tool for watching changes in state'''
    
    def __init__(self, csvfile:str, num:int, numChannels:int, critTimeOn:float, zero:float, sbWin):
        
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
        self.targetPoint = ['','','']
        self.sbWin = sbWin
        numchannels = len(sbWin.fluBox.pchannels)
        if num<numChannels:
            # this is a pressure channel
            self.pressure = True
            self.pressBox = sbWin.fluBox.pchannels[num].constBox
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
        if row['x']=='' or row['y']=='' or row['z']=='':
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
        self.targetPoint = [row['x'], row['y'], row['z']]
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
        elif row[f'p{c}_before']==1 and row[f'p{c}_after']==0:
            # turn off at point
            if self.pressure:
                # turn off pressure after we leave the point
                self.state = 2
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
        return np.sqrt((x-self.targetPoint[0])**2+(y-self.targetPoint[1])**2+(z-self.targetPoint[2])**2)
    
    def turnOn(self) -> None:
        '''turn the pressure on, or snap a picture'''
        if self.pressure:
            # turn pressure on
            press = int(self.pressBox.text())
            fgt.fgt_set_pressure(self.num, press)
        else:
            # snap pictures
            for camBox in self.camBoxes:
                if camBox.camObj.connected:
                    if camBox.camInclude.isChecked() and not camBox.camObj.recording:
                        camBox.cameraPic()
                        
    def turnOff(self) -> None:
        '''turn the pressure off'''
        if self.pressure:
            fgt.fgt_set_pressure(self.num, 0)
        
                
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
        elif self.state==2:
            # 2 = go to state 3 when flag is off
            if not sbFlag%2**(self.num+1)==2**self.num:
                # flag is off
                self.state=3
                return False
        elif self.state==3:
            # 3 = turn off when past critical distance of point
            if self.dist(x,y,z)>self.critDistance:
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

    def __init__(self, sbpfile:str, sbWin, critTimeOn:float=0.1, zero:float=0.1):
        if not sbpfile.endswith('.sbp'):
            raise ValueError('Input to SBPtimings must be an SBP file')
        self.sbpfile = sbpfile
        self.csvfile = self.sbpfile.replace('.sbp', '.csv')
        if not os.path.exists(self.csvfile):
            sp = SBPPoints(sbpfile)
            sp.export()

        self.channels =[]
        for key in self.points:
            if key.startswith('p'):
                channel = int(key[1])
                self.channels.append(channelWatch(self.csvfile, channel, critTimeOn, zero, sbWin))
        
    def check(self, sbFlag:int, x:float, y:float, z:float) -> bool:
        '''update status of channels based on position and flags
        return True if the run may be over, False if not'''
        allowEnd = True
        for c in self.channels:
            o = c.checkPoint(sbFlag, x, y, z)
            if not o:
                allowEnd = False
        return allowEnd