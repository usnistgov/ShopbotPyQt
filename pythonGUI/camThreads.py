#!/usr/bin/env python
'''Shopbot GUI functions for handling background camera functions'''

# external packages
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QMutex, QObject, QRunnable, QThread, QThreadPool, QTimer, Qt
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
from queue import Queue

# local packages
from general import *
from config import cfg


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


class vidWriter(QObject):
    '''The vidWriter creates a cv2.VideoWriter object at initialization, and it takes frames in the queue and writes them to file. This is a failsafe, so if the videowriter writes slower than the timer reads frames, then we can store those extra frames in memory until the vidWriter object can write them to the HD. 
    https://www.pythonforthelab.com/blog/handling-and-sharing-data-between-threads/
QRunnables run in the background. Trying to directly modify the GUI display from inside the QRunnable will make everything catastrophically slow, but you can pass messages back to the GUI using vrSignals.'''
    
    def __init__(self, fn:str, vidvars:dict, frames:Queue):
        super(vidWriter, self).__init__()        
        self.vFilename = fn
        self.vw = cv2.VideoWriter(fn, vidvars['fourcc'], vidvars['fps'], (vidvars['imw'], vidvars['imh']))
        self.signals = vwSignals()  
        self.frames = frames
        self.vidvars = vidvars
        self.recording = True
        self.frameNum = 0
    
    @pyqtSlot()
    def run(self) -> None:
        '''this loops until we receive a frame that is a string
        the save function will pass None to the frame queue when we are done recording'''
        printFreq = 100
        
        while True:
            time.sleep(1) 
                # this gives the GUI enough time to start adding frames before we start saving, otherwise we get stuck in infinite loop where it's immediately checking again and again if there are frames
            while not self.frames.empty():
                # remove the first frame once it's written
                f = self.frames.get()
                frame = f[0]
                frameNum = f[1]
                if frame is None:
                    # if this frame is a string, the video reader is done, and it's sent us a signal to stop
                    # we use this explicit signal instead of just stopping when the frame list is empty, just in case the writer is faster than the reader and manages to empty the queue before we're done reading frames
                    self.vw.release()
                    self.signals.finished.emit()
                    return
                self.frameNum = frameNum
                self.vw.write(frame) 

                size = int(self.frames.qsize())
                if size % printFreq==1:
                    # on every 100th frame, tell the GUI how many frames we still have to write
                    self.signals.progress.emit(size)
                    
    
       
                    
#---------------------------


class vrSignals(QObject):
    '''Defines the signals available from a running worker thread
        Supported signals are:
        finished: No data
        error: a string message and a bool whether this is worth printing to the log
        result:`object` data returned from processing, anything
        progress: `int` indicating % progress '''
    
    finished = pyqtSignal()
    error = pyqtSignal(str, bool)
    progress = pyqtSignal(str)
    frame = pyqtSignal(np.ndarray, bool)

class vidReader(QObject):
    '''vidReader puts frame collection into the background, so frames from different cameras can be collected in parallel. this collects a single frame from a camera. status is a camStatus object, vc is a vc object (defined in camObj)'''
    
    def __init__(self, vc:QMutex):
        super(vidReader, self).__init__()
        self.signals = vrSignals()
        self.vc = vc
        self.lastFrame = []
        self.cameraName = self.vc.cameraName
        self.diag = self.vc.diag
        self.mspf = self.vc.mspf
        self.startTime = datetime.datetime.now()  # time at beginning of reader
        self.lastTime = self.startTime   # time at beginning of last step
        self.dnow = self.startTime   # current time
        self.timeRec = 0             # time of video recorded
        self.timeElapsed = 0
        self.framesDropped = 0
        self.dt = 0
        self.sleepTime = 0

        
    @pyqtSlot()    
    def run(self) -> None:
        '''Run this function when this thread is started. Collect a frame and return to the gui'''
        if self.diag>1:
                                                   # if we're in super debug mode, print header for the table of frames
            self.signals.progress.emit('Camera name\tFrame t\tTotal t\tRec t\tSleep t\tAdj t')

#         while True:
#             self.loop()
        self.timer = QTimer()
        self.timer.timeout.connect(self.loop)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.start(self.mspf)
        self.timerRunning = True
                
    def loop(self):
        '''run this on each loop iteration'''
        self.lastTime = self.dnow
        self.dnow = datetime.datetime.now()
        frame = self.readFrame()  # read the frame
        if not self.cont:
            self.timer.stop()
            self.signals.finished.emit()
            return
        self.sendNewFrame(frame) # send back to window
        self.checkDrop(frame)   # check for dropped frames
        # loopEnd = datetime.datetime.now()
        # inStepTimeElapsed = (loopEnd - self.dnow).total_seconds()  # time elapsed from beginning of step to end
        # self.sleepTime = self.mspf/1000 - inStepTimeElapsed - self.dt
        # if self.sleepTime>0:
        #     time.sleep(self.sleepTime)   # wait for next frame

            
    def readFrame(self):
        '''get a frame from the camera'''
        try:
            self.vc.lock()     # lock camera so only this thread can read frames
            frame = self.vc.readFrame() # read frame
            mspf = self.vc.mspf    # update frame rate
            if not mspf==self.mspf:
                # update frame rate
                self.timer.stop()
                self.mspf = mspf
                self.timer.start(self.mspf)
            self.diag = self.vc.diag    # update logging
            self.cont = self.vc.previewing or self.vc.recording  # whether to continue
            self.vc.unlock()   # unlock camera
        except Exception as e:
            if len(str(e))>0:
                self.signals.error.emit(f'Error collecting frame: {e}', True)
            if len(self.lastFrame)>0:
                frame = self.lastFrame[0]
            else:
                self.signals.error.emit(f'Error collecting frame: no last frame', True)
                return
        else:
            self.lastFrame = [frame]
        return frame
    
    def sendFrame(self, frame:np.ndarray, pad:bool):
        '''send a frame to the GUI'''
        self.signals.frame.emit(frame, pad)  # send the frame back to be displayed and recorded
        self.timeRec = self.timeRec + self.mspf/1000 # keep track of time recorded
        
    def sendNewFrame(self, frame):
        '''send a new frame back to the GUI'''
        self.sendFrame(frame, False)
        
        if self.diag>1:
            frameElapsed = ((self.dnow-self.lastTime).total_seconds())  # time elapsed between this and the last frame
            s = f'{self.cameraName}\t'
            for si in ['%2.4f'%t for t in [frameElapsed,  self.timeElapsed, self.timeRec, self.sleepTime, self.dt]]:
                s = f'{s}{si}\t'
            self.signals.progress.emit(s)
        
    
    def checkDrop(self, frame):
        '''check for dropped frames'''
        # check timing
        if not self.cont:
            return
        self.timeElapsed = (self.dnow-self.startTime).total_seconds()
        framesElapsed = int(np.floor((self.timeElapsed-self.timeRec)/(self.mspf/1000)))
        
        if framesElapsed<0:
            # not pausing enough. pause more next time
            self.dt = self.dt-0.0005
        elif framesElapsed>2:
            # if we've progressed at least 2 frames, fill that space with duplicate frames
            self.dt = self.dt+0.0005    # pause less next time
            numfill = framesElapsed-1
            for i in range(numfill):
                self.sendFrame(frame, True)
                if self.diag>1:
                    self.signals.progress.emit(f'{self.cameraName}\tPAD{numfill}\t\t{self.timeRec:2.3f}\t\t{self.dt}')
        


   
 ###########################
    # snapshots
    
class snapSignals(QObject):
    '''signal class to send messages back to the GUI during snap collection'''
    
    result = pyqtSignal(str, bool)
    error = pyqtSignal(str, bool)

class camSnap(QRunnable):
    '''collects snapshots in the background'''
    
    def __init__(self, vc:QMutex, fn:str):
        super(camSnap, self).__init__()
        self.fn = fn
        self.vc = vc                  # cam is the camera object 
        self.signals = snapSignals()
        
    @pyqtSlot()
    def run(self):
        '''Get a frame, export it, and return a status string to the GUI.'''

        # if we're not currently previewing, we need to collect a new frame.
        try:
            frame = self.readFrame()
        except ValueError:
            return       
        out = self.exportFrame(frame)
        self.signals.result.emit(out, True)
        
    def readFrame(self):
        '''read a new frame'''
        try:
            self.vc.lock()      # lock the camera so only the snap can collect frames
            frame = self.vc.readFrame()
            self.vc.unlock()    
            # frame needs to be in cv2 format
        except Exception as e:
            if len(str(e))>0:
                self.signals.error.emit(f'Error collecting frame: {e}', True)
            raise ValueError('Error collecting frame')
        return frame
        
            
    def exportFrame(self, frame:np.ndarray) -> str:
        '''Export a single frame to file as a png'''
        try:
            cv2.imwrite(self.fn, frame)
        except:
            return('Error saving frame')
        else:
            return(f'File saved to {self.fn}') 
        