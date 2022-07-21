#!/usr/bin/env python
'''Shopbot GUI functions for handling camera functions'''

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
from general import *
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

#########################################################

class vwSignals(QObject):
    '''Defines the signals available from a running worker thread
        Supported signals are:
        finished: No data
        error: a string message and a bool whether this is worth printing to the log
        result:`object` data returned from processing, anything
        progress: `int` indicating % progress '''
    
    finished = pyqtSignal()
    error = pyqtSignal(str, bool)
    progress = pyqtSignal(int)

    

#########################################################

class vidWriter(QRunnable):
    '''The vidWriter creates a cv2.VideoWriter object at initialization, and it takes frames in the queue and writes them to file. This is a failsafe, so if the videowriter writes slower than the timer reads frames, then we can store those extra frames in memory until the vidWriter object can write them to the HD. 
QRunnables run in the background. Trying to directly modify the GUI display from inside the QRunnable will make everything catastrophically slow, but you can pass messages back to the GUI using vrSignals.'''
    
    def __init__(self, fn:str, vidvars, frames:List[np.ndarray], cam):
        super(vidWriter, self).__init__()        
        self.vFilename = fn
        self.vw = cv2.VideoWriter(fn, vidvars['fourcc'], vidvars['fps'], (vidvars['imw'], vidvars['imh']))
        self.signals = vwSignals()  
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

                if len(self.frames) % 100==1:
                    # on every 100th frame, tell the GUI how many frames we still have to write
                    self.signals.progress.emit(len(self.frames))
        
                    
                    
###############################################


class vrSignals(QObject):
    '''Defines the signals available from a running worker thread
        Supported signals are:
        finished: No data
        error: a string message and a bool whether this is worth printing to the log
        result:`object` data returned from processing, anything
        progress: `int` indicating % progress '''
    
    finished = pyqtSignal()
    error = pyqtSignal(str, bool)
    progress = pyqtSignal(int)
    prevFrame = pyqtSignal(np.ndarray)
    recFrame = pyqtSignal(np.ndarray, int)


                    
class vidReader(QRunnable):
    '''vidReader puts frame collection into the background, so frames from different cameras can be collected in parallel'''
    
    def __init__(self, cam, mspf:int, cameraName:str):
        super(vidReader, self).__init__()
        self.cam = cam              # the camera object that called this reader
        self.signals = vrSignals()  # signals that let this send messages back to the GUI
        self.mspf = mspf
        self.cameraName = cameraName
        if cam.type=='webcam':
            self.vc = webcamVC(cam.webcamNum, cam.cameraName, cam.diag)
        elif cam.type=='bascam':
            self.vc = bascamVC(cam.cameraName, cam.diag)

        self.lastFrame = []
        
        
    def run(self) -> None:
        '''Run this function when this thread is started. Collect a frame, and pad the frame list if we dropped frames.'''
        self.startTimer()
        
        
    def getFrame()
        # get an image
        try:
            frame = self.vc.readFrame()
        except Exception as e:
            frame = self.lastFrame[0]
            if len(str(e))>0:
                self.signals.error.emit(f'Error collecting frame: {e}', True)
                
        self.signals.prevFrame.emit(frame) # send the frame back to be displayed
        self.signals.recFrame.emit(frame, self.vrid) # send the frame back to be recorded
        
    def readFrame(self):
        '''get a frame from the webcam using cv2 '''
        try:
            rval, frame = self.camDevice.read()
        except:
            self.signals.error.emit('Error reading frame', True)
            raise Exception
        if not rval:
            raise Exception
        else:
            # if we successfully read the frame, keep it in lastFrame
            self.lastFrame = [frame]
            return frame
        
        
    # start the timer if there is not already a timer
    def startTimer(self) -> None:
        '''start updating preview or recording'''
        self.timer = QTimer()
        self.timer.timeout.connect(self.timerFunc)        # run the timerFunc every mspf milliseconds
        self.timer.setTimerType(Qt.PreciseTimer)   # may or may not improve timer accuracy, depending on computer
        self.timer.start(self.mspf)                       # start timer with frequency milliseconds per frame
        self.timerRunning = True
        if self.diag>1:
            logging.debug(f'Starting {self.cameraName} timer')

    
    def stopTimer(self) -> None:
        '''this only stops the timer if we are neither recording nor previewing'''
        if not self.recording and not self.previewing:
            self.timer.stop()
            if self.diag>1:
                logging.info(f'Stopping {self.cameraName} timer')
    
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
        runnable.signals.recFrame.connect(self.saveFrameCheck)
        QThreadPool.globalInstance().start(runnable)
        
    
    
    def timerCheckDrop(self) -> None:
        '''check to see if the timer has skipped steps and fills the missing frames with duplicates. Called by run '''
        dnow = datetime.datetime.now()
        if self.startTime==0:
            self.startTime = dnow
            if self.diag>1:
                self.lastTime = dnow
        else:
            timeElapsed = (dnow-self.startTime).total_seconds()
            if (timeElapsed - self.timeRec)>2*self.mspf/1000:
                # if we've skipped at least 2 frames, fill that space with duplicate frames
                numfill = int(np.floor((timeElapsed-self.timeRec)/(self.mspf/1000)))
                for i in range(numfill):
                    if self.diag>1:
                        logging.debug(f'{self.cameraName}\t{self.vrid}\tPAD\t\t\t\t '+'%2.3f'%self.timeRec)
                    self.framesDropped+=1
                    if len(self.lastFrame)>0:
                        self.saveFrame(self.lastFrame[0])
            if self.diag>1:
                frameElapsed = ((dnow-self.lastTime).total_seconds())*1000
                s = self.cameraName+'\t'+str(self.vrid)+'\t'
                for si in ['%2.3f'%t for t in [len(self.frames), frameElapsed, self.mspf, timeElapsed, self.timeRec]]:
                    s = s+si+'\t'
                logging.debug(s)
                self.lastTime = dnow
                
    def close(self):
        '''close the qrunnable'''
        try:
            self.timer.stop()
        except:
            pass
        else:
            if self.diag>0:
                logging.info(f'{self.cameraName} timer stopped')
                
                
    
    

 
          

   
 ###########################
    # snapshots
    
class snapSignals(QObject):
    '''signal class to send messages back to the GUI during snap collection'''
    
    result = pyqtSignal(str, bool)
    error = pyqtSignal(str, bool)

class camSnap(QRunnable):
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
                self.camDevice = cam.openCamDevice()
                rval, frame = self.camDevice.read()
                # frame needs to be in cv2 format
            except Exception as e:
                if len(str(e))>0:
                    self.signals.error.emit(f'Error collecting frame: {e}', True)
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