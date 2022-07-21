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
from camThreads import *
from config import cfg


try:
    os.environ["PYLON_CAMEMU"] = "3"
    from pypylon import genicam
    from pypylon import pylon
except:
    logging.warning('Pylon SDK not installed')
    pass

           

   

 #########################################################      
    
    
class vc:
    '''holds the videoCapture object and surrounding functions'''
    
    def __init__(self, cameraName:str, diag:int):
        self.cameraName = cameraName
        self.status = pyqtSignal(str,bool)
        self.diag = diag
        self.connected = False

    

class camera:
    '''a camera object is a generic camera which stores functions and camera info for both pylon cameras and webcams
        these objects are created by cameraBox objects
        each type of camera (Basler and webcam) has its own readFrame and close functions'''
    
    def __init__(self, sbWin:QMainWindow, guiBox:connectBox):
        self.previewing = False
        self.sbWin = sbWin                        # sbWin is the parent window
        self.guiBox = guiBox                      # guiBox is the parent box for this camera
        self.vFilename = ''                       # name of the current video file
        self.timerRunning = False                 # is the timer that controls frame collection running?
        self.previewing = False                   # is the live preview on?
        self.recording = False                    # are we collecting frames for a video?
        self.writing = True                       # are we writing video frames to file?
        self.timer = None                         # the timer that controls frame collection
        self.deviceOpen = False
        self.resetVidStats()
        self.framesSincePrev = 0  # how many frames we've collected since we updated the live display
#         self.diag = cfg.camera.diag             
        self.fps = 1              # this will be set during subclass init (webcam.__init__, bascam.__init__)
        self.previewFPS = 1
        self.exposure = 0         # this will be set during subclass init (webcam.__init__, bascam.__init__)
        self.fourcc = cv2.VideoWriter_fourcc('M','J','P','G')
        self.prevWindow = QLabel()                # the window that the live preview will be displayed in
        self.collisionCount = 0                       # this keeps track of frame read collisions
        self.lastCollision = datetime.datetime.now()  # this keeps track of the time between frame read collisions
        self.loadDict(guiBox.cdict)
        
        
    def loadDict(self, d:dict) -> None:
        '''load current settings from a dictionary'''
        self.flag1 = int(d['flag1'])        # shopbot output flag this camera is attached to, 1-indexed
        self.setFrameRate(int(d['fps']) )        # frames per second
        self.type = d['type']        # type of camera, either bascam or webcam
        self.cameraName = d['name']  # full name of the camera (e.g. Basler camera)
        self.updateDiag(int(d['diag']))        # diag tells us which messages to log. 0 means none, 1 means some, 2 means a lot
        self.previewFPS = int(d['previewFPS'])
        
    def updateDiag(self, diag:int) -> None:
        '''update the diag value'''
        self.diag = diag
        if self.deviceOpen:
            self.vc.diag = diag
        
    def loadConfig(self, cfg1):
        '''load the current settings from the config Box object'''
        self.loadDict(cfg1.camera[self.guiBox.cname])
                    
    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        cfg1.camera[self.guiBox.cname].flag1 = self.flag1
        cfg1.camera[self.guiBox.cname].fps = self.fps
        cfg1.camera[self.guiBox.cname].type = self.type
        cfg1.camera[self.guiBox.cname].name = self.cameraName
        cfg1.camera[self.guiBox.cname].diag = self.diag
        cfg1.camera[self.guiBox.cname].previewFPS = self.previewFPS
        return cfg1
    
    def writeToTable(self, writer) -> None:
        '''writes metadata to the csv writer'''
        if not self.connected:
            return
        b2 = self.guiBox.bTitle.replace(' ', '_')
        writer.writerow([f'{b2}_frame_rate','fps', self.fps])
        writer.writerow([f'{b2}_exposure','ms', self.exposure])
        writer.writerow([f'{b2}_flag1','', self.flag1])
        
    #-------
        
    def setPFrameRate(self, previewFPS:float) -> int:
        '''update the preview frame rate'''
        if self.previewFPS==previewFPS:
            return 1
        else:
            self.previewFPS =  previewFPS
            self.updateFramesToPrev()
            
    def setFrameRate(self, fps:float) -> int:
        '''Set the frame rate of the camera. Return 0 if value changed, 1 if not'''
        if self.fps==fps:
            return 1
        else:
            if 1000./fps<self.exposure and self.exposure>0:
                # requested fps is slower than exposure. reject
                if self.diag>0:
                    self.updateStatus(f'Requested frame rate {fps} is slower than exposure {self.exposure}. Frame rate not updated.', True)
                return 1
            self.fps = fps
            self.mspf = int(round(1000./self.fps))  # ms per frame
            self.updateFramesToPrev()   # update the preview downsample rate
            return 0
        
    def setFrameRateAuto(self) -> int:
        return self.setFrameRate(self.getFrameRate())
    
    def getFrameRate(self):
        '''get the native frame rate of the camera'''
        if self.deviceOpen:
            fps = self.vc.getFrameRate()
            if fps>0:
                return fps
            else:
                return self.fps
        else:
            return self.fps
        
    #-------

    def closeCam(self) -> None:
        '''disconnect from the camera when the window is closed'''
        self.recording = False
        self.previewing = False                
          
    def doneRecording(self) -> None:
        '''update the status box when we're done recording  '''
        self.writing = False
        self.updateRecordStatus()
    
    
    def getFilename(self, ext:str) -> str: 
        '''determine the file name for the file we're about to record. ext is the extension. Uses the timestamp for unique file names. The folder is determined by the saveFolder established in the top box of the GUI.'''

        try:
            fullfn = self.sbWin.newFile(self.cameraName, ext)
        except NameError as e:
            logging.error(e)
            return

        return fullfn
    
    
    def resetVidStats(self) -> None:
        '''reset video stats, to start a new video'''
        self.startTime = 0      # the time when we started the video
        self.timeRec = 0        # how long the video is
        self.framesDropped = 0  # how many frames we've dropped
        self.totalFrames = 0    # how many frames are in the video
        self.fleft = 0          # how many frames we still need to write to file
        self.frames = []        # frame queue. appended to back, popped from front.
        self.lastFrame = []     # last frame collected. kept in a list of one cv2 frame to make it easier to pass between functions
        self.vridlist = []      # list of videoReader ids (list of ints). could be deprecated?
        
    
    def snap(self) -> None:
        '''take a single snapshot and save it. Put this process in the background through QThreadPool'''
        if self.previewing or self.recording:
            # if we're currently collecting frames, we can use the last frame
            last = True
        else:
            # if we're not currently collecting frames, we need to collect a new frame.
            last = False
        snapthread = camSnap(self, last, self.lastFrame)       # create an object to collect and save the snapshot in background
        snapthread.signals.result.connect(self.updateStatus)   # let the camSnap object send messages to the status bar
        snapthread.signals.error.connect(self.updateStatus)
        QThreadPool.globalInstance().start(snapthread)  # get snapshot in background thread
            
            
    
    #---------------------------------
    
    def updateFramesToPrev(self):
        '''calculate the number of frames to downsample for preview'''
        self.critFramesToPrev = max(round(self.fps/self.previewFPS), 1)
        self.framesSincePrev = self.critFramesToPrev
    
    def startPreview(self) -> None: 
        '''start live preview'''
        # critFramesToPrev reduces the live display frame rate, 
        # so only have to update the display at a comfortable viewing rate.
        # if the camera is at 200 fps, the video will be saved at full rate but
        # preview will only show at 15 fps
        self.updateFramesToPrev()
        self.previewing = True
        self.startTimer()      # this only starts the timer if we're not already recording

    
    def stopPreview(self) -> None:
        '''stop live preview. This freezes the last frame on the screen.'''
        self.previewing = False
        self.stopTimer()       # this only stops the timer if we are neither recording nor previewing
 
    #---------------------------------
    
    def startRecording(self) -> None:
        '''start recording a video'''
        self.recording = True
        self.writing = True
        self.resetVidStats()                       # this resets the frame list, and other vars
        fn = self.getFilename('.avi')              # generate a new file name for this video
        self.vFilename = fn
        vidvars = {'fourcc':self.fourcc, 'fps':self.fps, 'imw':self.imw, 'imh':self.imh, 'cameraName':self.cameraName}
        self.frames = []                           # list of frames for this video. Frames are appended to back and popped from front.
        recthread = vidWriter(fn, vidvars, self.frames, self)         # creates a new thread to write frames to file      
        recthread.signals.finished.connect(self.doneRecording)        # connects vidWriter status updates to the status display
        recthread.signals.progress.connect(self.writingRecording)
        recthread.signals.error.connect(self.updateStatus)
        self.updateStatus(f'Recording {self.vFilename} ... ', True) 
        QThreadPool.globalInstance().start(recthread)          # start writing in a background thread
        self.startTimer()                          # this only starts the timer if we're not already previewing
        if self.diag>1:
                                                   # if we're in super debug mode, print header for the table of frames
            logging.debug('Camera name\tID\t# frames\tFrame time (ms)\tms/frame\tTotal time (s)')
    
    
    def stopRecording(self) -> None:
        '''stop collecting frames for the video'''
        if not self.recording:
            return
        self.frames.append('STOP') # this tells the vidWriter that this is the end of the video
        self.recording = False     # this helps the frame reader and the status update know we're not reading frames
        self.stopTimer()           # only turns off the timer if we're not recording or previewing


    #---------------------------------
    
    def stopTimer(self) -> None:
        '''this only stops the timer if we are neither recording nor previewing'''
        if not self.recording and not self.previewing:
            self.timer.stop()
            if self.diag>1:
                logging.info(f'Stopping {self.cameraName} timer')
    
    #---------------------------------
    
    def updatePrevFrame(self, frame:np.ndarray) -> None:
        '''update the live preview window'''
                # update the preview
        if not self.previewing:
            return
            
        # downsample preview frames
        if self.framesSincePrev==self.critFramesToPrev:
            if type(frame)==np.ndarray:
                self.framesSincePrev=0
            else:
                self.updateStatus(f'Frame is empty', True)
        else:
            self.framesSincePrev+=1
            return
                
        try:
            # we need to convert the frame from the OpenCV cv2 format to the Qt QPixmap format
            if self.convertColors:
                frame2 = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame2 = frame
            image = QImage(frame2, frame2.shape[1], frame2.shape[0], QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(image)
            self.prevWindow.setPixmap(pixmap)
        except Exception as e:
            # stop previewing if we can't preview
            logging.warning(str(e))
            self.updateStatus('Error displaying frame', True)
            self.previewing = False
            self.stopTimer()
            
            
        
    def saveFrameCheck(self, frame:np.ndarray, vrid) -> None:
        '''check if the frame should be saved. receives signals from vidReader'''
        # save the frame
        if self.recording:
            # if we've skipped at least 2 frames, fill that space with duplicate frames
            # if we have two vidReaders going at once, only do this with the first one
            if len(self.vridlist)==0 or vrid == min(self.vridlist):
                self.timerCheckDrop() 
                
            self.saveFrame(frame) 
            
            # remove this vidreader id from the list of ids
            if self.vrid in self.cam.vridlist:
                self.cam.vridlist.remove(self.vrid)
        
    
    def saveFrame(self, frame:np.ndarray, vrid) -> None:
        '''save the frame to the video file. frames are in cv2 format. '''
     
        try:
            self.frames.append(frame)
        except:
            # stop recording if we can't write
            self.signals.error.emit(f'Error writing to video', True)
            
        else:
            # display the time recorded
            self.timeRec = self.cam.timeRec+self.cam.mspf/1000
            self.totalFrames+=1
            self.updateRecordStatus()
            
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
            
                
            
    def updateCollisions(self, st:str) -> str:
        '''a common error during frame collection is 'Basler camera:Error collecting frame: Error collecting grab: There is already a thread waiting for a result. : RuntimeException thrown (file 'instantcameraimpl.h', line 1096)'. This prevents pile up of those messages. It returns a string to be logged.'''
        if 'There is already a thread waiting for a result' in st:
            now = datetime.datetime.now()
            elapsed = (now-self.lastCollision).total_seconds()
            self.lastCollision = now
            if elapsed<1:
                # if the last collision happened recently, note how many collisions there have been in a row
                self.collisionCount+=1
                if self.collisionCount % 1000 == 0 and self.diag>1:
                    # if we've had 50 collisions in a row in quick succession, report an error
                    st = f'{self.collisionCount} frame read collisions in a row. Consider decreasing exposure time.'
                    return st
                else:
                    raise Exception('Do not log this message')
            else:
                # reset the count and don't report if it's been at least 1 second since the last collision
                self.collisionCount = 1
                raise Exception('Do not log this message')
        else:
            return st       


    @pyqtSlot(str,bool)
    def updateStatus(self, st:str, log:bool) -> None:
        '''updates the status of the widget that this camera belongs to. 
        st is the status message. 
        log determines whether to write to log. '''
        
        try:
            st = self.updateCollisions(st)
        except Exception as e:
            return
        else:  
            self.guiBox.updateStatus(st, log)
    
    
    def updateRecordStatus(self) -> None:
        '''updates the status bar during recording and during save. 
        We turn off logging because this updates so frequently that we would flood the log with updates.'''
        log = False
        if self.recording:
            s = 'Recording '
        elif self.writing:
            s = 'Writing '
        else:
            s = 'Recorded '
            log = True
        s+=self.vFilename
        s+= ' : %2.2f s' % self.timeRec + ', '
        if self.writing and not self.recording:
            s+= f'{self.fleft}/{self.totalFrames} frames left'
        else:
            s+= f'{self.framesDropped}/{self.totalFrames} frames dropped'
        self.updateStatus(s, log)
        
    
    def writingRecording(self, fleft:int) -> None:  
        '''this function updates the status to say that the video is still being saved. 
        fleft is the number of frames left to record'''
        if self.cam.diag>1:
            # if we're in debug mode for this camera, log that we wrote a frame for this camera
            logging.debug(f'{self.cameraName}\twrite\t{fleft}')
        if not self.recording:
            self.fleft = fleft
            self.updateRecordStatus()
            
            
    def close(self) -> None:
        '''this gets triggered when the whole window is closed. Disconnects from the cameras and deletes videoCapture objects'''
        if hasattr(self, 'vc'):
            self.vc.close()
            del self.vc
        self.closeCam()
        
        

        
                    
    

