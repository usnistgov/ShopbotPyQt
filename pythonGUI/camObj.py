#!/usr/bin/env python
'''Shopbot GUI functions for handling camera functions'''

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
import sip

# local packages
from general import *
from camThreads import *
from config import cfg
   

 #########################################################   

class vcSignals(QObject):
    status = pyqtSignal(str,bool)
    
class vc(QMutex):
    '''holds the videoCapture object and surrounding functions'''
    
    def __init__(self, cameraName:str, diag:int, fps:int, prevFPS:int, recFPS:int):
        super(vc,self).__init__()
        self.cameraName = cameraName
        self.signals = vcSignals()
        self.diag = diag
        self.connected = False
        self.previewing = False                   # is the live preview on?
        self.recording = False                    # are we collecting frames for a video?
        self.writing = False                       # are we writing video frames to file?
        self.updateFPS(fps)
        self.updatePrevFPS(prevFPS)
        
    def updateStatus(self, msg:str, log:bool):
        '''update the status bar by sending a signal'''
        self.signals.status.emit(str(msg), log)
        
    def updateFPS(self, fps):
        self.fps = fps
        self.mspf = int(round(1000./self.fps))
        
    def updatePrevFPS(self, prevFPS):
        self.previewFPS = prevFPS
        self.prevmspf = int(round(1000./self.previewFPS))



class camera(QObject):
    '''a camera object is a generic camera which stores functions and camera info for both pylon cameras and webcams
        these objects are created by cameraBox objects
        each type of camera (Basler and webcam) has its own readFrame and close functions'''
    
    def __init__(self, sbWin:QMainWindow, guiBox:connectBox):
        super(camera, self).__init__()
        self.sbWin = sbWin                        # sbWin is the parent window
        self.guiBox = guiBox                      # guiBox is the parent box for this camera
        self.vFilename = ''                       # name of the current video file

        self.readerRunning = False                 # is the timer that controls frame collection running?
        self.prevRunning = False
        self.previewing = False                   # is the live preview on?
        self.recording = False                    # are we collecting frames for a video?
        self.writing = False                      # are we writing video frames to file?
        self.reader = None                         # the reader that controls frame collection
        self.writeWarning=False  # keep track if we've already warned about the write conflict
        self.deviceOpen = False
        self.frames = Queue()        # frame queue. appended to back, popped from front.
        self.resetVidStats()
        self.framesSincePrev = 0  # how many frames we've collected since we updated the live display
#         self.diag = cfg.camera.diag             
        self.fps = 1              # this will be set during subclass init (webcam.__init__, bascam.__init__)
        self.previewFPS = 1
        self.recFPS = 1  
        self.exposure = 0         # this will be set during subclass init (webcam.__init__, bascam.__init__)
        self.fourcc = cv2.VideoWriter_fourcc('M','J','P','G')
        self.prevWindow = QLabel()                # the window that the live preview will be displayed in
        self.collisionCount = 0                       # this keeps track of frame read collisions
        self.lastCollision = datetime.datetime.now()  # this keeps track of the time between frame read collisions
        self.loadDict(guiBox.cdict)
        
        
    def loadDict(self, d:dict) -> None:
        '''load current settings from a dictionary'''
        self.flag1 = int(d['flag1'])        # shopbot output flag this camera is attached to, 1-indexed
        self.setFrameRate(float(d['fps']) )        # frames per second
        self.type = d['type']        # type of camera, either bascam or webcam
        self.cameraName = d['name']  # full name of the camera (e.g. Basler camera)
        self.updateDiag(int(d['diag']))        # diag tells us which messages to log. 0 means none, 1 means some, 2 means a lot
        self.previewFPS = int(d['previewFPS'])
        self.recFPS = float(d['recFPS'])
        
    def updateDiag(self, diag:int) -> None:
        '''update the diag value'''
        self.diag = diag
        if self.deviceOpen:
            self.vc.lock()
            self.vc.diag = diag
            self.vc.unlock()
        
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
        cfg1.camera[self.guiBox.cname].recFPS = self.recFPS
        return cfg1
    
    def writeToTable(self, writer) -> None:
        '''writes metadata to the csv writer'''
        if not self.connected:
            return
        b2 = self.guiBox.bTitle.replace(' ', '_')
        writer.writerow([f'{b2}_collection_frame_rate','fps', self.fps])
        writer.writerow([f'{b2}_rec_frame_rate','fps', self.recFPS])
        writer.writerow([f'{b2}_prev_frame_rate','fps', self.previewFPS])
        writer.writerow([f'{b2}_exposure','ms', self.exposure])
        writer.writerow([f'{b2}_flag1','', self.flag1])
        
    #-------
    
    def updateFramesToPrev(self):
        '''calculate the number of frames to downsample for preview'''
        self.critFramesToPrev = max(round(self.fps/self.previewFPS), 1)
        self.framesSincePrev = self.critFramesToPrev
        
    def setPFrameRate(self, previewFPS:float) -> int:
        '''update the preview frame rate'''
        if self.previewFPS==previewFPS:
            return 1
        else:
            self.previewFPS =  previewFPS
            self.updateFramesToPrev()
            if hasattr(self, 'vc'):
                # update the vc object
                self.vc.lock()
                self.vc.updatePrevFPS(self.previewFPS)
                self.vc.unlock()
            
    def setFrameRate(self, fps:float) -> int:
        '''Set the frame rate of the camera. Return 0 if value changed, 1 if not'''
        if self.recording:
            logging.warning('Cannot change frame rate while recording.')
            self.guiBox.resetFPS(self.fps)
            return
            
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
            
            if hasattr(self, 'vc'):
                # update the vc object
                self.vc.lock()
                self.vc.updateFPS(self.fps)
                self.vc.unlock()
            return 0
        
    def setRecFrameRate(self, fps:float) -> int:
        '''set the recording frame rate of the camera. Return 0 if value changed, 1 if not'''
        if self.recording:
            logging.warning('Cannot change frame rate while recording.')
            self.guiBox.resetRecFPS(self.recFPS)
            return
            
        if self.recFPS==fps:
            return 1
        else:
            if hasattr(self, 'vc'):
                # update the vc object
                self.vc.lock()
                self.vc.recFPS=self.recFPS
                self.vc.unlock()
            return 0
        
    def setFrameRateAuto(self) -> int:
        return self.setFrameRate(self.getFrameRate())
    
    def getFrameRate(self):
        '''get the native frame rate of the camera'''
        if self.deviceOpen:
            self.vc.lock()
            fps = self.vc.getFrameRate()
            self.vc.unlock()
            if fps>0:
                return fps
            else:
                return self.fps
        else:
            return self.fps
        
    #-------
              

    def getFilename(self, ext:str) -> str: 
        '''determine the file name for the file we're about to record. ext is the extension. Uses the timestamp for unique file names. The folder is determined by the saveFolder established in the top box of the GUI.'''

        try:
            fullfn = self.sbWin.newFile(self.cameraName, ext)
        except NameError as e:
            logging.error(e)
            return

        return fullfn
    
    def snap(self) -> None:
        '''take a single snapshot and save it. Put this process in the background through QThreadPool'''
        
        fullfn = self.getFilename('.png')
        if self.previewing or self.recording:
            # if we're currently collecting frames, we can use the last frame
            self.vc.lock()
            cv2.imwrite(fullfn, self.vc.frame)
            self.vc.unlock()
            self.updateStatus(f'File saved to {fullfn}', True)
        else:
            # if we're not currently collecting frames, we need to collect a new frame.
            last = False
            snapthread = camSnap(self.vc, fullfn)       # create an object to collect and save the snapshot in background
            snapthread.signals.result.connect(self.updateStatus)   # let the camSnap object send messages to the status bar
            snapthread.signals.error.connect(self.updateStatus)
            QThreadPool.globalInstance().start(snapthread)  # get snapshot in background thread
        
        
    #---------------------------------
    
    
    
    def startPreview(self) -> None: 
        '''start live preview'''
        # critFramesToPrev reduces the live display frame rate, 
        # so only have to update the display at a comfortable viewing rate.
        # if the camera is at 200 fps, the video will be saved at full rate but
        # preview will only show at 15 fps
        self.updateFramesToPrev()
        self.previewing = True
        self.vc.lock()
        self.vc.previewing = True
        self.vc.unlock()
        self.startReader()      # this only starts the reader if we're not already recording
        self.startPreviewer()
    
    def stopPreview(self) -> None:
        '''stop live preview. This freezes the last frame on the screen.'''
        self.previewing = False
        if hasattr(self, 'vc'):
            self.vc.lock()
            self.vc.previewing = False
            self.vc.unlock()
        self.stopReader()       # this only stops the reader if we are neither recording nor previewing
        self.stopPreviewer()
 
    #---------------------------------
    
    def startRecording(self) -> None:
        '''start recording a video'''
        
        if self.writing:
            if not self.writeWarning:
                logging.info('Still writing last video. Waiting.')
                self.writeWarning=True
            QTimer.singleShot(50, self.startRecording) # stop previewing and recording
        else:
            self.createWriter()
                
                
    def createWriter(self) -> None:
        '''create a videoWriter object'''
        self.writeWarning=False
        self.recording = True
        self.writing = True
        self.vc.lock()
        self.vc.recording = True
        self.vc.writing = True
        self.vc.unlock()
        self.resetVidStats()                       # this resets the frame list, and other vars
        fn = self.getFilename('.avi')              # generate a new file name for this video
        self.vFilename = fn
        vidvars = {'fourcc':self.fourcc, 'fps':self.fps, 'recFPS':self.recFPS, 'imw':self.imw, 'imh':self.imh, 'cameraName':self.cameraName}
        
        # https://realpython.com/python-pyqt-qthread/
        self.writeThread = QThread()
        # Step 3: Create a worker object
        self.writeWorker = vidWriter(fn, vidvars, self.frames)         # creates a new thread to write frames to file      
        # Step 4: Move worker to the thread
        self.writeWorker.moveToThread(self.writeThread)
        # Step 5: Connect signals and slots
        self.writeThread.started.connect(self.writeWorker.run)       
        self.writeWorker.signals.finished.connect(self.writeThread.quit)
        self.writeWorker.signals.finished.connect(self.writeWorker.deleteLater)
        self.writeThread.finished.connect(self.writeThread.deleteLater)
        self.writeWorker.signals.finished.connect(self.doneRecording)        # connects vidWriter status updates to the status display
        self.writeWorker.signals.progress.connect(self.writingRecording)
        self.writeWorker.signals.error.connect(self.updateStatus)
        # Step 6: Start the thread
        self.writeThread.start()

        self.updateStatus(f'Recording {self.vFilename} ... ', True) 
        # QThreadPool.globalInstance().start(recthread)          # start writing in a background thread
        self.startReader()                          # this only starts the reader if we're not already previewing

    
    
    def stopRecording(self) -> None:
        '''stop collecting frames for the video'''
        if not self.recording:
            return
        self.frames.put([None,0]) # this tells the vidWriter that this is the end of the video
        self.recording = False
        if hasattr(self, 'vc'):
            self.vc.lock()
            self.vc.recording = False     # this helps the frame reader and the status update know we're not reading frames
            self.vc.unlock()
        self.stopReader()           # only turns off the reader if we're not recording or previewing

            
    
    #-------------------------------
    
    
    def resetVidStats(self) -> None:
        '''reset video stats, to start a new video'''
        self.startTime = 0      # the time when we started the video
        self.timeRec = 0        # how long the video is
        self.framesDropped = 0  # how many frames we've dropped
        self.totalFrames = 0    # how many frames are in the video
        self.fleft = 0          # how many frames we still need to write to file
        with self.frames.mutex:
            self.frames.queue.clear()
        self.lastFrame = []     # last frame collected. kept in a list of one cv2 frame to make it easier to pass between functions
        self.startTime = datetime.datetime.now()
        self.lastTime = self.startTime
        self.fnum = 0
        self.rids = []   # vidReader ids

        
    def startReader(self) -> None:
        '''start updating preview or recording'''
        if not self.readerRunning:
            self.readerRunning = True
            # if self.diag>1:
            #     logging.debug(f'Starting {self.cameraName} reader')
            
            # https://realpython.com/python-pyqt-qthread/
            self.readThread = QThread()
            # Step 3: Create a worker object
            self.readWorker = vidReader(self.vc)         # creates a new thread to read frames to GUI      
            # Step 4: Move worker to the thread
            self.readWorker.moveToThread(self.readThread)
            # Step 5: Connect signals and slots
            self.readThread.started.connect(self.readWorker.run)  
            self.readWorker.signals.finished.connect(self.readThread.quit)
            self.readWorker.signals.finished.connect(self.readWorker.deleteLater)
            self.readThread.finished.connect(self.readWorker.close)
            self.readThread.finished.connect(self.readThread.deleteLater)
            self.readWorker.signals.error.connect(self.updateStatus)
            self.readWorker.signals.frame.connect(self.receiveRecFrame)
            self.readWorker.signals.progress.connect(self.printDiagnostics)
            # Step 6: Start the thread
            self.readThread.start()
            
    def startPreviewer(self) -> None:
        '''start updating preview'''
        if not self.prevRunning:
            self.prevRunning = True
            # if self.diag>1:
            #     logging.debug(f'Starting {self.cameraName} reader')
            
            # https://realpython.com/python-pyqt-qthread/
            self.prevThread = QThread()
            # Step 3: Create a worker object
            self.prevWorker = previewer(self.vc)         # creates a new thread to read frames to GUI      
            # Step 4: Move worker to the thread
            self.prevWorker.moveToThread(self.prevThread)
            # Step 5: Connect signals and slots
            self.prevThread.started.connect(self.prevWorker.run)  
            self.prevWorker.signals.finished.connect(self.prevThread.quit)
            self.prevWorker.signals.finished.connect(self.prevWorker.deleteLater)
            self.prevThread.finished.connect(self.prevWorker.close)
            self.prevThread.finished.connect(self.prevThread.deleteLater)
            self.prevWorker.signals.error.connect(self.updateStatus)
            self.prevWorker.signals.frame.connect(self.receivePrevFrame)
            self.prevWorker.signals.progress.connect(self.printDiagnostics)
            # Step 6: Start the thread
            self.prevThread.start()

            
    @pyqtSlot(str)
    def printDiagnostics(self, s:str):
        '''print diagnostics to the log'''
        logging.debug(s)
        

    @pyqtSlot(np.ndarray, bool)
    # def receiveFrame(self, frame:np.ndarray, frameNum:int, vrid:int, checkDrop:bool=True):
    def receiveRecFrame(self, frame:np.ndarray, pad:bool):
        '''receive a frame from the vidReader thread. pad indicates whether the frame is a filler frame'''

        self.lastFrame = [frame]       
        self.saveFrame(frame)        # save to file
        if pad:
            self.framesDropped+=1
            
    @pyqtSlot(np.ndarray, bool)
    # def receiveFrame(self, frame:np.ndarray, frameNum:int, vrid:int, checkDrop:bool=True):
    def receivePrevFrame(self, frame:np.ndarray, pad:bool):
        '''receive a frame from the vidReader thread. pad indicates whether the frame is a filler frame'''

        self.lastFrame = [frame]       
        self.updatePrevFrame(frame)  # update the preview window 

    #---------------------------------
    
    def stopReader(self) -> None:
        '''this only stops the reader if we are neither recording nor previewing'''
        if not self.recording and not self.previewing and self.readerRunning:
            logging.info(f'{self.cameraName} reader stopped')
            self.readerRunning = False
            
    def stopPreviewer(self) -> None:
        if not self.recording and not self.previewing and self.prevRunning:
            logging.info(f'{self.cameraName} previewer stopped')
            self.prevRunning = False
           
    
    #---------------------------------
    
    def updatePrevFrame(self, frame:np.ndarray) -> None:
        '''update the live preview window'''
        # update the preview
        if not self.previewing:
            return
        
        if type(frame)==np.ndarray:
            self.framesSincePrev=1
            # convert frame to pixmap in separate thread and update window when done
            self.updatePrevWindow(frame)
        else:
            self.updateStatus(f'Frame is empty', True) 

        
    def updatePrevWindow(self, frame:np.ndarray) -> None:
        '''update the display with the new pixmap'''
        if self.convertColors:
            frame2 = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            frame2 = frame
        image = QImage(frame2, frame2.shape[1], frame2.shape[0], QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        self.prevWindow.setPixmap(pixmap)

        
    def saveFrame(self, frame:np.ndarray) -> None:
        '''save the frame to the video file. frames are in cv2 format. '''
        if not self.recording:
            return
     
        try:
            self.frames.put([frame, self.timeRec])  # add the frame to the queue that videoWriter is watching
        except:
            # stop recording if we can't write
            self.updateStatus(f'Error writing to video', True)
        else:
            # display the time recorded
            self.timeRec = self.timeRec+self.mspf/1000
            self.totalFrames+=1
            self.updateRecordStatus()
            
    #-----------------------------

            
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
                    raise ValueError('Do not log this message')
            else:
                # reset the count and don't report if it's been at least 1 second since the last collision
                self.collisionCount = 1
                raise ValueError('Do not log this message')
        else:
            return st       


    @pyqtSlot(str,bool)
    def updateStatus(self, st:str, log:bool) -> None:
        '''updates the status of the widget that this camera belongs to. 
        st is the status message. 
        log determines whether to write to log. '''
        
        try:
            st = self.updateCollisions(st)
        except ValueError as e:
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
        saveFreq = int(round(self.fps/self.recFPS))
        s+= f'{self.vFilename} {self.timeRec:2.2f} s, '
        if self.writing and not self.recording:
            s+= f'{int(np.floor(self.fleft/saveFreq))}/{int(np.floor(self.totalFrames/saveFreq))} frames left'
        else:
            s+= f'{int(np.floor(self.framesDropped/saveFreq))}/{int(np.floor(self.totalFrames/saveFreq))} frames dropped'
        self.updateStatus(s, log)
        
    @pyqtSlot(int)
    def writingRecording(self, fleft:int) -> None:  
        '''this function updates the status to say that the video is still being saved. 
        fleft is the number of frames left to record'''
        # if self.diag>1:
        #     # if we're in debug mode for this camera, log that we wrote a frame for this camera
        #     logging.debug(f'{self.cameraName}\twrite\t{fleft}')
        if not self.recording:
            self.fleft = fleft
            self.updateRecordStatus()
            
    @pyqtSlot()
    def doneRecording(self) -> None:
        '''update the status box when we're done recording  '''
        self.writing = False
        self.vc.lock()
        self.vc.writing = False
        self.vc.unlock()
        self.updateRecordStatus()
        
    #-----------------------------------    
    
    def closeCam(self) -> None:
        '''disconnect from the camera when the window is closed'''
        self.stopPreview()
        self.stopRecording()
        if hasattr(self, 'vc'):
            self.vc.lock()
            self.vc.recording = False
            self.vc.previewing = False  
            self.vc.unlock()
            
            
    def close(self) -> None:
        '''this gets triggered when the whole window is closed. Disconnects from the cameras and deletes videoCapture objects'''
        self.closeCam()   # tell reader to stop
        QTimer.singleShot(1000, self.finishClose)   # wait a bit, then finish closing  
        
    def finishClose(self) -> None:
        '''finish closing the camera'''
        for s in ['writeThread', 'recThread']:
            if hasattr(self, s):
                o = getattr(self, s)
                if not sip.isdeleted(o) and o.isRunning():
                    o.quit()
        if hasattr(self, 'vc'):
            self.vc.close()
            del self.vc
        
        

        
                    
    

