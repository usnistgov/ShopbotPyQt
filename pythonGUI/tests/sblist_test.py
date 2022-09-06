#!/usr/bin/env python
'''Shopbot GUI functions for setting up the GUI window'''

# external packages
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QMainWindow, QPushButton, QGridLayout, QTabWidget, QAction, QApplication, QCheckBox, QPlainTextEdit, QDesktopWidget
import os, sys
import ctypes
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import traceback


# local packages
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(currentdir)
sys.path.append(parentdir)
from general import *
import sbList
import shopbot

from config import cfg

        
####################### the whole window

class SBlistwindow(QMainWindow):
    '''The whole GUI window'''
    
    def __init__(self, parent=None, meta:bool=True, sb:bool=True, flu:bool=True, cam:bool=True, file:bool=True, test:bool=False):
        super(SBlistwindow, self).__init__(parent)
        
        # initialize all boxes to empty value so if we hit an error during setup and need to disconnect, we aren't trying to call empty variables

        try:
            self.central_widget = QWidget()               
            self.setCentralWidget(self.central_widget)      # create a central widget that everything else goes inside

            self.setWindowTitle("NIST Direct-write printer")
            self.setStyleSheet('background-color:white;')
            self.createGrid()                               # create boxes to go in main window

            logging.info('Window created')
        except Exception as e:
            logging.error(f'Error during initialization: {e}')
            traceback.print_exc()
            self.closeEvent(0)                              # if we fail to initialize the GUI, disconnect from everything we connected
        
    def createGrid(self):
        '''Create boxes that go inside of window'''
        self.sbBox = shopbot.sbBox(self, connect=True)   
        
        self.fullLayout = sbList.sbpNameList(self.sbBox, width=500)

        self.central_widget.setLayout(self.fullLayout)

   
    
    
    #----------------
    # close the window
    
    def closeEvent(self, event):
        '''runs when the window is closed. Disconnects everything we connected to.'''
        self.close()



class MainProgram(QWidget):
    '''The main application widget. Here, we can set fonts, icons, window info'''
    
    def __init__(self): 
        
        app = QApplication(sys.argv)
        sansFont = QFont("Arial", 9)
        app.setFont(sansFont)
        gallery = SBlistwindow()

        
        gallery.show()
        gallery.setWindowIcon(icon('sfcicon.ico'))
        app.setWindowIcon(icon('sfcicon.ico'))
        app.exec_()
    
        
        myappid = cfg.appid # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        
        
        
        
'''Run the program'''
if __name__ == "__main__":
    MainProgram()
        
        
        
        