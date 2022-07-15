#!/usr/bin/env python
'''Shopbot GUI functions for handling changes of state during a print'''

# external packages
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget 
import os, sys
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import csv
import re

# local packages
from config import cfg
from sbgui_general import *
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(currentdir)
sys.path.append(parentdir)
sys.path.append(os.path.join(parentdir, 'SBP_files'))  # add python folder
from sbpRead import *

printDiag = False


##################################################  

def ppdist(p1:List[float], p2:List[float]) -> float:
    '''distance between two points'''
    try:
        return np.sqrt((p1[0]-p2[0])**2+(p1[1]-p2[1])**2+(p1[2]-p2[2])**2)
    except ValueError:
        return 0
    except TypeError:
        return 0

    

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
        
        
def flagOn(sbFlag:int, flag0:int) -> bool:
    '''test if the 0-indexed flag is on'''
    binary = bin(sbFlag)   # convert to binary
    if len(binary)<2+flag0+1:
        return False       # binary doesn't have enough digits
    else:
        return bool(int(binary[-(flag0+1)]))     # find value at index
        
    
        

class channelWatch:
    '''a tool for watching changes in state'''
    
    def __init__(self, csvfile:str, flag0:int, sbWin):
        
        # state codes: 
        # 0 = no change at point
        # 1 = turn on when within critical distance of point
        # 2 = go to state 3 when flag is off
        # 3 = turn off when past critical distance of point
        # 4 = snap when flag is on
        self.state = 0    
        self.flag0 = flag0              
            # 0-indexed flag to watch
        self.critTimeOn = sbWin.sbBox.critTimeOn    
            # time before the corner when we turn on the flow
        self.zero = sbWin.sbBox.zeroDist               
            # margin of error for distance. 
            # if distance to the point is less than self.zero, we're at the point
        self.critTimeOff = sbWin.sbBox.critTimeOff  
            # time after the start of the new move when we turn off flow
        self.burstScale = sbWin.sbBox.burstScale
            # pressure scaling for initial burst
        self.burstLength = sbWin.sbBox.burstLength
            # length over which to decrease pressure to target pressure
        self.targetPoint = ['','','']   # next point to hit
        self.lastPoint = ['','','']     # point we're coming from
        self.sbWin = sbWin              # gui window
        self.on = False
        self.steps = 0
        

        self.points = pd.read_csv(csvfile, index_col=0)
        self.currentIndex = 0
        self.findChannel()
        self.readPoint()
        
        
    def findChannel(self) -> None:
        '''determine the pressure channel or camera that this flag corresponds to'''
        self.mode = -1
        
        if hasattr(self.sbWin, 'fluBox') and hasattr(self.sbWin.fluBox, 'pchannels'):
            for channel in self.sbWin.fluBox.pchannels:
                if channel.flag1==self.flag0+1:
                    self.mode = 1
                    self.pChannel = channel
                    self.pressBox = self.pChannel.constBox
                    if hasattr(self.sbWin, 'calibDialog'):
                        self.calibBox = self.sbWin.calibDialog.calibWidgets[self.pChannel.chanNum0]
                    return
            
        # didn't find any pressure channels
        if hasattr(self.sbWin, 'camBoxes'):
            iscam, camBox = self.sbWin.camBoxes.findFlag(self.flag0)
            if iscam:
                self.camBox = camBox
                self.mode = 2
                self.setCheck()
                
    def setCheck(self):
        '''set checked during the run'''
        if not self.mode==2:
            return
        if hasattr(self, 'camBox'):
            if hasattr(self.camBox, 'camInclude'):
                self.oldChecked = self.camBox.camInclude.isChecked()
                self.camBox.camInclude.setChecked(True)
        
    def resetCheck(self):
        '''reset to value at beginning of run'''
        if not self.mode==2:
            return
        if hasattr(self, 'camBox'):
            if hasattr(self.camBox, 'camInclude'):
                self.camBox.camInclude.setChecked(self.oldChecked)
                
    def dist(self, x:float, y:float, z:float) -> float:
        '''distance to the target point'''
        return ppdist([x,y,z], self.targetPoint)
        
    def lastDist(self, x:float, y:float, z:float) -> float:
        '''distance to the last target point'''
        return ppdist([x,y,z], self.lastPoint)
    
    def nextDist(self, x:float, y:float, z:float) -> float:
        '''distance to the next target point'''
        return ppdist([x,y,z], self.nextPoint)
    
#     def angle(self, x:float, y:float, z:float) -> float:
#         '''get the angle between the line between the last point and next point and the line between this point and the next point'''
#         v1 = [self.targetPoint[2]-self.lastPoint[2], self.targetPoint[1]-self.lastPoint[1], self.targetPoint[0]-self.lastPoint[0]]
#         v2 = [self.targetPoint[2]-x, self.targetPoint[1]-y, self.targetPoint[0]-z]
        
    
    def endPointDist(self) -> float:
        '''distance between the last point and target point'''
        return ppdist(self.targetPoint, self.lastPoint)
    
    def turnOn(self) -> None:
        '''turn the pressure on to the burst pressure, or snap a picture'''
        if self.mode == 1:
            # turn pressure on to burst pressure
            self.pChannel.goToRunPressure(self.burstScale)
            self.on=True
            if printDiag:
                print('turn on')
        elif self.mode == 2:
            # snap pictures
            if self.camBox.connected:
                self.camBox.cameraPic()
            else:
                logging.info(f'Cannot take picture: {self.camBox.bTitle} not connected')
                
    def turnDown(self, x:float, y:float, z:float) -> None:
        '''turn the pressure down'''
        if self.mode==1 and self.on:
            l = self.lastDist(x,y,z)
            if l>self.burstLength:
                scale = 1
            else:
                scale = 1 + (self.burstScale-1)*(1-l/self.burstLength)
            self.pChannel.goToRunPressure(scale)
            if printDiag:
                print(f'turn down {scale}')
                        
    def turnOff(self) -> None:
        '''turn the pressure off'''
        if self.mode == 1:
            self.pChannel.zeroChannel(status=False)
            self.on=False
            if printDiag:
                print('turn off')
            
    def printState(self) -> None:
        '''print the state of the print'''
        statecodes = {0:'No change at point', 1:'Turn on at point', 2:'Go to state 3 when flag is off', 3:'Turn off after point', 4:'snap picture when flag is on', 5:'Go to state 2 when flag is on'}
        logging.info(f'{self.state}:{statecodes[self.state]}. {self.targetPoint}')
        
        
    def readPoint(self) -> None:
        '''update the current state to reflect the next row'''
        self.steps=0
        if (self.currentIndex)>=len(self.points):
            # end of file
            return
        row = self.points.loc[self.currentIndex]
        if self.currentIndex+1<len(self.points):
            nextrow = self.points.loc[self.currentIndex+1]
            self.nextPoint =  [float(nextrow['x']), float(nextrow['y']), float(nextrow['z'])]
        else:
            nextrow = dict([[key, 1000] for key in self.points])
            self.nextPoint = [1000,1000,1000]
        
        self.currentIndex+=1
        if pd.isna(row['x']) or pd.isna(row['y']) or pd.isna(row['z']):
            # undefined points, skip
            if float(row[f'p{self.flag0}_before'])<0:
                # change the speed
                try:
                    speed = float(row[f'p{self.flag0}_after'])
                    if speed>0:
                        cali = self.calibBox
                        cali.updateSpeed(speed)   # update the speed in the calibration box
                        cali.plot.calcPressure()  # calculate the new pressure 
                        cali.copyPressure()       # store that pressure in the run box
                except:
                    pass
            self.readPoint()
            return
        self.lastPoint = self.targetPoint
        self.targetPoint = [float(row['x']), float(row['y']), float(row['z'])]
        if self.currentIndex+1<len(self.points):
            self.nextPoint =  [float(nextrow['x']), float(nextrow['y']), float(nextrow['z'])]
        else:
            self.nextPoint = [1000,1000,1000]
        if row[f'p{self.flag0}_before']==0 and row[f'p{self.flag0}_after']==1:
            # turn on at point
            
            if nextrow['x']==row['x'] and nextrow['y']==row['y'] and nextrow['z']==row['z'] and nextrow[f'p{self.flag0}_before']==1 and nextrow[f'p{self.flag0}_after']==0:
                # we're turning the flag on, then turning it right back off
                self.state=6
            
            if self.mode == 1:
                # turn on pressure before we hit the point
                self.state = 1
                self.critDistance = max(self.zero, self.critTimeOn*row['speed'])  # distance from point when we turn on
                
            elif self.mode == 2:
                # turn on camera with flag
                self.state = 4
                self.critDistance = self.zero
                
        elif row[f'p{self.flag0}_before']==1 and row[f'p{self.flag0}_after']==0:
            # turn off at point
            
            if self.mode == 1:
                # turn off pressure after we leave the point
                self.state = 5
                if self.critTimeOff>0:
                    self.critDistance = max(self.zero, self.critTimeOff*row['speed'])  # distance from point when we turn on
                else:
                    self.critDistance = max(self.zero, -self.critTimeOff*row['speed'])  # distance from point when we turn on
                    
            elif self.mode == 2:
                # turn off camera with flag
                self.state = 0
                self.critDistance = self.zero
        else:
            # no change in state
            self.state = 0
            self.critDistance = self.zero
          
        
    def state3turnOff(self, x:float, y:float, z:float) -> bool:
        '''determine if we are ready to leave state 3'''
        dist = self.dist(x,y,z)
        lastdist = self.lastDist(x,y,z)
        endPointDist = self.endPointDist()
        if self.critTimeOff>0:
            return (dist<self.critDistance or (dist+lastdist)>(endPointDist+self.zero))
        else:
            if printDiag:
                print((dist+lastdist),dist,self.critDistance,(endPointDist+self.zero), x, y, z, self.targetPoint)
            return (dist>self.critDistance and (dist+lastdist)>(endPointDist+self.zero))
        
    def state1turnOff(self, x:float, y:float, z:float) -> bool:
        '''determine if we are ready to leave state 1'''
        dist = self.dist(x,y,z)
        lastdist = self.lastDist(x,y,z)
        endPointDist = self.endPointDist()
        return dist<self.critDistance or (dist+lastdist)>(endPointDist+self.zero)
    
    def hitNextPoint(self, x:float, y:float, z:float) -> bool:
        '''determine if the next point was hit'''
        if not self.nextDist(x,y,z)<self.zero:
            return False
        if self.steps<5:
            return False
        logging.info(f'Skipped step at {x}, {y}, {z}')
        return True
        

    def checkPoint(self, sbFlag:int, x:float, y:float, z:float) -> bool:
        '''check if we need a change in pressure or a change in state, make changes
        return True if the run may be over, False if not'''
        # state codes: 
        if printDiag:
            print(self.state, sbFlag, x, y, z)
        if self.state==0:
            # 0 = no change at point
            if self.hitNextPoint(x,y,z):
                # if we've skipped a point, read 2 points
                self.readPoint()
                return True
            elif self.state1turnOff(x,y,z):
                # if we've reached the endpoint or left the line between the last point and target point, move on
                self.readPoint()
                return True
            else:
                self.turnDown(x,y,z)
                # we have not reached endpoint
                return False
        
        # fluigent            
        # turn on functions
        elif self.state==1:
            # 1 = turn on to high pressure when within critical distance of point
            if self.dist(x,y,z)<self.critDistance or flagOn(sbFlag, self.flag0):
                self.turnOn()    # go to burst pressure
                self.readPoint()  # look for next point
            elif self.hitNextPoint(x,y,z):
                self.turnOn()
                self.readPoint()
            return False
        elif self.state==5:
            # 5 = wait for the flag to turn on, then go to state 2
            if self.hitNextPoint(x,y,z):
                # if we've reached the next point, skip this point
                self.turnOff()
                self.readPoint()
            elif flagOn(sbFlag, self.flag0):
                # flag is on
                self.state=2
            return False
        elif self.state==6:
            self.turnOn()
            self.turnOff()
            self.readPoint()
            self.readPoint()
            return True
        
        # turn off functions
        elif self.state==2:
            # 2 = wait for the flag to turn off, then go to state 3
            if self.hitNextPoint(x,y,z):
                # we've skipped a point. turn off
                self.turnOff()
                self.readPoint()
            elif sbFlag>0 and not flagOn(sbFlag, self.flag0):  # flag is 1-indexed
                # flag is off
                self.state=3
            else:
                # continue to print line, scale pressure down
                self.turnDown(x,y,z)
            return False
        elif self.state==3:
            # 3 = turn off when past critical distance of point
            if self.hitNextPoint(x,y,z):
                # we've skipped a point. turn off and read 2 points
                self.turnOff()
                self.readPoint()
            elif self.state3turnOff(x,y,z):
                # if critTimeOff is positive, point must be within 
                # critDistance of endpoint or not on line between two endpoints
                # if critTimeOff is negative, point must not be on line 
                # between the two endpoints and must be greater than critDistance past endpoint
                self.turnOff()
                self.readPoint()
                return True
            else:
                return False
            
            
        # camera
        elif self.state==4:
            # 4 = snap when flag is on
            if flagOn(sbFlag, self.flag0):
                self.turnOn()
                self.readPoint()
                return True
            else:
                return False

            
    def done(self):
        if self.mode==2:
            self.resetCheck()

        
class SBPtimings:
    '''a tool for triggering changes in state
    numChannels is the number of pressure channels available
    critTimeOn: turn on flow this many seconds before you hit the corner
    critTimeOff: turn off flow this many seconds after you leave the corner
    zero: mm margin of error to be "at the point"
    '''

    def __init__(self, sbpfile:str, sbWin, critTimeOn:float=0.1, critTimeOff:float=0, zero:float=0.1):
        self.sbWin = sbWin
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
                if not list(sp[key].unique())==[0]:
                    # make sure flag changes
                    spl = re.split('p|_', key)
                    flag0 = int(spl[1])   # 0-indexed
                    if not flag0==self.sbWin.sbBox.runFlag1-1:
                        self.channels.append(channelWatch(self.csvfile, flag0, sbWin))
        
    def check(self, sbFlag:int, x:float, y:float, z:float) -> bool:
        '''update status of channels based on position and flags
        return True if the run may be over, False if not'''
        allowEnd = True
        
        for c in self.channels:
            o = c.checkPoint(sbFlag, x, y, z)
            if not o:
                allowEnd = False
        return allowEnd
    
    def done(self):
        for channel in self.channels:
            channel.done()