#!/usr/bin/env python
'''Shopbot GUI Shopbot functions for shopbot flag and registry key handling'''

# external packages
from PyQt5.QtCore import QMutex, Qt
from PyQt5.QtWidgets import QGridLayout, QLabel, QMainWindow
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
from config import cfg
from general import *
from sbprint import *

##################################################  



class flagGrid(QGridLayout):
    '''panel that labels what devices the shopbot flags correspond to, and state of flags'''
    
    def __init__(self, parent:connectBox, tall:bool=True):
        super(flagGrid, self).__init__()
        
        self.sbBox = parent.sbBox
        self.sbWin = parent
        self.flag1min = cfg.shopbot.flag1min
        self.flag1max = cfg.shopbot.flag1max
        self.numFlags = self.flag1max-self.flag1min+1
        self.resetFlagLabels()
            
        self.successLayout(tall=tall)
        self.labelFlags()
        
    def resetFlagLabels(self):
        self.flagLabels0 = dict([[flag0, ''] for flag0 in range(self.numFlags)])   
                    # dictionary that holds labels {flag:device name}
                    # 0=indexed
        
    def successLayout(self, tall:bool=True) -> None:
        # coords
        w = 25
        for i,dim in enumerate(['x', 'y', 'z']):
            dlabel = QLabel(dim)
            dlabel.setFixedWidth(w)
            dlabel.setFixedHeight(w)
            dlabel.setAlignment(Qt.AlignCenter)
            self.addWidget(dlabel, i, 0)
            setattr(self, dim, QLabel(''))
            self.addWidget(getattr(self, dim), i, 1)
        
        # flags
        row = -1
        col = 2
        for flag0 in range(self.numFlags):
            if tall:
                row = flag0+3
                col = 0
            else:
                # wide layout
                row+=1
                if row>3:
                    row = 0
                    col+=2
            # create the number label
            fname = self.flagName(flag0)
            flagBox = QLabel(str(flag0+1))
            flagBox.setFixedWidth(w)
            flagBox.setFixedHeight(w)
            flagBox.setAlignment(Qt.AlignCenter)
            setattr(self, fname, flagBox)           # label should be 1-indexed
            
            self.addWidget(getattr(self, fname), row, col)
            
            # create the device label
            label = self.flagLabelName(flag0)
            setattr(self, label, QLabel(''))
            self.addWidget(getattr(self, label), row, col+1)
            
        
        
    def updateXYZ(self, x, y, z) -> None:
        '''update the xyz display'''
        if not hasattr(self, 'x') or not hasattr(self, 'y') or not hasattr(self, 'z'):
            # missing attribute, can't set xyz labels
            return
        self.x.setText(f'{x:0.3f}')
        self.y.setText(f'{y:0.3f}')
        self.z.setText(f'{z:0.3f}')
 
    def flagTaken(self, flag0:int) -> bool:
        '''check the dictionary to see if the flag is taken'''
        if flag0<self.flag1min-1 or flag0>self.flag1max-1:
            # flag out of range
            return False
        label = self.flagLabels0[flag0]
        if len(label)>0:
            logging.info(f'Flag taken: {flag0+1}: {label}')
            return True
        else:
            return False
      
        
    def flagName(self, flag0:int) -> str:
        '''name of the flag number object, where flags are 0-indexed'''
        return f'flag{flag0}Label'
    
    def flagLabelName(self, flag0:int) -> str:
        '''name of the flag device label object, where flags are 0-indexed'''
        return f'flag{flag0}Device'
    
    def highlightFlag(self, flag0:int) -> None:
        '''highlight the flag on the shopbot flag panel'''
        fname = self.flagName(flag0)
        if not hasattr(self, fname):
            # missing attribute, can't update flag label
            return
        flagObj = getattr(self, fname)
        flagObj.setStyleSheet("background-color: #a3d9ba; border-radius: 3px")
        
    def unhighlightFlag(self, flag0:int) -> None:
        '''unhighlight the flag on the shopbot flag panel'''
        fname = self.flagName(flag0)
        if not hasattr(self, fname):
            # missing attribute, can't update flag label
            return
        flagObj = getattr(self, fname)
        flagObj.setStyleSheet("background-color: none")
        
    def update(self, sbFlag:int) -> None:
        '''update the highlight status based on sbFlag'''
        for flag0 in range(self.numFlags):
            if flagOn(sbFlag, flag0):
                self.highlightFlag(flag0)
            else:
                self.unhighlightFlag(flag0)

        
    def labelFlags(self) -> None:
        '''label the devices in the shopbot flag grid'''
        # reset all labels
        self.resetFlagLabels()
        
        for flag0 in range(self.numFlags):
            labelname = self.flagLabelName(flag0)
            if hasattr(self, labelname):
                labelObj = getattr(self, labelname)
                labelObj.setText('')
        
        # get flags from camBoxes and fluChannels and re-label
        if hasattr(self.sbWin, 'camBoxes'):
            objects = self.sbWin.camBoxes.list
        else:
            objects = []
        if hasattr(self.sbWin, 'fluBox'):
            objects = objects + self.sbWin.fluBox.pchannels
                
        for obj in objects:
            labelname = self.flagLabelName(obj.flag1-1)
            if hasattr(self, labelname):
                labelObj = getattr(self, labelname)
                labelObj.setText(obj.bTitle)   # update display
                self.flagLabels0[obj.flag1-1] = obj.bTitle   # keep in dictionary
            
        # shopbot run flag
        runFlag1 = self.sbBox.getRunFlag1()
        labelname = self.flagLabelName(runFlag1-1)
        if hasattr(self, labelname):
            labelObj = getattr(self, labelname)
            labelObj.setText('Run')
            self.flagLabels0[runFlag1-1] = 'Run'
        
        
        
######################################

class SBKeys(QMutex):
    '''class the holds information and functions about connecting to the shopbot'''
    
    def __init__(self, sbBox:connectBox):
        super(SBKeys,self).__init__()
        self.sbBox = sbBox
        self.connected = False
        self.ready = False
        self.status=6
        self.sb3File = ''
        self.prevFlag = 0
        self.currentFlag = 0
        self.msg = ''
        self.connectKeys()   # connect to the keys and open SB3.exe
        
    def updateStatus(self, message:str, log:bool) -> None:
        '''send the status back to the SBbox'''
        
        self.sbBox.updateStatus(message, log)
        
        
    def connectKeys(self) -> None:
        '''connects to the windows registry keys for the Shopbot flags'''

        # find registry
        try:
            aReg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        except AttributeError:
            self.updateStatus('Failed to connect to shopbot: Key not found: HKEY_CURRENT_USER', True)
            return
            
        # find key
        aKey = r'Software\VB and VBA Program Settings\Shopbot\UserData'
        try:
            self.aKey = winreg.OpenKey(aReg, aKey)
        except FileNotFoundError:
            self.updateStatus(f'Failed to connect to shopbot: Key not found: {aKey}', True)
            return
            
        # found key
        self.connected = True

        self.findSb3()                     # find the SB3 file
        subprocess.Popen([self.sb3File])   # open the SB3 program
        
    def queryValue(self, value) -> Any:
        '''try to get a value from a key located at self.aKey'''
        if not self.connected:
            raise ValueError
        
        try:
            val = winreg.QueryValueEx(self.aKey, value)
        except FileNotFoundError:  
            # if we fail to get the registry key, we have no way of knowing 
            # if the print is over, so just stop it now
            self.updateStatus(f'Failed to connect to shopbot: Value not found: {value}', True)
            self.connected = False
            raise ValueError
        except NameError:
            self.updateStatus(f'Failed to connect to shopbot: Key not found', True)
            self.connected = False
            raise ValueError
        else:
            return val
        
        
    def findSb3(self):
        '''find the sb3.exe file. return true if successful'''
        try:
            path,_ = self.queryValue('uAppPath')
        except ValueError:
            return
        
        # found file
        self.sb3File = os.path.join(path, 'Sb3.exe')
        return
        
            
    def sbStatus(self) -> int:
        '''find the status of the shopbot'''
        try:
            status, _ = self.queryValue('Status')
        except ValueError:
            return 6
        
        return int(status)
    
    
    def waitForSBReady(self) -> None:
        '''wait for the shopbot to be ready before starting the file'''
        self.ready=False
        status = self.sbStatus()
        inames = {0:'FileRunning', 1:'PreviewMode', 2:'KeyPadOpen', 3:'PauseinFile', 4:'StopHit', 5:'StackRunning', 6:'SBNotConnected'}
        if status>0:
            inames = []
            for i in inames:
                if flagOn(status, i):
                    inames.append(inames[i])
            self.updateStatus(f'{status}: {inames}: waiting for SB to be ready', False)
        else:
            self.updateStatus('Shopbot is ready', True)
            self.ready = True
 
    def getSBFlag(self) -> int:
        '''run this function continuously during print to watch the shopbot status'''
        
        try:
            sbFlag, _ = self.queryValue('OutPutSwitches')
        except ValueError:
            return -1
        
        self.prevFlag = self.currentFlag
        sbFlag = int(sbFlag)
        self.currentFlag = sbFlag
        self.sbBox.updateFlag(sbFlag)
        return sbFlag

    
    def getuCommands(self) -> List[str]:
        '''run this function continuously during print to watch the shopbot status'''
        
        clist = []
        for command in ['uCommand', 'uCommandQ1']:
            try:
                c, _ = self.queryValue('uCommand')
            except ValueError:
                return clist
            clist.append(c)
        return clist

    
    def getLoc(self) -> Tuple[int,int,int]:
        '''get the x,y,z location of the shopbot'''
        
        xlist = []
        for command in ['Loc_1', 'Loc_2', 'Loc_3']:
            try:
                c, _ = self.queryValue(command)
            except ValueError:
                return []
            xlist.append(c)
            
        xlist = [float(i) for i in xlist]
    
        self.sbBox.updateXYZ(xlist[0], xlist[1], xlist[2])
            
        return xlist
    
    
    def readMsg(self) -> None:
        '''read messages from the shopbot'''
        
        try:
            msg, _ = self.queryValue('uMsgBoxMessage')
        except ValueError:
            return

        if len(msg)>0:
            if not msg==self.msg:
                self.msg = msg
                self.updateStatus(f'Shopbot message: {msg}', True)
        else:
            self.msg = ''

        