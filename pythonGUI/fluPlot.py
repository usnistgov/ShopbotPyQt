#!/usr/bin/env python
'''Shopbot GUI functions for controlling fluigent mass flow controller'''

# external packages
from PyQt5.QtCore import pyqtSignal, QObject, QRunnable, Qt, QThread, QTimer, QThreadPool
from PyQt5.QtGui import QDoubleValidator, QIntValidator
from PyQt5.QtWidgets import QLabel, QColorDialog, QCheckBox, QDialogButtonBox, QFormLayout, QGridLayout, QLineEdit, QMainWindow, QMessageBox, QVBoxLayout, QWidget
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
from fluThreads import *

   
#----------------------------------------------------------------------


class fluPlot(QObject):
    '''produces a plot that can be displayed in fluBox'''
    
    def __init__(self, pcolors:List[str], fb:connectBox, pw):
        '''pcolors is a list of colors, e.g. ['#FFFFFF', '#000000']
        fb is a pointer to the fluigent box that contains this plot'''
        super().__init__()
        self.fluBox = fb # parent box
        self.sbWin = self.fluBox.sbWin
        self.numChans = self.fluBox.numChans
        self.connected = fb.connected
        
        
        # create the plot
        self.graphWidget = pg.PlotWidget() 
#         self.graphWidget.setFixedSize(800, 390)
        self.setBuffers()
        self.graphWidget.setYRange(self.negBuffer, fb.pmax + self.buffer, padding=0) 
            # set the range from 0 to 7000 mbar
        self.graphWidget.setBackground('w')         
        self.pcolors = pcolors
        
        self.pw = pw

        self.datalines = []
        self.updateColors()
        for i in range(self.numChans):
            press = self.pw.pressures[i]
            cname = f'Channel {i}'
            dl = self.graphWidget.plot(self.pw.time, press, pen=self.pens[i], name=cname)
            self.datalines.append(dl)
        
        self.graphWidget.setLabel('left', f'Pressure ({self.fluBox.units})')
        self.graphWidget.setLabel('bottom', 'Time (s)')
        
        self.timerRunning = False
        self.startTimer()
        # create a thread to update the pressure list
        
    def setBuffers(self) -> None:
        '''update the margins around the requested pressure range'''
        self.buffer = convertPressure(100, 'mbar', self.fluBox.units)
        self.negBuffer = convertPressure(-10, 'mbar', self.fluBox.units)
        
    def updateYRange(self):
        '''update the y range'''
        self.graphWidget.setYRange(self.negBuffer, self.fluBox.pmax + self.buffer, padding=0) 
        
    def updateUnits(self, units:str):
        '''update the display units'''
        self.graphWidget.setLabel('left', f'Pressure ({units})')
        self.setBuffers()
        self.updateYRange()
        # don't need to update pressure list, because that is stored in plotWatch self.pw, which was updated by fluBox
        
    def fullSize(self):
        '''full size plot widget'''
        self.graphWidget.setMaximumHeight(350)
        self.graphWidget.setMaximumWidth(600)
        
    def small(self):
        '''small plot widget'''
        self.graphWidget.setMaximumHeight(200)
        self.graphWidget.setMaximumWidth(500)
        
        
    def startTimer(self) -> None:
        '''start updating the plot'''
        if not self.timerRunning:
            # https://realpython.com/python-pyqt-qthread/
            self.readThread = QThread()
            # Step 3: Create a worker object
            self.readWorker = plotUpdate(self.fluBox.pw, self.fluBox.arduino, self.connected)       # creates a new thread to read pressures     
            # Step 4: Move worker to the thread
            self.readWorker.moveToThread(self.readThread)
            # Step 5: Connect signals and slots
            self.readThread.started.connect(self.readWorker.run)       
            self.readThread.finished.connect(self.readThread.deleteLater)
            self.readWorker.signals.progress.connect(self.update)   # update plot when this runnable stops
            self.readWorker.signals.error.connect(self.fluBox.updateStatus)
            # Step 6: Start the thread
            self.readThread.start()
            logging.debug('Fluigent thread started')
            self.timerRunning = True

        
    def updateColors(self) -> None:
        '''update pen colors'''
        self.pens = [pg.mkPen(color=c, width=2) for c in self.fluBox.colors]

    @pyqtSlot()
    def update(self) -> None:
        '''read the pressure and update the plot display'''
        # update display
        if self.connected:
            for i in range(self.numChans):
                # get updated values
                self.pw.lock()
                pressures = self.pw.pressures
                time = self.pw.time
                self.pw.unlock()
                
                # update the plot
                if len(time) == len(pressures[i]):
                    self.datalines[i].setData(time, pressures[i], pen=self.pens[i])
                # update the pressure reading
                self.fluBox.updateReading(i, str(pressures[i][-1])) 

        
    def updateRange(self) -> None:
        '''update the plot time and pressure range'''
        
        # get updated range
        self.pw.lock()
        pressures = self.pw.pressures
        time = self.pw.time
        self.pw.unlock()
        
        tmin = min(time)
        tgap = self.fluBox.trange - (max(time)-tmin)
        dt = self.fluBox.dt/1000
        tsteps = int(round(tgap/dt))
        
        # change size of lists
        if tsteps>0:
            # add tsteps points to the beginning
            time = [tmin+(i-tsteps)*dt for i in range(tsteps)] + time
            for j in range(len(pressures)):
                pressures[j] = [0 for i in range(tsteps)] + pressures[j]
        elif tsteps<0:
            time = time[(-tsteps):]
            for j in range(len(pressures)):
                pressures[j] = pressures[j][(-tsteps):]
                
        # update values
        self.pw.lock()
        self.pw.pressures = pressures
        self.pw.time = time
        self.pw.unlock()
          
        # update pressure range
        self.updateYRange()
        
        # update display
        self.update()
            
            
    
    #-----------------------------------------
    
    
    def close(self) -> None:
        '''gets triggered when the window is closed. It stops the pressure readings.'''
        for s in ['readThread']:
            if hasattr(self, s):
                o = getattr(self, s)
                if not sip.isdeleted(o) and o.isRunning():
                    o.quit()
        logging.info('Fluigent timer deleted')