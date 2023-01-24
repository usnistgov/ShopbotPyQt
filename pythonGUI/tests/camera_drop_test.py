#!/usr/bin/env python
'''for testing dropped frames from the camera'''

# external packages
import os, sys
from PySide2.QtTest import QTest
from PyQt5.QtCore import QTimer, QObject, Qt
from PyQt5.QtWidgets import QAction, QApplication, QGridLayout, QMainWindow, QWidget
from itertools import chain, combinations
import pandas as pd
import datetime
import logging
import time


# local packages
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(currentdir)
sys.path.append(parentdir)
import layout
from config import cfg
    
##################################################  




class DropTest(QWidget):
    '''The main application widget. Here, we can set fonts, icons, window info'''
    
    def __init__(self): 
        
        app = QApplication(sys.argv)
        self.sbwin = layout.SBwindow(meta=False, sb=False, flu=False, cam=True, file=True, test=True, convert=False, calib=False)
    
        self.sbwin.show()


        camBoxes = self.sbwin.camBoxes.list
        
        

        
'''Run the program'''
if __name__ == "__main__":
    mp = DropTest()
    