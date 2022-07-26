#!/usr/bin/env python
'''Shopbot GUI functions for handling camera functions'''

# external packages
from PyQt5.QtCore import pyqtSignal, QMutex, QObject, QRunnable, QThreadPool, QTimer, Qt
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
    https://www.pythonforthelab.com/blog/handling-and-sharing-data-between-threads/
QRunnables run in the background. Trying to directly modify the GUI display from inside the QRunnable will make everything catastrophically slow, but you can pass messages back to the GUI using vrSignals.'''
    
    def __init__(self, fn:str, vidvars, frames:Queue):
        super(vidWriter, self).__init__()        
        self.vFilename = fn
        self.vw = cv2.VideoWriter(fn, vidvars['fourcc'], vidvars['fps'], (vidvars['imw'], vidvars['imh']))
        self.signals = vwSignals()  
        self.frames = frames
        self.vidvars = vidvars
        self.recording = True
    
    @pyqtSlot()
    def run(self) -> None:
        '''this loops until we receive a frame that is a string
        the save function will pass None to the frame queue when we are done recording'''
        while True:
            time.sleep(1) 
                # this gives the GUI enough time to start adding frames before we start saving, otherwise we get stuck in infinite loop where it's immediately checking again and again if there are frames
            while not frames.empty():
                # remove the first frame once it's written
                frame = self.frames.get()
                if frame is None:
                    # if this frame is a string, the video reader is done, and it's sent us a signal to stop
                    # we use this explicit signal instead of just stopping when the frame list is empty, just in case the writer is faster than the reader and manages to empty the queue before we're done reading frames
                    self.vw.release()
                    self.signals.finished.emit()
                    return
                self.vw.write(frame) 

                size = self.frames.qsize()
                if size % 100==1:
                    # on every 100th frame, tell the GUI how many frames we still have to write
                    self.signals.progress.emit(size)
        
                    
                    
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
    frame = pyqtSignal(np.ndarray)
    

class frameConverter(QRunnable):
    '''converts frames to pixmaps in background'''
    
    def __init__(self, frame:np.array, convertColors:bool):
        super(frameConverter, self).__init__()
        self.frame = frame
        self.convertColors = convertColors
        self.frameOut = pyqtSignal(np.ndarray)
        self.error = pyqtSignal(str, bool)
        
    @pyqtSlot()
    def run(self) -> None:
        # we need to convert the frame from the OpenCV cv2 format to the Qt QPixmap format
        try:
        if self.convertColors:
            frame2 = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
        else:
            frame2 = self.frame
        image = QImage(frame2, frame2.shape[1], frame2.shape[0], QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        self.frameOut.emit(pixmap)

                    
class vidReader(QRunnable):
    '''vidReader puts frame collection into the background, so frames from different cameras can be collected in parallel'''
    
    def __init__(self, vc:QMutex, frames:Queue, lastFrame:list, cameraName:str, diag:int):
        super(vidReader, self).__init__()
        self.cam = cam              # the camera object that called this reader
        self.signals = vrSignals()  # signals that let this send messages back to the GUI
        self.mspf = mspf
        self.cameraName = cameraName
        self.diag = diag
        self.vrid = 0
        self.frames = frames
        self.lastFrame = lastFrame
        
    @pyqtSlot()    
    def run(self) -> None:
        '''Run this function when this thread is started. Collect a frame and return to the gui'''
        try:
            self.vc.lock()
            frame = self.vc.readFrame()
            self.vc.unlock()
        except Exception as e:
            if len(str(e))>0:
                self.signals.error.emit(f'Error collecting frame: {e}', True)
                
            if len(self.lastFrame)>0:
                frame = self.lastFrame[0]
            else:
                self.signals.error.emit(f'Error collecting frame: no last frame', True)
                return
        self.emitFrame(frame)
            
    def emitFrame(self, frame) -> None:
        '''emit the frame back to the GUI'''
        self.signals.frame.emit(frame)  # send the frame back to be displayed and recorded

    
    def timerCheckDrop(self) -> None:
        '''check to see if the timer has skipped steps and fills the missing frames with duplicates. Called by run '''
        dnow = datetime.datetime.now()
        if self.startTime==0:
            self.startTime = dnow
            if self.diag>1:
                self.lastTime = dnow
        else:
            timeElapsed = (dnow-self.startTime).total_seconds()
            framesElapsed = int(np.floor((timeElapsed-self.timeRec)/(self.mspf/1000)))
            if framesElapsed>2:
                # if we've progressed at least 2 frames, fill that space with duplicate frames
                numfill = framesElapsed-1
                for i in range(numfill):
                    if self.diag>1:
                        logging.debug(f'{self.cameraName}\t{self.vrid}\tPAD\t\t\t\t '+'%2.3f'%self.timeRec)
                    self.framesDropped+=1
                    self.emitFrame(self.lastFrame)
            if self.diag>1:
                frameElapsed = ((dnow-self.lastTime).total_seconds())*1000
                s = f'{self.cameraName}\t{self.vrid}\t'
                for si in ['%2.3f'%t for t in [len(self.frames), frameElapsed, self.mspf, timeElapsed, self.timeRec]]:
                    s = f'{s}{si}\t'
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
                self.vc.lock()      # lock the camera so only the snap can collect frames
                frame = self.vc.readFrame()
                self.vc.unlock()    
                # frame needs to be in cv2 format
            except Exception as e:
                if len(str(e))>0:
                    self.signals.error.emit(f'Error collecting frame: {e}', True)
                return
        else:
            # if we're not previewing, we can use the last frame
            if len(self.lastFrame)>0:
                frame = self.lastFrame
            else:
                self.signals.error.emit('Error collecting snap: no frame', True)
                return
        out = self.exportFrame(frame)
        self.signals.result.emit(out, True)
        
            
    def exportFrame(self, frame:np.ndarray) -> str:
        '''Export a single frame to file as a png'''
        try:
            cv2.imwrite(self.fn, frame)
        except:
            return('Error saving frame')
        else:
            return(f'File saved to {fullfn}') 
        