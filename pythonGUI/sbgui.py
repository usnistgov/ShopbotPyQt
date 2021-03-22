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

import Fluigent.SDK as fgt

try:
    os.environ["PYLON_CAMEMU"] = "3"
    from pypylon import genicam
    from pypylon import pylon
except:
    print('Pylon SDK not installed')
    pass

#################################################

DEFAULTFOLDER = r'C:\Users\lmf1\OneDriveNIST\NIST\data\shopbot\SBP files'
if not os.path.exists(DEFAULTFOLDER):
    DEFAULTFOLDER = r'C:\\'
INITSAVEFOLDER = r'C:\Users\lmf1\Videos\Shopbot videos'
if not os.path.exists(INITSAVEFOLDER):
    INITSAVEFOLDER = r'C:\\'

################################################

# FileDialog opens a dialog to select a file for reading
# startDir is the directory to start in, e.g. r'C:\Documents'
# fmt is a string file format, e.g. 'Gcode files (*.gcode *.sbp)'
# isFolder is bool true to only open folders
def FileDialog(startDir:str, fmt:str, isFolder:bool) -> str:
    dialog = qtw.QFileDialog()
    dialog.setFilter(dialog.filter() | QtCore.QDir.Hidden)

    # ARE WE TALKING ABOUT FILES OR FOLDERS
    if isFolder:
        dialog.setFileMode(qtw.QFileDialog.DirectoryOnly)
    else:
        dialog.setFileMode(qtw.QFileDialog.AnyFile)
        
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
        path = dialog.selectedFiles()[0]  # returns a list
        return path
    else:
        return ''

#####################################################
# findFileInFolder finds the full path name for a file in a folder
# file is the basename string
# folder is the folder to search in
# this searches recursively and returns an exception if it doesn't find the file
def findFileInFolder(file:str, folder:str) -> str:
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

# find the folder that the Sb3 program files are in
def findSb3Folder() -> str:
    for fold in [r'C:\\Program files', r'C:\\Program files (x86)']:
        for f in os.listdir(fold):
            if 'ShopBot'.lower() in f.lower():
                return os.path.join(fold, f)
    raise Exception('Shopbot folder not found')

# find the full path name for the Sb3.exe program
# raises an exception if it doesn't find the file
def findSb3() -> str:
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
# use this to remove an entire QtLayout and its children from the GUI
def deleteLayoutItems(layout) -> None:
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

# this is a gui box for managing files
class genBox(qtw.QGroupBox):
    def __init__(self, sbWin:qtw.QMainWindow):
        super(genBox, self).__init__()
        self.sbWin = sbWin
        self.layout = qtw.QGridLayout()
        
        self.appendName = qtw.QLineEdit()
        self.appendName.setText('')
        
        self.appendLabel = qtw.QLabel('Append to output file names:')
        self.appendLabel.setBuddy(self.appendName)
        
        self.saveButt = qtw.QPushButton('Set export folder')
        self.saveButt.clicked.connect(self.setSaveFolder)
        self.saveButt.setFixedSize(200, 40)
        self.saveFolder = INITSAVEFOLDER
        self.saveFolderLabel = qtw.QLabel('Export to ' + self.saveFolder)
        
        self.layout.addWidget(self.saveButt, 1, 0)
        self.layout.addWidget(self.saveFolderLabel, 1, 1)
        self.layout.addWidget(self.appendLabel, 2, 0)
        self.layout.addWidget(self.appendName, 2, 1)
        
        self.setLayout(self.layout)
    
    # set the folder to save all the files we generate from the whole gui
    def setSaveFolder(self) -> None:
        if os.path.exists(self.saveFolder):
            startFolder = os.path.dirname(self.saveFolder)
        else:
            startFolder = INITSAVEFOLDER
        sf = FileDialog(startFolder, '', True)
        if os.path.exists(sf):
            self.saveFolder = sf
            self.saveFolderLabel.setText('Export to ' + self.saveFolder)


            
##############################################################################       

# connectBox is a type of QGroupBox that can be used for cameras and fluigent, 
# which need to be initialized
# This gives us the option of showing an error message and reset button
# if the program doesn't connect

class connectBox(qtw.QGroupBox):
    
    def __init__(self):
        super(connectBox, self).__init__()
        self.connectAttempts = 0
        self.connected = False

    # if the computer is still trying to connect, show this waiting screen
    def connectingLayout(self) -> None:
        if self.connectAttempts>0:
            self.resetLayout()
        self.layout = qtw.QVBoxLayout()
        self.layout.addWidget(qtw.QLabel('Connecting to '+self.bTitle))
        self.setLayout(self.layout)  

    # if the computer fails to connect,
    # show an error message and a button to try again
    def failLayout(self) -> None:
        self.resetLayout()
        self.layout = qtw.QVBoxLayout()
        lstr = self.bTitle+' not connected. Connect attempts: '+str(self.connectAttempts)
        self.label = qtw.QLabel(lstr)            
        self.resetButt = qtw.QPushButton('Connect to ' + self.bTitle)
        self.resetButt.clicked.connect(self.connect) 
            # when the reset button is pressed, try to connect to the fluigent again
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.resetButt)
        self.setLayout(self.layout)
    
    # creates a section for displaying the device status
    def createStatus(self, width:int) -> None:
        self.status = qtw.QLabel('Ready')
        self.status.setFixedSize(width, 50)
        self.status.setWordWrap(True)
    
    # delete all the display items from the box
    def resetLayout(self) -> None:
        deleteLayoutItems(self.layout)
        
    # update the displayed device status
    def updateStatus(self, st) -> None:
        try:
            self.status.setText(st)
        except:
            print(st)

################################################################
# this is a gui box for the shopbot buttons
class sbBox(connectBox):
    ####################  
    ############## initialization functions
    
    # sbWin is the parent window that all of the widgets are in
    def __init__(self, sbWin:qtw.QMainWindow):
        super(sbBox, self).__init__()
        self.btitle = 'Shopbot'
        self.sbWin = sbWin
        self.runningSBP = False
        self.setTitle('Shopbot')
        try:
            self.sb3File = findSb3()
            self.connectKeys()
        except:
            self.failLayout()
        else:
            self.successLayout()
            
    # connects to the windows registry keys for the Shopbot flags
    def connectKeys(self) -> None:
        try:
            aKey = r'Software\VB and VBA Program Settings\Shopbot\UserData'
            aReg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            self.aKey = winreg.OpenKey(aReg, aKey)
            self.keyConnected = True
        except:
            self.keyConnected = False
            self.updateStatus('Failed to connect to Shopbot')
    
    # layout if we found the sb3 files and windows registry keys
    def successLayout(self) -> None:
        self.sbpName='No file loaded'
        
        self.layout = qtw.QGridLayout()
        
        self.createStatus(1200)
        
        self.sbpNameLabel = qtw.QLabel(self.sbpName)
        self.loadButt = qtw.QPushButton('Load file')
        self.loadButt.clicked.connect(self.loadFile)
        self.loadButt.setFixedSize(200, 40)
        
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
        
        self.layout.addWidget(self.status, 0, 0, 1, 2)
        self.layout.addWidget(self.loadButt, 1, 0)
        self.layout.addWidget(self.sbpNameLabel, 1, 1)
        self.layout.addItem(self.buttLayout, 2, 0, 1, 2)
 
        self.setLayout(self.layout)  
    
    # function to load a shopbot run file
    def loadFile(self) -> None:
        if os.path.exists(self.sbpName):
            openFolder = os.path.dirname(self.sbpName)
        else:
            openFolder = DEFAULTFOLDER
        sbpn = FileDialog(openFolder, 'Gcode files (*.gcode *.sbp)', False)
        if os.path.exists(sbpn):
            self.sbpName = sbpn
            self.sbpNameLabel.setText(self.sbpName)
            self.runButt.setEnabled(True)
        else:
            self.runButt.setEnabled(False)
            
    ####################            
    #### functions to start on run
    
    # critFlag is a shopbot flag value that indicates that the run is done
    # we run this function at the beginning of the run to determine what flag will trigger the start of videos, etc.
    def getCritFlag(self) -> int:
        # go through the file and determine if the 
        # output flags get turned on more than once. 
        # If they do, we should wait until the end 
        # of the whole file to stop watching the 
        # flags, so critFlag = 0. If they only change 
        # twice, we only extrude once, so we can stop
        # watching the flags and turn off the videos
        # when the flag is 8
        self.channelsTriggered = []
        with open(self.sbpName, 'r') as f:
            for line in f:
                if line.startswith('SO') and (line.endswith('1') or line.endswith('1\n')):
                    # the shopbot flags are 1-indexed, while our channels
                    # are 0-indexed, so when it means change channel 1, 
                    # we want to change channels[0]
                    li = int(line.split(',')[1])-1
                    if li not in self.channelsTriggered:
                        self.channelsTriggered.append(li) 
        if len(self.channelsTriggered)==0:
            return 0
        else:
            return 8  
    
    # run this function continuously during print to watch the shopbot status
    def getSBFlag(self) -> int:
        try:
            sbFlag, _ = winreg.QueryValueEx(self.aKey, 'OutPutSwitches')
        except:  
            # if we fail to get the registry key, we have no way of knowing 
            # if the print is over, so just stop it now
            self.triggerEndOfPrint()
            self.updateStatus('Failed to connect to Shopbot keys')
            self.keyConnected = False
            
        # if the flag has reached a critical value that signals the 
        # shopbot is done printing, stop tracking pressures and recording vids
        sbFlag = int(sbFlag)
        return sbFlag
    
            
    # runFile sends a file to the shopbot, starts camera recordings, 
    # and starts the fluigent watching for triggers to change pressure
    def runFile(self) -> None:
        self.allowEnd = False
        self.abortButt.setEnabled(True)
        self.updateStatus('Running SBP file')
        if not os.path.exists(self.sbpName):
            return
        
        self.critFlag = self.getCritFlag()
        if self.critFlag==0:
            self.allowEnd = True

        # send the file to the shopbot via command line
        appl = self.sb3File
        arg = self.sbpName + ', ,4, ,0,0,0"'
        subprocess.Popen([appl, arg])
        
        # wait 10 seconds after we send the command 
        # to the shopbot to make sure the running flags are on    
        self.runningSBP = True
        self.triggerWait()
        


    # timerFunc runs continuously while we are printing
    def timerFunc(self) -> None:
        # update the pressure if the shopbot state has changed
        if self.runningSBP and self.keyConnected:
            self.watchSBFlags()
        else:
            self.triggerEndOfPrint()
    
    # start the timer to watch for the start of print
    def triggerWait(self) -> None:
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.waitForStartTimerFunc)
        self.timer.start(100) # update every 100 ms
    
    # start the timer to watch for changes in pressure
    def triggerWatch(self) -> None:
        # eliminate the old timer
        self.timer.stop()
        
        # start the timer to watch for pressure triggers
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.timerFunc)
        self.timer.start(100) # update every 100 ms
        
        # start the cameras
        for camBox in self.sbWin.camBoxes:
            if camBox.camInclude.checkState() and not camBox.camObj.recording:
                camBox.cameraRec()
                
    # stop watching for changes in pressure, stop recording    
    def triggerEndOfPrint(self) -> None:
        if self.runningSBP:
            for camBox in self.sbWin.camBoxes:
                if camBox.camInclude.checkState() and camBox.camObj.recording:
                    camBox.cameraRec()
            try:
                self.timer.stop()
            except:
                pass
            self.sbWin.fluBox.resetAllChannels(-1)
        self.runningSBP = False
        self.abortButt.setEnabled(False)
        self.updateStatus('Ready')
            
    # goes inside the wait for start timer function
    # checks the shopbot flags and triggers the watch 
    # for pressure triggers if the test has started
    def waitForStart(self) -> None:
        sbFlag = self.getSBFlag()
        self.updateStatus('Waiting to start file, Shopbot output flag = ' + str(sbFlag) + ', start at ' + str(self.critFlag))
        if sbFlag==self.critFlag:
            self.triggerWatch()
    
    # this is the function we use when we're waiting for the nozzle to start extruding
    def waitForStartTimerFunc(self) -> None:
        if self.runningSBP and self.keyConnected:
            self.waitForStart()
        else:
            self.triggerEndOfPrint()

    # goes inside the timer function. 
    # checks the Shopbot flags and changes the 
    # pressure if the flags have changed    
    def watchSBFlags(self) -> None:
        sbFlag = self.getSBFlag()
        self.updateStatus('Running file, Shopbot output flag = ' + str(sbFlag) + ', end at ' + str(self.critFlag))
        
        # allowEnd is a failsafe measure because when the shopbot
        # starts running a file that changes output flags, it asks
        # the user to allow spindle movement to start. This means
        # that for an unpredictable amount of time, only flag 4 will be
        # up, which would indicate that the print is done. We create
        # an extra trigger to say that if we're extruding, we have to wait
        # for extrusion to start before we can let the tracking stop
        if self.allowEnd and (sbFlag==self.critFlag or sbFlag==0):
            self.triggerEndOfPrint()
            return
        
        # for each channel, check if the flag is up
        # if flag 0 is up for channel 0, the output will be odd, so 
        # flag mod 2 (2=2^(0+1)) will be 1, which is 2^0
        # if flag 1 is up for channel 1, it adds 2 to the output,
        # e.g. if we want channel 1 on, the value will be 10, so the
        # 10%2=2, which is 2^1
        for i in self.channelsTriggered:
            if sbFlag%2**(i+1)==2**i:
                # this channel is on
                
                # now that we've started extrusion, we know that
                # the run has really started, so we can allow it to end
                self.allowEnd = True
                
                # set this channel to the value in the 
                # constant box (run pressure)
                # if we triggered a flag that doesn't correspond to a 
                # pressure channel, skip this
                if i<len(self.sbWin.fluBox.pchannels):
                    channel = self.sbWin.fluBox.pchannels[i]
                    press = int(channel.constBox.text())
                    fgt.fgt_set_pressure(i, press)

                     # set the other channels to 0
                    self.sbWin.fluBox.resetAllChannels(i)                    
                return 
        
        # if we never hit a channel, turn off all of the channels       
        self.sbWin.fluBox.resetAllChannels(-1)


        
    #-----------------------------------------
    
    # this gets triggered when the whole window is closed
    def close(self):
        try:
            self.timer.stop()
        except:
            pass
        else:
            print('Shopbot timer stopped')
            
#########################################################
#########################################################
######################## CAMERAS #######################
#########################################################
#########################################################


def mode2title(mode:int) -> str:
    if mode==0:
        return 'Basler camera'
    elif mode==1:
        return 'Nozzle camera'
    elif mode==2:
        return 'Webcam 2'
    
#########################################################
# Defines the signals available from a running worker thread
# Supported signals are:
#     finished: No data
#     error: `tuple` (exctype, value, traceback.format_exc() )
#     result:`object` data returned from processing, anything
#     progress: `int` indicating % progress 
class vrSignals(QtCore.QObject):
    
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(tuple)
    result = QtCore.pyqtSignal(object)
    progress = QtCore.pyqtSignal(int)  

#########################################################
# The vidRecorder creates a cv2.VideoWriter object at initialization, and it takes frames in the queue and writes them to file. This is a failsafe, so if the videowriter writes slower than the timer reads frames, then we can store those extra frames in memory until the vidRecorder object can write them to the HD
# QRunnables run in the background. Trying to directly modify the GUI from inside the QRunnable will make everything catastrophically slow, but you can pass messages back to the GUI using vrSignals.
class vidRecorder(QtCore.QRunnable):
    def __init__(self, fn, vidvars, frames):
        super(vidRecorder, self).__init__()        
        self.vFilename = fn
        self.vw = cv2.VideoWriter(fn, vidvars['fourcc'], vidvars['fps'], (vidvars['imw'], vidvars['imh']))
        self.signals = vrSignals()  
        self.frames = frames
        self.vidvars = vidvars
        self.recording = True
    
    def run(self) -> None:
        # this loops until we receive a frame that is a string
        # the save function will pass STOP to the frame list when we are done recording
        while True:
            time.sleep(1) 
                # this gives the GUI enough time to start adding frames before we start saving, otherwise we get stuck in infinite loop where it's immediately checking again and again if there are frames
            while len(self.frames)>0:
                # remove the first frame once it's written
                frame = self.frames.pop()
                if type(frame)==str:
                    self.vw.release()
                    self.signals.finished.emit()
                    return
                self.vw.write(frame) 
                if len(self.frames) % 10==1:
                    self.signals.progress.emit(len(self.frames))
   

 #########################################################        
# a camera object is a generic camera which stores functions and camera
# info for both pylon cameras and webcams
# these objects are created by cameraBox objects
# each type of camera (Basler and webcam) has its own readFrame and close functions
class camera:
    def __init__(self, sbWin:qtw.QMainWindow, guiBox:connectBox):
        self.previewing = False
        self.sbWin = sbWin
        self.guiBox = guiBox
        self.cameraName = mode2title(guiBox.mode)
        self.vFilename = ''
        self.timerRunning = False
        self.previewing = False
        self.recording = False
        self.writing = True
        self.timer = None
        self.cam = None
        self.resetVidStats()
        self.framesSincePrev = 0

        self.fourcc = cv2.VideoWriter_fourcc('M','J','P','G')
        self.prevWindow = qtw.QLabel()
    
    # disconnect from the camera when the window is closed
    def closeCam(self) -> None:
        self.recording = False
        self.previewing = False
        if not self.timer==None:
            try:
                self.timer.stop()
            except:
                pass
            else:
                print(self.cameraName + ' timer stopped')
                
    # update the status box when we're done recording        
    def doneRecording(self) -> None:
        self.writing = False
        self.updateRecordStatus()
    
    # determine the file name for the file we're about to record
    # ext is the extension
    def getFilename(self, ext:str) -> str:      
        # determine the folder to save to
        folder = self.sbWin.genBox.saveFolder
        if not os.path.exists(folder):
            # open a save dialog if the folder does not exist
            self.sbWin.genBox.setSaveFolder()
            folder = self.sbWin.saveFolderLabel.text()
        if not os.path.exists(folder):
            self.updateStatus('Invalid folder name. Image not saved.')
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
    
    # reset video stats
    def resetVidStats(self) -> None:
        self.startTime = 0
        self.timeRec = 0
        self.framesDropped = 0
        self.totalFrames = 0
        self.fleft = 0
        self.frames = []
        
    # save the frame to the video file
    # frames are in cv2 format
    def saveFrame(self, frame) -> None:
        try:
            self.frames.append(frame)
        except:
            # stop recording if we can't write
            self.updateStatus('Error writing to video')
            self.recording = False
            self.stopTimer()
        else:
            # display the time recorded
            self.timeRec = self.timeRec+self.mspf/1000
            self.totalFrames+=1
            self.updateRecordStatus()
    
    # take a single snapshot and save it
    def snap(self) -> None:
        fullfn = self.getFilename('.png')
        try:
            frame = self.readFrame()
            # frame needs to be in cv2 format
        except:
            return
        try:
            cv2.imwrite(fullfn, frame)
        except:
            self.updateStatus('Error saving frame')
        else:
            self.updateStatus('File saved to ' + fullfn) 
    
    #---------------------------------
    # start preview
    def start(self) -> None:    
        # this counter reduces the display frame rate, 
        # so only have to update the display at a comfortable viewing rate.
        # if the camera is at 200 fps, the video will be saved at full rate but
        # preview will only show at 15 fps
        self.critFramesToPrev = max(round(self.fps/15), 1)
        self.framesSincePrev = self.critFramesToPrev
        self.previewing = True
        self.startTimer() # this only starts the timer if a timer doesn't already exist

    # stop preview
    def stop(self) -> None:
        self.previewing = False
        self.stopTimer() # this only stops the timer if we are neither recording nor previewing
 
    #---------------------------------
    # start recording
    def startRecording(self) -> None:
        self.recording = True
        self.writing = True
        self.resetVidStats()
        fn = self.getFilename('.avi')
        self.vFilename = fn
        vidvars = {'fourcc':self.fourcc, 'fps':self.fps, 'imw':self.imw, 'imh':self.imh, 'cameraName':self.cameraName}
        self.frames = []
        recthread = vidRecorder(fn, vidvars, self.frames)
        recthread.signals.finished.connect(self.doneRecording)
        recthread.signals.progress.connect(self.writingRecording)
        self.updateStatus('Recording ' + self.vFilename + ' ... ')
        self.sbWin.threadPool.start(recthread)
        self.startTimer() # this only starts the timer if a timer doesn't already exist
    
    # stop recording
    def stopRecording(self) -> None:
        if not self.recording:
            return
        self.frames.append('STOP')
        self.recording = False
        self.stopTimer()

    #---------------------------------
    # start the timer if there is not already a timer
    def startTimer(self) -> None:
        if not self.timerRunning:
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.timerFunc)
            self.timer.setTimerType(QtCore.Qt.PreciseTimer)
            self.timer.start(self.mspf)
            self.timerRunning = True
    
    # this only stops the timer if we are neither recording nor previewing
    def stopTimer(self) -> None:
        if not self.recording and not self.previewing:
            self.timer.stop()
            self.timerRunning = False
    
    # run this function continuously if we are recording or previewing
    def timerFunc(self) -> None:
        
        # get an image
        try:
            frame = self.readFrame()
        except:
            frame = self.lastFrame
            print(self.cameraname, ': Error collecting frame')
        # update the preview
        if self.previewing:
            # downsample preview frames
            if self.framesSincePrev==self.critFramesToPrev:
                self.updatePrevFrame(frame)
                self.framesSincePrev = 0
            else:
                self.framesSincePrev+=1
        # save the frame
        if self.recording:
            self.timerCheckDrop() # if we've skipped at least 2 frames, fill that space with duplicate frames
            self.saveFrame(frame) 
    
    # this function checks to see if the timer has skipped steps and fills the missing frames with duplicates        
    def timerCheckDrop(self) -> None:
        diag = False
        dnow = datetime.datetime.now()
        if self.startTime==0:
            self.startTime = dnow
            if diag:
                self.lastTime = dnow
        else:
            timeElapsed = (dnow-self.startTime).total_seconds()
            if (timeElapsed - self.timeRec)>2*self.mspf/1000:
                # if we've skipped at least 2 frames, fill that space with duplicate frames
                numfill = int(np.floor((timeElapsed-self.timeRec)/(self.mspf/1000)))
                for i in range(numfill):
                    #print('PADDING ', self.timeRec)
                    self.framesDropped+=1
                    self.saveFrame(self.lastFrame)
            if diag:
                elasped = ((dnow-self.lastTime).total_seconds())*1000
                print(self.cameraName, ['%2.3f'%t for t in [elasped, self.mspf, timeElapsed, self.timeRec]])
                self.lastTime = dnow
    
    #---------------------------------
    # update the preview window
    def updatePrevFrame(self, frame) -> None:
        
        try:
            if self.convertColors:
                frame2 = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame2 = frame
            image = QtGui.QImage(frame2, frame2.shape[1], frame2.shape[0], QtGui.QImage.Format_RGB888)
            pixmap = QtGui.QPixmap.fromImage(image)
            self.prevWindow.setPixmap(pixmap)
        except:
            # stop previewing if we can't preview
            self.updateStatus('Error displaying frame')
            self.previewing = False
            self.stopTimer()

    # updates the status of the widget that this camera belongs to            
    def updateStatus(self, st:str) -> None:
        self.guiBox.updateStatus(st)
    
    # updates the status during recording and during save
    def updateRecordStatus(self) -> None:
        if self.recording:
            s = 'Recording '
        elif self.writing:
            s = 'Writing '
        else:
            s = 'Recorded '
        s+=self.vFilename
        s+= ' : %2.2f s' % self.timeRec + ', '
        if self.writing and not self.recording:
            s+= str(self.fleft) + '/' + str(self.totalFrames) + ' frames left'
        else:
            s+= str(self.framesDropped) + '/' + str(self.totalFrames) +' frames dropped'
        self.updateStatus(s)
        
    # fleft is the number of frames left to record
    # this function updates the status to say that the video is still being saved
    def writingRecording(self, fleft:int) -> None:      
        if not self.recording:
            self.fleft = fleft
            self.updateRecordStatus()
        
        
##################

# webcams are conventional webcams that openCV (cv2) can communicate with
class webcam(camera):
    def __init__(self, sbWin:qtw.QMainWindow, guiBox:connectBox):
        super(webcam, self).__init__(sbWin, guiBox)

        # connect to webcam
        try:
            self.cam = cv2.VideoCapture(guiBox.mode-1)
            self.lastFrame = self.readFrame()
        except:
            self.connected = False
            return
        else:
            self.connected = True
        
        # get image stats
        self.fps = self.cam.get(cv2.CAP_PROP_FPS)/2 # frames per second
        self.mspf = int(round(1000./self.fps))  # ms per frame
        self.imw = int(self.cam.get(3)) # image width (px)
        self.imh = int(self.cam.get(4)) # image height (px)
        
        self.convertColors = True
        
    #-----------------------------------------
        
    # get a frame from the webcam    
    def readFrame(self):
        try:
            rval, frame = self.cam.read()
        except:
            self.updateStatus('Error reading frame')
            raise Exception
        if not rval:
            raise Exception
        else:
            self.lastFrame = frame
            return frame
 
    #-----------------------------------------
    
    # this gets triggered when the whole window is closed
    def close(self) -> None:
        self.closeCam()
        if not self.cam==None:
            try:
                self.cam.release()
            except:
                pass
            else:
                print(self.cameraName + ' camera closed')
    

#########################################      
      
# bascams are Basler cameras that require the pypylon SDK to communicate
class bascam(camera):
    def __init__(self, sbWin:qtw.QMainWindow, guiBox:connectBox):
        super(bascam, self).__init__(sbWin, guiBox)
        self.vFilename = ''
        # Get the transport layer factory.
        self.connected = False
        self.convertColors = True
        
        # connect to the camera
        try:
            self.tlf = pylon.TlFactory.GetInstance()
            self.cam = pylon.InstantCamera(self.tlf.CreateFirstDevice())
        except Exception as e:
            self.guiBox.updateStatus(e)
            self.connected = False
            return
        
        # open camera
        try:
            self.cam.Open()
            
            self.cam.StartGrabbing(pylon.GrabStrategy_OneByOne)
            #self.cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            #self.cam.Gain.SetValue(12)
            #self.cam.AutoTargetValue.SetValue(128)  ## this doesn't work
    
            self.connected = True
            # update the GUI display to show camera model
            self.guiBox.model = self.cam.GetDeviceInfo().GetModelName()
            self.guiBox.updateBoxTitle()
            
            # converter converts pylon images into cv2 images
            self.converter = pylon.ImageFormatConverter()
            self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
            self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
            
            # get camera stats
            self.fps = self.cam.ResultingFrameRate.GetValue() # frames per s
            #self.fps = 120
            self.mspf = int(round(1000./self.fps))  # ms per frame
            f1 = self.readFrame()
            self.imw = len(f1[0]) # image width (px)
            self.imh = len(f1) # image height (px)
            
            self.lastFrame = self.readFrame()

        except Exception as e:
            try:
                self.cam.Close() # close camera if we've already opened it
            except:
                pass
            self.guiBox.updateStatus(e)
            self.connected = False
            return   
        
    #-----------------------------------------
        
    # get a frame from the Basler camera
    def readFrame(self):
        try:            
            grabResult = self.cam.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        except:
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
        self.lastFrame = img
        return img       
    
    # update the status box when there's an error grabbing the frame
    def grabError(self, status:str) -> None:
        self.updateStatus(status)
    
    
    #-----------------------------------------
    
    # this gets triggered when the whole window is closed
    def close(self) -> None:
        self.closeCam()
        try:
            self.cam.StopGrabbing()
            self.cam.Close()
        except:
            pass
        else:
            print('Basler camera closed')
            
################################################

# this is the widget object that holds camera objects and displays buttons and preview frames
class cameraBox(connectBox):
    def __init__(self, mode:int, sbWin:qtw.QMainWindow):
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
        self.connect(sbWin) # try to connect to the camera
        self.updateBoxTitle()
        if self.connected:
            print(self.bTitle, ' ', self.camObj.fps, ' fps')

    # try to connect to the camera
    def connect(self, sbWin:qtw.QMainWindow) -> None:
        self.connectingLayout() # inherited from connectBox
        self.connectAttempts+=1
        if self.mode==0:
            self.camObj = bascam(sbWin, self)
        else:
            self.camObj = webcam(sbWin, self)
        if self.camObj.connected:
            self.successLayout()
        else:
            self.failLayout() # inherited from connectBox
            
    # this is the layout if we successfully connected to the camera
    def successLayout(self) -> None:
        self.resetLayout()
        self.layout = qtw.QVBoxLayout()
        self.camButts = qtw.QHBoxLayout()
        
        self.camInclude = qtw.QCheckBox('Export video on run')
        self.camInclude.setCheckState(False)
        
        self.camPrev = qtw.QPushButton()
        self.camPrev.clicked.connect(self.cameraPrev)
        self.setPrevButtStart()
        
        self.camRec = qtw.QPushButton('Record')
        self.camRec.clicked.connect(self.cameraRec)
        self.setRecButtStart()
        
        self.camPic = qtw.QPushButton('Capture image')
        self.camPic.clicked.connect(self.cameraPic)
        self.camPic.setIcon(QtGui.QIcon('icons/camera.png'))
        
        self.status = qtw.QLabel('Ready')
        self.status.setFixedSize(600, 50)
        self.status.setWordWrap(True)
        self.layout.addWidget(self.status)
        
        self.camButts.addWidget(self.camInclude)
        self.camButts.addWidget(self.camPrev)
        self.camButts.addWidget(self.camRec)
        self.camButts.addWidget(self.camPic)
        self.camButts.setSpacing(10) # spacing between buttons
        
        self.layout.addItem(self.camButts)
        self.layout.addStretch(1)
        
        self.layout.addWidget(self.camObj.prevWindow)
        self.setLayout(self.layout)
        
        
    #------------------------------------------------
    # functions to trigger camera actions and update the GUI
    
    # capture a single frame
    def cameraPic(self) -> None:
        self.camObj.snap()
       
    # start or stop previewing
    def cameraPrev(self) -> None:
        if self.previewing:
            # we're already previewing: stop the preview
            self.camObj.stop()
            self.setPrevButtStart()
        else:
            self.camObj.start()
            self.setPrevButtStop()
        self.previewing = not self.previewing
        
    # start or stop recording
    def cameraRec(self) -> None:
        if self.recording:
            self.setRecButtStart()
            self.camObj.stopRecording()
        else:
            self.setRecButtStop()
            self.camObj.startRecording()
        self.recording = not self.recording
        
    #------------------------------------------------
    #  functions to change appearance of buttons when they're pressed
        
    def setPrevButtStart(self) -> None:
        self.camPrev.setText('Start preview')
        self.camPrev.setStyleSheet('')
        self.camPrev.setIcon(QtGui.QIcon('icons/play.png'))
        
    def setPrevButtStop(self) -> None:
        self.camPrev.setText('Stop preview')
        self.camPrev.setStyleSheet('background-color:black; color:white;')
        self.camPrev.setIcon(QtGui.QIcon('icons/stopwhite.png'))

    def setRecButtStart(self) -> None:
        self.camRec.setText('Record')
        self.camRec.setStyleSheet('')
        self.camRec.setIcon(QtGui.QIcon('icons/Record.png'))
        
    def setRecButtStop(self) -> None:
        self.camRec.setText('Stop recording')
        self.camRec.setStyleSheet('background-color:black; color:white;')
        self.camRec.setIcon(QtGui.QIcon('icons/recordstop.png'))
        
    #------------------------------------------------
    
    # this updates the title of widget box
    def updateBoxTitle(self) -> None:
        self.setTitle(self.bTitle +"\t"+ self.model)
    
    # this gets triggered when the window is closed
    def close(self) -> None:
        self.camObj.close()

########################################################
################# FLUIGENT #############################
   
# chanNum is a channel number (e.g. 0)
# color is a string (e.g. #FFFFFF)
# this class describes a single channel on the Fluigent
# fgt functions come from the Fluigent SDK
# each channel gets a QLayout that can be incorporated into the fluBox widget
class fluChannel:
    def __init__(self, chanNum: int, color: str, fluBox:connectBox):
        self.chanNum = chanNum
        self.fluBox = fluBox
        
        # setBox is a one line input box
        self.setBox = qtw.QLineEdit()
        self.setBox.setText('0')
        self.setBox.returnPressed.connect(self.setPressure)
        objValidator = QtGui.QIntValidator()
        objValidator.setRange(0, 7000)
        self.setBox.setValidator(objValidator)

        # label is a text label that tells us what channel this box edits
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
    
    # set the pressure for this channel to the pressure in the setBox
    def setPressure(self) -> None:
        fgt.fgt_set_pressure(self.chanNum, int(self.setBox.text()))
    
    # turn on pressure to the setBox value for a constTimeBox amount of time
    def runConstTime(self) -> None:
        runtime = int(self.constTimeBox.text())
        if runtime<0:
            return
        runpressure = int(self.constBox.text())
        self.fluBox.updateStatus('Setting channel '+str(self.chanNum)+' to '+str(runpressure)+' for '+str(runtime)+' s')
        fgt.fgt_set_pressure(self.chanNum, runpressure)
        QtCore.QTimer.singleShot(runtime*1000, self.zeroChannel) 
            # QTimer wants time in milliseconds
    
    # zero the channel pressure
    def zeroChannel(self) -> None:
        self.fluBox.updateStatus('Setting channel '+str(self.chanNum)+' to 0')
        fgt.fgt_set_pressure(self.chanNum, 0)

        
##############################  

# pcolors is a list of colors, e.g. ['#FFFFFF', '#000000']
# fluBox is a pointer to the fluigent box that contains this plot
# this produces a widget that can be put into fluBox
# this stores the recent times and pressure readings
class fluPlot:
    def __init__(self, pcolors:List[str], fb:connectBox):
        self.fluBox = fb # parent box
        self.numChans = self.fluBox.numChans
        
        # create the plot
        self.graphWidget = pg.PlotWidget() 
        self.graphWidget.setYRange(-10, 7100, padding=0) 
            # set the range from 0 to 7000 mbar
        self.graphWidget.setBackground('w')         
        self.pcolors = pcolors
        self.initializePList()
        
        for i in range(self.numChans):
            press = self.pressures[i]
            pen = pg.mkPen(color=pcolors[i], width=2)
            cname = 'Channel '+str(i+1)
            dl = self.graphWidget.plot(self.time, press, pen=pen, name=cname)
            self.datalines.append(dl)
        
        self.graphWidget.setLabel('left', 'Pressure (mBar)')
        self.graphWidget.setLabel('bottom', 'Time (s)')
        
        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.dt)
        self.timer.timeout.connect(self.update)
        self.timer.start()
    
    # initialize the pressure list
    def initializePList(self) -> None:
        # initialize the time range
        self.dt = 200 # ms
        self.time = list(np.arange(-60*1, 0, self.dt/1000)) 
               
        # initialize pressures. assume 0 before we initialized the gui    
        self.pressures = []
        self.datalines = []
        for i in range(self.numChans):
            press = [0 for _ in range(len(self.time))]
            self.pressures.append(press)
    
    # read the pressure and update the plot display
    def update(self) -> None:
        try:
            newtime = self.time
            newpressures = self.pressures
            # update the plot and displayed pressure
            newtime = newtime[1:]  # Remove the first y element.
            newtime.append(newtime[-1] + self.dt/1000) # Add the next time.
            for i in range(self.numChans):
                newpressures[i] = newpressures[i][1:]
                pnew = self.fluBox.checkPressure(i)
                # update the plot
                newpressures[i].append(pnew)
        except Exception as e:
            print(e)
            self.fluBox.updateStatus('Error reading pressure')
        else:
            self.time = newtime
            self.pressures = newpressures   
            for i in range(self.numChans):
                self.datalines[i].setData(self.time, self.pressures[i])
                # update the pressure reading
                self.fluBox.updateReading(i, str(pnew)) 
    
    #-----------------------------------------
    
    # this gets triggered when the window is closed
    def close(self) -> None:
        try:
            self.fluPlot.timer.stop()       
        except:
            pass
        else:
            print('Fluigent timer deleted')
    
    
##############################    


# sbWin is a pointer to the parent window
class fluBox(connectBox):
    def __init__(self, sbWin:qtw.QMainWindow):
        super(fluBox, self).__init__()
        
        # this box is a QGroupBox. we are going to create a layout to put in the box
        self.bTitle = 'Fluigent'
        self.setTitle(self.bTitle)
        self.sbWin = sbWin
        self.pchannels = []
        self.connected = False
        self.connect()
        
    
    # try to connect to the Fluigent
    def connect(self) -> None: 
        self.connectAttempts+=1
        self.connectingLayout()
        ########### INITIALIZE FLUIGENT HERE
        
        fgt.fgt_init() # initialize fluigent
        self.numChans = fgt.fgt_get_pressureChannelCount()
        channels = list(range(self.numChans))
        
        if self.numChans>0:
            self.connected = True
            self.successLayout()
        else:
            self.failLayout()
            
#     # this tells us which Shopbot flag to watch for this channel
#     def setCritFlag(self, flag:int) -> None:
#         if self.connected:
#             self.fluPlot.critFlag = flag
    
    # display if we successfully connected to the fluigent
    def successLayout(self) -> None:
        self.resetLayout()
        self.layout = qtw.QVBoxLayout() ## whole fluigent layout
        
        self.createStatus(600)
        self.layout.addWidget(self.status)
        
        self.fluButts = qtw.QHBoxLayout()  ### fluigent button row
        
        self.pcolors = ['#3f8dd1', '#b0401e', '#3e8a5b', '#b8a665'][0:self.numChans]
        
        self.pchannels = [] # pchannels is a list of fluChannel objects
        for i in range(self.numChans):
            pc = fluChannel(i, self.pcolors[i], self)
            self.pchannels.append(pc)
            self.fluButts.addItem(pc.layout)

        self.fluButts.setSpacing(40) # 40px between channels
        self.layout.addItem(self.fluButts) # put the buttons in the layout
    
        self.fluPlot = fluPlot(self.pcolors, self) # create plot
        self.layout.addWidget(self.fluPlot.graphWidget) # add plot to the layout
        
        self.setLayout(self.layout) # put the whole layout in the box  
        
    #-----------------------------------------
    
    # this reads the pressure of a given channel
    def checkPressure(self, channel:int) -> None:
        pressure = int(fgt.fgt_get_pressure(channel))
        return pressure 
    
    # this reads the pressure of all channels
    def readPressures(self) -> List[int]:
        plist = []
        for i in range(self.numChans):
            plist.append(self.checkPressure(i))
        return plist
    
    # exclude is a channel that we want to keep on. Input -1 or any other unused value to turn everything off
    def resetAllChannels(self, exclude:int) -> None:
        for i in range(self.numChans):
            if not i==exclude:
                fgt.fgt_set_pressure(i,0)
                
    # this updates the status box that tells us what pressure this channel is at
    def updateReading(self, channum:int, preading:int) -> None:
        self.pchannels[channum].readBox.setText(preading)
        
        
    #-----------------------------------------
    
    # this runs when the window is closed
    def close(self) -> None:
        # close the fluigent
        if self.connected:      
            try:
                self.resetAllChannels(-1)
                fgt.fgt_close() 
            except:
                pass
            else:
                print('Fluigent closed')  
            # stop the timer used to create the fluigent plot
            self.fluPlot.close()

        
####################### the whole window

class SBwindow(qtw.QMainWindow):
    def __init__(self, parent=None):
        super(SBwindow, self).__init__(parent)
        
        # define central widget
        self.central_widget = qtw.QWidget()               
        self.setCentralWidget(self.central_widget) 
        
        self.setWindowTitle("Shopbot/Fluigent/Camera")
        self.setStyleSheet('background-color:white;')
        self.resize(1600, 1800)

        self.genBox = genBox(self)
        self.sbBox = sbBox(self)
        self.basBox = cameraBox(0, self)
        self.nozBox = cameraBox(1, self)
        self.ledBox = cameraBox(2, self)
        self.camBoxes = [self.basBox, self.nozBox, self.ledBox]
        self.fluBox = fluBox(self)
              
        self.fullLayout = qtw.QGridLayout()
        self.fullLayout.addWidget(self.genBox, 0, 0, 1, 2)
        self.fullLayout.addWidget(self.sbBox, 1, 0, 1, 2)
        self.fullLayout.addWidget(self.basBox, 2, 0)
        self.fullLayout.addWidget(self.fluBox, 3, 0)
        self.fullLayout.addWidget(self.nozBox, 2, 1)
        self.fullLayout.addWidget(self.ledBox, 3, 1)
        
        self.fullLayout.setRowStretch(0, 1)
        self.fullLayout.setRowStretch(1, 2)
        self.fullLayout.setRowStretch(2, 6)
        self.fullLayout.setRowStretch(3, 6)
        self.fullLayout.setColumnStretch(0, 1)
        self.fullLayout.setColumnStretch(1, 1)

        self.central_widget.setLayout(self.fullLayout)
        
        self.threadPool = QtCore.QThreadPool()
        
#     def setCritFlag(self, flag:int) -> None:
#         self.fluBox.setCritFlag(flag) 
    
    
#     def triggerEndOfPrint(self) -> None:
#         self.sbBox.endOfPrint()
    
#     # determines if the shopbot is currently running a file that was sent from this GUI
#     def sbpRunning(self) -> bool:
#         return self.sbBox.runningSBP
      
    # this runs when the window is closed
    def closeEvent(self, event):
        for o in [self.sbBox, self.basBox, self.nozBox, self.ledBox, self.fluBox]:
            o.close()

class MainProgram(qtw.QWidget):
    def __init__(self): 
        app = qtw.QApplication(sys.argv)
        gallery = SBwindow()
        gallery.show()
        gallery.setWindowIcon(QtGui.QIcon('icons/sfcicon.ico'))
        app.setWindowIcon(QtGui.QIcon('icons/sfcicon.ico'))
        app.exec_()
        myappid = 'leanfried.sbgui.v0.0' # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
      
        
if __name__ == "__main__":
    MainProgram()