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
    
def calcAngle(vec1, vec2):
    '''calculate the angle between two vectors'''
    dot = np.dot(vec1, vec2)
    if dot<=0:
        return 0
    else:
        return np.arccos(dot)   # angle between traveled vec and target vec


    
def naPoint(row:pd.Series) -> bool:
    '''determine if the point is not filled'''
    return pd.isna(row['x']) or pd.isna(row['y']) or pd.isna(row['z'])
    
def dummyPoint() -> dict:
    '''a point that we certainly won't be near'''
    return {'x':-1000, 'y':-1000, 'z':-1000}

def emptyPoint() -> dict:
    '''display nothing'''
    return {'x':'', 'y':'', 'z':''}

    
class distances:
    '''holds point locations and distances, vectors, and angles'''
    
    def __init__(self, trackPoints:bool):

        
        if trackPoints:
            self.estimate = toXYZ(dummyPoint()) # where we think we are
            self.target = dummyPoint()   # point we're trying to hit
            self.last = dummyPoint()     # point we're coming from
            self.next = dummyPoint()     # the next point we will try to hit
        else:
            self.estimate = ['','','']
            self.target = emptyPoint()   # point we're trying to hit
            self.last = emptyPoint()     # point we're coming from
            self.next = emptyPoint()     # the next point we will try to hit
            
        self.read = toXYZ(dummyPoint())     # where the shopbot software thinks we are
        self.lastread = toXYZ(dummyPoint()) # the last point where the shopbot software thought we were
        
        self.vec = [0,0,0]
        self.targetVec = [0,0,0]
        self.nextVec = [0,0,0]
        
        self.trd = 0  # distance between the read loc and the target point
        self.lrd = 0  # distance between the read loc and the last point
        self.tld = 0  # distance between last point and target point
        self.ted = 0  # distance between the estimated loc and the target point
        self.led = 0  # distance between estimated loc and last point
        self.angle = 0 # angle between read movement and target direction

        self.trackPoints = trackPoints

       
    def updateTarget(self, prevPoint:dict, newPoint:dict, nextPoint:dict) -> None:
        '''update the target point'''
        if not self.trackPoints:
            return
        self.last = prevPoint
        self.target = newPoint
        self.next = nextPoint
        self.targetVec = ppVec(self.last, self.target)
        self.nextVec = ppVec(self.target, self.next)
        if 'x' in self.last and 'x' in self.target:
            self.tld = ppDist(self.last, self.target)  
        else:
            self.tld = 0
        
    def updateRead(self, read:list) -> None:
        '''update the current positions'''
        self.lastread = self.read
        self.read = read
        if self.trackPoints:
            self.trd = ppDist(self.read, self.target)   
            if 'x' in self.last:
                self.lrd = ppDist(self.read, self.last)   
            else:
                self.lrd = 0
            
    def calcEst(self, timeTaken:bool, pointTime, speed:float) -> None:
        '''estimate the current location based on time since hitting last point and translation speed'''
        if not self.trackPoints:
            return
        if not timeTaken or not ('speed' in self.target and 'x' in self.last) or speed==0:
            self.estimate = self.last
        else:
            dnow = datetime.datetime.now()
            dt = (dnow - pointTime).total_seconds()   # time since we hit the last point
            pt = toXYZ(self.last, listOut=True)       # last point
            vec = self.targetVec                      # direction of travel
            distTraveled = speed*dt              # distance traveled since we hit the last point
            self.estimate = [pt[i]+distTraveled*vec[i] for i in range(3)]  # estimated position
        self.ted = ppDist(self.estimate, self.target) 
        self.led = ppDist(self.estimate, self.last) 
        self.calcAngle()
        
    def calcAngle(self):
        '''get angle between direction of movement and intended direction. run each time step'''
        self.vec = ppVec(self.lastread, self.read)  # vector from lastread to current read
        if self.trackPoints:
            self.angle = calcAngle(self.vec, self.targetVec)
        return
    
    def zeroMove(self, s:str) -> bool:
        '''determine if the point coordinates do not change between the two points. if s is last, compare last to target. if s is next, compare next to target'''
        if not self.trackPoints:
            return False
        if not hasattr(self, s):
            raise ValueError('Unexpected value passed to zeroMove. should be next or last')
        for c in ['x', 'y', 'z']:
            if not getattr(self, s)[c]==self.target[c]:
                return False
        return True
        
        
class pointWatchSignals(QObject):
    estimate = pyqtSignal(float,float,float)   # new estimated position
    target = pyqtSignal(float,float,float)      # send current target to GUI
    targetLine = pyqtSignal(int)   # send current target line to GUI 
    printStatus = pyqtSignal(str)  # status of the points
    trusted = pyqtSignal(bool)     # whether we can trust the point estimate and target

    
    
class pointWatch(QObject):
    '''holds functions for iterating through points in an sbp file'''
    
    def __init__(self, pSettings:dict, dt:float, diagStr, parent, runSimple:int):
        super().__init__()
        self.trackPoints = (not runSimple==1)
        self.d = distances(self.trackPoints)
        self.zeroDist = pSettings['zeroDist']
        self.dt = dt
        self.signals = pointWatchSignals()
        self.queuedLine = 0
        self.timeTaken = False
        self.hitRead = False
        self.trusted = False
        self.speed = 0
        self.tableDone = False
        self.waitingForLastRead = False
        self.diagStr = diagStr
        self.resetPointTime()
        self.onoffCount = {'on':{}, 'off':{}}   # count how many times the flag has turned on and off
        self.printLoop = parent
        
    def diagHeader(self) -> str:
        l = []
        if not self.trackPoints:
            llll = ['d']
        else:
            llll =  ['d', 'e', 't']
        for s1 in llll:
            for s2 in ['x', 'y', 'z']:
                l.append("{:6s}".format(f'{s2}{s1}'))
            l[-1] = l[-1]+'|'
        if self.trackPoints:
            l = l+['tln', 'qln|']
        l.append('flag')
        if self.trackPoints:
            l = l+['speed', 'strt', '@pt', 'trust|']
            for si in ['trd', 'lrd', 'tld', 'ted', 'led']:
                l.append(f'{si:5s}')
        return self.diagStr.addHeader('\t'.join(l)+'|')
    
    
    def diagPosRow(self, flag:int, newPoint:bool) -> str:
        l = []
        if not self.trackPoints:
            llll = ['read']
        else:
            llll =  ['read', 'estimate', 'target']
        for s1 in llll:
            if newPoint and not s1=='target':
                l = l+[f'{i:6s}' for i in [' ', ' ', ' ']]
            else:
                x,y,z = toXYZ(getattr(self.d, s1))
                l = l+[f'{i:6.2f}' for i in [x,y,z]]
            l[-1] = l[-1]+'|'
        if self.trackPoints:
            l = l+[str(int(self.d.target['line'])), f'{self.queuedLine}|']
        l.append(f'{flag:4.0f}')
             
        if self.trackPoints:
            if newPoint:
                s0 = ''
                l = l + [f'{s0:4s}', f'{s0:4s}',f'{s0:3s}', f'{s0:5s}|']
            else:
                l = l+[f'{self.speed:4.1f}', f'{self.timeTaken:4b}',f'{self.hitRead:3b}', f'{self.trusted:5b}|']

            for s in ['trd', 'lrd', 'tld', 'ted', 'led']:
                l.append(f'{getattr(self.d, s):5.2f}')
        self.diagStr.addRow('\t'.join(l)+'|')
    
        
    #-------------------  
    # initializing
    
    def readCSV(self, sbpfile:str):
        '''get list of points from the sbp file'''
        if not sbpfile.endswith('.sbp'):
            raise ValueError('Input to SBPtimings must be an SBP file')
        sbpfile = sbpfile
        csvfile = sbpfile.replace('.sbp', '.csv')
        if not os.path.exists(csvfile) or os.path.getmtime(csvfile)<os.path.getmtime(sbpfile):
            # if there is no csv file or the sbp file was edited since the csv file was created, create a csv
            sp = SBPPoints(sbpfile)
            sp.export()
            sp = pd.read_csv(csvfile, index_col=0)
        else:
            sp = pd.read_csv(csvfile, index_col=0)
            if not 'line' in sp:
                # overwrite the file
                sp = SBPPoints(sbpfile)
                sp.export()
                sp = pd.read_csv(csvfile, index_col=0)
        self.initializePoints(sp)
    
    def initializePoints(self, sp:pd.DataFrame):
        '''initialize the point table and the indices'''
        self.points = sp
        self.pointsi = -1
        negpoints = self.points[self.points.z<=0]
        if len(negpoints)>0:
            self.zmax = negpoints.z.max() + 2
        else:
            self.zmax = self.points.z.max()
        self.fillTable()    # fill empty entries with current position
        

    def fillTable(self) -> None:
        '''go through the top of the table and fill empty entries with the current position'''
        self.starti = 0
        for i,row in self.points.iterrows():
            if naPoint(self.points.loc[i]):
                for j,var in {0:'x', 1:'y', 2:'z'}.items():
                    if pd.isna(self.points.loc[i, var]):
                        self.points.loc[i, var] = self.d.read[j]   # fill empty value
                        self.starti = i+2
            else:
                return
            
    #-------------------
    # tracking points
    
    def readPoint(self, letQueuedKill:bool=True) -> pd.Series:
        '''read the next point from the points list'''
        if not self.trackPoints:
            return
        if letQueuedKill:
            if self.pointsi>0 and self.queuedLine>0 and self.points.iloc[self.pointsi]['line']>self.queuedLine+1:
                # don't read the point if we're ahead of the file
                self.waitingForLastRead = True
                return {}
        self.timeTaken = False
        self.hitRead = False
        self.waitingForLastRead = False
        self.trusted = False
        self.pointsi+=1
        if self.pointsi>=0 and self.pointsi<len(self.points):
            targetPoint = self.points.iloc[self.pointsi] 
            if pd.isna(targetPoint['speed']):
                # just changing flow speed
                return targetPoint
            
            # new target point
            if len(self.points)>self.pointsi+1:
                nextPoint = self.points.iloc[self.pointsi+1]
            else:
                nextPoint = dummyPoint()
            if self.pointsi>0:
                prevPoint = self.points.iloc[self.pointsi-1]
            else:
                prevPoint = dummyPoint()
            self.d.updateTarget(prevPoint, targetPoint, nextPoint)
            self.speed = float(self.d.target['speed'])
        else:
            self.tableDone = True
        return self.d.target
        
            
    def flagReset(self, flag0:int, on:bool) -> None:
        '''reset the time and find the right point because the real flag turned on'''
        # find the points when the pressure turns on
        if on:
            b = 0
            a = 1
        else:
            b = 1
            a = 0
        df = self.points[(self.points[f'p{flag0}_before']==b)&(self.points[f'p{flag0}_after']==a)]
        if on:
            s = 'on'
        else:
            s = 'off'
            
        if flag0 in self.onoffCount[s]:
            self.onoffCount[s][flag0]+=1
        else:
            self.onoffCount[s][flag0] = 0
        idx = self.onoffCount[s][flag0]
        if idx>=len(df):
            print(f'Too many flag resets:{flag0+1}:{s}, {idx}/{len(df)}')
            return
        # print(self.onoffCount)
        i = df.iloc[idx].name  # get the index of the point we just hit
        self.pointsi = i
        self.printLoop.readPoint(letQueuedKill=False)        # go to the next point
        self.resetPointTime()   # mark the start of the movement as now
        self.timeTaken = True
        self.trusted = True
        
            
    def findFirstPoint(self, flags:list) -> None:
        '''find the first point where pressure is on'''
        if not self.trackPoints:
            return
        self.resetPointTime()
        if len(self.points)>1:  
            on = False
            # find first flag change
            while not on and not self.tableDone:
                self.readPoint()
                for flag0 in flags:
                    if self.d.target[f'p{flag0}_after']==1:
                        on = True
        else:
            self.readPoint()
        self.pointsi = self.pointsi-1
        self.printLoop.readPoint()
        
        #-------------------
    # loop actions
    
    def resetPointTime(self):
        '''reset the time of the start of the last move'''
        self.pointTime = datetime.datetime.now()-datetime.timedelta(seconds=self.dt/1000)
        # print('new point time', self.pointTime)
    
    def updateReadLoc(self, readLoc:dict) -> None:
        '''update the read point'''
        # update read point and calculate read distances
        self.d.updateRead(readLoc)
        self.checkTimeTaken()   # check if we've taken the start time
        # update estimate point and angle
        self.d.calcEst(self.timeTaken, self.pointTime, self.speed)
        self.signals.trusted.emit(self.trusted) # send the trusted status back to the printLoop
        self.checkHitRead()     # check if we've hit the read point
        
        
    def updateLastRead(self, lastRead:int) -> None:
        '''update the queued line'''
        self.queuedLine = lastRead
        if self.waitingForLastRead:
            self.readPoint()


            
    #-------------------  
    # status   
    
    def printStarted(self) -> bool:
        '''determine if we have entered the printing space'''
        return self.d.read[2]<self.zmax
    
    def retracting(self, diag:bool=False) -> bool:
        '''determine if we are retracting above the printing space'''
        ret = float(self.d.read[2])>(self.zmax)
        if self.diagStr.diag>1 and ret and diag:
            print(f'\tz above max, {self.d.read[2]:0.2f}, {self.zmax:0.2f}, {self.pointsi}, {self.starti}')
        return ret
    
    def noFlagChanges(self) -> bool:
        '''flags are not changing during this move'''
        for c in self.d.target.keys():
            # iterate through columns
            if c.startswith('p') and c.endswith('before'):
                if self.d.target[c]!=self.d.target[c.replace('before', 'after')]:
                    # flags are changing during these moves
                    return False
        return True
    
    def zeroMove(self) -> bool:
        '''this move is smaller than the resolution of our measurement'''
        return self.d.tld<self.zeroDist   
    
    def readAtTarget(self) -> bool:
        '''read point is at the target point'''
        return self.d.trd<self.zeroDist
    
    def readOutsidePath(self) -> bool:
        '''read point is outside the path between the last point and target point'''
        return self.d.lrd+self.d.trd > self.d.tld+self.zeroDist
    
    def readAtLast(self) -> bool:
        '''read point has left the last point'''
        return self.d.lrd<self.zeroDist
    
    def readChangedDirection(self):
        '''the read point has changed direction'''
        return self.d.angle>=np.pi/4
    
    def estAtTarget(self) -> bool:
        '''estimated point is at the target point'''
        return self.d.led>=self.d.tld-self.zeroDist
    
    def estWithinCrit(self, crit:float) -> bool:
        '''estimated point is within critical distance of target. crit<0 to be after end of line'''
        return self.d.led>=self.d.tld-crit

    def checkHitRead(self):
        '''check if the read point has hit the target point'''
        if not self.hitRead:
            if self.readAtTarget() or self.readOutsidePath():
                self.hitRead = True    # indicate we've hit the read point and are ready to move on
 
    def checkTimeTaken(self):
        '''check if the time has started to write estimate points'''
        if not self.timeTaken:
            if not self.readAtLast():
                # reset the time when the stage actually starts moving
                self.resetPointTime()
                self.timeTaken = True
                
                
    def emitStatus(self, sadd:str) -> None:
        '''print the status'''
        self.diagStr.addStatus(sadd)
        self.signals.printStatus.emit(sadd)
                
    def getSadd(self, change:str, d:dict) -> None:
        '''get a status string based on a dictionary of bools. change is a string to put at the front'''
        s = f'PT: {change}'
        for key,val in d.items():
            if val:
                s = s + ' ' + key
        self.emitStatus(s)
      
    def readyForNextPoint(self) -> bool:
        '''check if we can go on to the next point'''
        if not self.trackPoints:
            return False
        if self.waitingForLastRead:
            return True
        d = {'Est at target':self.estAtTarget(), 'Zero move':(self.zeroMove() and self.noFlagChanges()), 'change direction':self.readChangedDirection()}
        if any(d.values()):
            sadd = self.getSadd('NEW', d)
            
            return True
        else:
            return False
        
                
