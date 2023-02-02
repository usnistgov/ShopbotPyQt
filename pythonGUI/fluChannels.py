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

class channel(QObject):
    '''either a UV LED or a fluigent pressure channel'''
    
    def __init__(self, chanNum0:int, fluBox:connectBox):
        super().__init__()
        self.chanNum0 = chanNum0  # 0-indexed
        self.printStatus = ''
        self.fluBox = fluBox
        self.columnw = fluBox.columnw
        
    def successLayout(self):
        for i in range(2):
            setattr(self, f'label{i}', fLabel(title=self.bTitle, width=1.5*self.columnw))
        self.readLabel = fLabel(title='0', width=1.5*self.columnw)
        
        
    def updateFlag(self, flag1) -> None:
        '''update the tracking flag'''
        self.flag1 = flag1
        
    def updateColor(self, color:str) -> None:
        '''update color of text items'''
        self.color = color
        try:
            for s in ['label0', 'label1', 'readLabel', 'setButton', 'constTimeButton', 'setBox', 'constTimeBox', 'constBox']:
                if hasattr(self, s):
                    o = getattr(self, s)
                    o.setStyleSheet(f'color: {color};')  
                # this makes the label our input color
        except:
            logging.warning(f'Failed to update color of channel {self.chanNum0} to {color}')
            
            
    def updatePrintStatus(self, status:str) -> None:
        '''store the status'''
        self.printStatus = status
        
    def getPrintStatus(self) -> None:
        '''get the status and clear it'''
        status = self.printStatus
        self.printStatus = ''
        return status
        
#----------------------

class uvChannel(channel):
    '''this class describes the UV output'''
    
    def __init__(self, chanNum0:int, fluBox:connectBox):
        super().__init__(chanNum0, fluBox)
        self.bTitle = 'UV LED'
        self.cname = 'UV'
        self.arduino = fluBox.arduino
        self.loadConfig(cfg)
        self.successLayout()
        
    def successLayout(self):
        # make 2 labels
        super().successLayout()
        
        # setBox is a one line input box that lets the user turn the pressure on to setBox
        self.doorLabel = fLabel(width=self.columnw, title='door open')
        self.setButton = fButton(None, title='On', width=self.columnw, func=self.toggle)
        self.setToolTips()
        self.updateColor(self.color)           
        
        # line up the label and input box horizontally
        col1 = 1+2*self.chanNum0
        self.fluBox.fluButts.addWidget(self.label0,          0, col1)
        self.fluBox.fluButts.addWidget(self.readLabel,       1, col1)
        self.fluBox.fluButts.addWidget(self.setButton,       4, col1)
        self.updateReading('')
        
    def updateDisplay(self):
        if self.arduino.uvOn:
            self.setButton.setText('Turn off')
        else:
            self.setButton.setText('Turn on')
        
    def setToolTips(self):
        self.readLabel.setToolTip(f'Interlock status')
        self.setButton.setToolTip(f'Turn UV lamp on/off')

    def loadConfig(self, cfg1) -> None:
        '''load settings from the config file'''
        self.color = cfg.uv.color
        self.flag1 = cfg.uv.flag1
        self.fluBox.settingsBox.flagBoxes[self.chanNum0].setText(str(self.flag1))
        
    def saveConfig(self, cfg1):
        '''save values to the config file'''
        cfg1.uv.color = self.color
        cfg1.uv.flag1 = self.flag1
        return cfg1
    
    def updateUnits(self, u):
        '''uv lamp does not have units'''
        return
    
    @pyqtSlot()
    @pyqtSlot(bool)
    def zeroChannel(self, status:bool=True) -> None:
        '''zero the channel pressure'''
        self.turnOff()
        
    def writeToTable(self, writer) -> None:
        '''write metatable values to a csv writer object'''
        writer.writerow([f'flag1_uv','', self.flag1])
        
    def toggle(self) -> None:
        '''turn the UV lamp on/off'''
        self.arduino.toggleUV()
        self.updateDisplay()
        
    def turnOn(self) -> None:
        self.arduino.turnOnUV()
        self.updateDisplay()
        
    def turnOff(self) -> None:
        self.arduino.turnOffUV()
        self.updateDisplay()
        
    @pyqtSlot(float)
    def goToRunPressure(self, scale:float) -> None:
        '''turn on UV lamp'''
        self.turnOn()
        
    def updateReading(self, s:str) -> None:
        '''update the displayed door status. this is called in a loop'''
        status = self.arduino.checkStatus()
        self.readLabel.setText(status)
        self.updateDisplay()

    
#----------------------   

class fluChannel(channel):
    '''this class describes a single channel on the Fluigent
        each channel gets a QLayout that can be incorporated into the fluBox widget'''
    
    def __init__(self, chanNum0:int, fluBox:connectBox):
        '''chanNum0 is a 0-indexed channel number (e.g. 0)
        fluBox is the parent box that holds the Fluigent GUI display'''
        super().__init__(chanNum0, fluBox)    
        self.bTitle = f'Channel {chanNum0}'
        self.cname = f'channel{self.chanNum0}'
        self.units = fluBox.units
        self.loadConfig(cfg)
        self.successLayout()
        
    def successLayout(self):
        # make 2 labels
        super().successLayout()
        
        
        # setBox is a one line input box that lets the user turn the pressure on to setBox
        self.objValidator = QDoubleValidator(0, 7000,2)
        self.setBox = fLineCommand(width=self.columnw, text='0', func=self.setPressure, validator=self.objValidator)
        self.setButton = fButton(None, title='Go', width=0.5*self.columnw, func=self.setPressure)
        self.constTimeBox = fLineCommand(width=self.columnw, text='0', validator=self.objValidator, func=self.runConstTime)
        self.constTimeButton = fButton(None, title='Go', width=0.5*self.columnw, func=self.runConstTime)
        self.constBox = fLineCommand(width=self.columnw, text='0', validator=self.objValidator)
        self.setToolTips()
        self.updateColor(self.color)           
        
        # line up the label and input box horizontally
        col1 = 1+2*self.chanNum0
        self.fluBox.fluButts.addWidget(self.label0,          0, col1+0, 1, 2)
        self.fluBox.fluButts.addWidget(self.readLabel,       1, col1+0, 1, 2)
        self.fluBox.fluButts.addWidget(self.setBox,          3, col1+0)
        self.fluBox.fluButts.addWidget(self.setButton,       4, col1+1)
        self.fluBox.fluButts.addWidget(self.constTimeBox,    5, col1+0)
        self.fluBox.fluButts.addWidget(self.constTimeButton, 5, col1+1)
        
        self.fluBox.printButts.addWidget(self.label1,        0, col1+0)
        self.fluBox.printButts.addWidget(self.constBox,      1, col1+0)
        
    def setToolTips(self):
        self.readLabel.setToolTip(f'Current pressure ({self.units})')
        self.setBox.setToolTip(f'Set the pressure ({self.units}). Press [enter] or click Go to set the pressure.')
        self.setButton.setToolTip(f'Set pressure to [Set pressure] {self.units}.')
        self.constTimeBox.setToolTip(f'Set pressure to [Set Pressure] {self.units} for [Fixed time] s,\
                                         then turn off.\nPress [enter] or click Go to start.')
        self.constTimeButton.setToolTip(f'Set pressure to [Set Pressure] {self.units} for [Fixed time] s, then turn off.')
        self.constBox.setToolTip(f'Pressure to use during printing ({self.units})')
        
    def updateUnits(self, units:str) -> None:
        '''update the display units'''
        oldUnits = self.units
        self.units = units
        self.setToolTips()
        for box in [self.setBox, self.constBox]:
            box.setText(str(convertPressure(float(box.text()), oldUnits, self.units)))
        
    def loadConfig(self, cfg1) -> None:
        '''load settings from the config file'''
        self.color = cfg.fluigent[self.cname].color
        self.flag1 = cfg.fluigent[self.cname].flag1
        self.fluBox.settingsBox.flagBoxes[self.chanNum0].setText(str(self.flag1))
        
    def saveConfig(self, cfg1):
        cfg1.fluigent[self.cname].color = self.color
        cfg1.fluigent[self.cname].flag1 = self.flag1
        return cfg1
            
            
    def goToPressure(self, runPressure:int, status:bool) -> None:
        '''to to the given pressure'''
        setPressure(self.chanNum0, runPressure, self.units)
        if status:
            self.fluBox.updateStatus(f'Setting channel {self.chanNum0} to {runPressure} {self.units}', True)
         
    @pyqtSlot(float)
    def goToRunPressure(self, scale:float) -> None:
        '''set the pressure for this channel to the pressure in the constBox'''
        runPressure = float(self.constBox.text())
        self.goToPressure(runPressure*scale, False)
#         print(f'go to {runPressure*scale}')
    
    def setPressure(self) -> None:
        '''set the pressure for this channel to the pressure in the setBox'''
        runPressure = int(self.setBox.text())
        self.goToPressure(runPressure, True)

    def runConstTime(self) -> None:
        '''turn on pressure to the setBox value for a constTimeBox amount of time'''
        runTime = int(self.constTimeBox.text())
        if runTime<0:
            return
        runPressure = int(self.setBox.text())
        self.fluBox.updateStatus(f'Setting channel {self.chanNum0} to {runPressure} {self.units} for {runTime} s', True)
        setPressure(self.chanNum0, runPressure, self.units)
        QTimer.singleShot(runTime*1000, self.zeroChannel) 
            # QTimer wants time in milliseconds
        self.fluBox.addRowToCalib(runPressure, runTime, self.chanNum0)

    @pyqtSlot()
    @pyqtSlot(bool)
    def zeroChannel(self, status:bool=True) -> None:
        '''zero the channel pressure'''
        if status:
            self.fluBox.updateStatus(f'Setting channel {self.chanNum0} to 0 {self.units}', True)
        setPressure(self.chanNum0, 0, self.units)

        
    def writeToTable(self, writer) -> None:
        '''write metatable values to a csv writer object'''
        press = self.constBox.text()
        writer.writerow([f'ink_pressure_channel_{self.chanNum0}',self.units, press])
        writer.writerow([f'flag1_channel_{self.chanNum0}','', self.flag1])
        
    def updateReading(self, preading:int) -> None:
        '''update the displayed pressure'''
        self.readLabel.setText(preading)