#!/usr/bin/env python
'''Shopbot GUI functions for creating camera GUI elements'''

# external packages
from PyQt5.QtCore import pyqtSignal, QObject, QRunnable, QThreadPool, QTimer, Qt
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

# local packages
from sbgui_general import *
from sbgui_camObj import *
from config import cfg


try:
    os.environ["PYLON_CAMEMU"] = "3"
    from pypylon import genicam
    from pypylon import pylon
except:
    logging.warning('Pylon SDK not installed')
    pass

           
#########################################################
#########################################################
######################## CAMERAS #######################
#########################################################
#########################################################

            
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
        self.fpsBox = fLineCommand(layout=fpsRow, text=str(self.camObj.fps), func = self.updateVars, width=w)
        self.fpsAutoButt = fButton(fpsRow, title='Auto', func=self.fpsAuto, width=w)
        form.addRow('Frame rate (fps)', fpsRow)
        
        pfpsRow = QHBoxLayout()
        self.pfpsBox = fLineCommand(layout=pfpsRow, text=str(self.camObj.previewFPS), func=self.updateVars, width=w)
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
        self.camObj.diag = self.diagGroup.value()
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
        
    def updateFPS(self):
        '''Update the frame rate used by the GUI to the given frame rate'''
        out = self.camObj.setPFrameRate(float(self.pfpsBox.text()))   # update preview fps
        if out==0:
            self.pfpsStatus()
        out = self.camObj.setFrameRate(float(self.fpsBox.text())) # update fps
        if out==0:
            self.fpsStatus()
            
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
        self.camObj.saveConfig(cfg1)
        return cfg1
    
    def loadConfig(self, cfg1):
        '''load settings from a config Box object'''
        self.bTitle = cfg1.camera[self.cname].name
        self.type = cfg1.camera[self.cname].type
        self.flag1 = cfg1.camera[self.cname].flag1
        self.camObj.loadConfig(cfg1)

    
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
    
    def cameraPic(self) -> None:
        '''capture a single frame'''
        self.camObj.snap()
       
    
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
        if connect:
            self.connect()
        else:
            self.list = [connectBox()]
            
    def connect(self)->None:
        '''connect the cameras'''
        self.webcams = 0
        self.list = [cameraBox(d, cfg.camera[d], self.sbWin) for d in cfg.camera]   # initialize cameras
        
    def startRecording(self) -> None:
        '''start all checked cameras recording'''
        for camBox in self.list:
            camBox.startRecording()
                    
    def stopRecording(self) -> None:
        '''stop all checked cameras recording'''
        for camBox in self.list:
            camBox.stopRecording()
            
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
                    
    def close(self) -> None:
        for camBox in self.list:
            camBox.close()
        
        
    
        
    
