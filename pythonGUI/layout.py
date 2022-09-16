#!/usr/bin/env python
'''Shopbot GUI functions for setting up the GUI window'''

# external packages
from PyQt5.QtCore import pyqtSignal, QObject, QThread, QTimer, QThreadPool
from PyQt5.QtGui import  QFont
from PyQt5.QtWidgets import QAction, QApplication, QGridLayout, QMainWindow, QWidget
import os, sys
import ctypes
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import traceback
import csv
import datetime


# local packages
from general import *
from settings import *
from log import *
import fluigent
import files
import shopbot
import cameras
import calibration
import sbprint
import flags
from config import cfg

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(currentdir)
sys.path.append(parentdir)
from sbpRead import SBPHeader
        
####################### the whole window

class SBwindow(QMainWindow):
    '''The whole GUI window'''
    
    def __init__(self, parent=None, meta:bool=True, sb:bool=True, flu:bool=True, cam:bool=True, file:bool=True, test:bool=False):
        super(SBwindow, self).__init__(parent)
        
        # initialize all boxes to empty value so if we hit an error during setup and need to disconnect, we aren't trying to call empty variables

        self.fileBox = files.fileBox(self, connect=False)
        self.sbBox = shopbot.sbBox(self, connect=False)   
        self.fluBox = fluigent.fluBox(self, connect=False)
        self.logDialog = None
        self.camBoxes = cameras.camBoxes(self, connect=False)
        self.metaBox = sbprint.metaBox(self, connect=False) 
        self.flagBox = flags.flagGrid(self, tall=False)
        self.settingsDialog = QDialog()
<<<<<<< Updated upstream:pythonGUI/layout.py
        self.save = False
=======
   '''     self.convertDialog = None    '''
>>>>>>> Stashed changes:pythonGUI/sbgui_layout.py
        
        self.meta = meta
        self.sb = sb
        self.flu = flu
        self.cam = cam
        self.test = test
        self.file = file

        try:
            self.central_widget = QWidget()               
            self.setCentralWidget(self.central_widget)      # create a central widget that everything else goes inside

            self.setWindowTitle("NIST Direct-write printer")
            self.setStyleSheet('background-color:white;')
            
#             self.resize(1500, 1600)                         # window size
            self.connect()
            self.createGrid()                               # create boxes to go in main window
            self.createMenu()                               # create menu bar to go at top of window
                # createMenu must go after createGrid, because it uses features created in createGrid

            logging.info('Window created. GUI is ready.')
        except Exception as e:
            logging.error(f'Error during initialization: {e}')
            traceback.print_exc()
            self.closeEvent(0)                              # if we fail to initialize the GUI, disconnect from everything we connected
   
        
    def boxes(self) -> List:
        b = []
        for s in ['settingsDialog', 'logDialog','fileBox', 'sbBox', 'fluBox', 'calibDialog', 'metaBox']:
            if hasattr(self, s):
                b.append(getattr(self, s))
        if hasattr(self, 'camBoxes'):
            b = b+self.camBoxes.list
        return b

            
    def connect(self) -> None:
        '''create the boxes. sbBox loads features from fluBox and camBoxes. fileBox loads features from sbBox and camBoxes. '''
        
        if self.flu and hasattr(self, 'fluBox'):
            print('Connecting Fluigent box')
            self.fluBox.connect()          # fluigent box
        else:
            print('Loading Fluigent test layout')
            self.fluBox.testLayout()
            
        if self.cam and hasattr(self, 'camBoxes'):
            print('Connecting camera boxes')
            self.camBoxes.connect()             # object that holds camera boxes
        
        if self.sb and hasattr(self, 'sbBox'):
            print('Connecting shopbot box')
            self.sbBox.connect()            # shopbot box
        else:
            print('Loading shopbot test layout')
            self.sbBox.testLayout(self.flu)

        if self.file and hasattr(self, 'fileBox'):
            print('Connecting file box')
            self.fileBox.connect()          # general file ops

        if self.meta and hasattr(self, 'metaBox'):
            print('Connecting metadata box')
            self.metaBox.connect()      # metadata box
            
        self.flagBox.labelFlags()  # relabel flags now that we've connected all the boxes
        

        
    def createGrid(self):
        '''Create boxes that go inside of window'''

        # use different layout depending on screen resolution
        user32 = ctypes.windll.user32
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)

        self.fullLayout = QGridLayout()
        self.fullLayout.addWidget(self.sbBox, 0, 0) 
        self.fullLayout.addWidget(self.fileBox, 0, 1)  # row 0, col 1
        
        if height<2000:
            logging.info('Low screen resolution: using wide window')
            # short window
            self.fullLayout.addWidget(self.fluBox, 0,2)
            self.fluBox.small()
            row = 2
            col = 0
            for camBox in self.camBoxes.list:
                self.fullLayout.addWidget(camBox, row, col)
                col+=1
                if col==3:
                    row+=1
                    col = 0
            self.move(max(50, int(width-3600)),50)
        else:
            # tall window
            self.fullLayout.addWidget(self.fluBox, 2,0)
            row = 2
            col = 1
            for camBox in self.camBoxes.list:
                self.fullLayout.addWidget(camBox, row, col)
                col+=1
                if col==2:
                    row+=1
                    col=0
            self.move(max(50, int(width-2800)),50)

        self.central_widget.setLayout(self.fullLayout)

    
    #----------------
    # log
                
    def setupLog(self, menubar) -> None:  
        '''Create the log dialog.'''
        self.logDialog = logDialog(self)
        self.logButt = QAction('Log', self)
        self.logButt.setStatusTip('Open running log of status messages')
        self.logButt.triggered.connect(self.openLog)
        menubar.addAction(self.logButt)  # add button to open log window
                 
    def openLog(self) -> None:
        '''Open the log window'''
        self.logDialog.show()
        self.logDialog.raise_()
        
    #----------------
    # settings
                
    def setupSettings(self, menubar) -> None:  
        '''Create the settings dialog.'''
        self.settingsDialog = settingsDialog(self)
        self.settingsButt = QAction(icon('settings.png'), 'Settings', self)
        self.settingsButt.setStatusTip('Open app settings')
        self.settingsButt.triggered.connect(self.openSettings)
        menubar.addAction(self.settingsButt)  # add button to open settings window
          
    def openSettings(self) -> None:
        '''Open the settings window'''
        self.settingsDialog.show()
        self.settingsDialog.raise_()
        
    #-------------- 
    # calibration tool
    
    def setupCalib(self, menubar) -> None:
        '''Create the pressure calibration tool dialog'''
        self.calibDialog = calibration.pCalibration(self)
        self.calibButt = QAction('Speed calibration tool', self)
        self.calibButt.setStatusTip('Tool for calibrating speed vs pressure')
        self.calibButt.triggered.connect(self.openCalib)
        menubar.addAction(self.calibButt)  # add button to open calibration window
        
    def openCalib(self) -> None:
        '''Open the calibration window'''
        self.calibDialog.show()
        self.calibDialog.raise_()
        
    #----------------
    # Convert
   ''' 
    def setupConvert(self, menubar) -> None:
        '''Create the convert dialog'''
        self.convertlog = convertDialog(self)
        self.convertButt = QAction('Convert', self)
        self.convertButt.setStatusTip('Convert .stl file to .sbp')
        self.convertButt.triggered.connect(self.openConvert)
        menubar.addAction(self.convertButt) # add button to open convertion window
        
    def openConvert(self) -> None:
        '''Open the convertion window'''
        self.convertDialog.show()
        self.convertDialog.raise_()
    '''
    #----------------
    # top menu
        
    def createMenu(self):
        '''Create the top menu of the window'''
        menubar = self.menuBar()
        self.setupLog(menubar)                  # create a log window, not open yet
        self.setupCalib(menubar)
   #     self.setupConvert(menubar)
        self.setupSettings(menubar)                  # create a log window, not open yet
        if self.test:
            self.setupDropTest(menubar)
        
    def setupDropTest(self, menubar):
        '''create test menu for dropped frames'''
        self.dropDialog = cameras.dropTestDialog(self)
        self.dropButt = QAction('Dropped frame tool', self)
        self.dropButt.triggered.connect(self.openDropTest)
        menubar.addAction(self.dropButt)
        
    def openDropTest(self) -> None:
        self.dropDialog.show()
        self.dropDialog.raise_()
        
        
        


    #-----------------
    # file names
    def newFile(self, deviceName:str, ext:str) -> Tuple[str, str]:
        '''Generate a new file name for device and with extension'''
        return self.fileBox.newFile(deviceName, ext)
    
    #----------------
    # metadata at print
    def saveMetaData(self) -> None:
        '''save metadata including print speeds, calibration values, presures, metadata'''
        try:
            fullfn = self.newFile('meta', '.csv')
        except NameError:
            self.updateStatus('Failed to save speed file', True)
            return

        with open(fullfn, mode='w', newline='', encoding='utf-8') as c:
            writer = csv.writer(c, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            
            for box in self.boxes():
                if hasattr(box, 'writeToTable'):
                    box.writeToTable(writer)
            
            self.sbBox.updateStatus(f'Saved {fullfn}', True)
        
    def flagTaken(self, flag0:int) -> bool:
        '''check if the flag is already occupied'''
        return self.sbBox.flagTaken(flag0)   
    
    #----------------
    
    def getFileName(self) -> str:
        try:
            fullfn = self.newFile('time', '.csv')
        except NameError:
            self.fileName = ''
            return
        self.fileName = fullfn
    
    def initSaveTable(self) -> None:
        '''initialize a table that saves data during a print'''
        if (hasattr(self, 'fluBox') and self.fluBox.savePressure) or (hasattr(self, 'sbBox') and self.sbBox.savePos):
            self.saveTable = []
            self.save = True
            self.ending = False
            self.getFileName() # determine the current file name
            self.tStart = datetime.datetime.now()
            self.timer = QTimer()
            self.timer.timeout.connect(self.readValues)
            self.timer.start(self.sbBox.saveFreq)
            
            
    def readValues(self) -> None:
        '''add values to the table'''
        if self.save:
            dnow = datetime.datetime.now()
            tnow = (dnow-self.tStart).total_seconds()
            if hasattr(self, 'fluBox'):
                plist = self.fluBox.timeRow()
            else:
                plist = []
            if hasattr(self, 'sbBox'):
                xyzlist = self.sbBox.timeRow()
            else:
                xyzlist = []
            self.saveTable.append([tnow]+plist+xyzlist)
        

    def writeSaveTable(self) -> None:
        '''save the table to csv'''
        
        if self.save:
            if hasattr(self, 'timer') and self.timer.isActive():
                self.timer.stop()
            self.ending = False
            self.save = False
            with open(self.fileName, mode='w', newline='', encoding='utf-8') as c:
                writer = csv.writer(c, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                phead = self.fluBox.timeHeader()
                xyzhead = self.sbBox.timeHeader()
                writer.writerow(['time(s)']+phead+xyzhead) # header
                for row in self.saveTable:
                    writer.writerow(row)
            self.sbBox.updateStatus(f'Saved {self.fileName}', True)
    
    
    #----------------
    # close the window
    
    def closeEvent(self, event):
        '''runs when the window is closed. Disconnects everything we connected to.'''
        logging.info('Closing boxes.')
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
        for o in self.boxes():
            if hasattr(o, 'close'):
                o.close()
            else:
                logging.info(f'No close function in {o}')
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.info('Done closing boxes.')
        self.close()


class MainProgram(QWidget):
    '''The main application widget. Here, we can set fonts, icons, window info'''
    
    def __init__(self, meta:bool=True, sb:bool=True, flu:bool=True, cam:bool=True, file:bool=True, test:bool=False): 
        
        app = QApplication(sys.argv)
        sansFont = QFont("Arial", 9)
        app.setFont(sansFont)
        self.sbwin = SBwindow(meta=meta, sb=sb, flu=flu, cam=cam, file=file, test=test)

        
        self.sbwin.show()
        self.sbwin.setWindowIcon(icon('sfcicon.ico'))
        app.setWindowIcon(icon('sfcicon.ico'))
        app.exec_()
    
        
        myappid = cfg.appid # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        
        
        

        
        