#!/usr/bin/env python
'''Shopbot GUI functions for creating camera GUI elements'''

# external packages
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QRunnable, QThreadPool, QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap, QIntValidator
from PyQt5.QtWidgets import QButtonGroup, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QRadioButton, QToolBar, QToolButton, QVBoxLayout, QWidget
import cv2
import time
import datetime
import numpy as np
import os, sys
import subprocess
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import pandas as pd
import itertools

# local packages
from general import *
from camObj import *
from cam_bascam import *
from cam_webcam import *
from config import cfg
   
################################################
        
class camSettingsBox(QWidget):
    '''This opens a window that holds settings about logging for cameras.'''
    
    
    def __init__(self, parent:connectBox, bTitle:str, camObj:camera):
        '''parent is the connectBox that this settings dialog belongs to. 
            bTitle is the box title, e.g. webcam 2. 
            camObj is the camera object that holds functions and info for a specific camera.'''
        
        super().__init__(parent)  
        self.camObj = camObj
        self.camBox = parent
        
        layout = QVBoxLayout()
        form = QFormLayout()
        setAlign(form, 'left')
        form.addRow('Type', QLabel(self.camObj.type))
        
        w = 100
              
        self.diagGroup = fRadioGroup(None, '', 
                                          {0:'None', 1:'Just critical', 2:'All frames'}, 
                                          {0:0, 1:1, 2:2},
                                         self.camObj.diag, col=False, headerRow=False,
                                          func=self.changeDiag)
        form.addRow("Log", self.diagGroup.layout)
        objValidator3 = QIntValidator(cfg.shopbot.flag1min,cfg.shopbot.flag1max)
        self.flagBox = fLineEdit(form, title='SB output flag'
                                 , text=str(self.camObj.flag1)
                                 , tooltip='1-indexed Shopbot output flag that triggers snaps on this camera.'
                                 , func=self.updateFlag
                                , validator=objValidator3
                                , width=w)

        fpsRow = QHBoxLayout()
        self.fpsBox = fLineCommand(layout=fpsRow, text=str(self.camObj.fps), func = self.updateVars, width=w
                                  , tooltip='How many frames are collected per second')
        self.fpsAutoButt = fButton(fpsRow, title='Auto', func=self.fpsAuto, width=w)
        form.addRow('Collection frame rate (fps)', fpsRow)
        
        recfpsRow = QHBoxLayout()
        self.recfpsBox = fLineCommand(layout=recfpsRow, text=str(self.camObj.recFPS), func=self.updateVars, width=w
                                         , tooltip='Frame rate for saved videos. Downsamples if less than fps')
        form.addRow('Export frame rate (fps)', recfpsRow)
        
        pfpsRow = QHBoxLayout()
        self.pfpsBox = fLineCommand(layout=pfpsRow, text=str(self.camObj.previewFPS), func=self.updateVars, width=w
                                   , tooltip='How many times per second the display is updated')
        form.addRow('Preview frame rate (fps)', pfpsRow)
        
        exposureRow = QHBoxLayout()
        self.exposureBox = fLineCommand(layout=exposureRow, text=str(self.camObj.exposure), func=self.updateVars, width=w)
        self.exposureAutoButt = fButton(exposureRow, title='Auto', func=self.exposureAuto, width=w)
        self.exposureAutoButt.setEnabled(False)   # exposure auto doesn't work yet
        if self.camObj.guiBox.type=='webcam':
            # webcam. exposure doesn't work
            self.enableExposureBox = False
            self.exposureBox.setEnabled(False)
        elif self.camObj.guiBox.type=='bascam':
            self.enableExposureBox = True

        form.addRow('Exposure (ms)', exposureRow)
        layout.addLayout(form)
        self.setLayout(layout)

        
    def changeDiag(self, diagbutton):
        '''Change the diagnostics status on the camera, so we print out the messages we want.'''
        self.camObj.updateDiag(self.diagGroup.value())
        logging.info(f'Changed logging mode on {self.camObj.cameraName}.')
        
            
    def updateVars(self):
        '''Update the set variables'''
        self.updateFPS()
        if self.enableExposureBox:
            self.updateExposure()
            
    def updateFlag(self):
        flag1 = int(self.flagBox.text())
        self.camObj.flag1 = flag1
        self.camBox.flag1 = flag1
        self.camBox.sbWin.flagBox.labelFlags()
        
    #--------------------------
    # fps

    def exposureStatus(self):
        '''Log the change in exposure time'''
        if self.camObj.diag>0:
            self.camObj.updateStatus(f'Changed exposure to {self.camObj.exposure} ms', True)
        
    def updateExposure(self):
        '''Update the exposure used by the GUI to the given exposure'''
        out = self.camObj.setExposure(float(self.exposureBox.text()))
        if out==0:
            self.exposureStatus()
            
    def exposureAuto(self):
        '''Automatically adjust the exposure'''
        out = int(self.camObj.exposureAuto())
        if out==0:
            self.exposureBox.setText(str(self.camObj.exposure))
            self.exposureStatus()
        
            
    #--------------------------
    # fps

    def fpsStatus(self):
        '''Log the change in fps'''
        if self.camObj.diag>0:
            self.camObj.updateStatus(f'Changed frame rate to {self.camObj.fps} fps', True)
            
    def pfpsStatus(self):
        '''Log the change in fps'''
        if self.camObj.diag>0:
            self.camObj.updateStatus(f'Changed preview frame rate to {self.camObj.previewFPS} fps', True)
            
    def recfpsStatus(self):
        '''Log the change in recording fps'''
        if self.camObj.diag>0:
            self.camObj.updateStatus(f'Changed export frame rate to {self.camObj.recFPS} fps', True)
        
    def updateFPS(self):
        '''Update the frame rate used by the GUI to the given frame rate'''
        
        # preview
        pfps = float(self.pfpsBox.text())
        if pfps>self.camObj.fps:
            logging.warning('Preview frame rate must be less than or equal to collection frame rate')
            self.pfpsBox.setText(str(self.camObj.previewFPS))
        else:
            out = self.camObj.setPFrameRate(pfps)   # update preview fps
            if out==0:
                self.pfpsStatus()
                
        # collection
        out = self.camObj.setFrameRate(float(self.fpsBox.text())) # update fps
        if out==0:
            self.fpsStatus()
            
        # recording
        recFPS = float(self.recfpsBox.text())
        if recFPS>self.camObj.fps:
            logging.warning('Recording frame rate must be less than or equal to collection frame rate')
            self.recfpsBox.setText(str(self.camObj.recFPS))
        else:
            recFPS2 = self.camObj.fps/max(np.ceil(self.camObj.fps/recFPS),1)
            if not recFPS2==recFPS:
                logging.info(f'FPS must be divisible by recording fps. Changing recording fps to {recFPS2}')
                self.recfpsBox.setText(str(recFPS2))
            out = self.camObj.setRecFrameRate(recFPS2) # update fps
            if out==0:
                self.fpsStatus()
            
    def resetFPS(self, fps:float):
        '''reset the displayed frame rate to the given frame rate'''
        self.fpsBox.setText(str(fps))
        
    def resetRecFPS(self, recFPS:float):
        '''reset the displayed frame rate to the given frame rate'''
        self.recfpsBox.setText(str(recFPS))
        
            
    def fpsAuto(self):
        '''Automatically adjust the frame rate to the frame rate of the camera'''
        out = self.camObj.setFrameRateAuto()
        if out==0:
            self.fpsBox.setText(str(self.camObj.fps))
            self.fpsStatus()

            
            
###################################################################################################

class cameraBox(connectBox):
    '''widget that holds camera objects and displays buttons and preview frames'''
    
    def __init__(self, cname:str, cdict:dict, sbWin:QMainWindow):
        '''cname is the name of the camera, e.g. cam0
        cdict is a dictionary holding information about the camera, from config.yml
        sbWin is the parent window that this box sits inside of.'''
        super(cameraBox, self).__init__()
        self.cname = cname
        self.mode = int(cname[3:])   # camera number
        self.model = ''              # name of camera
        self.cdict = cdict
        self.connected = False
        self.previewing = False
        self.recording = False
        self.imw=0
        self.imh=0
        self.img = []
        self.bTitle = cdict['name']
        self.type = cdict['type']
        self.flag1 = cdict['flag1']
        self.sbWin = sbWin
        self.connect() # try to connect to the camera
        self.updateBoxTitle()
        if self.connected:
            self.camObj.loadDict(cdict)
            if self.camObj.diag>0:
                logging.info(self.bTitle, ' ', self.camObj.fps, ' fps')
        
        
    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        cfg1.camera[self.cname].name = self.bTitle
        cfg1.camera[self.cname].type = self.type
        cfg1.camera[self.cname].flag1 = self.flag1
        if hasattr(self, 'camInclude'):
            cfg1.camera[self.cname].checked = self.camInclude.isChecked()
        self.camObj.saveConfig(cfg1)
        return cfg1
    
    def loadConfig(self, cfg1):
        '''load settings from a config Box object'''
        self.bTitle = cfg1.camera[self.cname].name
        self.type = cfg1.camera[self.cname].type
        self.flag1 = cfg1.camera[self.cname].flag1
        self.camObj.loadConfig(cfg1)
        self.camInclude.setChecked(cfg1.camera[self.cname].checked)
        self.updateCamInclude()
        
    def resetFPS(self, fps:int):
        self.settingsBox.resetFPS(fps)
        
    def resetRecFPS(self, fps:int):
        self.settingsBox.resetRecFPS(fps)

    
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
             
        if self.type=='bascam':
            self.camObj = bascam(sbWin, self)
        elif self.type=='webcam':
            self.camObj = webcam(sbWin, self)
        else:
            logging.error(f'No functions found for camera type {self.type}')
            self.failLayout()
            return 
        
        if self.camObj.connected:
            self.connected = True
            self.successLayout()
        else:
            self.failLayout() # inherited from connectBox
            
    
    def successLayout(self) -> None:
        '''this is the layout if we successfully connected to the camera'''
        
        self.settingsBox = camSettingsBox(self, self.bTitle, self.camObj)
        
        self.resetLayout()
        self.layout = QVBoxLayout()
        
        self.camInclude = fToolButton(None, func=self.updateCamInclude, checkable=True)
        self.camInclude.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.camInclude.setChecked(cfg.camera[self.cname].checked)
        self.updateCamInclude() 
        self.camButts = fToolBar(vertical=False)

        self.camPrev = fToolButton(self.camButts, func=self.cameraPrev, checkable=True)
        self.setPrevButtStart()
        self.camRec = fToolButton(self.camButts, func=self.cameraRec, checkable=True)
        self.setRecButtStart()
        self.camPic = fToolButton(self.camButts, icon='camera.png',func=self.cameraPic, tooltip='Snapshot')
        self.camPic.setStyleSheet(self.unclickedSheet())
        self.camButts.setMinimumWidth((self.camButts.iconSize().width()+20)*self.camButts.buttons)

        self.createStatus(self.camObj.imw - (self.camButts.iconSize().width()+20)*self.camButts.buttons, height=90)
        self.layout.addLayout(fHBoxLayout(self.camButts, self.status))
        
        self.layout.addStretch(1)
        
        self.layout.addWidget(self.camObj.prevWindow)
        self.setLayout(self.layout)
        
        
    #------------------------------------------------
    # functions to trigger camera actions and update the GUI
    
    @pyqtSlot()
    def cameraPic(self) -> None:
        '''capture a single frame'''
        if self.connected:
            self.camObj.snap()
        else:
            logging.info(f'Cannot take picture: {self.bTitle} not connected')
       
    
    def cameraPrev(self) -> None:
        '''start or stop previewing and update button appearance'''
        if not self.camObj.connected:
            return
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
        if not self.camObj.connected:
            return
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
            
            
        
    def startRecording(self) -> None:
        '''start all checked cameras recording'''
        if not hasattr(self, 'camObj'):
            return
        
        if self.camObj.connected:
            if self.camInclude.isChecked() and not self.camObj.recording:
                self.cameraRec()
                    
    def stopRecording(self) -> None:
        '''stop all checked cameras recording'''
        if not hasattr(self, 'camObj'):
            return
        
        if self.camObj.connected:
            if self.camInclude.isChecked() and self.camObj.recording: 
                self.cameraRec() # stop recording
        
    #------------------------------------------------
    #  functions to change appearance of buttons when they're pressed
    
    def clickedBoth(self) -> str:
        '''appearance of all of the camera box buttons'''
        
        return 'border:none; \
        padding:3px; \
        border-radius:3px;'
    
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
            self.camInclude.setIcon(icon('save.png'))
            self.camInclude.setToolTip('Videos will be exported during print')
        else:
            self.camInclude.setStyleSheet(self.unclickedSheet())
            self.camInclude.setText('Autosave is off')
            self.camInclude.setIcon(icon('nosave.png'))
            self.camInclude.setToolTip('Videos will not be exported during print')
        
    def setPrevButtStart(self) -> None:
        '''Update preview button appearance to not previewing status'''
        self.camPrev.setStyleSheet(self.unclickedSheet())
#         self.camPrev.setText('Start preview')
        self.camPrev.setIcon(icon('closedeye.png'))
        self.camPrev.setToolTip('Start live preview') 
        
    def setPrevButtStop(self) -> None:
        '''Update preview button appearance to previewing status'''
        self.camPrev.setStyleSheet(self.clickedSheet())
#         self.camPrev.setText('Stop preview')
        self.camPrev.setIcon(icon('eye.png'))
        self.camPrev.setToolTip('Stop live preview') 

    def setRecButtStart(self) -> None:
        '''Update record button appearance to not recording status'''
        self.camRec.setStyleSheet(self.unclickedSheet())
        self.camRec.setIcon(icon('Record.png'))
        self.camRec.setToolTip('Start recording') 
        
    def setRecButtStop(self) -> None:
        '''Update record button appearance to recording status'''
        self.camRec.setStyleSheet(self.clickedSheet())
        self.camRec.setIcon(icon('recordstop.png'))
        self.camRec.setToolTip('Stop recording') 
        
    @pyqtSlot()
    def tempCheck(self):
        '''set checked during run'''
        if hasattr(self, 'camInclude'):
            self.oldChecked = self.camInclude.isChecked()
            self.camInclude.setChecked(True)
        
    @pyqtSlot()
    def resetCheck(self):
        if hasattr(self, 'camInclude'):
            self.camInclude.setChecked(self.oldChecked)


    #-----------------------------------------------
    
    def updateBoxTitle(self) -> None:
        '''updates the title of widget box'''
        self.setTitle(f'{self.bTitle}\t{self.model}')
        
    def writeToTable(self, writer) -> None:
        '''writes metadata to the csv writer'''
        if hasattr(self, 'camObj'):
            self.camObj.writeToTable(writer)

    def close(self) -> None:
        '''gets triggered when the window is closed. Disconnects GUI from camera.'''
        if hasattr(self, 'camObj'):
            self.camObj.close()
#         self.settingsDialog.done()



class camBoxes:
    '''holds the camera boxes'''
    
    def __init__(self, sbWin:QMainWindow,  connect:bool=True):
        self.webcams = 0
        self.sbWin = sbWin
        self.stopTest = False
        if connect:
            self.connect()
        else:
            self.list = [connectBox()]
            
    def connect(self)->None:
        '''connect the cameras'''
        self.webcams = 0
        self.list = [cameraBox(d, cfg.camera[d], self.sbWin) for d in cfg.camera]   # initialize cameras
        self.names = [cfg.camera[d].name for d in cfg.camera]
        
    def startRecording(self) -> None:
        '''start all checked cameras recording'''
        for camBox in self.list:
            camBox.startRecording()
                    
    def stopRecording(self) -> None:
        '''stop all checked cameras recording'''
        for camBox in self.list:
            camBox.stopRecording()
            
    def listFlags0(self) -> dict:
        '''get a dictionary of 0-indexed flags and cameras'''
        return dict([[camBox.flag1-1, camBox] for camBox in self.list])
            
            
    def findFlag(self, flag0:int) -> Tuple[bool, cameraBox]:
        '''find the camBox that matches the flag. return True, camBox if we found one, otherwise return False, empty'''
        for camBox in self.list:
            if camBox.flag1==flag0+1:
                return True, camBox
        return False, None
    
    def autoSaveLayout(self, vert:bool=True):
        '''row or column of autosave camera buttons'''
        layout = QGridLayout()
        row = 0
        col = 0
        for camBox in self.list:
            if hasattr(camBox, 'camObj'):
                layout.addWidget(QLabel(camBox.camObj.cameraName), row, col)
                col = col+1
                if hasattr(camBox, 'camInclude'):
                    layout.addWidget(camBox.camInclude, row, col)
                    if vert:
                        row = row+1
                        col = 0
                    else:
                        col = col+1
            else:
                logging.debug(f'No camera object in {camBox.bTitle}')
        layout.setSpacing(5)
        fhb = fHBoxLayout(layout)
        fhb.addStretch()
        
        return fhb
    
    def writeToTable(self, writer) -> None:
        '''writes metadata to the csv writer'''
        for camBox in self.list:
            camBox.writeToTable(writer)
            
    def dropTest(self, times:List[float], testlist:List[dict]):
        '''count dropped frames under multiple conditions'''
        self.stopTest = False
        cams = []
        for box in self.list:
            cams.append(box.bTitle)

        self.tlist = []
        self.dropTestList = []
        for d in testlist:
            for t in times:
                d['time'] = t
                self.dropTestList.append(d)
        
        self.dropLoop()
                    
    def dropTestEnd(self):
        '''finish the drop test'''
        df = pd.DataFrame(self.tlist)
        date = datetime.datetime.now().strftime("%y%m%d_%H%M%S")
        fn = os.path.join(cfg.testFolder, f'dropTest_{date}.csv')
        df.to_csv(fn, index=False)
        logging.info(f'Exported {fn}')
        
    def dropLoop(self) -> None:
        '''on each loop, add to the end'''
        
        if len(self.dropTestList)==0 or self.stopTest:
            # no more tests
            self.dropTestEnd()
            return
        dt = self.dropTestList.pop(0)
        self.dti = dropTest(dt['rec'], dt['prev'], self)
        self.dti.test(dt['time'], dt['i'])
        
    def dropLoopEnd(self):
        self.tlist.append(self.dti.result)
        self.dropLoop()
                    
    def close(self) -> None:
        for camBox in self.list:
            camBox.close()
            
           
    
            
            
#-------------------
# tests

def str2strList(s):
    '''convert the string to a list of list of strings'''
    return [(l.split('[')[-1]).split(',') for l in list(s.split(']'))[:-1]]

class dropTestDialog(QDialog):
    '''Creates a window for running drop tests'''
    
    def __init__(self, sbWin):
        '''This is called by the sbWin, which is the main SBwindow'''
        super().__init__(sbWin)
        self.sbWin = sbWin
        self.layout= QVBoxLayout()
        self.form = QFormLayout()
        self.times = [20]
        
        self.combos = {}
        self.comboi = 0
        self.cameras = dict([[i,name] for i,name in enumerate(self.sbWin.camBoxes.names)])
        self.numcams = len(self.cameras)
        self.grid = QGridLayout()
        self.grid.addWidget(QLabel(''), 1,1)
        self.grid.addWidget(QLabel('Include'), 1,2)
        self.colors = ['#B80C09', '#0B4F6C', '#01BAEF', '#040F16', '#80858B']
        for i,name in self.cameras.items():
            label = QLabel(name)
            label.setStyleSheet(f'color: {self.colors[i]}')
            self.grid.addWidget(label, 1, 2*(i+1)+1, 1, 2)
        for ls in sorted(set(itertools.permutations([True for x in range(self.numcams*2)]+[False for x in range(self.numcams*2-1)], self.numcams*2))):
            # iterate through combos of on/off of camera rec and prev
            self.newCombo(ls)  
        
        for r in [['Basler camera'],['Basler camera', 'Nozzle camera'], ['Basler camera', 'Nozzle camera', 'Webcam 2'], ['Nozzle camera']]:
            for p in [[], ['Basler camera'],['Basler camera', 'Nozzle camera', 'Webcam 2']]:
                for i, d in self.combos.items():
                    if d['rec']==r and d['prev']==p:
                        d['checkbox'].setChecked(True)
        self.layout.addLayout(self.grid)
        self.timeEdit = fLineEdit(self.form, title='Times', text=str(self.times)[1:-1], tooltip='How long to run videos')
        self.go = fButton(self.form, title='Go', tooltip='Run test', func=self.runDropTest)
        self.stop = fButton(self.form, title='stop', tooltip='Stop test', func=self.stopTest)
        self.layout.addLayout(self.form)
        self.setLayout(self.layout)
        
    def newCombo(self, t:tuple) -> None:
        '''create a new combination of camera recording/previewing based on a true/false list'''  
        rec = []
        prev = []
        icons = []
        
        for i,name in self.cameras.items():
            r = t[2*(i)]
            p = t[2*(i)+1]
            if r:
                rec.append(name)
                l = 'R'
            else:
                l = ''
            label = QLabel(l)
            label.setStyleSheet(f'color: {self.colors[i]}')
            icons.append(label)
            if p:
                prev.append(name)
                l = 'P'  # put a prev icon in the grid for this row for this camera
            else:
                l = ''
            label = QLabel(l)
            label.setStyleSheet(f'color: {self.colors[i]}')
            icons.append(label)
            
                
        if len(rec)==0:
            # if we're not recording anything, don't add the combo
            return
        
        # create layout
        checkbox = fCheckBox(None, tooltip='Do this test')
        self.grid.addWidget(QLabel(str(self.comboi)), self.comboi+2, 1)
        self.grid.addWidget(checkbox, self.comboi+2, 2)
        for i,ic in enumerate(icons):
            if not type(ic) is str:
                self.grid.addWidget(ic, self.comboi+2, i+3)
        
        # create lists
        self.combos[self.comboi] = {'i':self.comboi, 'rec':rec, 'prev':prev, 'checkbox':checkbox}
        self.comboi+=1
        
    def getLists(self) -> None:
        '''get the list of cameras included in the tests'''
        self.testlists = []
        for i,d in self.combos.items():
            if d['checkbox'].isChecked():
                self.testlists.append(d)
        

    def runDropTest(self):
        '''run the drop test'''
        self.times = [float(t) for t in list(self.timeEdit.text().replace(' ','').split(','))]
        self.getLists()
        self.sbWin.camBoxes.dropTest(self.times, self.testlists)
        
    def stopTest(self):
        self.sbWin.camBoxes.stopTest = True
        
        

class dropTest(QObject):
    '''test the dropped frames. rec is a list of camera names to record, prev is a list of camera names to preview. camera names are in cfg.camera.name, e.g. 'Basler camera', 'Nozzle camera', 'Webcam 2' '''
    
    def __init__(self, rec:list, prev:list, parent:camBoxes):
        super().__init__()
        
        self.parent = parent
        self.boxList = parent.list
        self.rec = rec
        self.prev = prev
        
    
    def triggerPrev(self, box):
        '''start/stop previewing'''
        box.cameraPrev()

    def triggerRec(self, box):
        '''start/stop recording'''
        box.cameraRec()

    def triggerBoxes(self, prev:bool):
        '''start/stop recording on all boxes. prev=True to start/stop previewing, prev=False to start/stop recording'''
        for box in self.boxList:
            cname = box.bTitle
            if prev:
                if cname in self.prev:
                    self.triggerPrev(box)
            else:
                if cname in self.rec:
                    self.triggerRec(box)

    def triggerAll(self):
        '''start all previewing and recording or not'''
        self.triggerBoxes(True)
        self.triggerBoxes(False)
        
    def triggerDone(self):
        '''triggers when the loop is done'''
        logging.info(f'Counting frames')
        self.triggerAll()
        self.waitForWritingDone()
            
    def waitForWritingDone(self):
        writing = False
        for box in self.boxList:
            if box.camObj.writing:
                writing = True
        if writing:
            # wait for the file to be done writing
            logging.info('Waiting for writing to finish')
            QTimer.singleShot(1000, self.waitForWritingDone)
            return
        else:
            dropVals = self.checkDropped()  # count frames
            meta = self.meta()
            self.result = {**meta, **dropVals}
            QTimer.singleShot(1000, self.parent.dropLoopEnd) # pause 1 second to avoid thread conflict
        
        
    def checkDropped(self):
        '''check for dropped frames'''
        
        dropped = {}
        for box in self.boxList:
            cname = box.bTitle
            if cname in self.rec or cname in self.prev:
                dropped[f'{cname}_fps'] = box.camObj.fps
                dropped[f'{cname}_recfps'] = box.camObj.recFPS
                dropped[f'{cname}_prevfps'] = box.camObj.previewFPS
            else:
                dropped[f'{cname}_fps'] = None
                dropped[f'{cname}_recfps'] = None
                dropped[f'{cname}_prevfps'] = None
            if cname in self.rec:
                timeRec = box.camObj.timeRec
                dropped[f'{cname}_time'] = timeRec
                frames = int(np.floor(box.camObj.totalFrames*box.camObj.recFPS/box.camObj.fps))
                dropped[f'{cname}_frames'] = frames
                dropped[f'{cname}_dropped'] = box.camObj.framesDropped
                dropped[f'{cname}_pct_dropped'] = dropped[f'{cname}_dropped']/dropped[f'{cname}_frames']
                vn = box.camObj.vFilename
                if os.path.exists(vn):
                    video = cv2.VideoCapture(vn)
                    fps = video.get(cv2.CAP_PROP_FPS)
                    frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
                    duration = frame_count/fps
                    dropped[f'{cname}_realtime'] = duration
                    dropped[f'{cname}_realframes'] = frame_count
                    video.release()
                    dropped[f'{cname}_timeError'] = (duration-timeRec)/timeRec
                    dropped[f'{cname}_frameError'] = (frame_count-frames)/frames
            else:
                dropped[f'{cname}_time'] = None
                dropped[f'{cname}_frames'] = None
                dropped[f'{cname}_dropped'] = None
                dropped[f'{cname}_pct_dropped'] = None
                dropped[f'{cname}_realtime'] = None
                dropped[f'{cname}_realframes'] = None
                dropped[f'{cname}_timeError'] = None
                dropped[f'{cname}_frameError'] = None
            
        
        return dropped

    def meta(self):
        '''metadata for this test'''
        meta = {}
        for box in self.boxList:
            cname = box.bTitle
            meta[f'{cname}_prev'] = (cname in self.prev)
            meta[f'{cname}_rec'] = (cname in self.rec)

        return meta

    def test(self, times:float, i:int):
        '''test for dropped frames. time is in s'''
        logging.info(f'Starting test {i} for rec={self.rec}, prev={self.prev}, time={times}s')
        self.triggerAll()   # start previewing and recording
        QTimer.singleShot(times*1000, self.triggerDone) # stop previewing and recording

    
def sub_lists(l):
    return [list(li) for li in list(chain(*map(lambda x: combinations(l, x), range(0, len(l)+1))))]
        
        
    
        
    
