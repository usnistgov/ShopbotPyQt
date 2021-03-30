#!/usr/bin/env python
'''Shopbot GUI functions for setting up the GUI window'''

from PyQt5 import QtGui
import PyQt5.QtWidgets as qtw
import sys
import ctypes
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging

from sbgui_general import *
import sbgui_fluigent
import sbgui_files
import sbgui_shopbot
import sbgui_cameras

__author__ = "Leanne Friedrich"
__copyright__ = "This data is publicly available according to the NIST statements of copyright, fair use and licensing; see https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software"
__credits__ = ["Leanne Friedrich"]
__license__ = "MIT"
__version__ = "1.0.4"
__maintainer__ = "Leanne Friedrich"
__email__ = "Leanne.Friedrich@nist.gov"
__status__ = "Development"

################

APPID = 'leanfried.sbgui.v1.0.4'
       
##################################################          
########### logging window


class QPlainTextEditLogger(logging.Handler):
    '''This creates a text box that the log messages go to. Goes inside a logDialog window'''
    
    def __init__(self, parent):
        super().__init__()
        self.widget = QtGui.QPlainTextEdit(parent)
        self.widget.setReadOnly(True)    

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)    


class logDialog(QtGui.QDialog):
    '''Creates a window that displays log messages.'''
    
    def __init__(self, parent):
        super().__init__(parent)  

        logTextBox = QPlainTextEditLogger(self)
        logTextBox.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')) # format what is printed to text box
        logging.getLogger().addHandler(logTextBox)  # display log messages in text box
        logging.getLogger().setLevel(logging.DEBUG) # Set logging level to everything.

        layout = QtGui.QVBoxLayout()
        layout.addWidget(logTextBox.widget)         # Add the new logging box widget to the layout
        self.setLayout(layout) 
        
        self.setWindowTitle("Shopbot/Fluigent/Camera log")
        self.resize(900, 400)                       # window is 900 px x 400 px

        
####################### the whole window

class SBwindow(qtw.QMainWindow):
    '''The whole GUI window'''
    
    def __init__(self, parent=None):
        super(SBwindow, self).__init__(parent)
        
        # initialize all boxes to empty value so if we hit an error during setup and need to disconnect, we aren't trying to call empty variables
        
        self.genBox = None
        self.sbBox = None
        self.basBox = None
        self.nozBox = None
        self.web2Box = None
        self.fluBox = None
        self.logDialog = None
        
        try:
            self.central_widget = qtw.QWidget()               
            self.setCentralWidget(self.central_widget)      # create a central widget that everything else goes inside

            self.setWindowTitle("Shopbot/Fluigent/Camera")
            self.setStyleSheet('background-color:white;')
            self.resize(1600, 1800)                         # window size


            self.createGrid()                               # create boxes to go in main window
            self.createMenu()                               # create menu bar to go at top of window

            logging.info('Window created')
        except Exception as e:
            logging.error(f'Error during initialization: {e}')
            self.closeEvent(0)                              # if we fail to initialize the GUI, disconnect from everything we connected

        
    def createGrid(self):
        '''Create boxes that go inside of window'''
        self.genBox = sbgui_files.genBox(self)           # general file ops
        self.sbBox = sbgui_shopbot.sbBox(self)             # shopbot box
        self.basBox = sbgui_cameras.cameraBox(0, self)     # basler camera box
        self.nozBox = sbgui_cameras.cameraBox(1, self)     # nozzle webcam box
        self.web2Box = sbgui_cameras.cameraBox(2, self)     # webcam 2 box
        self.camBoxes = [self.basBox, self.nozBox, self.web2Box]
        self.fluBox = sbgui_fluigent.fluBox(self)           # fluigent box
              
        self.fullLayout = qtw.QGridLayout()
        self.fullLayout.addWidget(self.genBox, 0, 0, 1, 2)  # row 0, col 0, 1 row deep, 2 cols wide
        self.fullLayout.addWidget(self.sbBox, 1, 0, 1, 2)   # row 1, col 0, 1 row deep, 2 cols wide
        self.fullLayout.addWidget(self.basBox, 2, 0)
        self.fullLayout.addWidget(self.nozBox, 2, 1)
        self.fullLayout.addWidget(self.fluBox, 3, 0)
        self.fullLayout.addWidget(self.web2Box, 3, 1)
        
        # make the camera rows big so the whole window doesn't resize dramatically when we turn on previews
        self.fullLayout.setRowStretch(0, 1)
        self.fullLayout.setRowStretch(1, 2)
        self.fullLayout.setRowStretch(2, 6)     
        self.fullLayout.setRowStretch(3, 6)
        self.fullLayout.setColumnStretch(0, 1)
        self.fullLayout.setColumnStretch(1, 1)

        self.central_widget.setLayout(self.fullLayout)
        
                
    def setupLog(self):        
        self.logDialog = logDialog(self)
        self.logButt = qtw.QAction('Open log', self)
        self.logButt.triggered.connect(self.openLog)
    
        
    def createMenu(self):
        '''Create the top menu of the window'''
        
        menubar = self.menuBar()
        self.setupLog()                  # create a log window, not open yet
        menubar.addAction(self.logButt)  # add button to open log window
        
        self.openButt = qtw.QAction('Open video folder')
        self.openButt.triggered.connect(self.genBox.openSaveFolder)
        menubar.addAction(self.openButt)  # add a button to open the folder that videos are saved to in Windows explorer
    
    
    def closeEvent(self, event):
        '''runs when the window is closed. Disconnects everything we connected to.'''
        try:
            for o in [self.sbBox, self.basBox, self.nozBox, self.web2Box, self.fluBox]:
                try:
                    o.close()
                except:
                    pass
            for o in [self.logDialog]:
                try:
                    o.done(0)
                except:
                    pass
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)
        except:
            pass

                
    def openLog(self) -> None:
        '''Open the log window'''
        
        self.logDialog.show()
        self.logDialog.raise_()

class MainProgram(qtw.QWidget):
    '''The main application widget. Here, we can set fonts, icons, window info'''
    
    def __init__(self): 
        app = qtw.QApplication(sys.argv)
        sansFont = QtGui.QFont("Arial", 9)
        app.setFont(sansFont)
        gallery = SBwindow()
        gallery.show()
        gallery.setWindowIcon(QtGui.QIcon('icons/sfcicon.ico'))
        app.setWindowIcon(QtGui.QIcon('icons/sfcicon.ico'))
        app.exec_()
        
        myappid = APPID # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)