#!/usr/bin/env python
'''Shopbot GUI. 

Coordinating the shopbot with the cameras and Fluigent relies on the output flags that you can see in the Sb3 software. These flags are stored as windows registry keys, usually held in 'Software\\VB and VBA Program Settings\\Shopbot\\UserData'. This is designed for a shopbot with four output flags, a Fluigent with two channels, and three cameras. 

When the shopbot runs a program that sets the output flags, it first turns on output flag 4 (1-indexed). Then, it asks the user to let it turn on the spindle. (You should say yes.) This python GUI will watch those output flags for commands. If flag 3 (1-indexed) is turned on, the checked cameras will take a picture. If flag 1 is turned on, Fluigent channel 1 (1-indexed) will turn on to whatever is inserted into "Run Pressure". If there is a second channel, flag 2 will turn on Fluigent channel 2. When the shopbot is done with the whole file, it will turn off all output flags, and the python GUI will take that as a sign that it is time to stop recording.

'''


from PyQt5 import QtCore, QtWidgets, QtGui, QtMultimedia, QtMultimediaWidgets
import PyQt5.QtWidgets as qtw
import pyqtgraph as pg
import cv2
import sys
import time
import datetime
import numpy as np
from random import randint
import sip
import ctypes
import os
import winreg
import subprocess
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
from config import cfg


import Fluigent.SDK as fgt
try:
    os.environ["PYLON_CAMEMU"] = "3"
    from pypylon import genicam
    from pypylon import pylon
except:
    logging.warning('Pylon SDK not installed')
    pass

__author__ = "Leanne Friedrich"
__copyright__ = "This data is publicly available according to the NIST statements of copyright, fair use and licensing; see https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software"
__credits__ = ["Leanne Friedrich"]
__license__ = "MIT"
__version__ = "1.0.4"
__maintainer__ = "Leanne Friedrich"
__email__ = "Leanne.Friedrich@nist.gov"
__status__ = "Development"


APPID = 'leanfried.sbgui.v0.4'



#################################################

DEFAULTFOLDER = cfg.sbp
if not os.path.exists(DEFAULTFOLDER):
    DEFAULTFOLDER = r'C:\\'
INITSAVEFOLDER = cfg.vid
if not os.path.exists(INITSAVEFOLDER):
    INITSAVEFOLDER = r'C:\\'

################################################


def fileDialog(startDir:str, fmt:str, isFolder:bool) -> str:
    '''fileDialog opens a dialog to select a file for reading
    startDir is the directory to start in, e.g. r'C:\Documents'
    fmt is a string file format, e.g. 'Gcode files (*.gcode *.sbp)'
    isFolder is bool true to only open folders'''
    dialog = qtw.QFileDialog()
    dialog.setFilter(dialog.filter() | QtCore.QDir.Hidden)

    # ARE WE TALKING ABOUT FILES OR FOLDERS
    if isFolder:
        dialog.setFileMode(qtw.QFileDialog.DirectoryOnly)
    else:
        dialog.setFileMode(qtw.QFileDialog.ExistingFiles)
        
    # OPENING OR SAVING
    dialog.setAcceptMode(qtw.QFileDialog.AcceptOpen)

    # SET FORMAT, IF SPECIFIED
    if fmt != '' and isFolder is False:
        dialog.setDefaultSuffix(fmt)
        dialog.setNameFilters([f'{fmt} (*.{fmt})'])

    # SET THE STARTING DIRECTORY
    if startDir != '':
        dialog.setDirectory(str(startDir))
    else:
        dialog.setDirectory(str(ROOT_DIR))

    if dialog.exec_() == qtw.QDialog.Accepted:
        paths = dialog.selectedFiles()  # returns a list
        return paths
    else:
        return ''

#####################################################

def findFileInFolder(file:str, folder:str) -> str:
    '''findFileInFolder finds the full path name for a file in a folder
    file is the basename string
    folder is the folder to search in
    this searches recursively and returns an exception if it doesn't find the file'''
    f1 = os.path.join(folder, file)
    if os.path.exists(f1):
        return f1
    for subfold in os.listdir(folder):
        subfoldfull = os.path.join(folder, subfold)
        if os.path.isdir(subfoldfull):
            try:
                file = findFileInFolder(file, subfoldfull)
            except:
                pass
            else:
                return file
    raise Exception(file+' not found')


def findSb3Folder() -> str:
    '''find the folder that the Sb3 program files are in'''
    for fold in [r'C:\\Program files', r'C:\\Program files (x86)']:
        for f in os.listdir(fold):
            if 'ShopBot'.lower() in f.lower():
                return os.path.join(fold, f)
    raise Exception('Shopbot folder not found')


def findSb3() -> str:
    '''find the full path name for the Sb3.exe program
    raises an exception if it doesn't find the file'''
    try:
        fold = findSb3Folder()
    except:
        raise Exception('Sb3.exe not found')
    try:
        sb3File = findFileInFolder('Sb3.exe', fold)
        subprocess.Popen([sb3File])
    except:
        raise Exception('Sb3.exe not found')
    else:
        return sb3File

##############################################################

def deleteLayoutItems(layout) -> None:
    '''use this to remove an entire QtLayout and its children from the GUI'''
    if layout is not None:
        try:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    deleteItems(item.layout())
        except:
            return
    sip.delete(layout)

###############################################################

def formatExplorer(fn:str) -> str:
    '''Format the file name for use in subprocess.Popen(explorer)'''
    return fn.replace(r"/", "\\")

class genBox(qtw.QGroupBox):
    '''this is a gui box for managing files. It goes at the top of the window'''
    def __init__(self, sbWin:qtw.QMainWindow):
        super(genBox, self).__init__()
        self.sbWin = sbWin
        self.layout = qtw.QGridLayout()        

        self.appendName = qtw.QLineEdit()
        self.appendName.setText('')
        
        self.appendLabel = qtw.QLabel('Append to output file names:')
        self.appendLabel.setBuddy(self.appendName)
        
        self.saveButt = qtw.QPushButton('Set video folder')
        self.saveButt.setIcon(QtGui.QIcon('icons/open.png'))
        self.saveButt.clicked.connect(self.setSaveFolder)
        
        self.saveFolder = INITSAVEFOLDER
        self.saveFolderLabel = qtw.QLabel('Export to ' + self.saveFolder)
        
        self.layout.addWidget(self.saveButt, 1, 0)
        self.layout.addWidget(self.saveFolderLabel, 1, 1)
        self.layout.addWidget(self.appendLabel, 2, 0)
        self.layout.addWidget(self.appendName, 2, 1)
       
        self.setLayout(self.layout)
    
    
    def setSaveFolder(self) -> None:
        '''set the folder to save all the files we generate from the whole gui'''
        if os.path.exists(self.saveFolder):
            startFolder = os.path.dirname(self.saveFolder)
        else:
            startFolder = INITSAVEFOLDER
        sf = fileDialog(startFolder, '', True)
        if len(sf)>0:
            sf = sf[0]
            if os.path.exists(sf):
                self.saveFolder = formatExplorer(sf)
                
                logging.info('Changed save folder to %s' % self.saveFolder)
                self.saveFolderLabel.setText('Export to ' + self.saveFolder)
            
    def openSaveFolder(self) -> None:
        '''Open the save folder in windows explorer'''
        
        if not os.path.exists(self.saveFolder):
            logging.debug(f'Save folder does not exist: {self.saveFolder}')
            return
        logging.debug(f'Opening {self.saveFolder}')
        cmd = ['explorer',  formatExplorer(self.saveFolder)]
        
        subprocess.Popen(cmd, shell=True)



            
##############################################################################       



class connectBox(qtw.QGroupBox):
    '''connectBox is a type of QGroupBox that can be used for cameras and fluigent, which need to be initialized. This gives us the option of showing an error message and reset button if the program doesn't connect'''
    
    def __init__(self):
        super(connectBox, self).__init__()
        self.connectAttempts = 0
        self.connected = False
        self.diag=1

    
    def connectingLayout(self) -> None:
        '''if the computer is still trying to connect, show this waiting screen'''
        if self.connectAttempts>0:
            self.resetLayout()
        self.layout = qtw.QVBoxLayout()
        logging.info('Connecting to %s' % self.bTitle)
        self.layout.addWidget(qtw.QLabel('Connecting to '+self.bTitle))
        self.setLayout(self.layout)  

    
    def failLayout(self) -> None:
        '''if the computer fails to connect, show an error message and a button to try again'''
        self.resetLayout()
        self.layout = qtw.QVBoxLayout()
        lstr = self.bTitle+' not connected. Connect attempts: '+str(self.connectAttempts)
        logging.warning(lstr)
        self.label = qtw.QLabel(lstr)            
        self.resetButt = qtw.QPushButton('Connect to ' + self.bTitle)
        self.resetButt.clicked.connect(self.connect) 
            # when the reset button is pressed, try to connect to the fluigent again
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.resetButt)
        self.setLayout(self.layout)
    
    
    def createStatus(self, width:int) -> None:
        '''creates a section for displaying the device status'''
        self.status = qtw.QLabel('Ready')
        self.status.setFixedSize(width, 50)
        self.status.setWordWrap(True)
    
    
    def resetLayout(self) -> None:
        '''delete all the display items from the box'''
        deleteLayoutItems(self.layout)
        
    
    def updateStatus(self, st, log) -> None:
        '''update the displayed device status'''
        try:
            self.status.setText(st)
        except:
            if self.diag>0:
                logging.info(st)
        else:
            if log and self.diag>0:
                logging.info(st)

################################################################


class sbBox(connectBox):
    '''Holds shopbot functions and GUI items'''
    
    
    ####################  
    ############## initialization functions
    
    
    def __init__(self, sbWin:qtw.QMainWindow):
        '''sbWin is the parent window that all of the widgets are in'''
        super(sbBox, self).__init__()
        self.btitle = 'Shopbot'
        self.sbWin = sbWin
        self.runningSBP = False
        self.setTitle('Shopbot')
        self.prevFlag = 0
        self.currentFlag = 0
        self.sbpName='No file selected'
        try:
            self.sb3File = findSb3()
            self.connectKeys()
        except:
            self.failLayout()
        else:
            self.successLayout()
            
    def connectKeys(self) -> None:
        '''connects to the windows registry keys for the Shopbot flags'''
        try:
            aKey = r'Software\VB and VBA Program Settings\Shopbot\UserData'
            aReg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            self.aKey = winreg.OpenKey(aReg, aKey)
            self.keyConnected = True
        except:
            self.keyConnected = False
            self.updateStatus('Failed to connect to Shopbot', True)

    def successLayout(self) -> None:
        '''layout if we found the sb3 files and windows registry keys'''
            
        self.layout = qtw.QVBoxLayout()
        
        self.createStatus(1200)

        self.loadButt = qtw.QPushButton('Load file(s)')
        self.loadButt.setIcon(QtGui.QIcon('icons/open.png'))
        self.loadButt.clicked.connect(self.loadFile)
        
        self.deleteButt = qtw.QPushButton('Remove file(s)')
        self.deleteButt.setIcon(QtGui.QIcon('icons/delete.png'))
        self.deleteButt.clicked.connect(self.removeFiles)
        
        self.loadDelete = qtw.QVBoxLayout()
        self.loadDelete.addWidget(self.loadButt)
        self.loadDelete.addWidget(self.deleteButt)

        self.sbpNameList = qtw.QListWidget()
        self.sbpNameList.setFixedHeight(100)
        self.addFile(self.sbpName)
        self.sbpNameList.itemDoubleClicked.connect(self.activate)
        self.sbpNameList.setAcceptDrops(True)
        self.sbpNameList.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
        self.sbpNameList.setDragDropMode(QtGui.QAbstractItemView.InternalMove)
        self.sbpNameList.setDragEnabled(True)
       
        
        self.fileButts = qtw.QHBoxLayout()
        self.fileButts.addItem(self.loadDelete)
        self.fileButts.addWidget(self.sbpNameList)
        self.fileButts.setSpacing(10)
        
        self.runButt = qtw.QPushButton('Go')
        self.runButt.clicked.connect(self.runFile)
        self.runButt.setEnabled(False)
        self.runButt.setStyleSheet("background-color: #a3d9ba; height:50px")
        
        self.abortButt = qtw.QPushButton('Stop')
        self.abortButt.clicked.connect(self.triggerEndOfPrint)
        self.abortButt.setEnabled(False)
        self.abortButt.setStyleSheet("background-color: #de8383; height:50px")
        
        self.buttLayout = qtw.QHBoxLayout()
        self.buttLayout.addWidget(self.runButt)
        self.buttLayout.addWidget(self.abortButt)
        self.buttLayout.setSpacing(50)
        
        self.layout.addWidget(self.status)
        self.layout.addItem(self.fileButts)
        self.layout.addItem(self.buttLayout)
 
        self.setLayout(self.layout)

    def sbpNumber(self) -> int:
        '''Determine the index of the current file. Return -1 if it's not in the list.'''
        for i in range(self.sbpNameList.count()):
            if self.sbpNameList.item(i).text()==self.sbpName:
                return i
        return -1
    
    
    def activate(self, item:Union[int, qtw.QListWidgetItem]) -> None:
        '''set the sbp file that the GUI will run next. Input can be item number or the actual item object.'''
        
        # get the actual item if given a number
        if type(item) is int:
            if item>=self.sbpNameList.count(): # this item is out of range
                logging.warning(f'Item out of range: requested {item} out of {self.sbpNameList.count()}')
            else:
                item = self.sbpNameList.item(item)
          
        # make sure this is a real file
        if not os.path.exists(item.text()):
            logging.warning(f'Cannot activate {item.text()}: file not found')
            return
        
        # remove other play icons
        for i in range(self.sbpNameList.count()):
            self.sbpNameList.item(i).setIcon(QtGui.QIcon())
            
        self.sbpName = item.text() # new run file name
        item.setIcon(QtGui.QIcon('icons/play.png')) # show that this item is next
        
            
    def activateNext(self) -> None:
        '''Activate the next file in the list'''
        if self.sbpNameList.count()==1:
            # there is only one file in the list, so we're done.
            return
        newNum = self.sbpNumber() + 1
        if newNum>=self.sbpNameList.count(): 
            # if we're at the end of the list, restart from the beginning
            newNum = 0
        self.activate(newNum)
    
    def addFile(self, fn) -> None:
        '''Add this file to the list of files, and remove the original placeholder if it's still there.'''
        item = qtw.QListWidgetItem(fn) # create an item
        self.sbpNameList.addItem(item) # add it to the list
        
        if self.sbpNameList.count()>1: # if there was already an item in the list
            item0 = self.sbpNameList.item(0) # take the first item
            if not os.path.exists(item0.text()): # if the original item isn't a real file
                self.activate(self.sbpNumber()+1) # activate the next item in the list
                self.sbpNameList.takeItem(0) # remove bad name from the list                
        return
    
    def removeFiles(self) -> None:
        '''Remove the selected file from the list'''
        for item in self.sbpNameList.selectedItems():
            logging.info(f'Removing file from queue: {item.text()}')
            if item.text()==self.sbpName:
                # we're removing the current file. go to the next file.
                self.activateNext()
            row = self.sbpNameList.row(item)
            self.sbpNameList.takeItem(row)
        if len(self.sbpNameList)==0:
            # if we've deleted all the files, go back to placeholder text
            self.sbpName = 'No file selected'
            self.addFile(self.sbpName)
        
        
    def loadFile(self) -> None:
        '''load a shopbot run file using a standard file selection dialog'''
        if os.path.exists(self.sbpName):
            openFolder = os.path.dirname(self.sbpName)
        else:
            openFolder = DEFAULTFOLDER
        sbpnList = fileDialog(openFolder, 'Gcode files (*.gcode *.sbp)', False)
        for sbpn in sbpnList:
            if not os.path.exists(sbpn):
                logging.error(f'{sbpn} does not exist')
            else:
                self.runButt.setEnabled(True)
                logging.debug(f'Adding file to queue: {sbpn}')
                self.addFile(sbpn)        
            
    ########
    # communicating with the shopbot
    
    
    def getSBFlag(self) -> int:
        '''run this function continuously during print to watch the shopbot status'''
        self.prevFlag = self.currentFlag
        try:
            sbFlag, _ = winreg.QueryValueEx(self.aKey, 'OutPutSwitches')
        except:  
            # if we fail to get the registry key, we have no way of knowing 
            # if the print is over, so just stop it now
            self.triggerEndOfPrint()
            self.updateStatus('Failed to connect to Shopbot keys', True)
            self.keyConnected = False
            
        # if the flag has reached a critical value that signals the 
        # shopbot is done printing, stop tracking pressures and recording vids
        sbFlag = int(sbFlag)
        self.currentFlag = sbFlag
        return sbFlag
            
            
    ####################            
    #### functions to start on run
    
    ### set up the run
    
    def getCritFlag(self) -> int:
        '''Identify which channels are triggered during the run. critFlag is a shopbot flag value that indicates that the run is done. We always set this to 0. If you want the video to shut off after the first flow is done, set this to 8. We run this function at the beginning of the run to determine what flag will trigger the start of videos, etc.'''
        self.channelsTriggered = []
        with open(self.sbpName, 'r') as f:
            for line in f:
                if line.startswith('SO') and (line.endswith('1') or line.endswith('1\n')):
                    '''the shopbot flags are 1-indexed, while our channels list is 0-indexed, 
                    so when it says to change flag 1, we want to change channels[0]'''
                    li = int(line.split(',')[1])-1
                    if li not in self.channelsTriggered and not li==3:
                        self.channelsTriggered.append(li) 
        return 0
    
    
    ### start/stop
    
    def runFile(self) -> None:
        '''runFile sends a file to the shopbot and tells the GUI to wait for next steps'''
        if not os.path.exists(self.sbpName):
            self.updateStatus('SBP file does not exist: ' + self.sbpName, True)
            return
        
        self.abortButt.setEnabled(True)
        
        ''' allowEnd is a failsafe measure because when the shopbot starts running a file that changes output flags, it asks the user to allow spindle movement to start. While it is waiting for the user to hit ok, only flag 4 would be up, giving a flag value of 8. If critFlag=8 (i.e. we want to stop running after the first extrusion step), this means the GUI will think the file is done before it even starts. We create an extra trigger to say that if we're extruding, we have to wait for extrusion to start before we can let the tracking stop'''
        self.critFlag = self.getCritFlag()
        if self.critFlag==0:
            self.allowEnd = True
        else:
            self.allowEnd = False
            
        self.updateStatus(f'Running SBP file {self.sbpName}, critFlag = {self.critFlag}', True)

        # send the file to the shopbot via command line
        appl = self.sb3File
        arg = self.sbpName + ', ,4, ,0,0,0"'
        subprocess.Popen([appl, arg])
        
        # wait to start videos and fluigent
        self.runningSBP = True
        self.triggerWait()
        
    
    ### wait to start videos and fluigent
    
    def triggerWait(self) -> None:
        '''start the timer that watches for the start of print'''
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.waitForStartTimerFunc)
        self.timer.start(100) # update every 100 ms
        
    
    def waitForStartTimerFunc(self) -> None:
        '''Loop this when we're waiting for the extrude command. If the run has been aborted, trigger the end.'''
        if self.runningSBP and self.keyConnected:
            self.waitForStart()
        else:
            self.triggerEndOfPrint()
            
    
    def waitForStart(self) -> None:
        '''Loop this while we're waiting for the extrude command. Checks the shopbot flags and triggers the watch for pressure triggers if the test has started'''
        sbFlag = self.getSBFlag()
        cf = 8 + 2**(self.channelsTriggered[0]) # the critical flag at which flow starts
        self.updateStatus(f'Waiting to start file, Shopbot output flag = {sbflag}, start at {cf}', False)
        if sbFlag==cf:
            self.triggerWatch()
            
            
    ### start videos and fluigent
    
    
    def triggerWatch(self) -> None:
        '''start recording and start the timer to watch for changes in pressure'''
        # eliminate the old timer
        self.timer.stop()
        
        # start the timer to watch for pressure triggers
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.timerFunc)
        self.timer.start(100) # update every 100 ms
        
        # start the cameras if any flow is triggered in the run
        if min(self.channelsTriggered)<len(self.sbWin.fluBox.pchannels):
            for camBox in self.sbWin.camBoxes:
                if camBox.camInclude.isChecked() and not camBox.camObj.recording:
                    camBox.cameraRec()
    
    ### wait for end
    
    def timerFunc(self) -> None:
        '''timerFunc runs continuously while we are printing to determine if we're done.'''

        if self.runningSBP and self.keyConnected:
            self.watchSBFlags()
        else:
            # we turn off runningSBP when the file is done
            self.triggerEndOfPrint()


    def watchSBFlags(self) -> None:
        '''Runs continuously while we're printing. Checks the Shopbot flags and changes the pressure if the flags have changed. Triggers the end if we hit the critical flag.'''
        sbFlag = self.getSBFlag()
        self.updateStatus(f'Running file, Shopbot output flag = {sbFlag}, end at {self.critFlag}', False)
        
        if self.allowEnd and (sbFlag==self.critFlag or sbFlag==0):
            self.triggerEndOfPrint()
            return
        
        # for each channel, check if the flag is up if flag 0 is up for channel 0, the output will be odd, so  flag mod 2 (2=2^(0+1)) will be 1, which is 2^0. If flag 1 is up for channel 1, it adds 2 to the output, e.g. if we want channel 1 on, the value will be 10, so 10%2=2, which is 2^1
        for i in self.channelsTriggered:
            if sbFlag%2**(i+1)==2**i:
                # this channel is on
                
                # now that we've started extrusion, we know that the run has really started, so we can allow it to end
                self.allowEnd = True
                
                # set this channel to the value in the constant box (run pressure)
                if i<len(self.sbWin.fluBox.pchannels):
                    channel = self.sbWin.fluBox.pchannels[i]
                    press = int(channel.constBox.text())
                    fgt.fgt_set_pressure(i, press)

                     # set the other channels to 0
                    self.sbWin.fluBox.resetAllChannels(i)   
                else:
                    if not sbFlag==self.prevFlag:
                        # if we triggered a flag that doesn't correspond to a pressure channel, take a snapshot with all checked cameras. Only do this once, right after the flag is flipped.
                        for camBox in self.sbWin.camBoxes:
                            if camBox.camInclude.isChecked() and not camBox.camObj.recording:
                                if camBox.camObj.recording:
                                    camBox.cameraRec()
                                camBox.cameraPic()
                                
                        # originally, I had this set to turn the flag back off, but I can't get around the permissions, so instead you'll just have to program a wait into the .sbp file, using "PAUSE 5" for 5 seconds, etc.
#                         newkey = sbFlag-4
#                         sbFlag, _ = winreg.SetValueEx(self.aKey, 'OutPutSwitches',0, winreg.REG_DWORD, newkey)

                return 
        
        # if no channels are turned on, turn off all of the channels       
        self.sbWin.fluBox.resetAllChannels(-1)

    
    ### end           
      
    def triggerEndOfPrint(self) -> None:
        '''stop watching for changes in pressure, stop recording  '''
        if self.runningSBP:
            for camBox in self.sbWin.camBoxes:
                if camBox.camInclude.checkState() and camBox.camObj.recording:
                    camBox.cameraRec()
            try:
                self.timer.stop()
            except:
                pass
            self.sbWin.fluBox.resetAllChannels(-1)
        self.runningSBP = False # we're no longer running a sbp file
        self.abortButt.setEnabled(False)
        self.updateStatus('Ready', False)
        self.activateNext() # activate the next sbp file in the list

    #-----------------------------------------
    
    
    def close(self):
        '''this gets triggered when the whole window is closed'''
        try:
            self.timer.stop()
        except:
            pass
        else:
            logging.info('Shopbot timer stopped')
            
#########################################################
#########################################################
######################## CAMERAS #######################
#########################################################
#########################################################


def mode2title(mode:int) -> str:
    '''convert a mode number to a camera title'''
    if mode==0:
        return 'Basler camera'
    elif mode==1:
        return 'Nozzle camera'
    elif mode==2:
        return 'Webcam 2'
    
#########################################################

class vrSignals(QtCore.QObject):
    '''Defines the signals available from a running worker thread
        Supported signals are:
        finished: No data
        error: a string message and a bool whether this is worth printing to the log
        result:`object` data returned from processing, anything
        progress: `int` indicating % progress '''
    
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str, bool)
    progress = QtCore.pyqtSignal(int)
    prevFrame = QtCore.pyqtSignal(np.ndarray)

    

#########################################################

class vidWriter(QtCore.QRunnable):
    '''The vidWriter creates a cv2.VideoWriter object at initialization, and it takes frames in the queue and writes them to file. This is a failsafe, so if the videowriter writes slower than the timer reads frames, then we can store those extra frames in memory until the vidWriter object can write them to the HD. 
QRunnables run in the background. Trying to directly modify the GUI display from inside the QRunnable will make everything catastrophically slow, but you can pass messages back to the GUI using vrSignals.'''
    
    def __init__(self, fn:str, vidvars, frames:List[np.ndarray], cam):
        super(vidWriter, self).__init__()        
        self.vFilename = fn
        self.vw = cv2.VideoWriter(fn, vidvars['fourcc'], vidvars['fps'], (vidvars['imw'], vidvars['imh']))
        self.signals = vrSignals()  
        self.frames = frames
        self.vidvars = vidvars
        self.recording = True
        self.cam = cam
    
    def run(self) -> None:
        '''this loops until we receive a frame that is a string
        the save function will pass STOP to the frame list when we are done recording'''
        while True:
            time.sleep(1) 
                # this gives the GUI enough time to start adding frames before we start saving, otherwise we get stuck in infinite loop where it's immediately checking again and again if there are frames
            while len(self.frames)>0:
                # remove the first frame once it's written
                frame = self.frames.pop(0)
                if type(frame)==str:
                    # if this frame is a string, the video reader is done, and it's sent us a signal to stop
                    # we use this explicit signal instead of just stopping when the frame list is empty, just in case the writer is faster than the reader and manages to empty the queue before we're done reading frames
                    self.vw.release()
                    self.signals.finished.emit()
                    return
                self.vw.write(frame) 
                if self.cam.diag>1:
                    # if we're in debug mode for this camera, log that we wrote a frame for this camera
                    logging.debug(self.cam.cameraName+'\twrite\t'+str(len(self.frames)))
                if len(self.frames) % 100==1:
                    # on every 100th frame, tell the GUI how many frames we still have to write
                    self.signals.progress.emit(len(self.frames))
        
                    
                    
###############################################


                    
class vidReader(QtCore.QRunnable):
    '''vidReader puts frame collection into the background, so frames from different cameras can be collected in parallel'''
    
    def __init__(self, cam, vrid:int, frames:List[np.ndarray], lastFrame:List[np.ndarray]):
        super(vidReader, self).__init__()
        self.cam = cam              # the camera object that called this reader
        self.lastFrame = lastFrame  # pointer to the list that holds the last frame
        self.signals = vrSignals()  # signals that let this send messages back to the GUI
        self.frames = frames        # pointer to the list that holds the frames that haven't been written yet
        self.vrid = vrid            # vidReader id. Helps prevent duplicate padding.
        
    def run(self) -> None:
        '''Run this function when this thread is started. Collect a frame, and pad the frame list if we dropped frames.'''
        
        # get an image
        try:
            frame = self.cam.readFrame()
        except Exception as e:
            frame = self.lastFrame[0]
            self.signals.error.emit(f'{self.cam.cameraName}: Error collecting frame: {e}', True)
            
        # update the preview
        if self.cam.previewing:
            # downsample preview frames
            if self.cam.framesSincePrev==self.cam.critFramesToPrev:
                if type(frame)==np.ndarray:
                    self.signals.prevFrame.emit(frame)
                    self.cam.framesSincePrev=0
                else:
                    self.signals.error.emit(f'{self.cam.cameraName}: Frame is empty', True)
            else:
                self.cam.framesSincePrev+=1
                
        # save the frame
        if self.cam.recording:
            # if we've skipped at least 2 frames, fill that space with duplicate frames
            # if we have two vidReaders going at once, only do this with the first one
            if len(self.cam.vridlist)==0 or self.vrid == min(self.cam.vridlist):
                self.timerCheckDrop() 
                
            self.saveFrame(frame) 
            
            # remove this vidreader id from the list of ids
            if self.vrid in self.cam.vridlist:
                self.cam.vridlist.remove(self.vrid)
        
        
    
    def saveFrame(self, frame:np.ndarray) -> None:
        '''save the frame to the video file. frames are in cv2 format. Called by run'''
        try:
            self.frames.append(frame)
        except:
            # stop recording if we can't write
            self.signals.error.emit(f'{self.cam.cameraName}: Error writing to video', True)
            
        else:
            # display the time recorded
            self.cam.timeRec = self.cam.timeRec+self.cam.mspf/1000
            self.cam.totalFrames+=1
            self.cam.updateRecordStatus()
 
          
    def timerCheckDrop(self) -> None:
        '''check to see if the timer has skipped steps and fills the missing frames with duplicates. Called by run '''
        dnow = datetime.datetime.now()
        if self.cam.startTime==0:
            self.cam.startTime = dnow
            if self.cam.diag>1:
                self.cam.lastTime = dnow
        else:
            timeElapsed = (dnow-self.cam.startTime).total_seconds()
            if (timeElapsed - self.cam.timeRec)>2*self.cam.mspf/1000:
                # if we've skipped at least 2 frames, fill that space with duplicate frames
                numfill = int(np.floor((timeElapsed-self.cam.timeRec)/(self.cam.mspf/1000)))
                for i in range(numfill):
                    if self.cam.diag>1:
                        logging.debug(self.cam.cameraName+'\t'+str(self.vrid)+ '\tPAD\t\t\t\t '+'%2.3f'%self.cam.timeRec)
                    self.cam.framesDropped+=1
                    self.saveFrame(self.lastFrame[0])
            if self.cam.diag>1:
                frameElapsed = ((dnow-self.cam.lastTime).total_seconds())*1000
                s = self.cam.cameraName+'\t'+str(self.vrid)+'\t'
                for si in ['%2.3f'%t for t in [len(self.frames), frameElapsed, self.cam.mspf, timeElapsed, self.cam.timeRec]]:
                    s = s+si+'\t'
                logging.debug(s)
                self.cam.lastTime = dnow
   
 ###########################
    # snapshots
    
class snapSignals(QtCore.QObject):
    '''signal class to send messages back to the GUI during snap collection'''
    
    result = QtCore.pyqtSignal(str, bool)
    error = QtCore.pyqtSignal(str, bool)

class camSnap(QtCore.QRunnable):
    '''collects snapshots in the background'''
    
    def __init__(self, cam, readNew:bool, lastFrame:List):
        super(camSnap, self).__init__()
        self.cam = cam                  # cam is the camera object 
        self.readNew = readNew          # readnew tells us if we need to read a new frame
        self.signals = snapSignals()
        self.lastFrame = lastFrame      # lastFrame is the last frame collected by the camera, as a list of one cv2 frame
        
    def run(self):
        '''Get a frame, export it, and return a status string to the GUI.'''
        
        if self.readNew:
            # if we're not currently previewing, we need to collect a new frame.
            try:
                frame = self.cam.readFrame()
                # frame needs to be in cv2 format
            except Exception as e:
                self.signals.error.emit(f'{self.cam.cameraName}: Error collecting frame: {e}', True)
                return
        else:
            # if we're not previewing, we can use the last frame
            frame = self.lastFrame[0]
        self.signals.result.emit(exportFrame(self.cam, frame), True)
        
            
def exportFrame(cam, frame:np.ndarray) -> str:
    '''Export a single frame to file as a png'''
    fullfn = cam.getFilename('.png')
    try:
        cv2.imwrite(fullfn, frame)
    except:
        return('Error saving frame')
    else:
        return('File saved to ' + fullfn) 
   

 #########################################################        

class camera:
    '''a camera object is a generic camera which stores functions and camera info for both pylon cameras and webcams
        these objects are created by cameraBox objects
        each type of camera (Basler and webcam) has its own readFrame and close functions'''
    
    def __init__(self, sbWin:qtw.QMainWindow, guiBox:connectBox):
        self.previewing = False
        self.sbWin = sbWin                        # sbWin is the parent window
        self.guiBox = guiBox                      # guiBox is the parent box for this camera
        self.cameraName = mode2title(guiBox.mode) # name of the camera (a string)
        self.vFilename = ''                       # name of the current video file
        self.timerRunning = False                 # is the timer that controls frame collection running?
        self.previewing = False                   # is the live preview on?
        self.recording = False                    # are we collecting frames for a video?
        self.writing = True                       # are we writing video frames to file?
        self.timer = None                         # the timer that controls frame collection
#         self.cam = None           # 
        self.resetVidStats()
        self.framesSincePrev = 0  # how many frames we've collected since we updated the live display
#         self.errorFrames = 0 
        self.diag = 1             # diag tells us which messages to log. 0 means none, 1 means some, 2 means a ton

        self.fourcc = cv2.VideoWriter_fourcc('M','J','P','G')
        self.prevWindow = qtw.QLabel()
    
    
    def closeCam(self) -> None:
        '''disconnect from the camera when the window is closed'''
        self.recording = False
        self.previewing = False
        if not self.timer==None:
            try:
                self.timer.stop()
            except:
                pass
            else:
                if self.diag>0:
                    logging.info(self.cameraName + ' timer stopped')
                
          
    def doneRecording(self) -> None:
        '''update the status box when we're done recording  '''
        self.writing = False
        self.updateRecordStatus()
    
    
    def getFilename(self, ext:str) -> str: 
        '''determine the file name for the file we're about to record. ext is the extension. Uses the timestamp for unique file names. The folder is determined by the saveFolder established in the top box of the GUI.'''
        
        # determine the folder to save to
        folder = self.sbWin.genBox.saveFolder
        if not os.path.exists(folder):
            # open a save dialog if the folder does not exist
            self.sbWin.genBox.setSaveFolder()
            folder = self.sbWin.saveFolderLabel.text()
        if not os.path.exists(folder):
            self.updateStatus('Invalid folder name. Image not saved.', True)
            return
        
        # determine if we should include the shopbot file name in the file
        if self.sbWin.sbBox.runningSBP:
            sbname = os.path.basename(self.sbWin.sbBox.sbpName)
            filename = os.path.splitext(sbname)[0]+'_'
        else:
            filename = ""
        filename = filename + self.cameraName
        t1 = self.sbWin.genBox.appendName.text()
        if len(t1)>0:
            filename = filename + '_'+t1
        filename = filename + '_'+time.strftime('%y%m%d_%H%M%S')+ext
        fullfn = os.path.join(folder, filename)
        return fullfn
    
    
    def resetVidStats(self) -> None:
        '''reset video stats, to start a new video'''
        self.startTime = 0      # the time when we started the video
        self.timeRec = 0        # how long the video is
        self.framesDropped = 0  # how many frames we've dropped
        self.totalFrames = 0    # how many frames are in the video
        self.fleft = 0          # how many frames we still need to write to file
        self.frames = []        # frame queue. appended to back, popped from front.
        self.lastFrame = []     # last frame collected. kept in a list of one cv2 frame to make it easier to pass between functions
        self.vridlist = []      # list of videoReader ids (list of ints). could be deprecated?
        
    
    def snap(self) -> None:
        '''take a single snapshot and save it. Put this process in the background through QThreadPool'''
        if self.previewing or self.recording:
            # if we're currently collecting frames, we can use the last frame
            last = True
        else:
            # if we're not currently collecting frames, we need to collect a new frame.
            last = False
        snapthread = camSnap(self, last, self.lastFrame)       # create an object to collect and save the snapshot in background
        snapthread.signals.result.connect(self.updateStatus)   # let the camSnap object send messages to the status bar
        snapthread.signals.error.connect(self.updateStatus)
        QtCore.QThreadPool.globalInstance().start(snapthread)  # get snapshot in background thread
            
            
    
    #---------------------------------
    
    def startPreview(self) -> None: 
        '''start live preview'''
        # critFramesToPrev reduces the live display frame rate, 
        # so only have to update the display at a comfortable viewing rate.
        # if the camera is at 200 fps, the video will be saved at full rate but
        # preview will only show at 15 fps
        self.critFramesToPrev = max(round(self.fps/15), 1)
        self.framesSincePrev = self.critFramesToPrev
        self.previewing = True
        self.startTimer()      # this only starts the timer if we're not already recording

    
    def stopPreview(self) -> None:
        '''stop live preview. This freezes the last frame on the screen.'''
        self.previewing = False
        self.stopTimer()       # this only stops the timer if we are neither recording nor previewing
 
    #---------------------------------
    
    def startRecording(self) -> None:
        '''start recording a video'''
        self.recording = True
        self.writing = True
        self.resetVidStats()                       # this resets the frame list, and other vars
        fn = self.getFilename('.avi')              # generate a new file name for this video
        self.vFilename = fn
        vidvars = {'fourcc':self.fourcc, 'fps':self.fps, 'imw':self.imw, 'imh':self.imh, 'cameraName':self.cameraName}
        self.frames = []                           # list of frames for this video. Frames are appended to back and popped from front.
        recthread = vidWriter(fn, vidvars, self.frames, self)         # creates a new thread to write frames to file      
        recthread.signals.finished.connect(self.doneRecording)        # connects vidWriter status updates to the status display
        recthread.signals.progress.connect(self.writingRecording)
        recthread.signals.error.connect(self.updateStatus)
        self.updateStatus(f'Recording {self.vFilename} ... ', True) 
        QtCore.QThreadPool.globalInstance().start(recthread)          # start writing in a background thread
        self.startTimer()                          # this only starts the timer if we're not already previewing
        if self.diag>1:
                                                   # if we're in super debug mode, print header for the table of frames
            logging.debug('Camera name\tID\t# frames\tFrame time (ms)\tms/frame\tTotal time (s)')
    
    
    def stopRecording(self) -> None:
        '''stop collecting frames for the video'''
        if not self.recording:
            return
        self.frames.append('STOP') # this tells the vidWriter that this is the end of the video
        self.recording = False     # this helps the frame reader and the status update know we're not reading frames
        self.stopTimer()           # only turns off the timer if we're not recording or previewing

    #---------------------------------
    # start the timer if there is not already a timer
    def startTimer(self) -> None:
        if not self.timerRunning:
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.timerFunc)        # run the timerFunc every mspf milliseconds
            self.timer.setTimerType(QtCore.Qt.PreciseTimer)   # may or may not improve timer accuracy, depending on computer
            self.timer.start(self.mspf)                       # start timer with frequency milliseconds per frame
            self.timerRunning = True
            if self.diag>1:
                logging.debug(self.cameraName + ': Starting timer')
        
#     def readError(self, errnum:int, errstr:str) -> None:
#         self.updateStatus(errstr, True)
#         if errnum==1:
#             self.recording = False  
    
    
    def stopTimer(self) -> None:
        '''this only stops the timer if we are neither recording nor previewing'''
        if not self.recording and not self.previewing:
            self.timer.stop()
            self.timerRunning = False
            if self.diag>0:
                logging.info(self.cameraName + ': Stopping timer')
    
    def timerFunc(self) -> None:
        '''Run this continuously when we are recording or previewing. Generates a vidReader object for each frame, letting us collect frames in the background. 
        vidReader ids (vrid) were implemented as a possible fix for a frame jumbling error. In the rare case where there are two vidReaders running at the same time and we have dropped frames to pad, it only lets one of the vidReaders generate the padded frames. It is possible that the vrids are not necessary, but I have not tried removing them. 
        We generate a new vidReader for each frame instead of having one continuously running vidReader because there may be a case where the camera can generate frames faster than the computer can read them. If we have a separate thread for each frame, we can have the computer receive multiple frames at once. This is a bit of a simplification because of the way memory is managed, but the multi-thread process lowers the number of dropped frames, compared to a single vidReader thread.'''
        if len(self.vridlist)==0:
            vrid = 1
        else:
            vrid = max(self.vridlist)+1
        self.vridlist.append(vrid)
        runnable = vidReader(self, vrid, self.frames, self.lastFrame)  
        runnable.signals.prevFrame.connect(self.updatePrevFrame)      # let the vidReader send back frames to display
        runnable.signals.error.connect(self.updateStatus)           # let the vidReader send back error statuses to display
        QtCore.QThreadPool.globalInstance().start(runnable)
    
    #---------------------------------
    
    def updatePrevFrame(self, frame:np.ndarray) -> None:
        '''update the live preview window'''
        try:
            # we need to convert the frame from the OpenCV cv2 format to the Qt QPixmap format
            if self.convertColors:
                frame2 = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame2 = frame
            image = QtGui.QImage(frame2, frame2.shape[1], frame2.shape[0], QtGui.QImage.Format_RGB888)
            pixmap = QtGui.QPixmap.fromImage(image)
            self.prevWindow.setPixmap(pixmap)
        except Exception as e:
            # stop previewing if we can't preview
            self.updateStatus('Error displaying frame', True)
            self.previewing = False
            self.stopTimer()

    
    def updateStatus(self, st:str, log:bool) -> None:
        '''updates the status of the widget that this camera belongs to. 
        st is the status message. 
        log determines whether to write to log. '''
        self.guiBox.updateStatus(st, log)
    
    
    def updateRecordStatus(self) -> None:
        '''updates the status bar during recording and during save. 
        We turn off logging because this updates so frequently that we would flood the log with updates.'''
        log = False
        if self.recording:
            s = 'Recording '
        elif self.writing:
            s = 'Writing '
        else:
            s = 'Recorded '
            log = True
        s+=self.vFilename
        s+= ' : %2.2f s' % self.timeRec + ', '
        if self.writing and not self.recording:
            s+= str(self.fleft) + '/' + str(self.totalFrames) + ' frames left'
        else:
            s+= str(self.framesDropped) + '/' + str(self.totalFrames) +' frames dropped'
        self.updateStatus(s, log)
        
    
    def writingRecording(self, fleft:int) -> None:  
        '''this function updates the status to say that the video is still being saved. 
        fleft is the number of frames left to record'''
        if not self.recording:
            self.fleft = fleft
            self.updateRecordStatus()
        
        
##################


class webcam(camera):
    '''webcams are objects that hold functions for conventional webcams that openCV (cv2) can communicate with'''
    
    def __init__(self, sbWin:qtw.QMainWindow, guiBox:connectBox):
        super(webcam, self).__init__(sbWin, guiBox)

        # connect to webcam through OpenCV
        try:
            self.camDevice = cv2.VideoCapture(guiBox.mode-1)
            self.readFrame()
        except:
            self.connected = False
            return
        else:
            self.connected = True
        
        # get image stats
        self.fps = self.camDevice.get(cv2.CAP_PROP_FPS)/2   # frames per second
        self.mspf = int(round(1000./self.fps))              # ms per frame
        self.imw = int(self.camDevice.get(3))               # image width (px)
        self.imh = int(self.camDevice.get(4))               # image height (px)
        
        self.convertColors = True
        
    #-----------------------------------------
        
     
    def readFrame(self):
        '''get a frame from the webcam using cv2 '''
        try:
            rval, frame = self.camDevice.read()
        except:
            self.updateStatus('Error reading frame', True)
            raise Exception
        if not rval:
            raise Exception
        else:
            # if we successfully read the frame, keep it in lastFrame
            self.lastFrame = [frame]
            return frame
 
    #-----------------------------------------
    
    
    def close(self) -> None:
        '''this gets triggered when the whole window is closed. Disconnects from the cameras'''
        
        self.closeCam()
        if not self.camDevice==None:
            try:
                self.camDevice.release()
            except:
                pass
            else:
                if self.diag>0:
                    logging.info(self.cameraName + ' closed')
    

#########################################      
      

class bascam(camera):
    '''bascams are Basler cameras that require the pypylon SDK to communicate'''
    
    def __init__(self, sbWin:qtw.QMainWindow, guiBox:connectBox):
        super(bascam, self).__init__(sbWin, guiBox)
        self.vFilename = ''
        self.connected = False
        self.convertColors = True
        
        # connect to the camera
        try:
            self.tlf = pylon.TlFactory.GetInstance()
            self.camDevice = pylon.InstantCamera(self.tlf.CreateFirstDevice())
        except Exception as e:
            if self.diag>0:
                logging.error(e)
            self.guiBox.updateStatus(e, False)
            self.connected = False
            return
        
        # open camera
        try:
            self.camDevice.Open()
            
            self.camDevice.StartGrabbing(pylon.GrabStrategy_OneByOne)
            #self.camDevice.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            #self.camDevice.Gain.SetValue(12)
            #self.camDevice.AutoTargetValue.SetValue(128)  ## this doesn't work
    
            self.connected = True
            # update the GUI display to show camera model
            self.guiBox.model = self.camDevice.GetDeviceInfo().GetModelName()
            self.guiBox.updateBoxTitle()
            
            # converter converts pylon images into cv2 images
            self.converter = pylon.ImageFormatConverter()
            self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
            self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
            
            # get camera stats
            self.fps = self.camDevice.ResultingFrameRate.GetValue() # frames per s
            self.mspf = int(round(1000./self.fps))  # ms per frame
            f1 = self.readFrame()
            self.imw = len(f1[0]) # image width (px)
            self.imh = len(f1) # image height (px)
            
            # if we successfully read the frame, keep it in lastFrame
            self.lastFrame = [f1]

        # if we failed to connect to the camera, close it, and display a failure state on the GUI
        except Exception as e:
            try:
                self.camDevice.Close() # close camera if we've already opened it
            except:
                pass
            if self.diag>0:
                logging.error(e)
            self.guiBox.updateStatus(e, False)
            self.connected = False
            return   
        
    #-----------------------------------------
        
    
    def readFrame(self):
        '''get a frame from the Basler camera using pypylong'''
        
        try:            
            grabResult = self.camDevice.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        except Exception as e:
            return self.grabError('Error collecting grab')
        if not grabResult.GrabSucceeded():
            return self.grabError('Error: Grab failed')
        try:
            # converts to cv2 format
            image = self.converter.Convert(grabResult)
            img = image.GetArray() 
        except:
            return self.grabError('Error: image conversion failed')
        try:               
            grabResult.Release()
        except:
            pass
        if type(img)==np.ndarray:
            # if we successfully read the frame, keep it in lastFrame
            self.lastFrame = [img]
            return img  
        else:
            return self.grabError('Error: Frame is not array')
    
    
    def grabError(self, status:str) -> None:
        '''update the status box when there's an error grabbing the frame'''
        raise Exception(status)
    
    
    #-----------------------------------------
    
    def close(self) -> None:
        '''this gets triggered when the whole window is closed'''
        self.closeCam()
        try:
            self.camDevice.StopGrabbing()
            self.camDevice.Close()
        except:
            pass
        else:
            if self.diag>0:
                logging.info('Basler camera closed')
            
################################################
        
class settingsDialog(QtGui.QDialog):
    '''This opens a window that holds settings about logging for cameras.'''
    
    
    def __init__(self, parent:connectBox, bTitle:str, camObj:camera):
        '''parent is the connectBox that this settings dialog belongs to. 
            bTitle is the box title, e.g. webcam 2. 
            camObj is the camera object that holds functions and info for a specific camera.'''
        
        super().__init__(parent)  
        self.camObj = camObj
        self.layout = qtw.QVBoxLayout()
        
        self.diagRow = qtw.QHBoxLayout()
        self.diagLabel = qtw.QLabel('Log')
        self.diag1 = qtw.QRadioButton('None')
        self.diag2 = qtw.QRadioButton('Just critical')
        self.diag2.setChecked(True)
        self.diag3 = qtw.QRadioButton('All frames')
        self.diaggroup = qtw.QButtonGroup()
        self.diaggroup.addButton(self.diag1, 0)
        self.diaggroup.addButton(self.diag2, 1)
        self.diaggroup.addButton(self.diag3, 2)
        self.diaggroup.buttonClicked.connect(self.changeDiag)
        self.diagRow.addWidget(self.diagLabel)
        self.diagRow.addWidget(self.diag1)
        self.diagRow.addWidget(self.diag2)
        self.diagRow.addWidget(self.diag3)
        self.layout.addLayout(self.diagRow)
        
#         self.reset = qtw.QPushButton('Reset camera')
#         self.reset.clicked.connect(parent.connect)
#         self.layout.addWidget(self.reset)
    
        self.setLayout(self.layout)
        self.setWindowTitle(bTitle + " settings")
        
    def changeDiag(self, diagbutton):
        '''Change the diagnostics status on the camera, so we print out the messages we want.'''
        self.camObj.diag = self.diaggroup.id(diagbutton)      



class cameraBox(connectBox):
    '''widget that holds camera objects and displays buttons and preview frames'''
    
    def __init__(self, mode:int, sbWin:qtw.QMainWindow):
        '''Mode is the type of camera. 0 is a basler camera, 1 is the nozzle camera, and 2 is webcam 2.
        sbWin is the parent window that this box sits inside of.'''
        super(cameraBox, self).__init__()
        self.mode = mode # 
        self.model = ''   # name of camera
        self.connected = False
        self.previewing = False
        self.recording = False
        self.imw=0
        self.imh=0
        self.img = []
        self.bTitle = mode2title(mode)
        self.sbWin = sbWin
        self.connect() # try to connect to the camera
        self.updateBoxTitle()
        if self.connected:
            if self.camObj.diag>0:
                logging.info(self.bTitle, ' ', self.camObj.fps, ' fps')

    
    def connect(self) -> None:
        '''try to connect to the camera'''
        sbWin = self.sbWin
        self.connectingLayout() # inherited from connectBox
        self.connectAttempts+=1
        
        # if we've already defined a camera object, delete it
        try:
            self.camObj.close()
            self.resetLayout()
        except:
            pass
        
        # define a new camera object
        if self.mode==0:
            self.camObj = bascam(sbWin, self)
        else:
            self.camObj = webcam(sbWin, self)
        if self.camObj.connected:
            self.successLayout()
        else:
            self.failLayout() # inherited from connectBox
            
    
    def successLayout(self) -> None:
        '''this is the layout if we successfully connected to the camera'''
        
        self.resetLayout()
        self.layout = qtw.QVBoxLayout()

        self.camInclude = qtw.QToolButton()        
        self.camInclude.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.camInclude.setCheckable(True)
        self.camInclude.clicked.connect(self.updateCamInclude)
        self.updateCamInclude() 
        
        self.camPrev = qtw.QToolButton()
        self.camPrev.clicked.connect(self.cameraPrev)
#         self.camPrev.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.camPrev.setCheckable(True)
        self.setPrevButtStart()
        
        self.camRec = qtw.QToolButton()
        self.camRec.clicked.connect(self.cameraRec)
        self.camRec.setCheckable(True)
        self.setRecButtStart()
        
        self.camPic = qtw.QToolButton()
        self.camPic.setIcon(QtGui.QIcon('icons/camera.png'))
        self.camPic.setStyleSheet(self.unclickedSheet())
        self.camPic.clicked.connect(self.cameraPic)
        self.camPic.setToolTip('Snapshot') 
        
        self.settings = qtw.QToolButton()
        self.settings.setIcon(QtGui.QIcon('icons/settings.png'))
        self.settings.setStyleSheet(self.unclickedSheet())
        self.settings.clicked.connect(self.openSettings)
        self.settings.setToolTip(self.bTitle+' settings') 
        
        self.settingsDialog = settingsDialog(self, self.bTitle, self.camObj)
                
        self.camButts = qtw.QToolBar()
        self.camButts.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.camButts.addWidget(self.camInclude)
        self.camButts.addWidget(self.camPrev)
        self.camButts.addWidget(self.camRec)
        self.camButts.addWidget(self.camPic)
        self.camButts.addWidget(self.settings)
        self.camButts.setStyleSheet("QToolBar{spacing:5px;}");
        
        self.layout.addWidget(self.camButts)
        
        self.status = qtw.QLabel('Ready')
        self.status.setFixedSize(500, 50)
        self.status.setWordWrap(True)
        self.layout.addWidget(self.status)
        
        self.layout.addStretch(1)
        
        self.layout.addWidget(self.camObj.prevWindow)
        self.setLayout(self.layout)
        
        
    #------------------------------------------------
    # functions to trigger camera actions and update the GUI
    
    def cameraPic(self) -> None:
        '''capture a single frame'''
        self.camObj.snap()
       
    
    def cameraPrev(self) -> None:
        '''start or stop previewing and update button appearance'''
        if self.previewing:
            # we're already previewing: stop the preview and update the button appearance
            self.camObj.stopPreview()
            self.setPrevButtStart()
        else:
            # we're not previewing: start the preview and update button appearance
            self.camObj.startPreview()
            self.setPrevButtStop()
        self.previewing = not self.previewing
        
        # update toggle status if this change was made internally, not by the user clicking the button
        if self.camPrev.isChecked() and (not self.previewing):
            self.camPrev.toggle()
        elif (not self.camPrev.isChecked()) and self.previewing:
            self.camPrev.toggle()
        
    
    def cameraRec(self) -> None:
        '''start or stop recording and update button appearance'''
        if self.recording:
            self.setRecButtStart()
            self.camObj.stopRecording()
        else:
            self.setRecButtStop()
            self.camObj.startRecording()
        self.recording = not self.recording
        
        # update toggle status if this change was made internally, not by the user clicking the button
        if self.camRec.isChecked() and (not self.recording):
            self.camRec.toggle()
        elif (not self.camRec.isChecked()) and self.recording:
            self.camRec.toggle()
        
    #------------------------------------------------
    #  functions to change appearance of buttons when they're pressed
    
    def clickedBoth(self) -> str:
        '''appearance of all of the camera box buttons'''
        
        return 'border:none; \
        padding:3px; \
        border-radius:3px; \
        box-shadow: 2px 2px 2px #888888;'
    
    def clickedSheet(self) -> str:
        '''Stylesheet for clicked camera buttons'''
        
        return self.clickedBoth()+' background-color:#666666; color:white;'
    
    def unclickedSheet(self) -> str:
        '''Stylesheet for unclicked camera buttons'''
        
        return self.clickedBoth()+' background-color:#eeeeee;'
        
    
    def updateCamInclude(self) -> None:
        '''Update the camInclude button appearance to reflect status'''
        if self.camInclude.isChecked():
            self.camInclude.setStyleSheet(self.clickedSheet())
            self.camInclude.setText('Autosave is on')
            self.camInclude.setIcon(QtGui.QIcon('icons/save.png'))
            self.camInclude.setToolTip('Do not export videos with shopbot')
        else:
            self.camInclude.setStyleSheet(self.unclickedSheet())
            self.camInclude.setText('Autosave is off')
            self.camInclude.setIcon(QtGui.QIcon('icons/nosave.png'))
            self.camInclude.setToolTip('Export videos with shopbot')
        
    def setPrevButtStart(self) -> None:
        '''Update preview button appearance to not previewing status'''
        self.camPrev.setStyleSheet(self.unclickedSheet())
#         self.camPrev.setText('Start preview')
        self.camPrev.setIcon(QtGui.QIcon('icons/closedeye.png'))
        self.camPrev.setToolTip('Start live preview') 
        
    def setPrevButtStop(self) -> None:
        '''Update preview button appearance to previewing status'''
        self.camPrev.setStyleSheet(self.clickedSheet())
#         self.camPrev.setText('Stop preview')
        self.camPrev.setIcon(QtGui.QIcon('icons/eye.png'))
        self.camPrev.setToolTip('Stop live preview') 

    def setRecButtStart(self) -> None:
        '''Update record button appearance to not recording status'''
        self.camRec.setStyleSheet(self.unclickedSheet())
        self.camRec.setIcon(QtGui.QIcon('icons/Record.png'))
        self.camRec.setToolTip('Start recording') 
        
    def setRecButtStop(self) -> None:
        '''Update record button appearance to recording status'''
        self.camRec.setStyleSheet(self.clickedSheet())
        self.camRec.setIcon(QtGui.QIcon('icons/recordstop.png'))
        self.camRec.setToolTip('Stop recording') 
        
    def openSettings(self) -> None:
        '''Open the camera settings dialog window'''
        self.settingsDialog.show()
        self.settingsDialog.raise_()

    #------------------------------------------------
    
    
    def updateBoxTitle(self) -> None:
        '''updates the title of widget box'''
        self.setTitle(f'{self.bTitle}\t{self.model}')
    

    def close(self) -> None:
        '''gets triggered when the window is closed. Disconnects GUI from camera.'''
        self.camObj.close()

########################################################
################# FLUIGENT #############################
   


class fluChannel:
    '''this class describes a single channel on the Fluigent
        fgt functions come from the Fluigent SDK
        each channel gets a QLayout that can be incorporated into the fluBox widget'''
    
    def __init__(self, chanNum: int, color: str, fluBox:connectBox):
        '''chanNum is a 0-indexed channel number (e.g. 0)
        color is a string (e.g. #FFFFFF)
        fluBox is the parent box that holds the Fluigent GUI display'''
        self.chanNum = chanNum
        self.fluBox = fluBox
        
        # setBox is a one line input box
        self.setBox = qtw.QLineEdit()
        self.setBox.setText('0')
        self.setBox.returnPressed.connect(self.setPressure)
        objValidator = QtGui.QIntValidator()
        objValidator.setRange(0, 7000)
        self.setBox.setValidator(objValidator)

        # label is a text label that tells us what channel this box edits. For the display, channels are 1-indexed.
        self.label = qtw.QLabel('Channel '+str(chanNum+1)+' (mBar)')
        self.label.setBuddy(self.setBox)
        
        self.readBox = qtw.QLabel('0')
        self.readLabel = qtw.QLabel('Actual pressure (mBar)')
        self.readLabel.setBuddy(self.readBox)
        
        # constBox is a one line input box that is the 
        # "on" pressure for running files for this channel
        self.constBox = qtw.QLineEdit()
        self.constBox.setText('0')
        self.constBox.setValidator(objValidator)
        
        self.constLabel = qtw.QLabel('Run pressure (mBar)')
        self.constLabel.setBuddy(self.constBox)
        
        self.constTimeBox = qtw.QLineEdit()
        self.constTimeBox.setText('0')
        self.constTimeBox.setValidator(objValidator)
        self.constTimeButton = qtw.QPushButton('Turn on for _ s:')
        self.constTimeButton.clicked.connect(self.runConstTime)
        
        
        for o in [self.label, self.readLabel, self.constLabel]:
            o.setStyleSheet('color: '+color+';')  
            # this makes the label our input color
        
        # line up the label and input box horizontally
        self.layout = qtw.QGridLayout()
        self.layout.addWidget(self.label, 0, 0)
        self.layout.addWidget(self.setBox, 0, 1)
        self.layout.addWidget(self.readLabel, 1, 0)
        self.layout.addWidget(self.readBox, 1, 1)
        self.layout.addWidget(self.constLabel, 2, 0)
        self.layout.addWidget(self.constBox, 2, 1)
        self.layout.addWidget(self.constTimeButton, 3, 0)
        self.layout.addWidget(self.constTimeBox, 3, 1)
        
        # 10 px between the label and input box
        self.layout.setSpacing(10)
    
    
    def setPressure(self) -> None:
        '''set the pressure for this channel to the pressure in the setBox'''
        fgt.fgt_set_pressure(self.chanNum, int(self.setBox.text()))
    
    
    def runConstTime(self) -> None:
        '''turn on pressure to the setBox value for a constTimeBox amount of time'''
        runtime = int(self.constTimeBox.text())
        if runtime<0:
            return
        runpressure = int(self.constBox.text())
        self.fluBox.updateStatus(f'Setting channel {self.chanNum} to {runpressure} mbar for {runtime} s', True)
        fgt.fgt_set_pressure(self.chanNum, runpressure)
        QtCore.QTimer.singleShot(runtime*1000, self.zeroChannel) 
            # QTimer wants time in milliseconds
    
    
    def zeroChannel(self) -> None:
        '''zero the channel pressure'''
        self.fluBox.updateStatus('Setting channel {self.chanNum} to 0 mbar', True)
        fgt.fgt_set_pressure(self.chanNum, 0)

        
##############################  

class fluSignals(QtCore.QObject):
    '''Signals connector that lets us send status updates back to the GUI from the fluPlot object'''
    
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str, bool)
    progress = QtCore.pyqtSignal()
    

#########################################################

class plotWatch:
    '''Holds the pressure/time list for all channels'''

    def __init__(self, numChans):
        self.stop = False          # tells us to stop reading pressures
        self.numChans = numChans   # number of channels
        self.initializePList()
        
            
    def initializePList(self) -> None:
        '''initialize the pressure list and time list'''
        # initialize the time range
        self.dt = 200 # ms
        self.time = list(np.arange(-60*1, 0, self.dt/1000)) 
               
        # initialize pressures. assume 0 before we initialized the gui    
        self.pressures = []
        
        for i in range(self.numChans):
            press = [0 for _ in range(len(self.time))]
            self.pressures.append(press)


def checkPressure(channel:int) -> int:
    '''reads the pressure of a given channel, 0-indexed'''
    pressure = int(fgt.fgt_get_pressure(channel))
    return pressure
            
class plotRunnable(QtCore.QRunnable):
    '''plotRunnable updates the list of times and pressures and allows us to read pressures continuously in a background thread.'''
    
    def __init__(self, pw):
        super(plotRunnable, self).__init__()   
        self.pw = pw                  # plotWatch object (stores pressure list)
        self.numChans = pw.numChans   # number of channels
        self.signals = fluSignals()   # lets us send messages and data back to the GUI
        self.dprev = datetime.datetime.now()  # the last time when we read the pressures

    
    def run(self) -> None:
        '''update the plot and displayed pressure'''
        while not self.pw.stop:
            try:
                newtime = self.pw.time
                newpressures = self.pw.pressures        
                newtime = newtime[1:]                   # Remove the first y element.
                dnow = datetime.datetime.now()          # Finds current time relative to when the plot was created
                dt = (dnow-self.dprev).total_seconds()
                self.dprev = dnow
                newtime.append(newtime[-1] + dt)         # Add the current time to the list
                for i in range(self.numChans):
                    newpressures[i] = newpressures[i][1:]
                    pnew = checkPressure(i)
                    newpressures[i].append(pnew)         # Add the current pressure to the list, for each channel
            except Exception as e:
                self.signals.error.emit(f'Error reading pressure', True)
            else:
                self.pw.time = newtime                   # Save lists to plotWatch object
                self.pw.pressures = newpressures   
                self.signals.progress.emit()             # Tell the GUI to update plot
            time.sleep(200/1000)                         # Update every 200 ms

            
class fluPlot:
    '''produces a plot that can be displayed in fluBox'''
    
    def __init__(self, pcolors:List[str], fb:connectBox):
        '''pcolors is a list of colors, e.g. ['#FFFFFF', '#000000']
        fb is a pointer to the fluigent box that contains this plot'''
        self.fluBox = fb # parent box
        self.numChans = self.fluBox.numChans
        
        
        # create the plot
        self.graphWidget = pg.PlotWidget() 
        self.graphWidget.setYRange(-10, 7100, padding=0) 
            # set the range from 0 to 7000 mbar
        self.graphWidget.setBackground('w')         
        self.pcolors = pcolors
        
        self.pw = plotWatch(self.numChans)

        self.datalines = []
        for i in range(self.numChans):
            press = self.pw.pressures[i]
            pen = pg.mkPen(color=pcolors[i], width=2)
            cname = 'Channel '+str(i+1)
            dl = self.graphWidget.plot(self.pw.time, press, pen=pen, name=cname)
            self.datalines.append(dl)
        
        self.graphWidget.setLabel('left', 'Pressure (mBar)')
        self.graphWidget.setLabel('bottom', 'Time (s)')

        # create a thread to update the pressure list
        plotThread = plotRunnable(self.pw)
        plotThread.signals.progress.connect(self.update)
        QtCore.QThreadPool.globalInstance().start(plotThread)   

    
    def update(self) -> None:
        '''read the pressure and update the plot display'''
        try:
            for i in range(self.numChans):
                self.datalines[i].setData(self.pw.time, self.pw.pressures[i])
                # update the pressure reading
                self.fluBox.updateReading(i, str(self.pw.pressures[i][-1])) 
        except:
            pass
    
    #-----------------------------------------
    
    
    def close(self) -> None:
        '''gets triggered when the window is closed. It stops the pressure readings.'''
        try: 
            self.pw.stop = True
        except:
            pass
        else:
            logging.info('Fluigent timer deleted')
    
    
############################## 



class fluBox(connectBox):
    '''The GUI box that holds info about the Fluigent pressure controller.'''
    
    
    def __init__(self, sbWin:qtw.QMainWindow):
        '''sbWin is a pointer to the parent window'''
        
        super(fluBox, self).__init__()
        
        # this box is a QGroupBox. we are going to create a layout to put in the box
        self.bTitle = 'Fluigent'    # box title
        self.setTitle(self.bTitle)
        self.sbWin = sbWin        
        self.pchannels = []         # list of pressure channels as fluChannel objects
        self.connected = False      # connected to the fluigent
        self.connect() 
        
    
    
    def connect(self) -> None: 
        '''try to connect to the Fluigent'''
        
        self.connectAttempts+=1
        self.connectingLayout()  # temporarily put up a layout saying we're connected
        
        fgt.fgt_init()           # initialize fluigent
        self.numChans = fgt.fgt_get_pressureChannelCount()  # how many Fluigent channels do we have
        
        if self.numChans>0:
            self.connected = True
            self.successLayout()
        else:
            self.failLayout()

    
    
    def successLayout(self) -> None:
        '''display if we successfully connected to the fluigent'''
        
        self.resetLayout()                  # erase the old layout
        self.layout = qtw.QVBoxLayout()     # whole fluigent layout
        
        self.createStatus(600)              # 600 px wide status bar
        self.layout.addWidget(self.status)
        
        self.fluButts = qtw.QHBoxLayout()   # fluigent button row
        
        self.pcolors = ['#3f8dd1', '#b0401e', '#3e8a5b', '#b8a665'][0:self.numChans]  # preset channel colors
        
        self.pchannels = []                 # pchannels is a list of fluChannel objects
        for i in range(self.numChans):
            pc = fluChannel(i, self.pcolors[i], self)
            self.pchannels.append(pc)
            self.fluButts.addItem(pc.layout) # add a set of buttons to the layout for each channel

        self.fluButts.setSpacing(40)         # 40px between channel buttons
        self.layout.addItem(self.fluButts)   # put the buttons in the layout
    
        self.fluPlot = fluPlot(self.pcolors, self)      # create plot
        self.layout.addWidget(self.fluPlot.graphWidget) # add plot to the layout
        
        self.setLayout(self.layout)          # put the whole layout in the box  
        
    #-----------------------------------------
    
    
#     def readPressures(self) -> List[int]:
#         '''reads the pressure of all channels'''
#         plist = []
#         for i in range(self.numChans):
#             plist.append(checkPressure(i))
#         return plist
    
    
    def resetAllChannels(self, exclude:int) -> None:
        '''Set all of the channels to 0 except for exclude (0-indexed). exclude is a channel that we want to keep on. Input -1 to turn everything off'''
        for i in range(self.numChans):
            if not i==exclude:
                fgt.fgt_set_pressure(i,0)
                
    
    def updateReading(self, channum:int, preading:int) -> None:
        '''updates the status box that tells us what pressure this channel is at'''
        self.pchannels[channum].readBox.setText(preading)
        
        
    #-----------------------------------------
    
    
    def close(self) -> None:
        '''this runs when the window is closed'''
        # close the fluigent
        if self.connected:      
            try:
                self.resetAllChannels(-1)
                fgt.fgt_close() 
            except:
                pass
            else:
                logging.info('Fluigent closed')  
            # stop the timer used to create the fluigent plot
            self.fluPlot.close()
            
            
##################################################          
########### logging window


class QPlainTextEditLogger(logging.Handler):
    '''This creates a text box that the log messages go to. Goes inside a logDialog window'''
    
    def __init__(self, parent):
        super().__init__()
        self.widget = QtGui.QPlainTextEdit(parent)
        self.widget.setReadOnly(True)    

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)    


class logDialog(QtGui.QDialog):
    '''Creates a window that displays log messages.'''
    
    def __init__(self, parent):
        super().__init__(parent)  

        logTextBox = QPlainTextEditLogger(self)
        logTextBox.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')) # format what is printed to text box
        logging.getLogger().addHandler(logTextBox)  # display log messages in text box
        logging.getLogger().setLevel(logging.DEBUG) # Set logging level to everything.

        layout = QtGui.QVBoxLayout()
        layout.addWidget(logTextBox.widget)         # Add the new logging box widget to the layout
        self.setLayout(layout) 
        
        self.setWindowTitle("Shopbot/Fluigent/Camera log")
        self.resize(900, 400)                       # window is 900 px x 400 px

        
####################### the whole window

class SBwindow(qtw.QMainWindow):
    '''The whole GUI window'''
    
    def __init__(self, parent=None):
        super(SBwindow, self).__init__(parent)
        
        # initialize all boxes to empty value so if we hit an error during setup and need to disconnect, we aren't trying to call empty variables
        
        self.genBox = None
        self.sbBox = None
        self.basBox = None
        self.nozBox = None
        self.web2Box = None
        self.fluBox = None
        self.logDialog = None
        
        try:
            self.central_widget = qtw.QWidget()               
            self.setCentralWidget(self.central_widget)      # create a central widget that everything else goes inside

            self.setWindowTitle("Shopbot/Fluigent/Camera")
            self.setStyleSheet('background-color:white;')
            self.resize(1600, 1800)                         # window size


            self.createGrid()                               # create boxes to go in main window
            self.createMenu()                               # create menu bar to go at top of window

            logging.info('Window created')
        except:
            self.closeEvent(0)                              # if we fail to initialize the GUI, disconnect from everything we connected

        
    def createGrid(self):
        '''Create boxes that go inside of window'''
        self.genBox = genBox(self)           # general file ops
        self.sbBox = sbBox(self)             # shopbot box
        self.basBox = cameraBox(0, self)     # basler camera box
        self.nozBox = cameraBox(1, self)     # nozzle webcam box
        self.web2Box = cameraBox(2, self)     # webcam 2 box
        self.camBoxes = [self.basBox, self.nozBox, self.web2Box]
        self.fluBox = fluBox(self)           # fluigent box
              
        self.fullLayout = qtw.QGridLayout()
        self.fullLayout.addWidget(self.genBox, 0, 0, 1, 2)  # row 0, col 0, 1 row deep, 2 cols wide
        self.fullLayout.addWidget(self.sbBox, 1, 0, 1, 2)   # row 1, col 0, 1 row deep, 2 cols wide
        self.fullLayout.addWidget(self.basBox, 2, 0)
        self.fullLayout.addWidget(self.nozBox, 2, 1)
        self.fullLayout.addWidget(self.fluBox, 3, 0)
        self.fullLayout.addWidget(self.web2Box, 3, 1)
        
        # make the camera rows big so the whole window doesn't resize dramatically when we turn on previews
        self.fullLayout.setRowStretch(0, 1)
        self.fullLayout.setRowStretch(1, 2)
        self.fullLayout.setRowStretch(2, 6)     
        self.fullLayout.setRowStretch(3, 6)
        self.fullLayout.setColumnStretch(0, 1)
        self.fullLayout.setColumnStretch(1, 1)

        self.central_widget.setLayout(self.fullLayout)
        
                
    def setupLog(self):        
        self.logDialog = logDialog(self)
        self.logButt = qtw.QAction('Open log', self)
        self.logButt.triggered.connect(self.openLog)
    
        
    def createMenu(self):
        '''Create the top menu of the window'''
        
        menubar = self.menuBar()
        self.setupLog()                  # create a log window, not open yet
        menubar.addAction(self.logButt)  # add button to open log window
        
        self.openButt = qtw.QAction('Open video folder')
        self.openButt.triggered.connect(self.genBox.openSaveFolder)
        menubar.addAction(self.openButt)  # add a button to open the folder that videos are saved to in Windows explorer
    
    
    def closeEvent(self, event):
        '''runs when the window is closed. Disconnects everything we connected to.'''
        try:
            for o in [self.sbBox, self.basBox, self.nozBox, self.web2Box, self.fluBox]:
                try:
                    o.close()
                except:
                    pass
            for o in [self.logDialog]:
                try:
                    o.done(0)
                except:
                    pass
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)
        except:
            pass

                
    def openLog(self) -> None:
        '''Open the log window'''
        
        self.logDialog.show()
        self.logDialog.raise_()

class MainProgram(qtw.QWidget):
    '''The main application widget. Here, we can set fonts, icons, window info'''
    
    def __init__(self): 
        app = qtw.QApplication(sys.argv)
        sansFont = QtGui.QFont("Arial", 9)
        app.setFont(sansFont)
        gallery = SBwindow()
        gallery.show()
        gallery.setWindowIcon(QtGui.QIcon('icons/sfcicon.ico'))
        app.setWindowIcon(QtGui.QIcon('icons/sfcicon.ico'))
        app.exec_()
        
        myappid = APPID # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        
        
'''Run the program'''
if __name__ == "__main__":
    MainProgram()