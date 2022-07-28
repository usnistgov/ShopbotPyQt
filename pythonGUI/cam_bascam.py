#!/usr/bin/env python
'''Shopbot GUI functions for handling basler cameras'''

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


try:
    os.environ["PYLON_CAMEMU"] = "3"
    from pypylon import genicam
    from pypylon import pylon
except:
    logging.warning('Pylon SDK not installed')
    pass



#########################################    


class bascamVC(vc):
    '''holds a videoCapture object that reads frames from a basler cam'''
    
    def __init__(self, cameraName:str, diag:int):
        super(bascamVC, self).__init__(cameraName, diag)
        self.errorStatus = 0     # 0 means we have no outstanding errors. This prevents us from printing a ton of the same error in a row.
        self.connectVC()
        
        
    def connectVC(self):
        '''create the camDevice object'''
        
        # connect to the camera
        try:
            self.tlf = pylon.TlFactory.GetInstance()
            self.camDevice = pylon.InstantCamera(self.tlf.CreateFirstDevice())
        except Exception as e:
            self.grabError(e, 1, False)
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

            # converter converts pylon images into cv2 images
            self.converter = pylon.ImageFormatConverter()
            self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
            self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

        # if we failed to connect to the camera, close it, and display a failure state on the GUI
        except Exception as e:
            try:
                self.camDevice.Close() # close camera if we've already opened it
            except:
                pass
            self.grabError(e, 2, False)
            self.connected = False
            return 
        
    def modelName(self) -> str:
        '''get the model name from the camera'''
        if self.connected:
            return self.camDevice.GetDeviceInfo().GetModelName()
        else:
            return ''
            
    def getFrameRate(self) -> int:
        '''get the frame rate from the camera'''
        if self.connected:
            fps = self.camDevice.ResultingFrameRate.GetValue()
            return int(fps)

    def getExposure(self) -> float:
        '''get the stored exposure value from the camera'''
        return self.camDevice.ExposureTime.GetValue()/1000 # convert from microseconds to milliseconds
    
    def setExposure(self):
        '''set the exposure time of the device'''
        self.camDevice.ExposureTime.SetValue(val*1000) # convert from milliseconds to microseconds
        self.getExposure()
        
    def exposureAuto(self) -> int:
        '''Automatically adjust the exposure. https://docs.baslerweb.com/exposure-auto.  Returns 0 if the value was changed, 1 if not.'''
        if self.diag>0:
            self.updateStatus('Cannot set auto exposure. Feature in development.', True)
        return 1
#         # Set the &#160;Exposure Auto auto function to its minimum lower limit
#         # and its maximum upper limit
#         minLowerLimit = self.camDevice.AutoExposureTimeLowerLimit.GetMin()
#         maxUpperLimit = self.camDevice.AutoExposureTimeUpperLimit.GetMax()
#         self.camDevice.AutoExposureTimeLowerLimit.SetValue(minLowerLimit)
#         self.camDevice.AutoExposureTimeUpperLimit.SetValue(maxUpperLimit)
#         # Set the target brightness value to 0.6
#         self.camDevice.AutoTargetBrightness.SetValue(0.6)
# #         # Select auto function ROI 1
# #         self.camDevice.AutoFunctionROISelector.SetValue('AutoFunctionROISelector_ROI1');
#         # Enable the 'Brightness' auto function (Gain Auto + Exposure Auto)
#         # for the auto function ROI selected
#         self.camDevice.AutoFunctionROIUseBrightness.SetValue(True)
#         # Enable Exposure Auto by setting the operating mode to Continuous
#         self.camDevice.ExposureAuto.SetValue('ExposureAuto_Once')
    
    def readFrame(self):
        '''get a frame from the Basler camera using pypylon'''
        
        try:            
            grabResult = self.camDevice.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        except Exception as e:
            return self.grabError(f'Error collecting grab: {e}', 3, True)
        if not grabResult.GrabSucceeded():
            return self.grabError('Error: Grab failed', 4, True)
        try:
            # converts to cv2 format
            image = self.converter.Convert(grabResult)
            img = image.GetArray() 
        except:
            return self.grabError('Error: image conversion failed', 5, True)
        try:               
            grabResult.Release()
        except:
            pass
        if type(img)==np.ndarray:
            self.errorStatus=0
            return img  
        else:
            return self.grabError('Error: Frame is not array', 6, True)
        
    def grabError(self, status:str, statusNum:int, exc:bool) -> None:
        '''update the status box when there's an error grabbing the frame. Status is a number representing the type of error. This prevents us from printing the same error over in a loop. exc is true to return an exception and false to return nothing'''
        if exc:
#             if self.diag>0:
#                 logging.info(f'errorStatus={self.errorStatus},statusNum={statusNum}')
            if self.errorStatus==statusNum:
                raise Exception('')
            else:
                self.errorStatus=statusNum
                raise Exception(status)
        else:
            if not self.errorStatus==statusNum:
                self.errorStatus=statusNum
                self.updateStatus(status, self.diag>0) 
        
    def close(self):
        '''close the videocapture object'''
        if not self.camDevice==None:
            try:
                self.camDevice.StopGrabbing()
                self.camDevice.Close()
            except Exception as e:
                logging.info('Failed to close basler camera')
                pass
            else:
                if self.diag>0:
                    logging.info('Basler camera closed')
      

    
    
    
class bascam(camera):
    '''bascams are Basler cameras that require the pypylon SDK to communicate'''
    
    def __init__(self, sbWin:QMainWindow, guiBox:connectBox):
        super(bascam, self).__init__(sbWin, guiBox)
        self.vFilename = ''
        self.connected = False
        self.convertColors = True

        # get camera stats
        self.vc = self.createVC()
        if self.vc.connected:
            self.connected = True
            self.vc.signals.status.connect(self.updateStatus)   # send status messages back to window
            
            # update the window size
            f1 = self.vc.readFrame()                               # get a sample frame
            self.imw = len(f1[0])                               # image width (px)
            self.imh = len(f1)                                  # image height (px)
            self.prevWindow.setFixedSize(self.imw, self.imh)    # set the preview window to the image size
            
            # read exposure from camera, reset fps if config was empty
            self.exposure = self.vc.getExposure()                                  # read the default exposure time from the camera
            if self.fps==0:
                self.setFrameRate(100)
            
            # update the GUI display to show camera model
            self.guiBox.model = self.vc.modelName()
            self.guiBox.updateBoxTitle()
        else:
            self.connected = False
        
    def createVC(self):
        '''connect to the videocapture object'''
        return bascamVC(self.guiBox.bTitle, self.diag)

    def setExposure(self, val:float) -> int:
        '''Set the exposure time to val. Returns 0 if the value was changed, 1 if not.'''
        if self.exposure==val:
            return 1
        else:
            if val>self.mspf:
                # exposure time is longer than frame rate. reject.
                if self.diag>0:
                    self.updateStatus(f'Requested exposure time {val} is higher than frame rate {self.mspf} ms per frame. Exposure time not updated.', True)
                return 1
            if hasattr(self, 'vc') and not self.vc==None:
                self.vc.setExposure(val)                
            return 0
                