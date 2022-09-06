#!/usr/bin/env python
'''Shopbot GUI functions for controlling fluigent mass flow controller separate threads'''

# external packages
from PyQt5.QtCore import pyqtSignal, QMutex, QObject, QRunnable, Qt, QThread, QTimer, QThreadPool
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import QLabel, QColorDialog, QCheckBox, QFormLayout, QGridLayout, QLineEdit, QMainWindow, QVBoxLayout, QWidget
import pyqtgraph as pg
import csv
import time
import datetime
import numpy as np
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import os, sys
import traceback

# local packages
import Fluigent.SDK as fgt
from config import cfg
from general import *

   
#----------------------------------------------------------------------

class plotWatch(QMutex):
    '''Holds the pressure/time list for all channels'''

    def __init__(self, numChans:int, trange:float, dt:float):
        super().__init__()
        self.stop = False          # tells us to stop reading pressures
        self.numChans = numChans   # number of channels
        self.trange = cfg.fluigent.trange       # time range
        self.dt = dt
        self.d0 = datetime.datetime.now()
        self.initializePList()

        
    def initializePList(self) -> None:
        '''initialize the pressure list and time list'''
        # initialize the time range
        self.time = list(np.arange(-self.trange*1, 0, self.dt/1000)) 
               
        # initialize pressures. assume 0 before we initialized the gui    
        self.pressures = []
        
        for i in range(self.numChans):
            press = [0 for _ in range(len(self.time))]
            self.pressures.append(press)


class fluSignals(QObject):
    '''Signals connector that lets us send status updates back to the GUI from the fluPlot object'''
    
    error = pyqtSignal(str, bool)
    progress = pyqtSignal()
    
    
def checkPressure(channel:int) -> int:
    '''reads the pressure of a given channel, 0-indexed'''
    pressure = int(fgt.fgt_get_pressure(channel))
    return pressure
            
class plotUpdate(QObject):
    '''plotUpdate updates the list of times and pressures and allows us to read pressures continuously in a background thread.'''
    
    def __init__(self, pw:plotWatch, connected:bool):
        super().__init__()   
        self.pw = pw                  # plotWatch object (stores pressure list)
        self.numChans = pw.numChans   # number of channels
        self.signals = fluSignals()   # lets us send messages and data back to the GUI
        self.connected = connected  # if the fluigent is connected
        self.pw.lock()
        self.dt = self.pw.dt   # dt in milliseconds
        self.pw.unlock()

    @pyqtSlot()
    def run(self) -> None:
        '''update the plot and displayed pressure'''
        while True:
            try:
                # get initial list from plotwatch
                self.pw.lock()
                newtime = self.pw.time
                newpressures = self.pw.pressures  
                d0 = self.pw.d0   # initial time
                stop = self.pw.stop
                self.dt = self.pw.dt   # dt in milliseconds
                self.pw.unlock()
                
                if stop:
                    return
                
                newtime = newtime[1:]                   # Remove the first y element.
                dnow = datetime.datetime.now()          # Finds current time relative to when the plot was created
                tnow = (dnow-d0).total_seconds()
                newtime.append(tnow)         # Add the current time to the list
                for i in range(self.numChans):
                    newpressures[i] = newpressures[i][1:]
                    if self.connected:
                        pnew = checkPressure(i)
                    else:
                        pnew = 0
                    newpressures[i].append(pnew)         # Add the current pressure to the list, for each channel
            except Exception as e:
                self.signals.error.emit(f'Error reading pressure: {e}', True)
            else:
                # update plotwatch
                self.pw.lock()
                self.pw.time = newtime                   # Save lists to plotWatch object
                self.pw.pressures = newpressures   
                self.pw.unlock()
                self.signals.progress.emit()             # Tell the GUI to update plot
            
            time.sleep(self.dt/1000)
            