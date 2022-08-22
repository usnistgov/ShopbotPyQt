#!/usr/bin/env python
'''Shopbot GUI functions for handling background camera functions'''

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


class vidWriter(QRunnable):
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
                print(size)
                if size % printFreq==1:
                    # on every 100th frame, tell the GUI how many frames we still have to write
                    self.signals.progress.emit(size)
       
                    
#---------------------------

# class frameCheckerSignals(QObject):
#     frameOut = pyqtSignal(np.ndarray, int)
#     timeOut = pyqtSignal(datetime.datetime)


# class frameChecker(QRunnable):
#     '''checks for dropped frames'''
    
#     def __init__(self, frame:np.ndarray, startTime:datetime.datetime, lastTime:datetime.datetime, timeRec:float, cameraName:str, mspf:int, diag:bool, frameNum:int):
#         super(frameChecker,self).__init__()
#         self.frame = frame
#         self.startTime = startTime
#         self.lastTime = lastTime
#         self.timeRec = timeRec
#         self.cameraName = cameraName
#         self.mspf = mspf
#         self.diag = diag
#         self.frameNum = frameNum
#         self.signals = frameCheckerSignals()

        
#     @pyqtSlot()
#     def run(self) -> None:
#         '''check to see if the timer has skipped steps and fills the missing frames with duplicates. Called by run '''
#         dnow = datetime.datetime.now()
#         timeElapsed = (dnow-self.startTime).total_seconds()
#         framesElapsed = int(np.floor((timeElapsed-self.timeRec)/(self.mspf/1000)))
            
#         if self.diag>1:
#             self.signals.timeOut.emit(dnow)
            
#         if framesElapsed>2:
#             # if we've progressed at least 2 frames, fill that space with duplicate frames
#             numfill = framesElapsed-1
#             for i in range(numfill):
#                 if self.diag>1:
#                     logging.debug(f'{self.cameraName}\tPAD{numfill}\t\t'+'%2.3f'%self.timeRec)
#                     self.timeRec = self.timeRec+self.mspf/1000
#                 self.signals.frameOut.emit(self.frame, self.frameNum)
#         if self.diag>1:
#             frameElapsed = ((dnow-self.lastTime).total_seconds())
#             s = f'{self.cameraName}\t'
#             for si in ['%2.3f'%t for t in [frameElapsed,  timeElapsed, self.timeRec]]:
#                 s = f'{s}{si}\t'
#             logging.debug(s)
    

        
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
    progress = pyqtSignal(int)
    frame = pyqtSignal(np.ndarray, int, int)
        
                    
class vidReader(QRunnable):
    '''vidReader puts frame collection into the background, so frames from different cameras can be collected in parallel. this collects a single frame from a camera'''
    
    def __init__(self, vc:QMutex, frames:Queue, lastFrame:list, cameraName:str, diag:int, frameNumber:int, vrid:int):
        super(vidReader, self).__init__()
        self.signals = vrSignals()  # signals that let this send messages back to the GUI
        self.vc = vc
        self.frames = frames
        self.lastFrame = lastFrame
        self.cameraName = cameraName
        self.diag = diag
        self.vrid = vrid
        self.frameNumber = frameNumber
        
        
    @pyqtSlot()    
    def run(self) -> None:
        '''Run this function when this thread is started. Collect a frame and return to the gui'''
        try:
            self.vc.lock()     # lock camera so only this thread can read frames
            frame = self.vc.readFrame()
            self.vc.unlock()   # unlock camera
        except Exception as e:
            if len(str(e))>0:
                self.signals.error.emit(f'Error collecting frame: {e}', True)
                
            if len(self.lastFrame)>0:
                frame = self.lastFrame[0]
            else:
                self.signals.error.emit(f'Error collecting frame: no last frame', True)
                return
        self.signals.frame.emit(frame, self.frameNumber, self.vrid)  # send the frame back to be displayed and recorded


   
 ###########################
    # snapshots
    
class snapSignals(QObject):
    '''signal class to send messages back to the GUI during snap collection'''
    
    result = pyqtSignal(str, bool)
    error = pyqtSignal(str, bool)

class camSnap(QRunnable):
    '''collects snapshots in the background'''
    
    def __init__(self, vc:QMutex, readNew:bool, lastFrame:np.ndarray, fn:str):
        super(camSnap, self).__init__()
        self.fn = fn
        self.vc = vc                  # cam is the camera object 
        self.readNew = readNew          # readnew tells us if we need to read a new frame
        self.signals = snapSignals()
        self.lastFrame = lastFrame      # lastFrame is the last frame collected by the camera, as a list of one cv2 frame
        
    def run(self):
        '''Get a frame, export it, and return a status string to the GUI.'''
        
        if self.readNew:
            # if we're not currently previewing, we need to collect a new frame.
            try:
                frame = self.readFrame()
            except ValueError:
                return
        else:
            # if we're not previewing, we can use the last frame
            if len(self.lastFrame)>0:
                frame = self.lastFrame
            else:
                try:
                    frame = self.readFrame()
                except ValueError:
                    self.signals.error.emit('Error collecting snap: no frame', True)
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
        