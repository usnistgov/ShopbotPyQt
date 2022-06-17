#!/usr/bin/env python
'''Shopbot GUI functions for setting up the log window'''

# external packages
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon 
from PyQt5.QtWidgets import QAction, QApplication, QCheckBox, QDesktopWidget, QGridLayout, QPlainTextEdit, QPushButton, QTabWidget, QMainWindow, QVBoxLayout, QWidget
import os, sys
import ctypes
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import traceback


# local packages
from sbgui_general import *

       
##################################################          
########### logging window


class QPlainTextEditLogger(logging.Handler):
    '''This creates a text box that the log messages go to. Goes inside a logDialog window'''
    
    def __init__(self, parent):
        super().__init__()
        self.widget = QPlainTextEdit(parent)
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

        layout = QVBoxLayout()
        layout.addWidget(logTextBox.widget)         # Add the new logging box widget to the layout
        self.setLayout(layout) 
        
        self.setWindowTitle("Shopbot/Fluigent/Camera log")
        self.resize(900, 400)                       # window is 900 px x 400 px
        
        
    def close(self):
        '''close the window'''
        self.done(0)