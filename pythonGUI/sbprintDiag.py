#!/usr/bin/env python
'''Shopbot GUI functions for printing diagnostics during a print'''

# external packages
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QMutex, QObject, QRunnable, QThread, QTimer
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget 
import os, sys
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import re

# local packages
from config import cfg
from general import *

##################################################  


class diagStr:
    '''holds a diagnostic string that describes the current time step'''
    
    def __init__(self, diag:int):
        self.header = '\t'
        self.newRow()
        self.diag = diag
        self.printi = 0
        self.lastPrinted = ''
        
    def newRow(self):
        self.row = '\t'
        self.status = ''
        
    def addHeader(self, s) -> None:
        self.header = self.header +' | '+ s
        
    def addRow(self, s:str) -> None:
        self.row = self.row + ' | '+ s
        
    def addStatus(self, s:str) -> None:
        if len(self.status)>0:
            self.status = self.status + ', '
        self.status = self.status + s
        
    def printRow(self) -> None:
        line = f'{self.row}| {self.status}'
        if line==self.lastPrinted:
            # no change, don't print
            self.newRow()
            return
        self.lastPrinted = line
        if self.diag>2:
            # print every step
            print(line)
            self.printi+=1
        elif self.diag>1 and len(self.status)>0:
            print(line)
            self.printi+=1
        if (self.diag>1 and (self.printi>50)):
            print(self.header)
            self.printi = 0
        self.newRow()
            
    def printHeader(self) -> None:
        if self.diag>1:
            print(self.header)