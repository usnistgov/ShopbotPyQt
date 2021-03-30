#!/usr/bin/env python
'''Shopbot GUI Shopbot functions'''


from PyQt5 import QtCore, QtGui
import PyQt5.QtWidgets as qtw
import cv2
import time
import datetime
import numpy as np
import os
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging

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
        self.diag = 1             # diag tells us which messages to log. 0 means none, 1 means some, 2 means a ton

        self.fourcc = cv2.VideoWriter_fourcc('M','J','P','G')
        self.prevWindow = qtw.QLabel()
    
    
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
        
        # determine the folder to save to
        folder = self.sbWin.genBox.saveFolder
        if not os.path.exists(folder):
            # open a save dialog if the folder does not exist
            self.sbWin.genBox.setSaveFolder()
            folder = self.sbWin.saveFolderLabel.text()
        if not os.path.exists(folder):
            self.updateStatus('Invalid folder name. Image not saved.', True)
            return
        
        # determine if we should include the shopbot file name in the file
        if self.sbWin.sbBox.runningSBP:
            sbname = os.path.basename(self.sbWin.sbBox.sbpName)
            filename = os.path.splitext(sbname)[0]+'_'
        else:
            filename = ""
        filename = filename + self.cameraName
        t1 = self.sbWin.genBox.appendName.text()
        if len(t1)>0:
            filename = filename + '_'+t1
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

    
    def updateStatus(self, st:str, log:bool) -> None:
        '''updates the status of the widget that this camera belongs to. 
        st is the status message. 
        log determines whether to write to log. '''
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
        self.getFrameRate()
        self.imw = int(self.camDevice.get(3))               # image width (px)
        self.imh = int(self.camDevice.get(4))               # image height (px)
        
        self.convertColors = True
        
    def getFrameRate(self):
        self.fps = self.camDevice.get(cv2.CAP_PROP_FPS)/2   # frames per second
        self.mspf = int(round(1000./self.fps))              # ms per frame
        
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
            self.getFrameRate()
            f1 = self.readFrame()
            self.imw = len(f1[0]) # image width (px)
            self.imh = len(f1) # image height (px)
            
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
        self.fps = self.camDevice.ResultingFrameRate.GetValue() # frames per s
        self.mspf = int(round(1000./self.fps))  # ms per frame
        
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
            if self.errorStatus==statusNum:
                raise Exception('')
            else:
                self.errorStatus=statusNum
                raise Exception(status)
        else:
            if not self.errorStatus==statusNum:
                self.errorStatus=statusNum
                self.updateStatus(e, self.diag>0)  
    
    
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
        
class settingsDialog(QtGui.QDialog):
    '''This opens a window that holds settings about logging for cameras.'''
    
    
    def __init__(self, parent:connectBox, bTitle:str, camObj:camera):
        '''parent is the connectBox that this settings dialog belongs to. 
            bTitle is the box title, e.g. webcam 2. 
            camObj is the camera object that holds functions and info for a specific camera.'''
        
        super().__init__(parent)  
        self.camObj = camObj
        self.layout = qtw.QVBoxLayout()
        
        self.diagRow = qtw.QHBoxLayout()
        self.diagLabel = qtw.QLabel('Log')
        self.diag1 = qtw.QRadioButton('None')
        self.diag2 = qtw.QRadioButton('Just critical')
        self.diag2.setChecked(True)
        self.diag3 = qtw.QRadioButton('All frames')
        self.diaggroup = qtw.QButtonGroup()
        self.diaggroup.addButton(self.diag1, 0)
        self.diaggroup.addButton(self.diag2, 1)
        self.diaggroup.addButton(self.diag3, 2)
        self.diaggroup.buttonClicked.connect(self.changeDiag)
        self.diagRow.addWidget(self.diagLabel)
        self.diagRow.addWidget(self.diag1)
        self.diagRow.addWidget(self.diag2)
        self.diagRow.addWidget(self.diag3)
        self.layout.addLayout(self.diagRow)
        
        self.varGrid = qtw.QGridLayout()
        self.fpsBox = qtw.QLineEdit()
        self.fpsBox.setText(str(self.camObj.fps))
        self.fpsLabel = qtw.QLabel('Frame rate (fps)')
        self.fpsLabel.setBuddy(self.fpsBox)
        self.fpsBox.returnPressed.connect(self.updateFPS)
        self.fpsAutoButt = qtw.QPushButton('Auto')
        self.fpsAutoButt.clicked.connect(self.fpsAuto)
        self.fpsAutoButt.setAutoDefault(False)
        
        self.varGrid.addWidget(self.fpsLabel, 0,0)
        self.varGrid.addWidget(self.fpsBox, 0,1)
        self.varGrid.addWidget(self.fpsAutoButt, 0,2)
        
        self.layout.addLayout(self.varGrid)
        
        self.goButt = qtw.QPushButton('Save')
        self.goButt.clicked.connect(self.updateVars)
        self.goButt.setFocus()
        self.layout.addWidget(self.goButt)
        
#         self.reset = qtw.QPushButton('Reset camera')
#         self.reset.clicked.connect(parent.connect)
#         self.layout.addWidget(self.reset)
    
        self.setLayout(self.layout)
        self.setWindowTitle(bTitle + " settings")

        
    def changeDiag(self, diagbutton):
        '''Change the diagnostics status on the camera, so we print out the messages we want.'''
        self.camObj.diag = self.diaggroup.id(diagbutton) 
        
            
    def updateVars(self):
        '''Update the frame rate'''
        self.updateFPS()
        
            
    #--------------------------
    # fps
    
    
    def fpsStatus(self):
        '''Log the change in fps'''
        if self.camObj.diag>0:
            self.camObj.updateStatus(f'Changed frame rate to {self.camObj.fps} fps', True)
        
    def updateFPS(self):
        '''Update the frame rate used by the GUI to the given frame rate'''
        self.camObj.fps = int(self.fpsBox.text())
        self.camObj.mspf = int(round(1000./self.camObj.fps))  # ms per frame
        self.fpsStatus()
            
    def fpsAuto(self):
        '''Automatically adjust the frame rate to the frame rate of the camera'''
        self.camObj.getFrameRate()
        self.fpsBox.setText(str(self.camObj.fps))
        self.fpsStatus()

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
        self.camPic.setIcon(QtGui.QIcon('icons/camera.png'))
        self.camPic.setStyleSheet(self.unclickedSheet())
        self.camPic.clicked.connect(self.cameraPic)
        self.camPic.setToolTip('Snapshot') 
        
        self.settings = qtw.QToolButton()
        self.settings.setIcon(QtGui.QIcon('icons/settings.png'))
        self.settings.setStyleSheet(self.unclickedSheet())
        self.settings.clicked.connect(self.openSettings)
        self.settings.setToolTip(self.bTitle+' settings') 
        
        self.settingsDialog = settingsDialog(self, self.bTitle, self.camObj)
                
        self.camButts = qtw.QToolBar()
        self.camButts.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.camButts.addWidget(self.camInclude)
        self.camButts.addWidget(self.camPrev)
        self.camButts.addWidget(self.camRec)
        self.camButts.addWidget(self.camPic)
        self.camButts.addWidget(self.settings)
        self.camButts.setStyleSheet("QToolBar{spacing:5px;}");
        
        self.layout.addWidget(self.camButts)
        
        self.status = qtw.QLabel('Ready')
        self.status.setFixedSize(500, 50)
        self.status.setWordWrap(True)
        self.layout.addWidget(self.status)
        
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
            self.camInclude.setIcon(QtGui.QIcon('icons/save.png'))
            self.camInclude.setToolTip('Do not export videos with shopbot')
        else:
            self.camInclude.setStyleSheet(self.unclickedSheet())
            self.camInclude.setText('Autosave is off')
            self.camInclude.setIcon(QtGui.QIcon('icons/nosave.png'))
            self.camInclude.setToolTip('Export videos with shopbot')
        
    def setPrevButtStart(self) -> None:
        '''Update preview button appearance to not previewing status'''
        self.camPrev.setStyleSheet(self.unclickedSheet())
#         self.camPrev.setText('Start preview')
        self.camPrev.setIcon(QtGui.QIcon('icons/closedeye.png'))
        self.camPrev.setToolTip('Start live preview') 
        
    def setPrevButtStop(self) -> None:
        '''Update preview button appearance to previewing status'''
        self.camPrev.setStyleSheet(self.clickedSheet())
#         self.camPrev.setText('Stop preview')
        self.camPrev.setIcon(QtGui.QIcon('icons/eye.png'))
        self.camPrev.setToolTip('Stop live preview') 

    def setRecButtStart(self) -> None:
        '''Update record button appearance to not recording status'''
        self.camRec.setStyleSheet(self.unclickedSheet())
        self.camRec.setIcon(QtGui.QIcon('icons/Record.png'))
        self.camRec.setToolTip('Start recording') 
        
    def setRecButtStop(self) -> None:
        '''Update record button appearance to recording status'''
        self.camRec.setStyleSheet(self.clickedSheet())
        self.camRec.setIcon(QtGui.QIcon('icons/recordstop.png'))
        self.camRec.setToolTip('Stop recording') 
        
    def openSettings(self) -> None:
        '''Open the camera settings dialog window'''
        self.settingsDialog.show()
        self.settingsDialog.raise_()

    #------------------------------------------------
    
    
    def updateBoxTitle(self) -> None:
        '''updates the title of widget box'''
        self.setTitle(f'{self.bTitle}\t{self.model}')
    

    def close(self) -> None:
        '''gets triggered when the window is closed. Disconnects GUI from camera.'''
        self.camObj.close()

