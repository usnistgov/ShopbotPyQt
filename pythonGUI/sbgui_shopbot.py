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

# local packages
import Fluigent.SDK as fgt
from config import cfg
from sbgui_general import *

# info
__author__ = "Leanne Friedrich"
__copyright__ = "This data is publicly available according to the NIST statements of copyright, fair use and licensing; see https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software"
__credits__ = ["Leanne Friedrich"]
__license__ = "MIT"
__version__ = "1.0.4"
__maintainer__ = "Leanne Friedrich"
__email__ = "Leanne.Friedrich@nist.gov"
__status__ = "Development"

##################################################  

      
class sbSettingsBox(qtw.QWidget):
    '''This opens a window that holds settings about logging for the shopbot.'''
    
    
    def __init__(self, parent:connectBox):
        '''parent is the connectBox that this settings dialog belongs to. '''
        
        super().__init__(parent)  
        self.parent = parent
        
        layout = qtw.QVBoxLayout()
        layout.addStretch()
        
        self.showFolderCheck = fCheckBox(layout, title='Show folder name', tooltip='Show folder name in the file display box', checked=cfg.shopbot.showFolder, func=self.parent.reformatFileList)
        
        self.autoPlayRow = qtw.QVBoxLayout()
        self.autoPlayLabel = qtw.QLabel('When the print is done:')
        self.autoPlayRow.addWidget(self.autoPlayLabel)
        self.autoPlay1 = qtw.QRadioButton('Automatically start the next file')
        self.autoPlay2 = qtw.QRadioButton('Wait for the user to press play')
        if self.parent.autoPlay:
            self.autoPlay1.setChecked(True)
        else:
            self.autoPlay2.setChecked(True)
        self.autoPlayGroup = qtw.QButtonGroup()
        for i,b in enumerate([self.autoPlay1, self.autoPlay2]):
            self.autoPlayGroup.addButton(b, i)
            self.autoPlayRow.addWidget(b)
        self.autoPlayGroup.buttonClicked.connect(self.changeautoPlay)
        layout.addLayout(self.autoPlayRow)
        self.fsor = fileSetOpenRow(self, width=400, title='Set SBP folder', initFolder=self.parent.sbpFolder, tooltip='Open SBP folder')
        folderRow = self.fsor.makeDisplay()
        self.fsor.saveButt.clicked.connect(self.setSBPFolder)
        self.fsor.saveFolderLink.clicked.connect(self.openSBPFolder)
        
        layout.addLayout(folderRow)
        
        self.setLayout(layout)
        
    def changeautoPlay(self, autoPlayButton) -> None:
        '''Change autoPlay settings'''
        bid = self.autoPlayGroup.id(autoPlayButton) 
        if bid==0:
            self.parent.autoPlay = True
            self.parent.updateStatus('Turned on autoplay', True)
        else:
            self.parent.autoPlay = False
            self.parent.updateStatus('Turned off autoplay', True)
            
#     def updateFolder(self, folder:str) -> None:
#         self.parent.sbpFolder = folder

    def setSBPFolder(self) -> None:
        '''set the folder to save all the files we generate from the whole gui'''
        self.parent.sbpFolder = setFolder(self.parent.sbpFolder)        
        logging.info('Changed shopbot file folder to %s' % self.parent.sbpFolder)
        self.fsor.updateText(self.parent.sbpFolder)
            
    def openSBPFolder(self) -> None:
        '''Open the save folder in windows explorer'''
        openFolder(self.parent.sbpFolder)

        
            
###########################################



class sbBox(connectBox):
    '''Holds shopbot functions and GUI items'''
    
    
    ####################  
    ############## initialization functions
    
    
    def __init__(self, sbWin:qtw.QMainWindow):
        '''sbWin is the parent window that all of the widgets are in'''
        super(sbBox, self).__init__()
        self.bTitle = 'Shopbot'
        self.sbWin = sbWin
        self.runningSBP = False
        self.setTitle('Shopbot')
        self.prevFlag = 0
        self.currentFlag = 0
        self.sbpName = cfg.shopbot.sbpName
        self.sbpRealList = [self.sbpName]
        self.autoPlay = cfg.shopbot.autoplay 
        self.sbpFolder = cfg.shopbot.sbpFolder
        self.connect()

            
    def connect(self):
        '''connect to the SB3 software'''
        try:
            self.sb3File = findSb3()
            self.connectKeys()
        except:
            self.failLayout()
        else:
            self.successLayout()
            
    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        cfg1.shopbot.sbpName = self.getFullPath(self.sbpName)
        cfg1.shopbot.autoplay = self.autoPlay   
        cfg1.shopbot.sbpFolder = self.sbpFolder
        l = []
        for x in range(self.sbpNameList.count()):
            l.append(self.getFullPath(self.sbpNameList.item(x).text()))
        cfg1.shopbot.sbpFiles = l
        return cfg1
    
    def loadConfig(self, cfg1):
        '''load settings from a config Box object'''
        self.sbpName = cfg1.shopbot.sbpName
        self.autoPlay = cfg1.shopbot.autoplay  
        self.sbpFolder = checkPath(cfg1.shopbot.sbpFolder)
            
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
        
        self.settingsBox = sbSettingsBox(self)
        
        self.resetLayout()
            
        self.layout = qtw.QVBoxLayout()
        
        self.runButt = qtw.QPushButton()
        self.runButt.setFixedSize(50, 50)
        self.runButt.setEnabled(False)
#         self.runButt.setStyleSheet('border-radius:10px; padding:5px; border-style: outset; border: 2px solid #555;')
        self.updateRunButt()
        
        self.createStatus(725, height=50, status='Waiting for file ...')
#         self.status = qtw.QLabel('Waiting for file ...')
#         self.status.setFixedSize(725, 50)
#         self.status.setWordWrap(True)
        
        self.topBar = qtw.QHBoxLayout()
        self.topBar.addWidget(self.runButt)
        self.topBar.addWidget(self.status)
        self.topBar.setSpacing(10)
        
        self.loadButt = qtw.QToolButton()
        self.loadButt.setToolTip('Load shopbot file(s)')
        self.loadButt.setIcon(icon('open.png'))
        self.loadButt.clicked.connect(self.loadFile)
        
        self.deleteButt = qtw.QToolButton()
        self.deleteButt.setToolTip('Remove selected file(s)')
        self.deleteButt.setIcon(icon('delete.png'))
        self.deleteButt.clicked.connect(self.removeFiles)
        
        self.breakButt = qtw.QToolButton()
        self.breakButt.setToolTip('Add a breakpoint to the list')
        self.breakButt.setIcon(icon('breakpoint.png'))
        self.breakButt.clicked.connect(self.addBreakPoint)
        
        self.sbButts = qtw.QToolBar()
        self.sbButts.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        for b in [self.loadButt, self.deleteButt, self.breakButt]:
            self.sbButts.addWidget(b)
        self.sbButts.setStyleSheet("QToolBar{spacing:5px;}");
        self.sbButts.setOrientation(QtCore.Qt.Vertical)
        self.sbButts.setFixedHeight(180)

        self.sbpNameList = qtw.QListWidget()
        self.sbpNameList.setFixedHeight(180)
        for file in cfg.shopbot.sbpFiles:
            self.addFile(file)
#         self.addFile(self.sbpName)
        if os.path.exists(self.sbpName):
            self.activate(0)
            self.runButt.setEnabled(True)
            self.updateRunButt()
            self.updateStatus('Ready ... ', False)
        self.sbpNameList.itemDoubleClicked.connect(self.activate)
        self.sbpNameList.setAcceptDrops(True)
        self.sbpNameList.setSelectionMode(qtw.QAbstractItemView.MultiSelection)
        self.sbpNameList.setDragDropMode(qtw.QAbstractItemView.InternalMove)
        self.sbpNameList.setDragEnabled(True)
        self.sbpNameList.setToolTip('Double click to select the next file to run.\nSingle click to select files to delete.\nClick and drag to reorder.')
       
        self.fileButts = qtw.QHBoxLayout()
        self.fileButts.addWidget(self.sbButts)
        self.fileButts.addWidget(self.sbpNameList)
        self.fileButts.setSpacing(10)
        
        self.layout.addItem(self.topBar)
        self.layout.addItem(self.fileButts)
        try:
            self.layout.addItem(self.sbWin.fluBox.printButts)
        except:
            pass
 
        self.setLayout(self.layout)
    
    def reformatFileList(self) -> None:
        '''change the display of the file list'''
        showfolders = self.settingsBox.showFolderCheck.isChecked()
        
        for i,item in enumerate(self.sbpNameList.items()):
            if showfolders:
                item.setText(self.getFullPath(item.text()))
            else:
                item.setText(os.path.basename(item.text()))
        
    
    def updateRunButt(self) -> None:
        '''Update the appearance of the run button'''
        if self.runningSBP:
            try:
                self.runButt.clicked.disconnect()
            except:
                pass
            self.runButt.clicked.connect(self.triggerKill)
            self.runButt.setStyleSheet("background-color: #de8383; border-radius:10px")
            self.runButt.setToolTip('Stop print')
            self.runButt.setIcon(icon('stop.png'))
        else:
            try:
                self.runButt.clicked.disconnect()
            except:
                pass
            self.runButt.clicked.connect(self.runFile)
            self.runButt.setStyleSheet("background-color: #a3d9ba; border-radius:10px")
            self.runButt.setToolTip('Start print')
            self.runButt.setIcon(icon('play.png'))
        return


    def sbpNumber(self) -> int:
        '''Determine the index of the current file. Return -1 if it's not in the list.'''
        for i in range(self.sbpNameList.count()):
            if self.sbpNameList.item(i).data(QtCore.Qt.UserRole):
                return i
        return -1
    
    def updateItem(self, item:qtw.QListWidgetItem, active:bool) -> None:
        '''Update the item status to active or inactive'''
        if active:
            item.setIcon(icon('play.png')) # show that this item is next
            item.setData(QtCore.Qt.UserRole, True)
        else:
            item.setIcon(QtGui.QIcon()) # show that this item is not next
            item.setData(QtCore.Qt.UserRole, False)
        return
    
    
    def activate(self, item:Union[int, qtw.QListWidgetItem]) -> None:
        '''set the sbp file that the GUI will run next. Input can be item number or the actual item object.'''
        
        # get the actual item if given a number
        if type(item) is int:
            if item>=self.sbpNameList.count(): # this item is out of range
                logging.warning(f'Item out of range: requested {item} out of {self.sbpNameList.count()}')
            else:
                item = self.sbpNameList.item(item)
          
        # make sure this is a real file

        
        if not os.path.exists(self.getFullPath(item.text())) and not item.text()=='BREAK':
            logging.warning(f'Cannot activate {item.text()}: file not found')
            return
        
        # remove other play icons
        for i in range(self.sbpNameList.count()):
            self.updateItem(self.sbpNameList.item(i), False)
            
        self.sbpName = self.getFullPath(item.text()) # find the full path name of the item
#         self.sbpName = item.text() # new run file name
        self.updateItem(item, True)
        self.sbpNameList.scrollToItem(item, QtGui.QAbstractItemView.PositionAtTop) # scroll to the current item
        
            
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
        
        self.sbpRealList.append(fn)
        
        if fn=='BREAK':
            short=fn
        else:
            short = os.path.basename(fn)
        
        if self.settingsBox.showFolderCheck.isChecked():
            # show the full path name
            item = qtw.QListWidgetItem(fn) # create an item
        else:
            item = qtw.QListWidgetItem(short) # create an item with basename
        item.setData(QtCore.Qt.UserRole, False)
        self.sbpNameList.addItem(item) # add it to the list
        if self.sbpNameList.count()>1: # if there was already an item in the list
            item0 = self.sbpNameList.item(0) # take the first item
            if not os.path.exists(self.getFullPath(item0.text())) and not item0.text()=='BREAK': # if the original item isn't a real file
                self.activate(1) # activate the next item in the list
                self.sbpNameList.takeItem(0) # remove bad name from the list
                self.sbpRealList.pop(0) # remove bad name from full path list
        return
    
    def getFullPath(self, file:str) -> str:
        '''get the full path name of the file'''
        if file=='BREAK':
            return file
        for fullpath in self.sbpRealList:
            if file in fullpath:
                return fullpath
    
    def removeFiles(self) -> None:
        '''Remove the selected file from the list'''
        for item in self.sbpNameList.selectedItems():
            logging.info(f'Removing file from queue: {item.text()}')
#             if item.text()==self.sbpName:
            if item.data(QtCore.Qt.UserRole):
                # we're removing the current file. go to the next file.
                self.activateNext()

            self.sbpRealList.remove(self.getFullPath(item.text())) # remove the file from the list of full paths
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
            openFolder = self.sbpFolder
            if not os.path.exists(openFolder):
                openFolder = r'C:\\'
        sbpnList = fileDialog(openFolder, 'Gcode files (*.gcode *.sbp)', False)
        for sbpn in sbpnList:
            if not os.path.exists(sbpn):
                logging.error(f'{sbpn} does not exist')
            else:
                self.runButt.setEnabled(True)
                self.updateRunButt()
                self.addFile(sbpn)
                logging.debug(f'Added file to queue: {sbpn}')
                self.updateStatus('Ready ... ', False)
                
    def addBreakPoint(self) -> None:
        '''add a stop point to the list of files, where autoplay will stop'''
        self.addFile('BREAK')
        self.updateStatus('Added break point', False)
            
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
    
    def findStageSpeed(self) -> float:
        '''find the stage speed from the current shopbot file'''
        with open(self.sbpName, mode='r') as f:
            cont = True
            l = 'a'
            while cont and len(l)>0:
                l = f.readline()
                if l.startswith('MS'):
                    cont = False
        if len(l)==0:
            return -1
        else:
            return float(re.split(',|\n',l)[1])
    
                
    def saveSpeeds(self) -> None:
        '''create a csv file that describes the run speeds'''
        try:
            fullfn = self.sbWin.newFile('speeds', '.csv')
        except NameError:
            self.updateStatus('Failed to save speed file', True)
            return

        with open(fullfn, mode='w', newline='', encoding='utf-8') as c:
            writer = csv.writer(c, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for i in range(len(self.sbWin.fluBox.pchannels)):
                channel = self.sbWin.fluBox.pchannels[i]
                press = int(channel.constBox.text())
                writer.writerow([f'ink pressure channel {i}','mbar', press])
            inkspeed = self.sbWin.calibDialog.speedBox.text()
            writer.writerow(['ink speed', 'mm/s', inkspeed])
            supspeed = self.findStageSpeed()
            writer.writerow(['support speed', 'mm/s', supspeed])
            caliba = self.sbWin.calibDialog.plot.a
            writer.writerow(['caliba', 'mm/s/mbar^2', caliba])
            calibb = self.sbWin.calibDialog.plot.b
            writer.writerow(['calibb', 'mm/s/mbar', calibb])
            calibc = self.sbWin.calibDialog.plot.c
            writer.writerow(['calibc', 'mm/s', calibc])
            self.updateStatus(f'Saved {fullfn}', True)
    
    def runFile(self) -> None:
        '''runFile sends a file to the shopbot and tells the GUI to wait for next steps'''
        if not os.path.exists(self.sbpName):
            if self.sbpName=='BREAK':
                self.updateStatus('Break point hit.', True)
            else:
                self.updateStatus('SBP file does not exist: ' + self.sbpName, True)
            self.runningSBP=False
            self.updateRunButt()
            self.activateNext()
            return
        
#         self.abortButt.setEnabled(True)


        
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
        self.updateRunButt()
        self.triggerWait()
        
    
    ### wait to start videos and fluigent
    
    def triggerWait(self) -> None:
        '''start the timer that watches for the start of print'''
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.waitForStartTimerFunc)
        self.timer.start(cfg.shopbot.dt) # update every 100 ms
        
    
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
        self.updateStatus(f'Waiting to start file, Shopbot output flag = {sbFlag}, start at {cf}', False)
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
        self.timer.start(cfg.shopbot.dt) # update every 100 ms
        
        # start the cameras if any flow is triggered in the run
        if min(self.channelsTriggered)<len(self.sbWin.fluBox.pchannels):
            for camBox in self.sbWin.camBoxes:
                if camBox.camInclude.isChecked() and not camBox.camObj.recording:
                    camBox.cameraRec()
        if len(self.channelsTriggered)>0 and not self.channelsTriggered==[2]:
            # only record if there is extrusion
            self.saveSpeeds() 
            self.sbWin.fluBox.startRecording()
    
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
#                     QtCore.QTimer.singleShot(500, lambda:fgt.fgt_set_pressure(i,press))
#                     fgt.fgt_set_pressure(i, press)

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
      
    def stopRunning(self) -> None:
        '''stop watching for changes in pressure, stop recording  '''
        if self.runningSBP:
            self.sbWin.fluBox.resetAllChannels(-1) # turn off all channels
            self.sbWin.fluBox.stopRecording()  # save fluigent
            for camBox in self.sbWin.camBoxes:
                if camBox.camInclude.isChecked() and camBox.camObj.recording: 
                    camBox.cameraRec() # stop recording
            try:
                self.timer.stop()
            except:
                pass
        
    def triggerKill(self) -> None:
        '''the stop buttonw was hit, so stop'''
        self.stopRunning()
        self.activateNext() # activate the next sbp file in the list
        self.runningSBP = False # we're no longer running a sbp file
        self.updateRunButt()
        self.updateStatus('Stop button was clicked', False)
        
    def triggerEndOfPrint(self) -> None:
        '''we finished the file, so stop and move onto the next one'''
        self.stopRunning()
        self.activateNext() # activate the next sbp file in the list
        if self.autoPlay and self.sbpNumber()>0: # if we're in autoplay and we're not at the beginning of the list, play the next file
            self.updateStatus('Autoplay is on: Running next file.', True)
            
#             timer = QtCore.QTimer()  # set up your QTimer
#             timer.timeout.connect(self.runFile)  # connect it to your update function
#             timer.start(1000)  # set it to timeout in 5000 ms
            
            QtCore.QTimer.singleShot(2000, self.runFile)
#             self.runFile()
        else:
            self.runningSBP = False # we're no longer running a sbp file
            self.updateRunButt()
            self.updateStatus('Ready', False)


    #-----------------------------------------
    
    
    def close(self):
        '''this gets triggered when the whole window is closed'''
        try:
            self.timer.stop()
        except:
            pass
        else:
            logging.info('Shopbot timer stopped')

