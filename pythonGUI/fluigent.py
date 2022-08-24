#!/usr/bin/env python
'''Shopbot GUI functions for controlling fluigent mass flow controller'''

# external packages
from PyQt5.QtCore import pyqtSignal, QObject, QRunnable, Qt, QTimer, QThreadPool
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

class fluChannel:
    '''this class describes a single channel on the Fluigent
        fgt functions come from the Fluigent SDK
        each channel gets a QLayout that can be incorporated into the fluBox widget'''
    
    def __init__(self, chanNum0:int, fluBox:connectBox):
        '''chanNum0 is a 0-indexed channel number (e.g. 0)
        fluBox is the parent box that holds the Fluigent GUI display'''

        self.chanNum0 = chanNum0  # 0-indexed
        self.bTitle = f'Channel {chanNum0}'
        self.cname = f'channel{self.chanNum0}'
        
        self.fluBox = fluBox
        self.loadConfig(cfg)
        
        columnw = fluBox.columnw
        # make 2 labels
        for i in range(2):
            setattr(self, f'label{i}', fLabel(title=self.bTitle, width=1.5*columnw))
        self.readLabel = fLabel(title='0', width=1.5*columnw, tooltip='Current pressure')
        
        # setBox is a one line input box that lets the user turn the pressure on to setBox
        objValidator = QIntValidator(0, 7000)
        self.setBox = fLineCommand(width=columnw, text='0'
                                   , func=self.setPressure
                                   , tooltip='Set the pressure. Press [enter] or click Go to set the pressure.'
                                   , validator=objValidator)
        self.setButton = fButton(None, title='Go', width=0.5*columnw
                                 , func=self.setPressure
                                 , tooltip='Set pressure to [Set pressure] mbar.')
        self.constTimeBox = fLineCommand(width=columnw, text='0', validator=objValidator
                                         , func=self.runConstTime
                                         , tooltip = 'Set pressure to [Set Pressure] for [Fixed time] s,\
                                         then turn off.\nPress [enter] or click Go to start.')
        self.constTimeButton = fButton(None, title='Go', width=0.5*columnw, func=self.runConstTime,
                                      tooltip = 'Set pressure to [Set Pressure] for [Fixed time] s, then turn off.')
        self.constBox = fLineCommand(width=columnw, text='0', validator=objValidator
                                     , tooltip='Pressure to use during printing')
        
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
        
    def loadConfig(self, cfg1) -> None:
        '''load settings from the config file'''
        self.color = cfg.fluigent[self.cname].color
        self.flag1 = cfg.fluigent[self.cname].flag1
        self.fluBox.settingsBox.flagBoxes[self.chanNum0].setText(str(self.flag1))
        
    def saveConfig(self, cfg1):
        cfg1.fluigent[self.cname].color = self.color
        cfg1.fluigent[self.cname].flag1 = self.flag1
        return cfg1
    
    def updateFlag(self, flag1) -> None:
        '''update the tracking flag'''
        self.flag1 = flag1
        
    def updateColor(self, color:str) -> None:
        '''update color of text items'''
        self.color = color
        try:
            for o in [self.label0, self.label1, self.readLabel, self.setButton, self.constTimeButton, self.setBox, self.constTimeBox, self.constBox]:
                o.setStyleSheet(f'color: {color};')  
                # this makes the label our input color
        except:
            logging.warning(f'Failed to update color of channel {self.chanNum0} to {color}')
            
            
    def goToPressure(self, runPressure:int, status:bool) -> None:
        '''to to the given pressure'''
        fgt.fgt_set_pressure(self.chanNum0, runPressure)
        if status:
            self.fluBox.updateStatus(f'Setting channel {self.chanNum0} to {runPressure} mbar', True)
            
    def goToRunPressure(self, scale:float=1) -> None:
        '''set the pressure for this channel to the pressure in the constBox'''
        runPressure = int(self.constBox.text())
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
        self.fluBox.updateStatus(f'Setting channel {self.chanNum0} to {runPressure} mbar for {runTime} s', True)
        fgt.fgt_set_pressure(self.chanNum0, runPressure)
        QTimer.singleShot(runTime*1000, self.zeroChannel) 
            # QTimer wants time in milliseconds
        self.fluBox.addRowToCalib(runPressure, runTime, self.chanNum0)
    
    
    def zeroChannel(self, status:bool=True) -> None:
        '''zero the channel pressure'''
        if status:
            self.fluBox.updateStatus(f'Setting channel {self.chanNum0} to 0 mbar', True)
        fgt.fgt_set_pressure(self.chanNum0, 0)
        
        
    def writeToTable(self, writer) -> None:
        '''write metatable values to a csv writer object'''
        press = int(self.constBox.text())
        writer.writerow([f'ink_pressure_channel_{self.chanNum0}','mbar', press])
        writer.writerow([f'flag1_channel_{self.chanNum0}','', self.flag1])
        

        
##############################  


    

#########################################################

class plotWatch:
    '''Holds the pressure/time list for all channels'''

    def __init__(self, numChans:int, fb:connectBox):
        self.stop = False          # tells us to stop reading pressures
        self.numChans = numChans   # number of channels
        self.fluBox = fb
        self.initializePList()

        
            
    def initializePList(self) -> None:
        '''initialize the pressure list and time list'''
        # initialize the time range
        self.time = list(np.arange(-cfg.fluigent.trange*1, 0, self.fluBox.dt/1000)) 
               
        # initialize pressures. assume 0 before we initialized the gui    
        self.pressures = []
        
        for i in range(self.numChans):
            press = [0 for _ in range(len(self.time))]
            self.pressures.append(press)

#------------------------------

def checkPressure(channel:int) -> int:
    '''reads the pressure of a given channel, 0-indexed'''
    pressure = int(fgt.fgt_get_pressure(channel))
    return pressure

#------------------------------

class fluSignals(QObject):
    '''Signals connector that lets us send status updates back to the GUI from the fluPlot object'''
    
    finished = pyqtSignal()
    error = pyqtSignal(str, bool)
    progress = pyqtSignal()
            
class plotRunnable(QRunnable):
    '''plotRunnable updates the list of times and pressures and allows us to read pressures continuously in a background thread.'''
    
    def __init__(self, pw, fluBox:connectBox):
        super(plotRunnable, self).__init__()   
        self.pw = pw                  # plotWatch object (stores pressure list)
        self.numChans = pw.numChans   # number of channels
        self.signals = fluSignals()   # lets us send messages and data back to the GUI
        self.fluBox = fluBox
        self.connected = fluBox.connected

    
    def run(self) -> None:
        '''update the plot and displayed pressure'''
        try:
            newtime = self.pw.time
            newpressures = self.pw.pressures        
            newtime = newtime[1:]                   # Remove the first y element.
            dnow = datetime.datetime.now()          # Finds current time relative to when the plot was created
            tnow = (dnow-self.fluBox.d0).total_seconds()
            newtime.append(tnow)         # Add the current time to the list
            for i in range(self.numChans):
                newpressures[i] = newpressures[i][1:]
                if self.connected:
                    pnew = checkPressure(i)
                else:
                    pnew = 0
                newpressures[i].append(pnew)         # Add the current pressure to the list, for each channel
        except Exception as e:
            self.signals.error.emit(f'Error reading pressure', True)
        else:
            self.pw.time = newtime                   # Save lists to plotWatch object
            self.pw.pressures = newpressures   
            self.signals.progress.emit()             # Tell the GUI to update plot

#------------------------------
            
class fluPlot:
    '''produces a plot that can be displayed in fluBox'''
    
    def __init__(self, pcolors:List[str], fb:connectBox):
        '''pcolors is a list of colors, e.g. ['#FFFFFF', '#000000']
        fb is a pointer to the fluigent box that contains this plot'''
        self.fluBox = fb # parent box
        self.sbWin = self.fluBox.sbWin
        self.numChans = self.fluBox.numChans
        self.connected = fb.connected
        
        
        # create the plot
        self.graphWidget = pg.PlotWidget() 
#         self.graphWidget.setFixedSize(800, 390)
        
        self.graphWidget.setYRange(-10, fb.pmax + 100, padding=0) 
            # set the range from 0 to 7000 mbar
        self.graphWidget.setBackground('w')         
        self.pcolors = pcolors
        
        self.pw = plotWatch(self.numChans, fb)

        self.datalines = []
        self.updateColors()
        for i in range(self.numChans):
            press = self.pw.pressures[i]
            cname = f'Channel {i}'
            dl = self.graphWidget.plot(self.pw.time, press, pen=self.pens[i], name=cname)
            self.datalines.append(dl)
        
        self.graphWidget.setLabel('left', 'Pressure (mBar)')
        self.graphWidget.setLabel('bottom', 'Time (s)')
        
        self.timerRunning = False
        self.startTimer()
        # create a thread to update the pressure list
        
    def fullSize(self):
        '''full size plot widget'''
        self.graphWidget.setMaximumHeight(390)
        self.graphWidget.setMaximumWidth(600)
        
    def small(self):
        '''small plot widget'''
        self.graphWidget.setMaximumHeight(200)
        self.graphWidget.setMaximumWidth(500)
        
        
    def startTimer(self) -> None:
        '''start updating the plot'''
        if not self.timerRunning:
            self.fluBox.d0 = datetime.datetime.now()  # the last time when we read the pressures
            self.timer = QTimer()
            self.timer.timeout.connect(self.timerFunc)        # run the timerFunc every mspf milliseconds
            self.timer.setTimerType(Qt.PreciseTimer)   # may or may not improve timer accuracy, depending on computer
            self.timer.start(self.fluBox.dt)                       # start timer with frequency milliseconds per frame
            self.timerRunning = True
            
            logging.debug('Fluigent timer started')

    def stopTimer(self) -> None:
        '''this only stops the timer if we are neither recording nor previewing'''
        self.timer.stop()
        self.timerRunning = False
        logging.info('Fluigent timer stopped')
                
    def timerFunc(self) -> None:
        '''on each timer hit, create a plotRunnable to update the plot and record values'''
        plotThread = plotRunnable(self.pw, self.fluBox)
        plotThread.signals.progress.connect(self.update)
        QThreadPool.globalInstance().start(plotThread) 

        
    def updateColors(self) -> None:
        '''update pen colors'''
        self.pens = [pg.mkPen(color=c, width=2) for c in self.fluBox.colors]

    
    def update(self) -> None:
        '''read the pressure and update the plot display'''
        # add pressures to table if we're saving
        if self.fluBox.save:
            tlist = [self.pw.time[-1]]
            plist = self.fluBox.timeRow()
            if hasattr(self.sbWin, 'sbBox'):
                xyzlist = self.sbWin.sbBox.timeRow()
            else:
                xyzlist = []
            self.fluBox.saveTable.append(tlist+plist+xyzlist)

        # update display
        if self.connected:
            for i in range(self.numChans):
                # update the plot
                if len(self.pw.time) == len(self.pw.pressures[i]):
                    self.datalines[i].setData(self.pw.time, self.pw.pressures[i], pen=self.pens[i])
                # update the pressure reading
                self.fluBox.updateReading(i, str(self.pw.pressures[i][-1])) 
                
#         self.sbWin.sbBox.readAndUpdateFlag()  # update flags reading
        
    def updateRange(self) -> None:
        '''update the plot time and pressure range'''
        
        # update time range
        tmin = min(self.pw.time)
        tgap = self.fluBox.trange - (max(self.pw.time)-tmin)
        dt = self.fluBox.dt/1000
        tsteps = int(round(tgap/dt))
        
        if tsteps>0:
            # add tsteps points to the beginning
            self.pw.time = [tmin+(i-tsteps)*dt for i in range(tsteps)] + self.pw.time
            for j in range(len(self.pw.pressures)):
                self.pw.pressures[j] = [0 for i in range(tsteps)] + self.pw.pressures[j]
        elif tsteps<0:
            self.pw.time = self.pw.time[(-tsteps):]
            for j in range(len(self.pw.pressures)):
                self.pw.pressures[j] = self.pw.pressures[j][(-tsteps):]
          
        # update pressure range
        self.graphWidget.setYRange(-10, self.fluBox.pmax + 100, padding=0) 
        
        # update display
        self.update()
            
            
    
    #-----------------------------------------
    
    
    def close(self) -> None:
        '''gets triggered when the window is closed. It stops the pressure readings.'''
        try: 
            self.pw.stop = True
            self.stopTimer()
        except:
            pass
        else:
            logging.info('Fluigent timer deleted')
    
    
#--------------------------------------

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
        self.pmaxBox = fLineEdit(form, title='Plot pressure range (mbar)'
                                 , text=str(fluBox.pmax)
                                 , tooltip='Max pressure in mbar to display in plot'
                                 , func=self.updatePmax, width=editw
                                , validator=objValidator)

        layout.addItem(form)
        
        grid = QGridLayout()
        
        grid.addWidget(QLabel('Color'), 2, 0)
        grid.addWidget(QLabel('Flag (1-12)'), 4, 0)
        padding = 20
        for r in [1,3]:
            grid.setRowMinimumHeight(r, padding)
        
        objValidator2 = QIntValidator(1, 12)
        self.clabs = [QLabel(f'Channel {i}') for i in range(self.fluBox.numChans)]
        self.colorBoxes = ['' for i in range(self.fluBox.numChans)]
        self.flagBoxes = ['' for i in range(self.fluBox.numChans)]     # 1-indexed
        for i in range(fluBox.numChans):
            col = 2*i+2
            grid.setColumnMinimumWidth(col-1, padding)
            color = self.fluBox.colors[i]
            grid.addWidget(self.clabs[i], 0, col)
            cboxsize = 50
            self.colorBoxes[i] = fButton(None, width=cboxsize, height=cboxsize, tooltip=f'Channel {i} color', func=self.selectColor)
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
        self.fluBox.updateStatus(f'Changed Fluigent plot dt to {self.fluBox.dt} ms', True)
        
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
            self.sender.setText(str(oldflag1))
            return
        else:
            # free flag: assign
            self.fluBox.pchannels[chanNum0].flag1 = newflag1
            self.fluBox.sbWin.flagBox.labelFlags()
            self.fluBox.updateStatus(f'Changing flag of channel {chanNum0} to {newflag1}', True)
            
        
        
#--------------------------------------


class fluBox(connectBox):
    '''The GUI box that holds info about the Fluigent pressure controller.'''
    
    
    def __init__(self, sbWin:QMainWindow, connect:bool=True):
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
        if connect:
            self.connect() 
        

    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        cfg1.fluigent.dt = self.dt 
        cfg1.fluigent.trange = self.trange
        cfg1.fluigent.pmax = self.pmax
        cfg1.fluigent.savePressure = self.savePressure
        for channel in self.pchannels:
            channel.saveConfig(cfg1)
        return cfg1
    
    def loadConfig(self, cfg1):
        '''load settings from a config Box object'''
        self.dt = cfg1.fluigent.dt
        self.trange = cfg1.fluigent.trange
        self.pmax = cfg1.fluigent.pmax
        self.savePressure = cfg1.fluigent.savePressure
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
        return colors
    
    def connect(self) -> None: 
        '''try to connect to the Fluigent'''
        
        self.connectAttempts+=1
        self.connectingLayout()  # temporarily put up a layout saying we're connected
        
        fgt.fgt_init()           # initialize fluigent
        self.numChans = fgt.fgt_get_pressureChannelCount()  # how many Fluigent channels do we have
        
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
        self.fluPlot = fluPlot(self.pcolors, self)      # create plot
        
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
        self.pchannels = []                 # pchannels is a list of fluChannel objects
        for i in range(self.numChans):
            pc = fluChannel(i, self)  # channel buttons are added to the layout during initialization
            self.pchannels.append(pc)
            
        # create plot
        self.fluPlot = fluPlot(self.pcolors, self)      # create plot

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
        
    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        cfg1.fluigent.dt = self.dt 
        cfg1.fluigent.trange = self.trange
        cfg1.fluigent.pmax = self.pmax 
        cfg1.savePressure = self.savePressure
        for pchannel in self.pchannels:
            cfg1 = pchannel.saveConfig(cfg1)
        return cfg1
        
    #-----------------------------------------
    
    def turnOnChannel(self, chanNum0:int) -> None:
        '''turn the pressure channel on to the run pressure'''
        self.pchannels[chanNum0].goToRunPressure()
        
    def turnOffChannel(self, chanNum0:int) -> None:
        '''turn the pressure channel on to the run pressure'''
        self.pchannels[chanNum0].zeroChannel()

    def resetAllChannels(self, exclude:int) -> None:
        '''Set all of the channels to 0 except for exclude (0-indexed). exclude is a channel that we want to keep on. Input -1 to turn everything off'''
        for i in range(self.numChans):
            if not i==exclude:
                fgt.fgt_set_pressure(i,0)
                
    
    def updateReading(self, chanNum0:int, preading:int) -> None:
        '''updates the status box that tells us what pressure this channel is at'''
        self.pchannels[chanNum0].readLabel.setText(preading)
        
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
        
        
    #-----------------------------------------
    
    def getFileName(self) -> str:
        try:
            fullfn = self.sbWin.newFile('time', '.csv')
        except NameError:
            self.fileName = ''
            return
        self.fileName = fullfn
    
    def startRecording(self) -> None:
        '''Start keeping track of pressure readings in a table to be saved to file'''
        if self.savePressure or self.sbWin.sbBox.savePos:
            self.saveTable = []
            self.save = True
            self.getFileName() # determine the current file name

    def stopRecording(self) -> None:
        '''Save the recorded pressure readings in a csv'''
        dummy = 0
        # get 10 more points
        while dummy<10:
            if not hasattr(self, 'dt'):
                # load dt if there is none
                self.dt = cfg.fluigent.dt
            time.sleep(self.dt/1000) 
            self.fluPlot.update()
            dummy+=1
            
        # write the table to file
        if (self.savePressure or self.sbWin.sbBox.savePos) and self.save:
            self.save = False
            with open(self.fileName, mode='w', newline='', encoding='utf-8') as c:
                writer = csv.writer(c, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                phead = self.timeHeader()
                xyzhead = self.sbWin.sbBox.timeHeader()
                writer.writerow(['time(s)']+phead+xyzhead) # header
                for row in self.saveTable:
                    writer.writerow(row)
            self.updateStatus(f'Saved {self.fileName}', True)
            
            
    #----------------------------------------
    def timeRow(self) -> List:
        '''get a list of values to collect for the time table'''
        if self.savePressure and self.connected:
            out = [j[-1] for j in self.fluPlot.pw.pressures]  # most recent pressure
        else:
            out = []
        return out
    
    def timeHeader(self) -> List:
        '''get a list of header values for the time table'''
        if self.savePressure and self.connected:
            out = [f'Channel_{i}_pressure(mbar)' for i in range(self.numChans)]
        else:
            out = []
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
            