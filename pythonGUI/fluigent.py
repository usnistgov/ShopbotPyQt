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
from fluChannels import *
from fluPlot import *

   
#----------------------------------------------------------------------


class fluSettingsBox(QWidget):
    '''This opens a window that holds settings about the Fluigent.'''
    
    
    def __init__(self, fluBox:connectBox):
        '''parent is the connectBox that this settings dialog belongs to.'''
        
        super().__init__(fluBox) 

        self.fluBox = fluBox
        
        layout = QVBoxLayout()
    
        
        self.savePressureCheck = fCheckBox(layout, title='Save pressure graph during print'
                                           , checked=fluBox.savePressure
                                           , func=self.updateSavePressure)
        
        unitDict = {0:'mbar', 1:'kPa', 2:'psi'}
        self.unitInv = {v: k for k, v in unitDict.items()}
        
        self.unitsGroup = fRadioGroup(layout, 'Pressure units', unitDict, unitDict,
                                         self.fluBox.units, col=False, headerRow=False,
                                          func=self.changeUnits)
        
        objValidator = QIntValidator()
        form = QFormLayout()
        form.setSpacing(10)
        
        editw = 100
        self.dtBox = fLineEdit(form, title='Time between readings (ms)'
                               , text=str(fluBox.dt)
                               , tooltip='Time in ms between pressure readings'
                               , func=self.updateDt, width=editw
                              , validator=objValidator)
        self.trangeBox = fLineEdit(form, title='Plot time range (s)'
                                   , text=str(fluBox.trange)
                                   , tooltip='Time in s to display in plot'
                                   , func=self.updateTrange, width=editw
                                  , validator=objValidator)
        self.pmaxBox = fLineEdit(form, title=f'Plot pressure range'
                                 , text=str(fluBox.pmax)
                                 , tooltip=f'Max pressure in chosen units to display in plot'
                                 , func=self.updatePmax, width=editw
                                , validator=objValidator)

        layout.addItem(form)
        
        grid = QGridLayout()
        
        grid.addWidget(QLabel('Color'), 2, 0)
        grid.addWidget(QLabel(f'Flag ({cfg.shopbot.flag1min}-{cfg.shopbot.flag1max})'), 4, 0)
        padding = 20
        for r in [1,3]:
            grid.setRowMinimumHeight(r, padding)
        
        objValidator2 = QIntValidator(1, 12)
        self.clabs = [QLabel(f'Channel {i}') for i in range(self.fluBox.numChans-self.fluBox.uvChans)]
        if self.fluBox.uvChans==1:
            self.clabs.append(QLabel('UV LED'))
        self.colorBoxes = ['' for i in range(self.fluBox.numChans)]
        self.flagBoxes = ['' for i in range(self.fluBox.numChans)]     # 1-indexed
        for i in range(fluBox.numChans):
            col = 2*i+2
            grid.setColumnMinimumWidth(col-1, padding)
            color = self.fluBox.colors[i]
            grid.addWidget(self.clabs[i], 0, col)
            cboxsize = 50
            if i<self.fluBox.numChans-self.fluBox.uvChans:
                nm = f'Channel {i} color'
            else:
                nm = 'UV lamp color'
            self.colorBoxes[i] = fButton(None, width=cboxsize, height=cboxsize, tooltip=nm, func=self.selectColor)
            self.colorBoxes[i].chanNum0 = i
            grid.addWidget(self.colorBoxes[i], 2, col)
            self.flagBoxes[i] = fLineCommand(func=self.updateFlags, validator=objValidator2, maxwidth=editw)
            self.flagBoxes[i].chanNum0 = i
            grid.addWidget(self.flagBoxes[i], 4, col)
            self.setLabelColor(i, color)
            
        grid.addWidget(QLabel(), 1, 2*fluBox.numChans+1)   # spacer

        layout.addItem(grid)
        layout.addStretch()
        
        self.setLayout(layout)

    
    def updateDt(self) -> None:
        '''update the value of dt in the parent'''
        self.fluBox.dt = int(self.dtBox.text())
        self.fluBox.pw.lock()
        self.fluBox.pw.dt = self.fluBox.dt   # update plotwatch object
        self.fluBox.pw.unlock()
        self.fluBox.updateStatus(f'Changed Fluigent plot dt to {self.fluBox.dt} ms', True)
        
    def changeUnits(self) -> None:
        '''update the display units'''
        units = self.fluBox.units
        newUnits = self.unitsGroup.value()
        if newUnits==units:
            return
        if newUnits=='psi':
            self.imperialDialog()
        else:
            self.acceptUnits()
            
    def imperialDialog(self) -> None:
        '''open an annoying dialog if the user tries to select imperial units'''        
        dlg = QDialog(self)
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Are you sure you want to use pounds per square inch?"))
        buttonBox = QDialogButtonBox()
        buttonBox.addButton('Yes, I reject the \ncool logic of SI \nand choose the devil\'s \nimperial units.', QDialogButtonBox.AcceptRole)
        buttonBox.addButton('No, take me back \nto my old units', QDialogButtonBox.RejectRole)
        buttonBox.accepted.connect(dlg.accept)
        buttonBox.rejected.connect(dlg.reject)
        layout.addWidget(buttonBox)
        dlg.setLayout(layout)
        if dlg.exec():
            self.acceptUnits()
        else:
            self.resetUnits()
            
    def acceptUnits(self) -> None:
        '''store the new units'''
        self.fluBox.setUnits(self.unitsGroup.value())
        self.pmaxBox.setText(str(self.fluBox.pmax))
        
        
    def resetUnits(self) -> None:
        '''go back to the old units'''
        self.unitsGroup.setChecked(self.unitInv[self.fluBox.units])
        
    def setLabelColor(self, chanNum0:int, color:str) -> None:
        '''set the labels on the settings boxes'''
        for b in [self.clabs[chanNum0], self.flagBoxes[chanNum0]]:
            b.setStyleSheet(f'color: {color}')
        for b in [self.colorBoxes[chanNum0]]:
            b.setStyleSheet(f'background-color: {color}; border-radius:10px')
        
    def selectColor(self) -> None:
        '''select a new channel color'''
        color = QColorDialog.getColor()
        if color.isValid():
            color = str(color.name())  # convert to hex string
            chanNum0 = self.sender().chanNum0
            self.fluBox.colors[chanNum0] = color
            self.fluBox.updateColors()
            self.setLabelColor(chanNum0, color)

        
    def updateTrange(self) -> None:
        '''update the value of trange in the parent'''
        self.fluBox.trange = int(self.trangeBox.text())
        self.fluBox.updateRange()
        
    def updatePmax(self) -> None:
        '''update the value of pmax in the parent'''
        self.fluBox.pmax = int(self.pmaxBox.text())
        self.fluBox.updateRange()
        self.fluBox.pw.lock()
        self.fluBox.pw.pmax = self.fluBox.pmax   # update plotwatch object
        self.fluBox.pw.unlock()
        
    def updateSavePressure(self) -> None:
        '''update the save pressure status of the fluigent box'''
        self.fluBox.savePressure = self.savePressureCheck.isChecked()
        
    def updateColors(self) -> None:
        '''update the colors in the plot and gui'''
        for i in range(self.fluBox.numChans):
            self.fluBox.colors[i] = self.colorBoxes[i].text()
        self.fluBox.updateColors()
        
    def updateFlags(self) -> None:
        '''update the flags in the channel objects'''
        chanNum0 = self.sender().chanNum0
        oldflag1 = self.fluBox.pchannels[chanNum0].flag1
        newflag1 = int(self.sender().text())
        if newflag1==oldflag1:
            return
        if self.fluBox.sbWin.flagTaken(newflag1-1): # convert to 0-indexed
            # another device is already assigned to that flag. revert
            self.sender().setText(str(oldflag1))
            return
        else:
            # free flag: assign
            self.fluBox.pchannels[chanNum0].flag1 = newflag1
            self.fluBox.sbWin.flagBox.labelFlags()
            if chanNum0<self.fluBox.pChans:
                s = f'channel {chanNum0}'
            else:
                s = 'uv lamp'
            self.fluBox.updateStatus(f'Changing flag of {s} to {newflag1}', True)

        
#--------------------------------------


class fluBox(connectBox):
    '''The GUI box that holds info about the Fluigent pressure controller.'''
    
    
    def __init__(self, sbWin:QMainWindow, arduino, connect:bool=True):
        '''sbWin is a pointer to the parent window'''
        
        super(fluBox, self).__init__()
        # this box is a QGroupBox. we are going to create a layout to put in the box
        self.bTitle = 'Fluigent'    # box title
        self.setTitle(self.bTitle)
        self.sbWin = sbWin 
        self.pchannels = []         # list of pressure channels as fluChannel objects
        self.connected = False      # connected to the fluigent
        self.save = False
        self.fileName = ''
        self.freshFileName = False
        self.numChans = 0
        self.uvChans = 0
        self.pChans = 0
        self.arduino = arduino
        if connect:
            self.connect() 
        

    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        cfg1.fluigent.dt = self.dt 
        cfg1.fluigent.trange = self.trange
        cfg1.fluigent.pmax = self.pmax
        cfg1.fluigent.savePressure = self.savePressure
        cfg1.fluigent.units = self.units
        for channel in self.pchannels:
            channel.saveConfig(cfg1)
        return cfg1
    
    def loadConfig(self, cfg1):
        '''load settings from a config Box object'''
        
        for s in ['dt', 'trange', 'pmax', 'savePressure', 'units']:
            if s in cfg1.fluigent:
                setattr(self, s, cfg1.fluigent[s])
            else:
                setattr(self, s, {'dt':100, 'trange':60, 'pmax':7000, 'savePressure':True, 'units':'mbar'}[s])
        for channel in self.pchannels:
            channel.loadConfig(cfg1)
        self.pcolors = self.cfgColors()  # preset channel colors
        self.colors = self.pcolors
        

    def cfgColors(self) -> List[str]:
        '''get a list of colors from the config file'''
        colors = []
        for key in cfg.fluigent:
            if key.startswith('channel'):
                colors.append(cfg.fluigent[key].color)
        if 'uv' in cfg:
            colors.append(cfg.uv.color)
        return colors
    
    def connect(self) -> None: 
        '''try to connect to the Fluigent'''
        
        self.connectAttempts+=1
        self.connectingLayout()  # temporarily put up a layout saying we're connected
        
        fgt.fgt_init()           # initialize fluigent
        self.pChans = fgt.fgt_get_pressureChannelCount()  # how many Fluigent channels do we have
        
        if self.arduino.uvConnected:
            # add a UV channel
            self.uvChans = 1
        else:
            self.uvChans = 0
            print('no uv channels')
            
        self.numChans = self.pChans + self.uvChans
        
        
        if self.numChans>0:
            self.connected = True
            self.successLayout()
        else:
            self.failLayout()
            self.testLayout()
            
    def testLayout(self) -> None:
        '''create timers for testing other boxes'''
        self.loadConfig(cfg)
        self.pcolors = self.cfgColors()
        self.pw = plotWatch(self.pChans, self.uvChans, self.trange, self.dt, self.units, self.pmax)
        self.fluPlot = fluPlot(self.pcolors, self, self.pw)      # create plot
        
    def small(self):
        self.fluPlot.small()

    def successLayout(self) -> None:
        '''display if we successfully connected to the fluigent'''
        self.loadConfig(cfg)
        
        self.settingsBox = fluSettingsBox(self)
        
        self.resetLayout()                  # erase the old layout
        self.layout = QVBoxLayout()     # whole fluigent layout
        
        self.createStatus(800)              # 800 px wide status bar
        self.layout.addWidget(self.status)
        
        self.fluButts = fGridLayout(spacing=10, alignment='left')
        self.printButts = fGridLayout(spacing=10, alignment='left')
        
        self.columnw = 100  
        channelLabel = fLabel(title=' ')
        readLabel = fLabel(title='Current pressure (mBar)')
        setPressureLabel = fLabel(title='Set pressure (mBar)')
        pressureGoLabel = fLabel(title='  ... indefinitely')
        runTimeLabel = fLabel(title='  ... for fixed time (s)')
        qhline = QHLine()
        
        for i, l in enumerate([channelLabel, readLabel, qhline, setPressureLabel, pressureGoLabel, runTimeLabel]):
            if i==2 or i==6:
                w = 1+2*self.numChans
            else:
                w=1
            self.fluButts.addWidget(l, i, 0, 1, w)
            
        runPressureLabel = fLabel(title='Pressure during print (mBar)')
        self.printButts.addWidget(runPressureLabel, 1,0)
        
        # create channels
        self.pchannels = []                 # pchannels is a list of fluChannel and uvChannel objects
        for i in range(self.pChans):
            pc = fluChannel(i, self)  # channel buttons are added to the layout during initialization
            self.pchannels.append(pc)
        for j in range(self.uvChans):
            pc = uvChannel(self.pChans, self)   
            self.pchannels.append(pc)
            
        # create plot
        self.pw = plotWatch(self.pChans, self.uvChans, self.trange, self.dt, self.units, self.pmax)
        self.fluPlot = fluPlot(self.pcolors, self, self.pw)      # create plot

        self.layout = fVBoxLayout(self.status, self.fluButtRow(), self.fluPlot.graphWidget)
        self.setLayout(self.layout)          # put the whole layout in the box
        
    def buttRow(self, name:str) -> QLayout:
        if hasattr(self, name):
            box = fHBoxLayout(getattr(self, name))
            box.addStretch()
            return box
        else:
            return QHBoxLayout()
        
    def printButtRow(self) -> QLayout:
        '''get a layout with the print pressure buttons'''
        return self.buttRow('printButts')
    
    def addPrintButtRow(self, layout:QLayout):
        '''add the print butts to the lyout'''
        if hasattr(self, 'printButts'):
            layout.addItem(self.printButtRow())
        
    def fluButtRow(self) -> QLayout:
        '''get a layout with the fluigent buttons'''
        return self.buttRow('fluButts')
        

        
    #-----------------------------------------
    
    def turnOnChannel(self, chanNum0:int) -> None:
        '''turn the pressure channel on to the run pressure'''
        self.pchannels[chanNum0].goToRunPressure(1)
        
    def turnOffChannel(self, chanNum0:int) -> None:
        '''turn the pressure channel on to the run pressure'''
        self.pchannels[chanNum0].zeroChannel()

    def resetAllChannels(self, exclude:int) -> None:
        '''Set all of the channels to 0 except for exclude (0-indexed). exclude is a channel that we want to keep on. Input -1 to turn everything off'''
        for i in range(self.numChans):
            if not i==exclude:
                self.turnOffChannel(i)
                
    
    def updateReading(self, chanNum0:int, preading:int) -> None:
        '''updates the status box that tells us what pressure this channel is at'''
        self.pchannels[chanNum0].updateReading(preading)
        
    def setUnits(self, units:str):
        '''change pressure units'''
        if units==self.units:
            return
        self.oldUnits = self.units
        self.units = units
        for s in ['pw', 'fluPlot']:
            if hasattr(self, s):
                getattr(self, s).updateUnits(self.units)
        if hasattr(self, 'pchannels'):
            for channel in self.pchannels:
                channel.updateUnits(self.units)
        self.pmax = convertPressure(self.pmax, self.oldUnits, self.units)
        self.updateRange()
        self.sbWin.calibDialog.updateUnits(self.units)
        
    def updateRange(self) -> None:
        '''Update the plot time range'''
        self.fluPlot.updateRange()
        
    def updateRunPressure(self, p:float, channel:int) -> None:
        self.pchannels[channel].constBox.setText(str(p))
        
    def updateColors(self) -> None:
        '''Update channel colors'''
        self.fluPlot.updateColors()
        for i in range(len(self.pchannels)):
            self.pchannels[i].updateColor(self.colors[i])
            
    def addRowToCalib(self, runPressure:float, runTime:float, chanNum0:int) -> None:
        '''add pressure and time to the calibration table'''
        self.sbWin.calibDialog.addRowToCalib(runPressure, runTime, chanNum0)

    #----------------------------------------
    
    def pressureTriggered(self, channels0Triggered:dict) -> bool:
        '''determine if any pressure channels are triggered during the print'''
        for i in range(self.numChans):
            if self.pchannels[i].flag1-1 in channels0Triggered:
                return True
        return False
    
    def timeRow(self, channels0Triggered:dict) -> List:
        '''get a list of values to collect for the time table'''
        out = []
        if self.savePressure and self.connected:
            for i in range(self.pChans):
                if self.pchannels[i].flag1-1 in channels0Triggered:
                    out.append(self.fluPlot.pw.pressures[i][-1])
            for i in range(self.uvChans):
                if self.pchannels[i+self.pChans].flag1-1 in channels0Triggered:
                    if self.arduino.uvOn:
                        out.append(1)
                    else:
                        out.append(0)
        return out
    
    def timeHeader(self, channels0Triggered:dict) -> List:
        '''get a list of header values for the time table'''
        out = []
        if self.savePressure and self.connected:
            for i in range(self.pChans):
                if self.pchannels[i].flag1-1 in channels0Triggered:
                    out.append(f'Channel_{i}_pressure({self.units})')
            for i in range(self.uvChans):
                if self.pchannels[i+self.pChans].flag1-1 in channels0Triggered:
                    out.append('UV')
        return out
    
    
    def writeToTable(self, writer) -> None:
        '''write metadata to the csv writer'''
        for i in range(len(self.pchannels)):
            channel = self.pchannels[i]
            channel.writeToTable(writer)
            if hasattr(self.sbWin, 'calibDialog'):
                self.sbWin.calibDialog.writeValuesToTable(i, writer)

    #-----------------------------------------
    
    
    def close(self) -> None:
        '''this runs when the window is closed'''
        # close the fluigent
        if self.connected:   
            if hasattr(self, 'pw'):
                self.pw.lock()
                self.pw.stop = True
                self.pw.unlock()
            if hasattr(self, 'fluPlot'):
                self.fluPlot.close()
            try:
                self.resetAllChannels(-1)
                fgt.fgt_close() 
            except Exception as e:
                print(e)
                pass
            else:
                logging.info('Fluigent closed')  
            # stop the timer used to create the fluigent plot
            