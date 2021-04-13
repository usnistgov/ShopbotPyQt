#!/usr/bin/env python
'''Shopbot GUI Shopbot functions'''

from PyQt5 import QtCore, QtGui
import PyQt5.QtWidgets as qtw
import cv2
import time
import datetime
import numpy as np
import os, sys
import subprocess
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging

# currentdir = os.path.dirname(os.path.realpath(__file__))
# sys.path.append(currentdir)
# sys.path.append(os.path.join(currentdir, 'icons'))

from sbgui_general import *

__author__ = "Leanne Friedrich"
__copyright__ = "This data is publicly available according to the NIST statements of copyright, fair use and licensing; see https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software"
__credits__ = ["Leanne Friedrich"]
__license__ = "MIT"
__version__ = "1.0.4"
__maintainer__ = "Leanne Friedrich"
__email__ = "Leanne.Friedrich@nist.gov"
__status__ = "Development"

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


def mode2title(mode:int) -> str:
    '''convert a mode number to a camera title'''
    if mode==0:
        return 'Basler camera'
    elif mode==1:
        return 'Nozzle camera'
    elif mode==2:
        return 'Webcam 2'
    
#########################################################

class vrSignals(QtCore.QObject):
    '''Defines the signals available from a running worker thread
        Supported signals are:
        finished: No data
        error: a string message and a bool whether this is worth printing to the log
        result:`object` data returned from processing, anything
        progress: `int` indicating % progress '''
    
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str, bool)
    progress = QtCore.pyqtSignal(int)
    prevFrame = QtCore.pyqtSignal(np.ndarray)

    

#########################################################

class vidWriter(QtCore.QRunnable):
    '''The vidWriter creates a cv2.VideoWriter object at initialization, and it takes frames in the queue and writes them to file. This is a failsafe, so if the videowriter writes slower than the timer reads frames, then we can store those extra frames in memory until the vidWriter object can write them to the HD. 
QRunnables run in the background. Trying to directly modify the GUI display from inside the QRunnable will make everything catastrophically slow, but you can pass messages back to the GUI using vrSignals.'''
    
    def __init__(self, fn:str, vidvars, frames:List[np.ndarray], cam):
        super(vidWriter, self).__init__()        
        self.vFilename = fn
        self.vw = cv2.VideoWriter(fn, vidvars['fourcc'], vidvars['fps'], (vidvars['imw'], vidvars['imh']))
        self.signals = vrSignals()  
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
                if self.cam.diag>1:
                    # if we're in debug mode for this camera, log that we wrote a frame for this camera
                    logging.debug(self.cam.cameraName+'\twrite\t'+str(len(self.frames)))
                if len(self.frames) % 100==1:
                    # on every 100th frame, tell the GUI how many frames we still have to write
                    self.signals.progress.emit(len(self.frames))
        
                    
                    
###############################################


                    
class vidReader(QtCore.QRunnable):
    '''vidReader puts frame collection into the background, so frames from different cameras can be collected in parallel'''
    
    def __init__(self, cam, vrid:int, frames:List[np.ndarray], lastFrame:List[np.ndarray]):
        super(vidReader, self).__init__()
        self.cam = cam              # the camera object that called this reader
        self.lastFrame = lastFrame  # pointer to the list that holds the last frame
        self.signals = vrSignals()  # signals that let this send messages back to the GUI
        self.frames = frames        # pointer to the list that holds the frames that haven't been written yet
        self.vrid = vrid            # vidReader id. Helps prevent duplicate padding.
        
    def run(self) -> None:
        '''Run this function when this thread is started. Collect a frame, and pad the frame list if we dropped frames.'''
        
        # get an image
        try:
            frame = self.cam.readFrame()
        except Exception as e:
            frame = self.lastFrame[0]
            if len(str(e))>0:
                self.signals.error.emit(f'Error collecting frame: {e}', True)
            
        # update the preview
        if self.cam.previewing:
            # downsample preview frames
            if self.cam.framesSincePrev==self.cam.critFramesToPrev:
                if type(frame)==np.ndarray:
                    self.signals.prevFrame.emit(frame)
                    self.cam.framesSincePrev=0
                else:
                    self.signals.error.emit(f'Frame is empty', True)
            else:
                self.cam.framesSincePrev+=1
                
        # save the frame
        if self.cam.recording:
            # if we've skipped at least 2 frames, fill that space with duplicate frames
            # if we have two vidReaders going at once, only do this with the first one
            if len(self.cam.vridlist)==0 or self.vrid == min(self.cam.vridlist):
                self.timerCheckDrop() 
                
            self.saveFrame(frame) 
            
            # remove this vidreader id from the list of ids
            if self.vrid in self.cam.vridlist:
                self.cam.vridlist.remove(self.vrid)
        
        
    
    def saveFrame(self, frame:np.ndarray) -> None:
        '''save the frame to the video file. frames are in cv2 format. Called by run'''
        try:
            self.frames.append(frame)
        except:
            # stop recording if we can't write
            self.signals.error.emit(f'Error writing to video', True)
            
        else:
            # display the time recorded
            self.cam.timeRec = self.cam.timeRec+self.cam.mspf/1000
            self.cam.totalFrames+=1
            self.cam.updateRecordStatus()
 
          
    def timerCheckDrop(self) -> None:
        '''check to see if the timer has skipped steps and fills the missing frames with duplicates. Called by run '''
        dnow = datetime.datetime.now()
        if self.cam.startTime==0:
            self.cam.startTime = dnow
            if self.cam.diag>1:
                self.cam.lastTime = dnow
        else:
            timeElapsed = (dnow-self.cam.startTime).total_seconds()
            if (timeElapsed - self.cam.timeRec)>2*self.cam.mspf/1000:
                # if we've skipped at least 2 frames, fill that space with duplicate frames
                numfill = int(np.floor((timeElapsed-self.cam.timeRec)/(self.cam.mspf/1000)))
                for i in range(numfill):
                    if self.cam.diag>1:
                        logging.debug(self.cam.cameraName+'\t'+str(self.vrid)+ '\tPAD\t\t\t\t '+'%2.3f'%self.cam.timeRec)
                    self.cam.framesDropped+=1
                    self.saveFrame(self.lastFrame[0])
            if self.cam.diag>1:
                frameElapsed = ((dnow-self.cam.lastTime).total_seconds())*1000
                s = self.cam.cameraName+'\t'+str(self.vrid)+'\t'
                for si in ['%2.3f'%t for t in [len(self.frames), frameElapsed, self.cam.mspf, timeElapsed, self.cam.timeRec]]:
                    s = s+si+'\t'
                logging.debug(s)
                self.cam.lastTime = dnow
   
 ###########################
    # snapshots
    
class snapSignals(QtCore.QObject):
    '''signal class to send messages back to the GUI during snap collection'''
    
    result = QtCore.pyqtSignal(str, bool)
    error = QtCore.pyqtSignal(str, bool)

class camSnap(QtCore.QRunnable):
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
                frame = self.cam.readFrame()
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
   

 #########################################################        

class camera:
    '''a camera object is a generic camera which stores functions and camera info for both pylon cameras and webcams
        these objects are created by cameraBox objects
        each type of camera (Basler and webcam) has its own readFrame and close functions'''
    
    def __init__(self, sbWin:qtw.QMainWindow, guiBox:connectBox):
        self.previewing = False
        self.sbWin = sbWin                        # sbWin is the parent window
        self.guiBox = guiBox                      # guiBox is the parent box for this camera
        self.cameraName = mode2title(guiBox.mode) # name of the camera (a string)
        self.vFilename = ''                       # name of the current video file
        self.timerRunning = False                 # is the timer that controls frame collection running?
        self.previewing = False                   # is the live preview on?
        self.recording = False                    # are we collecting frames for a video?
        self.writing = True                       # are we writing video frames to file?
        self.timer = None                         # the timer that controls frame collection
        self.resetVidStats()
        self.framesSincePrev = 0  # how many frames we've collected since we updated the live display
        self.diag = 1             # diag tells us which messages to log. 0 means none, 1 means some, 2 means a lot
        self.fps = 0              # this will be set during subclass init (webcam.__init__, bascam.__init__)
        self.exposure = 0         # this will be set during subclass init (webcam.__init__, bascam.__init__)
        self.fourcc = cv2.VideoWriter_fourcc('M','J','P','G')
        self.prevWindow = qtw.QLabel()                # the window that the live preview will be displayed in
        self.collisionCount = 0                       # this keeps track of frame read collisions
        self.lastCollision = datetime.datetime.now()  # this keeps track of the time between frame read collisions
            
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
            return 0
        
    def setFrameRateAuto(self) -> int:
        return self.setFrameRate(self.getFrameRate())
    
    
    def closeCam(self) -> None:
        '''disconnect from the camera when the window is closed'''
        self.recording = False
        self.previewing = False
        if not self.timer==None:
            try:
                self.timer.stop()
            except:
                pass
            else:
                if self.diag>0:
                    logging.info(self.cameraName + ' timer stopped')
                
          
    def doneRecording(self) -> None:
        '''update the status box when we're done recording  '''
        self.writing = False
        self.updateRecordStatus()
    
    
    def getFilename(self, ext:str) -> str: 
        '''determine the file name for the file we're about to record. ext is the extension. Uses the timestamp for unique file names. The folder is determined by the saveFolder established in the top box of the GUI.'''

        try:
            folder, filename = self.sbWin.newFile()
        except NameError:
            return
        
        filename = filename + ('_' if len(filename)>0 else '')+self.cameraName
        filename = filename + '_'+time.strftime('%y%m%d_%H%M%S')+ext
        fullfn = os.path.join(folder, filename)
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
        QtCore.QThreadPool.globalInstance().start(snapthread)  # get snapshot in background thread
            
            
    
    #---------------------------------
    
    def startPreview(self) -> None: 
        '''start live preview'''
        # critFramesToPrev reduces the live display frame rate, 
        # so only have to update the display at a comfortable viewing rate.
        # if the camera is at 200 fps, the video will be saved at full rate but
        # preview will only show at 15 fps
        self.critFramesToPrev = max(round(self.fps/15), 1)
        self.framesSincePrev = self.critFramesToPrev
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
        QtCore.QThreadPool.globalInstance().start(recthread)          # start writing in a background thread
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
    # start the timer if there is not already a timer
    def startTimer(self) -> None:
        if not self.timerRunning:
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self.timerFunc)        # run the timerFunc every mspf milliseconds
            self.timer.setTimerType(QtCore.Qt.PreciseTimer)   # may or may not improve timer accuracy, depending on computer
            self.timer.start(self.mspf)                       # start timer with frequency milliseconds per frame
            self.timerRunning = True
            if self.diag>1:
                logging.debug(self.cameraName + ': Starting timer')
        
#     def readError(self, errnum:int, errstr:str) -> None:
#         self.updateStatus(errstr, True)
#         if errnum==1:
#             self.recording = False  
    
    
    def stopTimer(self) -> None:
        '''this only stops the timer if we are neither recording nor previewing'''
        if not self.recording and not self.previewing:
            self.timer.stop()
            self.timerRunning = False
            if self.diag>1:
                logging.info(self.cameraName + ': Stopping timer')
    
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
        QtCore.QThreadPool.globalInstance().start(runnable)
    
    #---------------------------------
    
    def updatePrevFrame(self, frame:np.ndarray) -> None:
        '''update the live preview window'''
        try:
            # we need to convert the frame from the OpenCV cv2 format to the Qt QPixmap format
            if self.convertColors:
                frame2 = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                frame2 = frame
            image = QtGui.QImage(frame2, frame2.shape[1], frame2.shape[0], QtGui.QImage.Format_RGB888)
            pixmap = QtGui.QPixmap.fromImage(image)
            self.prevWindow.setPixmap(pixmap)
        except Exception as e:
            # stop previewing if we can't preview
            self.updateStatus('Error displaying frame', True)
            self.previewing = False
            self.stopTimer()
            
    def updateCollisions(self, st:str) -> str:
        '''a common error during frame collection is 'Basler camera:Error collecting frame: Error collecting grab: There is already a thread waiting for a result. : RuntimeException thrown (file 'instantcameraimpl.h', line 1096)'. This prevents pile up of those messages. It returns a string to be logged.'''
        if 'There is already a thread waiting for a result' in st:
            now = datetime.datetime.now()
            elapsed = (now-self.lastCollision).total_seconds()
            self.lastCollision = now
            if elapsed<1:
                # if the last collision happened recently, note how many collisions there have been in a row
                self.collisionCount+=1
                if self.collisionCount % 50 == 0:
                    # if we've had 50 collisions in a row in quick succession, report an error
                    st = f'{self.collisionCount} frame read collisions in a row. Consider decreasing frame rate.'
                    return st
                else:
                    raise Exception('Do not log this message')
            else:
                # reset the count and don't report if it's been at least 1 second since the last collision
                self.collisionCount = 1
                raise Exception('Do not log this message')
        else:
            return st

    
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
            s+= str(self.fleft) + '/' + str(self.totalFrames) + ' frames left'
        else:
            s+= str(self.framesDropped) + '/' + str(self.totalFrames) +' frames dropped'
        self.updateStatus(s, log)
        
    
    def writingRecording(self, fleft:int) -> None:  
        '''this function updates the status to say that the video is still being saved. 
        fleft is the number of frames left to record'''
        if not self.recording:
            self.fleft = fleft
            self.updateRecordStatus()
        
        
##################


class webcam(camera):
    '''webcams are objects that hold functions for conventional webcams that openCV (cv2) can communicate with'''
    
    def __init__(self, sbWin:qtw.QMainWindow, guiBox:connectBox):
        super(webcam, self).__init__(sbWin, guiBox)

        # connect to webcam through OpenCV
        try:
            self.camDevice = cv2.VideoCapture(guiBox.mode-1)
            self.readFrame()
        except:
            self.connected = False
            return
        else:
            self.connected = True
        
        # get image stats
        self.setFrameRateAuto()
        self.imw = int(self.camDevice.get(3))               # image width (px)
        self.imh = int(self.camDevice.get(4))               # image height (px)
        self.prevWindow.setFixedSize(self.imw, self.imh)    # set the preview window to the image size
        self.getExposure()
        
        self.convertColors = True
        
    def getFrameRate(self) -> float:
        '''Determine the native device frame rate'''
        return self.camDevice.get(cv2.CAP_PROP_FPS)/2 # frames per second

    def getExposure(self):
        '''Read the current exposure on the camera'''
        self.exposure=1000*2**self.camDevice.get(cv2.CAP_PROP_EXPOSURE)
        
    def exposureAuto(self):
        '''Automatically adjust the exposure. https://docs.baslerweb.com/exposure-auto'''
#         self.camDevice.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
#         self.getExposure()
        if self.diag>0:
            self.updateStatus('Cannot update webcam exposure. Feature in development.', True)
        return 1
        
    def setExposure(self, val:float) -> int:
        '''Set the exposure time to val'''
        if self.diag>0:
            self.updateStatus('Cannot update webcam exposure. Feature in development.', True)
        return 1
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
        
    #-----------------------------------------
        
     
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
            # if we successfully read the frame, keep it in lastFrame
            self.lastFrame = [frame]
            return frame
 
    #-----------------------------------------
    
    
    def close(self) -> None:
        '''this gets triggered when the whole window is closed. Disconnects from the cameras'''
        
        self.closeCam()
        if not self.camDevice==None:
            try:
                self.camDevice.release()
            except:
                pass
            else:
                if self.diag>0:
                    logging.info(self.cameraName + ' closed')
    

#########################################      
      

class bascam(camera):
    '''bascams are Basler cameras that require the pypylon SDK to communicate'''
    
    def __init__(self, sbWin:qtw.QMainWindow, guiBox:connectBox):
        super(bascam, self).__init__(sbWin, guiBox)
        self.vFilename = ''
        self.connected = False
        self.convertColors = True
        self.errorStatus = 0      # 0 means we have no outstanding errors. This prevents us from printing a ton of the same error in a row.
        
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
            self.errorStatus = 0
            # update the GUI display to show camera model
            self.guiBox.model = self.camDevice.GetDeviceInfo().GetModelName()
            self.guiBox.updateBoxTitle()
            
            # converter converts pylon images into cv2 images
            self.converter = pylon.ImageFormatConverter()
            self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
            self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
            
            # get camera stats
            self.setFrameRateAuto()                             # read the default frame rate from the camera
            tryFrame = 0
            while tryFrame<10:
                try:
                    f1 = self.readFrame()                               # get a sample frame
                    self.imw = len(f1[0])                               # image width (px)
                    self.imh = len(f1)                                  # image height (px)
                    self.prevWindow.setFixedSize(self.imw, self.imh)    # set the preview window to the image size
                except:
                    tryFrame+=1     # if we failed to read a frame, try again
                    time.sleep(1)
                else:
                    tryFrame = 10
                
            self.getExposure()                                  # read the default exposure time from the camera
            
            # if we successfully read the frame, keep it in lastFrame
            self.lastFrame = [f1]

        # if we failed to connect to the camera, close it, and display a failure state on the GUI
        except Exception as e:
            try:
                self.camDevice.Close() # close camera if we've already opened it
            except:
                pass
            self.grabError(e, 2, False)
            self.connected = False
            return 
        
    def getFrameRate(self):
        '''Determine the frame rate of the camera'''
        fps = self.camDevice.ResultingFrameRate.GetValue()
        return fps
        
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
        
    def setExposure(self, val:float) -> int:
        '''Set the exposure time to val. Returns 0 if the value was changed, 1 if not.'''
        if self.exposure==val*1000:
            return 1
        else:
            if val>self.mspf:
                # exposure time is longer than frame rate. reject.
                if self.diag>0:
                    self.updateStatus(f'Requested exposure time {val} is higher than frame rate {self.mspf} ms per frame. Exposure time not updated.', True)
                return 1
            self.camDevice.ExposureTime.SetValue(val*1000) # convert from milliseconds to microseconds
            self.getExposure()
            return 0
        
    def getExposure(self):
        self.exposure = self.camDevice.ExposureTime.GetValue()/1000 # convert from microseconds to milliseconds
        
        
    #-----------------------------------------
        
    
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
            # if we successfully read the frame, keep it in lastFrame
            self.lastFrame = [img]
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
    
    
    #-----------------------------------------
    
    def close(self) -> None:
        '''this gets triggered when the whole window is closed'''
        self.closeCam()
        try:
            self.camDevice.StopGrabbing()
            self.camDevice.Close()
        except:
            pass
        else:
            if self.diag>0:
                logging.info('Basler camera closed')
            
################################################
        
class camSettingsBox(qtw.QWidget):
    '''This opens a window that holds settings about logging for cameras.'''
    
    
    def __init__(self, parent:connectBox, bTitle:str, camObj:camera):
        '''parent is the connectBox that this settings dialog belongs to. 
            bTitle is the box title, e.g. webcam 2. 
            camObj is the camera object that holds functions and info for a specific camera.'''
        
        super().__init__(parent)  
        self.camObj = camObj
        
        layout = qtw.QVBoxLayout()
        
        form = qtw.QFormLayout()
        
        self.diagRow = qtw.QHBoxLayout()
        self.diag1 = qtw.QRadioButton('None')
        self.diag2 = qtw.QRadioButton('Just critical')
        self.diag2.setChecked(True)
        self.diag3 = qtw.QRadioButton('All frames')
        self.diagGroup = qtw.QButtonGroup()
        for i,b in enumerate([self.diag1, self.diag2, self.diag3]):
            self.diagGroup.addButton(b, i)
            self.diagRow.addWidget(b)
        self.diagGroup.buttonClicked.connect(self.changeDiag)
        form.addRow("Log", self.diagRow)
              
        self.fpsBox = qtw.QLineEdit()
        self.fpsBox.setText(str(self.camObj.fps))
        self.fpsAutoButt = qtw.QPushButton('Auto')
        self.fpsAutoButt.clicked.connect(self.fpsAuto)
        self.fpsAutoButt.setAutoDefault(False)
        fpsRow = qtw.QHBoxLayout()
        fpsRow.addWidget(self.fpsBox)
        fpsRow.addWidget(self.fpsAutoButt)
        form.addRow('Frame rate (fps)', fpsRow)
        
        self.exposureBox = qtw.QLineEdit()
        self.exposureBox.setText(str(self.camObj.exposure))
        self.exposureAutoButt = qtw.QPushButton('Auto')
        self.exposureAutoButt.clicked.connect(self.exposureAuto)
        self.exposureAutoButt.setAutoDefault(False)
        self.exposureAutoButt.setEnabled(False)   # exposure auto doesn't work yet
        if self.camObj.guiBox.mode>0:
            # webcam. exposure doesn't work
            self.enableExposureBox = False
            self.exposureBox.setEnabled(False)
        else:
            self.enableExposureBox = True
        exposureRow = qtw.QHBoxLayout()
        exposureRow.addWidget(self.exposureBox)
        exposureRow.addWidget(self.exposureAutoButt)
        form.addRow('Exposure (ms)', exposureRow)

        layout.addLayout(form)
        
        self.goButt = qtw.QPushButton('Save')
        self.goButt.clicked.connect(self.updateVars)
        self.goButt.setFocus()
        self.goButt.setAutoDefault(True)
        layout.addWidget(self.goButt)
        self.setLayout(layout)
        
#         self.reset = qtw.QPushButton('Reset camera')
#         self.reset.clicked.connect(parent.connect)
#         self.layout.addWidget(self.reset)

        
    def changeDiag(self, diagbutton):
        '''Change the diagnostics status on the camera, so we print out the messages we want.'''
        self.camObj.diag = self.diagGroup.id(diagbutton) 
        
            
    def updateVars(self):
        '''Update the set variables'''
        self.updateFPS()
        if self.enableExposureBox:
            self.updateExposure()
        
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
        out = self.camObj.exposureAuto()
        if out==0:
            self.exposureBox.setText(str(self.camObj.exposure))
            self.exposureStatus()
        
            
    #--------------------------
    # fps

    def fpsStatus(self):
        '''Log the change in fps'''
        if self.camObj.diag>0:
            self.camObj.updateStatus(f'Changed frame rate to {self.camObj.fps} fps', True)
        
    def updateFPS(self):
        '''Update the frame rate used by the GUI to the given frame rate'''
        out = self.camObj.setFrameRate(float(self.fpsBox.text()))
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
    
    def __init__(self, mode:int, sbWin:qtw.QMainWindow):
        '''Mode is the type of camera. 0 is a basler camera, 1 is the nozzle camera, and 2 is webcam 2.
        sbWin is the parent window that this box sits inside of.'''
        super(cameraBox, self).__init__()
        self.mode = mode # 
        self.model = ''   # name of camera
        self.connected = False
        self.previewing = False
        self.recording = False
        self.imw=0
        self.imh=0
        self.img = []
        self.bTitle = mode2title(mode)
        self.sbWin = sbWin
        self.connect() # try to connect to the camera
        self.updateBoxTitle()
        if self.connected:
            if self.camObj.diag>0:
                logging.info(self.bTitle, ' ', self.camObj.fps, ' fps')

    
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
        if self.mode==0:
            self.camObj = bascam(sbWin, self)
        else:
            self.camObj = webcam(sbWin, self)
        if self.camObj.connected:
            self.successLayout()
        else:
            self.failLayout() # inherited from connectBox
            
    
    def successLayout(self) -> None:
        '''this is the layout if we successfully connected to the camera'''
        
        self.settingsBox = camSettingsBox(self, self.bTitle, self.camObj)
        
        self.resetLayout()
        self.layout = qtw.QVBoxLayout()

        self.camInclude = qtw.QToolButton()        
        self.camInclude.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.camInclude.setCheckable(True)
        self.camInclude.clicked.connect(self.updateCamInclude)
        self.updateCamInclude() 
        
        self.camPrev = qtw.QToolButton()
        self.camPrev.clicked.connect(self.cameraPrev)
#         self.camPrev.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.camPrev.setCheckable(True)
        self.setPrevButtStart()
        
        self.camRec = qtw.QToolButton()
        self.camRec.clicked.connect(self.cameraRec)
        self.camRec.setCheckable(True)
        self.setRecButtStart()
        
        self.camPic = qtw.QToolButton()
        self.camPic.setIcon(icon('camera.png'))
        self.camPic.setStyleSheet(self.unclickedSheet())
        self.camPic.clicked.connect(self.cameraPic)
        self.camPic.setToolTip('Snapshot') 

        self.camButts = qtw.QToolBar()
        self.camButts.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        buttons =  [self.camPrev, self.camRec, self.camPic]
        for b in buttons:
            self.camButts.addWidget(b)
        self.camButts.setStyleSheet("QToolBar{spacing:5px;}");
        
        self.status = qtw.QLabel('Ready')
        self.status.setFixedSize(self.camObj.imw - (self.camButts.iconSize().width()+20)*len(buttons), 70)
        self.status.setWordWrap(True)
                
        buttRow = qtw.QHBoxLayout()
        buttRow.addWidget(self.camButts)
        buttRow.addWidget(self.status)
        self.layout.addLayout(buttRow)
        
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
        
#     def openSettings(self) -> None:
#         '''Open the camera settings dialog window'''
#         self.settingsDialog.show()
#         self.settingsDialog.raise_()

    #------------------------------------------------
    
    
    def updateBoxTitle(self) -> None:
        '''updates the title of widget box'''
        self.setTitle(f'{self.bTitle}\t{self.model}')
    

    def close(self) -> None:
        '''gets triggered when the window is closed. Disconnects GUI from camera.'''
        self.camObj.close()
#         self.settingsDialog.done()

