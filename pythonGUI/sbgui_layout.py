#!/usr/bin/env python
'''Shopbot GUI functions for setting up the GUI window'''

# external packages
from PyQt5 import QtGui
from PyQt5.QtWidgets import QDialog
import PyQt5.QtWidgets as qtw
import os, sys
import ctypes
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import traceback

# local packages
from sbgui_general import *
import sbgui_fluigent
import sbgui_files
import sbgui_shopbot
import sbgui_cameras
import sbgui_calibration
from config import *

# info
__author__ = "Leanne Friedrich"
__copyright__ = "This data is publicly available according to the NIST statements of copyright, fair use and licensing; see https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software"
__credits__ = ["Leanne Friedrich"]
__license__ = "MIT"
__version__ = "1.0.4"
__maintainer__ = "Leanne Friedrich"
__email__ = "Leanne.Friedrich@nist.gov"
__status__ = "Development"


       
##################################################          
########### logging window


class QPlainTextEditLogger(logging.Handler):
    '''This creates a text box that the log messages go to. Goes inside a logDialog window'''
    
    def __init__(self, parent):
        super().__init__()
        self.widget = qtw.QPlainTextEdit(parent)
        self.widget.setReadOnly(True)    

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)    


class logDialog(QDialog):
    '''Creates a window that displays log messages.'''
    
    def __init__(self, parent):
        super().__init__(parent)  

        logTextBox = QPlainTextEditLogger(self)
        logTextBox.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')) # format what is printed to text box
        logging.getLogger().addHandler(logTextBox)  # display log messages in text box
        logging.getLogger().setLevel(logging.DEBUG) # Set logging level to everything.

        layout = qtw.QVBoxLayout()
        layout.addWidget(logTextBox.widget)         # Add the new logging box widget to the layout
        self.setLayout(layout) 
        
        self.setWindowTitle("Shopbot/Fluigent/Camera log")
        self.resize(900, 400)                       # window is 900 px x 400 px
        
        
    def close(self):
        '''close the window'''
        self.done(0)
        
######################## settings window

class TabBar(qtw.QTabBar):
    '''for vertical tabs. https://stackoverflow.com/questions/51404102/pyqt5-tabwidget-vertical-tab-horizontal-text-alignment-left'''
    
    def tabSizeHint(self, index):
        s = qtw.QTabBar.tabSizeHint(self, index)
        s.transpose()
        return s

    def paintEvent(self, event):
        painter = qtw.QStylePainter(self)
        opt = qtw.QStyleOptionTab()

        for i in range(self.count()):
            self.initStyleOption(opt, i)
            painter.drawControl(qtw.QStyle.CE_TabBarTabShape, opt)
            painter.save()

            s = opt.rect.size()
            s.transpose()
            s.setHeight(s.height()+20)
            r = QtCore.QRect(QtCore.QPoint(), s)
            r.moveCenter(opt.rect.center())
            opt.rect = r

            c = self.tabRect(i).center()
            painter.translate(c)
            painter.rotate(90)
            painter.translate(-c)
            painter.drawControl(qtw.QStyle.CE_TabBarTabLabel, opt);
            painter.restore()
            
        
class ProxyStyle(qtw.QProxyStyle):
    '''for vertical tabs. https://stackoverflow.com/questions/51404102/pyqt5-tabwidget-vertical-tab-horizontal-text-alignment-left'''
    
    def drawControl(self, element, opt, painter, widget):
        if element == qtw.QStyle.CE_TabBarTabLabel:
            ic = self.pixelMetric(qtw.QStyle.PM_TabBarIconSize)
            r = QtCore.QRect(opt.rect)
            w =  0 if opt.icon.isNull() else opt.rect.width() + self.pixelMetric(qtw.QStyle.PM_TabBarIconSize)
            r.setHeight(opt.fontMetrics.width(opt.text) + w + 50) # needed to add 50 to not cut off words
            r.moveBottom(opt.rect.bottom())
            opt.rect = r
        qtw.QProxyStyle.drawControl(self, element, opt, painter, widget)
        
        
        
class settingsDialog(QDialog):
    '''Creates a settings window'''
    
    def __init__(self, parent):
        '''This is called by the parent, which is the main SBwindow'''
        
        super().__init__(parent)
        self.parent = parent
        
        self.setStyle(ProxyStyle())
        self.layout = qtw.QVBoxLayout()
        
        self.generalBox() # create a layout for general settings
        self.tabs = qtw.QTabWidget()       
        self.tabs.setTabBar(TabBar(self))
        self.tabs.setTabPosition(qtw.QTabWidget.West)
        for box in [self, parent.fileBox, parent.sbBox, parent.basBox, parent.nozBox, parent.web2Box, parent.fluBox]:
            try:
                self.tabs.addTab(box.settingsBox, box.bTitle)    
            except:
                pass
        parent.fileBox.settingsBox.checkFormats() # update the initial file format
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)
        
        self.setWindowTitle('Settings')
        
    def generalBox(self) -> None:
        '''create a tab for settings of settings'''
        self.settingsBox = qtw.QWidget()
        self.bTitle = 'Load/save'
        layout = qtw.QVBoxLayout()
        loadButton = qtw.QPushButton('Load settings from file')
        loadButton.clicked.connect(self.loadSettings)
        loadButton.setIcon(icon('open.png'))
        loadButton.clearFocus()
        layout.addWidget(loadButton)
        
        saveButton = qtw.QPushButton('Save settings to file')
        saveButton.clicked.connect(self.saveSettings)
        saveButton.setIcon(icon('save.png'))
        saveButton.clearFocus()
        layout.addWidget(saveButton)
        
        self.alwaysSave = qtw.QCheckBox('Save settings for next session')
        self.alwaysSave.setChecked(cfg.layout.save)
        self.alwaysSave.clearFocus()
        layout.addWidget(self.alwaysSave)
        
        self.settingsBox.setLayout(layout)
        
        
    def loadSettings(self) -> None:
        '''Load settings from file'''
        sf = fileDialog(getConfigDir(), 'config files (*.yaml *.yml)', False)
        if len(sf)>0:
            sf = sf[0]
        else:
            return 
        if not os.path.exists(sf):
            return
        cfg = loadConfigFile(sf)
        parent = self.parent
        for box in [parent.fileBox, parent.sbBox, parent.basBox, parent.nozBox, parent.web2Box, parent.fluBox]:
            box.loadConfig(cfg)
        logging.info(f'Loaded settings from {sf}')
        
    def saveCfg(self, file:str):
        '''save the config file to file'''
        parent = self.parent
        from config import cfg
        for box in [parent.fileBox, parent.sbBox, parent.basBox, parent.nozBox, parent.web2Box, parent.fluBox, parent.calibDialog]:
            cfg = box.saveConfig(cfg)
        dumpConfigs(cfg, file)
        logging.info(f'Saved settings to {file}')
            
    def saveSettings(self):
        '''Save all settings to file'''
        sf = fileDialog(getConfigDir(), 'config files (*.yml)', False, opening=False)
        if len(sf)>0:
            sf = sf[0]
            if sf.endswith(','):
                sf = sf[:-1]
        else:
            return 
        self.saveCfg(sf)
        
        
    def close(self):
        '''Close the window'''
        if self.alwaysSave.isChecked():
            self.saveCfg(os.path.join(getConfigDir(), 'config.yml'))
        self.done(0)
        

        

        
####################### the whole window

class SBwindow(qtw.QMainWindow):
    '''The whole GUI window'''
    
    def __init__(self, parent=None):
        super(SBwindow, self).__init__(parent)
        
        # initialize all boxes to empty value so if we hit an error during setup and need to disconnect, we aren't trying to call empty variables
        
        self.fileBox = None
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
            self.resize(1500, 1600)                         # window size


            self.createGrid()                               # create boxes to go in main window
            self.createMenu()                               # create menu bar to go at top of window
                # createMenu must go after createGrid, because it uses features created in createGrid

            logging.info('Window created')
        except Exception as e:
            logging.error(f'Error during initialization: {e}')
            traceback.print_exc()
            self.closeEvent(0)                              # if we fail to initialize the GUI, disconnect from everything we connected

        
    def createGrid(self):
        '''Create boxes that go inside of window'''

        self.basBox = sbgui_cameras.cameraBox(0, self)     # basler camera box
        self.nozBox = sbgui_cameras.cameraBox(1, self)     # nozzle webcam box
        self.web2Box = sbgui_cameras.cameraBox(2, self)     # webcam 2 box
        self.camBoxes = [self.basBox, self.nozBox, self.web2Box]
        self.fluBox = sbgui_fluigent.fluBox(self)           # fluigent box
        
        self.fileBox = sbgui_files.fileBox(self)           # general file ops
        self.sbBox = sbgui_shopbot.sbBox(self)             # shopbot box
              
        self.fullLayout = qtw.QGridLayout()
        self.fullLayout.addWidget(self.fileBox, 0, 1)  # row 0, col 1
        self.fullLayout.addWidget(self.sbBox, 0, 0)  
        self.fullLayout.addWidget(self.basBox, 2, 0)
        self.fullLayout.addWidget(self.nozBox, 2, 1)
        self.fullLayout.addWidget(self.fluBox, 3, 0)
        self.fullLayout.addWidget(self.web2Box, 3, 1)

        self.central_widget.setLayout(self.fullLayout)
    
    
    #----------------
    # log
                
    def setupLog(self, menubar) -> None:  
        '''Create the log dialog.'''
        self.logDialog = logDialog(self)
        self.logButt = qtw.QAction('Log', self)
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
        self.settingsButt = qtw.QAction(icon('settings.png'), 'Settings', self)
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
        self.calibDialog = sbgui_calibration.pCalibration(self)
        self.calibButt = qtw.QAction('Speed calibration tool', self)
        self.calibButt.setStatusTip('Tool for calibrating speed vs pressure')
        self.calibButt.triggered.connect(self.openCalib)
        menubar.addAction(self.calibButt)  # add button to open calibration window
        
    def openCalib(self) -> None:
        '''Open the calibration window'''
        self.calibDialog.show()
        self.calibDialog.raise_()
        
    #----------------
    # top menu
        
    def createMenu(self):
        '''Create the top menu of the window'''
        menubar = self.menuBar()
        self.setupLog(menubar)                  # create a log window, not open yet
        self.setupCalib(menubar)
        self.setupSettings(menubar)                  # create a log window, not open yet
        


    #-----------------
    # file names
    def newFile(self, deviceName:str, ext:str) -> Tuple[str, str]:
        '''Generate a new file name for device and with extension'''
        return self.fileBox.newFile(deviceName, ext)
    
    #----------------
    # close the window
    
    def closeEvent(self, event):
        '''runs when the window is closed. Disconnects everything we connected to.'''
        try:
            for o in [self.sbBox, self.basBox, self.nozBox, self.web2Box, self.fluBox, self.settingsDialog, self.logDialog, self.calibDialog]:
                try:
                    o.close()
                except:
                    pass
            for handler in logging.root.handlers[:]:
                logging.root.removeHandler(handler)
        except:
            pass
        self.close()


class MainProgram(qtw.QWidget):
    '''The main application widget. Here, we can set fonts, icons, window info'''
    
    def __init__(self): 
        app = qtw.QApplication(sys.argv)
        sansFont = QtGui.QFont("Arial", 9)
        app.setFont(sansFont)
        gallery = SBwindow()
        gallery.show()
        gallery.setWindowIcon(icon('sfcicon.ico'))
        app.setWindowIcon(icon('sfcicon.ico'))
        app.exec_()
        
        myappid = cfg.appid # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)