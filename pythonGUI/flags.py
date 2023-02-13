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
import pyfirmata
from pyfirmata import util, Arduino


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
        self.pins = {}
        
        self.resetFlagLabels()
            
        self.successLayout(tall=tall)
        self.labelFlags()
        
    def resetFlagLabels(self) -> None:
        '''create a new dictionary to hold flags and labels'''
        self.flagLabels0 = dict([[flag0, ''] for flag0 in range(self.numFlags)])   
                    # dictionary that holds labels {flag:device name}
                    # 0=indexed
        self.flagLabels0[3] = 'Reserved'
                
    def unusedFlag0(self) -> int:
        '''find an unused flag'''
        i = 0
        while i<12:
            if self.flagLabels0[i]=='':
                return i
            i+=1
        raise ValueError('All flags are taken')       

        
    def successLayout(self, tall:bool=True) -> None:
        # coords
        self.addWidget(QLabel('SB3'), 0, 0, 1, 2)
        self.addWidget(QLabel('Estimate'), 0, 2, 1, 2)
        self.addWidget(QLabel('Target'), 0, 4, 1, 2)
        self.addWidget(QLabel('Flags'), 0, 6, 1, 6)
        
        w = 25
        for j,s in enumerate(['', 'e', 't']):
            for i,dim in enumerate(['x', 'y', 'z']):
                dname = f'{dim}{s}'
                dlabel = QLabel(dname)
                dlabel.setFixedWidth(w)
                dlabel.setFixedHeight(w)
                dlabel.setAlignment(Qt.AlignCenter)
                self.addWidget(dlabel, i+1, 0+j*2)
                setattr(self, dname, QLabel(''))
                self.addWidget(getattr(self, dname), i+1, 1+j*2)
        
        # flags
        row = -1
        col = 6
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
            
            self.addWidget(getattr(self, fname), row+1, col)
            
            # create the device label
            label = self.flagLabelName(flag0)
            setattr(self, label, QLabel(''))
            self.addWidget(getattr(self, label), row+1, col+1)
            
        
        
    def updateXYZ(self, x, y, z) -> None:
        '''update the xyz display'''
        if not hasattr(self, 'x') or not hasattr(self, 'y') or not hasattr(self, 'z'):
            # missing attribute, can't set xyz labels
            return
        self.x.setText(f'{x:0.3f}')
        self.y.setText(f'{y:0.3f}')
        self.z.setText(f'{z:0.3f}')
        
    def updateXYZest(self, x,y,z) -> None:
        '''update the estimated xyz display'''
        if not hasattr(self, 'xe') or not hasattr(self, 'ye') or not hasattr(self, 'ze'):
            # missing attribute, can't set xyz labels
            return
        self.xe.setText(f'{x:0.3f}')
        self.ye.setText(f'{y:0.3f}')
        self.ze.setText(f'{z:0.3f}')
        
    def updateXYZt(self, x,y,z) -> None:
        '''update the target xyz display'''
        if not hasattr(self, 'xt') or not hasattr(self, 'yt') or not hasattr(self, 'zt'):
            # missing attribute, can't set xyz labels
            return
        self.xt.setText(f'{x:0.3f}')
        self.yt.setText(f'{y:0.3f}')
        self.zt.setText(f'{z:0.3f}')
 
    def flagTaken(self, flag0:int) -> bool:
        '''check the dictionary to see if the flag is taken'''
        if flag0<self.flag1min-1 or flag0>self.flag1max-1 or flag0==3:
            # flag out of range, or special spindle flag
            return True
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
        style = "background-color: #a3d9ba; border-radius: 3px"
        if flag0+1 in self.pins:
            style = style + '; font-weight: bold;'
        flagObj.setStyleSheet(style)
        
    def unhighlightFlag(self, flag0:int) -> None:
        '''unhighlight the flag on the shopbot flag panel'''
        fname = self.flagName(flag0)
        if not hasattr(self, fname):
            # missing attribute, can't update flag label
            return
        flagObj = getattr(self, fname)
        style = "background-color: none"
        if flag0+1 in self.pins:
            style = style + '; font-weight: bold;'
        flagObj.setStyleSheet(style)
        
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
                
        self.flag3Device.setText('Reserved')
        
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
            
    def boldFlags(self, pins:dict) -> None:
        '''bold the labels for flags that are going through the arduino'''
        self.pins = pins
        for flag0 in range(self.numFlags):
            self.unhighlightFlag(flag0)
            
    def writeToTable(self, writer) -> None:
        '''write metadata values to the table'''
        writer.writerow(['arduino_trust', '1-indexed', list(self.pins.keys())])
        
    def close(self) -> None:
        return
        
        
######################################

class arduinoSignals(QObject):
    status = pyqtSignal(str, bool) # send status message back to GUI


class arduino(QMutex):
    '''class that connects to the arduino'''
    
    def __init__(self, connect:bool=True):
        super().__init__()
        self.signals = arduinoSignals()
        self.uvOn = False    # this indicates whether we have commanded the UV on. still need to press physical button to allow on
        self.uvAsked = False  # this indicates whether we have asked for the UV to turn on. if we asked for it and door is open, uvAsked is True but ovOn is false
        self.uvpins = {}
        self.pins = {}
        self.connected = False
        self.SBConnected = False
        self.uvConnected = False
        if connect:
            self.connect()
            
    @pyqtSlot(str,bool)
    def updateStatus(self, message:str, log:bool) -> None:
        '''send the status back to the main window'''
        self.signals.status.emit(message, log)
        
    def connect(self) -> None:
        '''connect to the arduino'''
        try:
            self.board = Arduino(cfg.arduino.port)
            it = util.Iterator(self.board)
            it.start()
        except:
            print('Failed to connect to Arduino')
            return
        self.connected = True
        self.connectSB()
        self.connectUV()   
        
    def connectSB(self) -> None:
        '''connect the SB output flags'''
        # get the pin-flag correspondences from the config file
        for f in [5,6,7,8]:
            p = int(cfg.arduino.flag1pins[f'f{f}'])   # pin this 1-indexed flag is assigned to
            self.board.digital[p].mode = pyfirmata.INPUT    # set this pin to receive input
            self.board.digital[p].enable_reporting()        # set this pin to let us read it
        time.sleep(0.1)
        self.finishConnectingSB()  # wait 0.1 seconds before checking values
        
    def startCheck(self) -> None:
        '''set all the pins except the UV pins to input mode to check what flags they are connected to.'''
        for p in range(2, 14):
            if not p in cfg.arduino.uvpins.values():
                self.board.digital[p].mode = pyfirmata.INPUT    # set this pin to receive input
                self.board.digital[p].enable_reporting()        # set this pin to let us read it
                
                
    def findOnPin(self, flag1:int) -> None:
        '''find the arduino pin that is on. flag1 is the flag that is on. assign the new value to pins'''
        if not self.connected:
            return
        if flag1 in self.pins:
            self.pins.pop(flag1) # remove this flag from the pins dict
        for p in range(2,14):
            if not p in cfg.arduino.uvpins.values():
                val = self.board.digital[p].read()  
                if val==True:
                    self.pins[flag1] = p
                    return
        
        
            
    def finishConnectingSB(self) -> None:
        '''check that the pins are actually connected'''
        for f in [5,6,7,8]:
            p = int(cfg.arduino.flag1pins[f'f{f}'])   # pin this 1-indexed flag is assigned to
            val = self.board.digital[p].read()   # read value twice because the first will be empty
            if val==True or val==False:
                self.pins[f] = p
            else:
                print(f'Failed to read arduino pin {p} for flag {f}: {val}')
        self.checkConnect()
                
    def checkConnect(self) -> None:
        '''check if the pins are connected'''
        if not self.connected:
            return
        if len(self.pins)>0:
            self.SBConnected = True
        else:
            self.SBConnected = False
            
    def connectUV(self) -> None:
        '''connect the UV interlock and output pins'''
        if 'uvpins' in cfg.arduino:
            for s in ['in', 'out']:
                if s in cfg.arduino.uvpins:
                    p = int(cfg.arduino.uvpins[s])
                    if s=='in':
                        self.board.digital[p].mode = pyfirmata.INPUT    # set this pin to receive input
                        self.board.digital[p].enable_reporting()        # set this pin to let us read it
                        time.sleep(0.1)
                        val = self.board.digital[p].read()
                        if val==True or val==False:
                            self.uvpins[s] = p
                        else:
                            print(f'Failed to read arduino pin {p} for uv {s}', True)
                    else:
                        self.uvpins[s] = p
                        self.board.digital[p].mode = pyfirmata.OUTPUT
        if len(self.uvpins)==2:
            self.uvConnected = True
        self.turnOffUV()
                        
            
    def readSB(self, sbFlag:int) -> int:
        '''read the flags from the arduino and update the sbFlag'''
        if not self.connected:
            return
        for f1,p in self.pins.items():
            status = self.board.digital[p].read()   # read the pin, returns a bool
            on = flagOn(sbFlag, f1-1)
            if status and not on:
                # sb3 thinks the flag is off, but hardware says it's on
                sbFlag = sbFlag + 2**(f1-1)
                # logging.info(f'SB3 {p} {on} and Arduino {f1} {status}: disagree')
            elif not status and on:
                # sb3 thinks the flag is on, but hardware says it's off
                sbFlag = sbFlag - 2**(f1-1)
                # logging.info(f'SB3 {p} {on} and Arduino {f1} {status}: disagree')
        return sbFlag
    
    def doorsClosed(self) -> bool:
        '''check if there are any doors open'''
        if not self.connected or not self.uvConnected:
            # no uv pins detected, assume doors are open
            return False
        sensor = self.board.digital[self.uvpins['in']].read()  # true if door is open
        if sensor and self.uvOn:
            # door is open
            self.updateStatus('Turned off UV lamp: door is open', True)
            self.turnOffUV()  # turn off uv
        return not sensor
    
    def checkStatus(self) -> str:
        '''check the door status and the lamp status'''
        closed = self.doorsClosed()
        if self.uvAsked and not self.uvOn and closed:
            # we have been waiting for the door to close
            self.turnOnUV()
        if closed:
            if self.uvAsked and not self.uvOn:
                return 'waiting for door'
            else:
                return 'doors closed'
        else:
            return 'door open'
 
            
    def turnOnUV(self) -> int:
        '''send a signal to the UV lamp to turn on uv'''
        self.uvAsked = True
        if not self.connected or not self.uvConnected:
            # no uv pins detected, do nothing
            self.updateStatus('Did not turn on UV lamp: no UV found', True)
            return 1
        if not self.doorsClosed():
            self.updateStatus('Did not turn on UV lamp: door is open', True)
            return 1
        else:
            self.board.digital[self.uvpins['out']].write(1)
            self.updateStatus('Turning on UV', True)
            self.uvOn = True
            return 0
            
    def turnOffUV(self) -> int:
        '''turn off the UV lamp'''
        self.uvAsked = False
        if not self.connected or not self.uvConnected:
            # no uv pins detected, assume doors are open
            return 1
        self.board.digital[self.uvpins['out']].write(0)
        self.uvOn = False
        self.updateStatus('Turning off UV', True)
        return 0
        
    def toggleUV(self) -> int:
        '''turn uv on or off'''
        if self.uvOn:
            return self.turnOffUV()
        else:
            return self.turnOnUV()
        
    

class SBKeySignals(QObject):
    status = pyqtSignal(str, bool) # send status message back to GUI
    flag = pyqtSignal(int)         # send current flag status back to GUI
    pos = pyqtSignal(float,float,float) # send current position back to GUI
    lastRead = pyqtSignal(int)   # send last line read back to GUI
    

class SBKeys(QMutex):
    '''class that holds information and functions about connecting to the shopbot'''
    
    def __init__(self, diag:int, ard:arduino):
        super(SBKeys,self).__init__()
        self.connected = False
        self.ready = False
        self.status=6
        self.sb3File = ''
        self.prevFlag = 0
        self.currentFlag = 0
        self.lastRead = 0
        self.msg = ''
        self.runningSBP = False
        self.diag = diag
        self.signals = SBKeySignals()
        self.connectKeys()   # connect to the keys and open SB3.exe
        self.ctr = 0
        self.arduino = ard
  
    def updateStatus(self, message:str, log:bool) -> None:
        '''send the status back to the SBbox'''
        self.signals.status.emit(message, log)

    #------------------------------
        
        
    def connectKey(self, aReg, path:str, name:str):
        '''connect a single key'''
        key = os.path.join(r'Software\VB and VBA Program Settings\Shopbot', path)
        try:
            k = winreg.OpenKey(aReg, key)
            setattr(self, f'{name}Key', k)
        except FileNotFoundError:
            self.updateStatus(f'Failed to connect to shopbot: Key not found: {key}', True)
            return
        except Exception as e:
            print(e)
        
        
    def connectKeys(self) -> None:
        '''connects to the windows registry keys for the Shopbot flags'''

        # find registry
        try:
            aReg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        except AttributeError:
            self.updateStatus('Failed to connect to shopbot: Key not found: HKEY_CURRENT_USER', True)
            return
            
        # find key
        self.connectKey(aReg, 'UserData', 'UserData')
        self.connectKey(aReg, r'Sb3\Settings', 'Settings')
        self.connectKey(aReg, r'Sb3\DebugStatus', 'DebugStatus')
            
        # found key
        self.connected = True

        self.findSb3()                     # find the SB3 file
        subprocess.Popen([self.sb3File])   # open the SB3 program
        
    def keyFolderDict(self) -> dict:
        return {'UserData':
                    ['AnInp1', 'AnInp2', 'InputSwitches'
                     , 'Loc_1', 'Loc_2', 'Loc_3'
                     , 'OutPutSwitches', 'SpindleStatus','Status'
                     , 'uAppPath'
                     , 'uCommand', 'uCommandQ1', 'uMsgBoxCaption'
                     , 'uMsgBoxMessage', 'uPartFileName', 'uResponse'
                     , 'uSpindleStatus', 'uUsrPath', 'uValueClrd']
            , 'Settings':
                    ['Cheight', 'Cheight_prev', 'Cleft', 'Cleft_prev'
                     , 'Ctop', 'Ctop_prev', 'Cwidth', 'Cwidth_prev'
                     , 'DoneEASY', 'DoneWelcome', 'LAstConnected'
                     , 'LAstRead', 'LastSoftwareLoaded', 'RegInteractionActive']
            , 'Debug':
                    ['Status01', 'Status02', 'Status03']}
        
    def getKeyFolder(self, value:str):
        '''get the key folder, as a QueryValueEx, that holds the requested key'''
        d0 = self.keyFolderDict()
        for key,val in d0.items():
            if value in val:
                ks = f'{key}Key'
                if not hasattr(self, ks):
                    raise ValueError(f'Unexpected key requested: {ks}')
                else:
                    k = getattr(self, ks)
                    return k
        raise ValueError(f'Unexpected key requested: {value}')
        
    def queryValue(self, value) -> Any:
        '''try to get a value from a key located at self.UserDataKey'''
        if not self.connected:
            raise ValueError
        k = self.getKeyFolder(value)
        try:
            val = winreg.QueryValueEx(k, value)
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
            raise ValueError('Could not find SB3.exe path')        
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
    
    
    def SBisReady(self) -> None:
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
        return self.ready
    
    def checkStop(self) -> None:
        '''check if stop was hit on shopbot'''
        status = self.sbStatus()
        inames = {0:'FileRunning', 1:'PreviewMode', 2:'KeyPadOpen', 3:'PauseinFile', 4:'StopHit', 5:'StackRunning', 6:'SBNotConnected'}
        if status>0:
            if not flagOn(status, 0):
                # file is not running, stop
                return True
            if flagOn(status, 4):
                # stop was hit, stop
                return True
        return False
 
    def getSBFlag(self) -> int:
        '''run this function continuously during print to watch the shopbot status'''
        
        try:
            sbFlag, _ = self.queryValue('OutPutSwitches')
        except ValueError:
            return -1
        sbFlag = self.arduino.readSB(int(sbFlag))  # cross reference this result with arduino
        
        self.prevFlag = self.currentFlag
        sbFlag = int(sbFlag)
        self.currentFlag = sbFlag
        self.signals.flag.emit(sbFlag)    # send flag back to gui
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
    
        self.signals.pos.emit(xlist[0], xlist[1], xlist[2])   # send position back to GUI
            
        return xlist
    
    def getLastRead(self) -> int:
        '''get the line number of the last line read into the file'''
        try:
            c, _ = self.queryValue('LAstRead')
        except ValueError:
            return -1
        self.lastRead = int(c)
        self.signals.lastRead.emit(self.lastRead)
        return self.lastRead
    
    def getListOfKeys(self, l:List[str]) -> dict:
        '''probe the given list of keys and return a dictionary'''
        d = {}
        for command in l:
            try:
                c, _ = self.queryValue(command)
            except ValueError:
                pass
            else:
                d[command]=c
        return d
    
    def printAllKeys(self) -> None:
        '''print all of the registry keys available to us in Shopbot/UserData'''
        d0 = self.keyFolderDict()
        d = {}
        for key,l in d0.items():
            d = {**d, **self.getListOfKeys(l)}
        print(d)
        
    def printChangingKeys(self) -> None:
        '''print the registry keys that change during a print'''
        self.ctr+=1
        l = ['Loc_1', 'Loc_2', 'Loc_3', 'Status', 'OutPutSwitches', 'LAstRead'] 
        d = self.getListOfKeys(l)
        if self.ctr%100==0:
            print('\t'.join(list(d.keys())))
        print('\t'.join(list(d.values())))
        
    
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

        