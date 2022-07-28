#!/usr/bin/env python
'''Shopbot GUI functions for handling webcams'''

# external packages
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QMutex, QObject, QRunnable, QThreadPool, QTimer, Qt
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
from general import *
from camThreads import *
from camObj import *
from config import cfg



##################

class webcamVC(vc):
    '''holds a videoCapture object that reads frames from a webcam. lock this so only one thread can collect frames at a time'''
    
    def __init__(self, webcamNum:int, cameraName:str, diag:int):
        super(webcamVC, self).__init__(cameraName, diag)
        self.webcamNum = webcamNum
        self.connectVC()
        

        
    def connectVC(self):
        try:
            self.camDevice = cv2.VideoCapture(self.webcamNum, cv2.CAP_DSHOW)
        except Exception as e:
            logging.info(f'Failed connect to {self.cameraName}: {e}')
            self.connected = False
            return
        else:
            self.connected = True
            
    def getFrameRate(self) -> float:
        '''Determine the native device frame rate'''
        fps = self.camDevice.get(cv2.CAP_PROP_FPS)/2 # frames per second
        if fps>0:
            return int(fps)
        else:
            self.updateStatus(f'Invalid auto frame rate returned from {self.cameraName}: {fps}', True)
            return 0

    def getExposure(self):
        '''Read the current exposure on the camera'''
        return 1000*2**self.camDevice.get(cv2.CAP_PROP_EXPOSURE)
        
    def exposureAuto(self):
        '''Automatically adjust the exposure.'''
#         self.camDevice.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
#         self.getExposure()

#         self.camDevice.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
#         if self.diag>1:
#             logging.debug(f'{self.cameraName}: CAP_PROP_EXPOSURE requested: {np.log2(val/1000)}')
#             logging.debug(f'{self.cameraName}: CAP_PROP_EXPOSURE before: {self.camDevice.get(cv2.CAP_PROP_EXPOSURE)}')
#         self.camDevice.set(cv2.CAP_PROP_EXPOSURE, np.log2(val/1000))
#         if self.diag>1:
#             logging.debug(f'{self.cameraName}: CAP_PROP_EXPOSURE after: {self.camDevice.get(cv2.CAP_PROP_EXPOSURE)}')
#         self.exposure = val
#         if self.exposure==val:
#             return 1
#         else:
#             subprocess.check_call("v4l2-ctl -d /dev/video0 -c exposure_absolute="+str(val),shell=True)
#             self.getExposure()
#             return 0
        if self.diag>0:
            self.updateStatus('Cannot update webcam exposure. Feature in development.', True)
        return 1
    
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
            return frame

    def close(self):
        '''close the videocapture object'''
        if hasattr(self, 'camDevice') and not self.camDevice==None:
            try:
                self.camDevice.release()
            except Exception as e:
                logging.info(f'Failed to release cam device for {self.cameraName}: {e}')
                pass

            

class webcam(camera):
    '''webcams are objects that hold functions for conventional webcams that openCV (cv2) can communicate with'''
    
    def __init__(self, sbWin:QMainWindow, guiBox:connectBox):
        super(webcam, self).__init__(sbWin, guiBox)

        # connect to webcam through OpenCV
        self.webcamNum = sbWin.camBoxes.webcams
        sbWin.camBoxes.webcams+=1    # assign a webcam number to this webcam
        
        
        # get image stats
        self.vc = self.createVC()
        if self.vc.connected:
            self.connected = True
            self.vc.signals.status.connect(self.updateStatus)   # send status messages back to window
            self.deviceOpen = True
            self.vc.readFrame()
            if self.fps==0:
                self.setFrameRateAuto()
            self.imw = int(self.vc.camDevice.get(3))               # image width (px)
            self.imh = int(self.vc.camDevice.get(4))               # image height (px)
    #        self.prevWindow.setFixedSize(self.imw, self.imh)    # set the preview window to the image size
        else:
            self.connected = False

        self.convertColors = True
        

    def createVC(self):
        '''connect to the videocapture object'''
        return webcamVC(self.webcamNum, self.guiBox.bTitle, self.diag)
        
    def setExposure(self, val:float) -> int:
        '''Set the exposure time to val'''
        if self.diag>0:
            self.updateStatus('Cannot update webcam exposure. Feature in development.', True)
        return 1


    