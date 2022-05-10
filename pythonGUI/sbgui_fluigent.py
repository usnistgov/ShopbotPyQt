#!/usr/bin/env python
'''Shopbot GUI functions for controlling fluigent mass flow controller'''

# external packages
from PyQt5 import QtCore, QtGui
import PyQt5.QtWidgets as qtw
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
from sbgui_general import *

# info
__author__ = "Leanne Friedrich"
__copyright__ = "This data is publicly available according to the NIST statements of copyright, fair use and licensing; see https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software"
__credits__ = ["Leanne Friedrich"]
__license__ = "MIT"
__version__ = "1.0.4"
__maintainer__ = "Leanne Friedrich"
__email__ = "Leanne.Friedrich@nist.gov"
__status__ = "Development"
   
#----------------------------------------------------------------------

class fluChannel:
    '''this class describes a single channel on the Fluigent
        fgt functions come from the Fluigent SDK
        each channel gets a QLayout that can be incorporated into the fluBox widget'''
    
    def __init__(self, chanNum: int, color: str, fluBox:connectBox):
        '''chanNum is a 0-indexed channel number (e.g. 0)
        color is a string (e.g. #FFFFFF)
        fluBox is the parent box that holds the Fluigent GUI display'''
        self.chanNum = chanNum
        self.fluBox = fluBox
        
        columnw = fluBox.columnw
        
        self.label = qtw.QLabel('Channel '+str(chanNum+1))
        self.label.setFixedWidth(1.5*columnw)
        self.label2 = qtw.QLabel('Channel '+str(chanNum+1))
        self.label2.setFixedWidth(1.5*columnw)
              
        self.readLabel = qtw.QLabel('0')
        self.readLabel.setFixedWidth(1.5*columnw)
        self.readLabel.setToolTip('Current pressure')
        
        # setBox is a one line input box that lets the user turn the pressure on to setBox
        self.setBox = qtw.QLineEdit()
        self.setBox.setFixedWidth(columnw)
        self.setBox.setText('0')
#         self.setBox.selectionChanged.connect(self.setSetPressureFocus)
        self.setBox.returnPressed.connect(self.setPressure)
        self.setBox.setToolTip('Set the pressure. Press [enter] or click Go to set the pressure.')
        objValidator = QtGui.QIntValidator()
        objValidator.setRange(0, 7000)
        self.setBox.setValidator(objValidator)
        self.setButton = qtw.QPushButton('Go')
        self.setButton.setFixedWidth(0.5*columnw)
        self.setButton.clicked.connect(self.setPressure)
        self.setButton.setAutoDefault(False)
        self.setButton.setToolTip('Set pressure to [Set pressure] mbar.')
        

        
        # constTimeBox is an input box that lets the user turn on the pressure to constBox for constTimeBox seconds and then turn off
        self.constTimeBox = qtw.QLineEdit()
        self.constTimeBox.setFixedWidth(columnw)
        self.constTimeBox.setText('0')
        self.constTimeBox.setValidator(objValidator)
        self.constTimeBox.returnPressed.connect(self.runConstTime)
        self.constTimeBox.setToolTip('Set pressure to [Set Pressure] for [Fixed time] s, then turn off.\nPress [enter] or click Go to start.')
#         self.constTimeBox.selectionChanged.connect(self.setSetTimeFocus)
        self.constTimeButton = qtw.QPushButton('Go')
        self.constTimeButton.setFixedWidth(0.5*columnw)
        self.constTimeButton.clicked.connect(self.runConstTime)
        self.constTimeButton.setAutoDefault(False)
        self.constTimeButton.setToolTip('Set pressure to [Set Pressure] for [Fixed time] s, then turn off.')
        
        
        # constBox is a one line input box that is the 
        # "on" pressure for running files for this channel
        self.constBox = qtw.QLineEdit()
        self.constBox.setFixedWidth(columnw)
        self.constBox.setText('0')
        self.constBox.setValidator(objValidator)
#         self.constBox.selectionChanged.connect(self.setNoFocus)
        self.constBox.setToolTip('Pressure to use during printing')
        
        self.updateColor(color)           
        
        # line up the label and input box horizontally
        col1 = 1+2*self.chanNum
        self.fluBox.fluButts.addWidget(self.label, 0, col1+0, 1, 2)
        self.fluBox.fluButts.addWidget(self.readLabel, 1,col1+ 0, 1, 2)
        self.fluBox.fluButts.addWidget(self.setBox, 3, col1+0)
        self.fluBox.fluButts.addWidget(self.setButton, 4, col1+1)
        self.fluBox.fluButts.addWidget(self.constTimeBox, 5, col1+0)
        self.fluBox.fluButts.addWidget(self.constTimeButton, 5, col1+1)
        
        self.fluBox.printButts.addWidget(self.label2, 0, col1+0)
        self.fluBox.printButts.addWidget(self.constBox, 1, col1+0)
        
    def updateColor(self, color:str) -> None:
        '''update color of text items'''
        try:
            for o in [self.label, self.label2, self.readLabel, self.setButton, self.constTimeButton, self.setBox, self.constTimeBox, self.constBox]:
                o.setStyleSheet('color: '+color+';')  
                # this makes the label our input color
        except:
            logging.warning(f'Failed to update color of channel {self.chanNum} to {color}')
    
    def setPressure(self) -> None:
        '''set the pressure for this channel to the pressure in the setBox'''
        runPressure = int(self.setBox.text())
        fgt.fgt_set_pressure(self.chanNum, runPressure)
        self.fluBox.updateStatus(f'Setting channel {self.chanNum+1} to {runPressure} mbar', True)
    
    
    def runConstTime(self) -> None:
        '''turn on pressure to the setBox value for a constTimeBox amount of time'''
        runTime = int(self.constTimeBox.text())
        if runTime<0:
            return
        runPressure = int(self.setBox.text())
        self.fluBox.updateStatus(f'Setting channel {self.chanNum+1} to {runPressure} mbar for {runTime} s', True)
        fgt.fgt_set_pressure(self.chanNum, runPressure)
        QtCore.QTimer.singleShot(runTime*1000, self.zeroChannel) 
            # QTimer wants time in milliseconds
        self.fluBox.addRowToCalib(runPressure, runTime)
    
    
    def zeroChannel(self) -> None:
        '''zero the channel pressure'''
        self.fluBox.updateStatus(f'Setting channel {self.chanNum+1} to 0 mbar', True)
        fgt.fgt_set_pressure(self.chanNum, 0)

        
##############################  

class fluSignals(QtCore.QObject):
    '''Signals connector that lets us send status updates back to the GUI from the fluPlot object'''
    
    finished = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str, bool)
    progress = QtCore.pyqtSignal()
    

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
            
class plotRunnable(QtCore.QRunnable):
    '''plotRunnable updates the list of times and pressures and allows us to read pressures continuously in a background thread.'''
    
    def __init__(self, pw, fluBox:connectBox):
        super(plotRunnable, self).__init__()   
        self.pw = pw                  # plotWatch object (stores pressure list)
        self.numChans = pw.numChans   # number of channels
        self.signals = fluSignals()   # lets us send messages and data back to the GUI
        self.dprev = datetime.datetime.now()  # the last time when we read the pressures
        self.fluBox = fluBox

    
    def run(self) -> None:
        '''update the plot and displayed pressure'''
        while not self.pw.stop:
            try:
                newtime = self.pw.time
                newpressures = self.pw.pressures        
                newtime = newtime[1:]                   # Remove the first y element.
                dnow = datetime.datetime.now()          # Finds current time relative to when the plot was created
                dt = (dnow-self.dprev).total_seconds()
                self.dprev = dnow
                newtime.append(newtime[-1] + dt)         # Add the current time to the list
                for i in range(self.numChans):
                    newpressures[i] = newpressures[i][1:]
                    pnew = checkPressure(i)
                    newpressures[i].append(pnew)         # Add the current pressure to the list, for each channel
            except Exception as e:
                self.signals.error.emit(f'Error reading pressure', True)
            else:
                self.pw.time = newtime                   # Save lists to plotWatch object
                self.pw.pressures = newpressures   
                self.signals.progress.emit()             # Tell the GUI to update plot
            time.sleep(self.fluBox.dt/1000)                         # Update every 200 ms

#------------------------------
            
class fluPlot:
    '''produces a plot that can be displayed in fluBox'''
    
    def __init__(self, pcolors:List[str], fb:connectBox):
        '''pcolors is a list of colors, e.g. ['#FFFFFF', '#000000']
        fb is a pointer to the fluigent box that contains this plot'''
        self.fluBox = fb # parent box
        self.numChans = self.fluBox.numChans
        
        
        # create the plot
        self.graphWidget = pg.PlotWidget() 
#         self.graphWidget.setFixedSize(800, 390)
        self.graphWidget.setFixedHeight(390)
        self.graphWidget.setYRange(-10, fb.pmax + 100, padding=0) 
            # set the range from 0 to 7000 mbar
        self.graphWidget.setBackground('w')         
        self.pcolors = pcolors
        
        self.pw = plotWatch(self.numChans, fb)

        self.datalines = []
        self.updateColors()
        for i in range(self.numChans):
            press = self.pw.pressures[i]
            cname = 'Channel '+str(i+1)
            dl = self.graphWidget.plot(self.pw.time, press, pen=self.pens[i], name=cname)
            self.datalines.append(dl)
        
        self.graphWidget.setLabel('left', 'Pressure (mBar)')
        self.graphWidget.setLabel('bottom', 'Time (s)')

        # create a thread to update the pressure list
        plotThread = plotRunnable(self.pw, fb)
        plotThread.signals.progress.connect(self.update)
        QtCore.QThreadPool.globalInstance().start(plotThread)  
        
    def updateColors(self) -> None:
        '''update pen colors'''
        self.pens = [pg.mkPen(color=c, width=2) for c in self.fluBox.colors]

    
    def update(self) -> None:
        '''read the pressure and update the plot display'''
        try:
            # add pressures to table if we're saving
            if self.fluBox.save:
                tlist = [self.pw.time[-1]]
                plist = [j[-1] for j in self.pw.pressures]
                xyzlist = [self.fluBox.sbWin.sbBox.x, self.fluBox.sbWin.sbBox.y, self.fluBox.sbWin.sbBox.z]
                self.fluBox.saveTable.append(tlist+plist+xyzlist)
            for i in range(self.numChans):
                # update the plot
                self.datalines[i].setData(self.pw.time, self.pw.pressures[i], pen=self.pens[i])
                # update the pressure reading
                self.fluBox.updateReading(i, str(self.pw.pressures[i][-1]))  
        except:
            pass
        
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
        except:
            pass
        else:
            logging.info('Fluigent timer deleted')
    
    
#--------------------------------------

class fluSettingsBox(qtw.QWidget):
    '''This opens a window that holds settings about the Fluigent.'''
    
    
    def __init__(self, parent:connectBox):
        '''parent is the connectBox that this settings dialog belongs to.'''
        
        super().__init__(parent)  
        self.parent = parent
        
        layout = qtw.QVBoxLayout()
        
        self.savePressureCheck = qtw.QCheckBox('Save pressure graph during print')
        self.savePressureCheck.setChecked(parent.savePressure)
        self.savePressureCheck.clicked.connect(self.updateSavePressure)
        layout.addWidget(self.savePressureCheck)
        
        objValidator = QtGui.QIntValidator()
        form = qtw.QFormLayout()
        form.setSpacing(10)
        
        self.dtBox = qtw.QLineEdit()
        self.dtBox.setText(str(parent.dt))
        self.dtBox.setValidator(objValidator)
        self.dtBox.setToolTip('Time in ms between pressure readings')
        self.dtBox.returnPressed.connect(self.updateDt)
        
        self.trangeBox = qtw.QLineEdit()
        self.trangeBox.setText(str(parent.trange))
        self.trangeBox.setValidator(objValidator)
        self.trangeBox.setToolTip('Time in s to display in plot')
        self.trangeBox.returnPressed.connect(self.updateTrange)
        
        self.pmaxBox = qtw.QLineEdit()
        self.pmaxBox.setText(str(parent.pmax))
        self.pmaxBox.setValidator(objValidator)
        self.pmaxBox.setToolTip('Max pressure to display in plot')
        self.pmaxBox.returnPressed.connect(self.updatePmax)
        
        form.addRow('Time between readings (ms)', self.dtBox)
        form.addRow('Plot time range (s)', self.trangeBox)
        form.addRow('Plot pressure range (mbar)', self.pmaxBox)
        
        self.colorBoxes = [qtw.QLineEdit() for i in range(parent.numChans)]
        for i in range(parent.numChans):
            self.colorBoxes[i].setText(parent.colors[i])
            self.colorBoxes[i].setToolTip(f'Channel {i+1} color')
            self.colorBoxes[i].returnPressed.connect(self.updateColors)
            form.addRow(f'Channel {i+1} color', self.colorBoxes[i])
        
        layout.addItem(form)
        
        self.setLayout(layout)

    
    def updateDt(self) -> None:
        '''update the value of dt in the parent'''
        self.parent.dt = int(self.dtBox.text())
        
        
    def updateTrange(self) -> None:
        '''update the value of trange in the parent'''
        self.parent.trange = int(self.trangeBox.text())
        self.parent.updateRange()
        
    def updatePmax(self) -> None:
        '''update the value of pmax in the parent'''
        self.parent.pmax = int(self.pmaxBox.text())
        self.parent.updateRange()
        
    def updateSavePressure(self) -> None:
        '''update the save pressure status of the fluigent box'''
        self.parent.savePressure = self.savePressureCheck.isChecked()
        
    def updateColors(self) -> None:
        for i in range(self.parent.numChans):
            self.parent.colors[i] = self.colorBoxes[i].text()
        self.parent.updateColors()
        
        
        
#--------------------------------------


class fluBox(connectBox):
    '''The GUI box that holds info about the Fluigent pressure controller.'''
    
    
    def __init__(self, sbWin:qtw.QMainWindow):
        '''sbWin is a pointer to the parent window'''
        
        super(fluBox, self).__init__()
        # this box is a QGroupBox. we are going to create a layout to put in the box

        self.loadConfig(cfg)
        self.bTitle = 'Fluigent'    # box title
        self.setTitle(self.bTitle)
        self.sbWin = sbWin        
        self.pchannels = []         # list of pressure channels as fluChannel objects
        self.connected = False      # connected to the fluigent
        self.connect() 
        self.save = False
        self.fileName = ''
        self.freshFileName = False

    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        cfg1.fluigent.dt = self.dt 
        cfg1.fluigent.trange = self.trange
        cfg1.fluigent.pmax = self.pmax
        cfg1.fluigent.colors = self.colors
        cfg1.fluigent.savePressure = self.savePressure
        return cfg1
    
    def loadConfig(self, cfg1):
        '''load settings from a config Box object'''
        self.dt = cfg1.fluigent.dt
        self.trange = cfg1.fluigent.trange
        self.pmax = cfg1.fluigent.pmax
        self.colors = cfg1.fluigent.colors
        self.savePressure = cfg1.fluigent.savePressure
    
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

    
    
    def successLayout(self) -> None:
        '''display if we successfully connected to the fluigent'''
        
        self.settingsBox = fluSettingsBox(self)
        
        self.resetLayout()                  # erase the old layout
        self.layout = qtw.QVBoxLayout()     # whole fluigent layout
        
        self.createStatus(800)              # 800 px wide status bar
        self.layout.addWidget(self.status)
        
        self.fluButts = qtw.QGridLayout()   # fluigent operations grid
        self.fluButts.setSpacing(5)         # px between channel buttons
        self.fluButts.setAlignment(QtCore.Qt.AlignLeft)
        self.printButts = qtw.QGridLayout()
        self.printButts.setSpacing(5)         # px between channel buttons
        self.printButts.setAlignment(QtCore.Qt.AlignLeft)
        
        self.columnw = 100       
        
        channelLabel = qtw.QLabel(' ')
        readLabel = qtw.QLabel('Current pressure (mBar)')
        setPressureLabel = qtw.QLabel('Set pressure (mBar)')
        pressureGoLabel = qtw.QLabel('  ... indefinitely')
        runTimeLabel = qtw.QLabel('  ... for fixed time (s)')
        qhline = QHLine()
        qhline2 = QHLine()
        
        for i, l in enumerate([channelLabel, readLabel, qhline, setPressureLabel, pressureGoLabel, runTimeLabel]):
            if i==2 or i==6:
                w = 1+2*self.numChans
            else:
                w=1
                l.setFixedWidth(self.columnw*2.2)
            self.fluButts.addWidget(l, i, 0, 1, w)
            
        runPressureLabel = qtw.QLabel('Pressure during print (mBar)')
        runPressureLabel.setFixedWidth(self.columnw*3)
        self.printButts.addWidget(runPressureLabel, 1,0)
        
        self.pcolors = cfg.fluigent.colors[0:self.numChans]  # preset channel colors
        
        self.pchannels = []                 # pchannels is a list of fluChannel objects
        for i in range(self.numChans):
            pc = fluChannel(i, self.pcolors[i], self)  # channel buttons are added to the layout during initialization
            self.pchannels.append(pc)


        self.layout.addItem(self.fluButts)   # put the buttons in the layout
    
        self.fluPlot = fluPlot(self.pcolors, self)      # create plot
        self.layout.addWidget(self.fluPlot.graphWidget) # add plot to the layout
        
        self.setLayout(self.layout)          # put the whole layout in the box 
        
    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        cfg1.fluigent.dt = self.dt 
        cfg1.fluigent.trange = self.trange
        cfg1.fluigent.pmax = self.pmax 
        cfg1.savePressure = self.savePressure
        return cfg1
        
    #-----------------------------------------

    def resetAllChannels(self, exclude:int) -> None:
        '''Set all of the channels to 0 except for exclude (0-indexed). exclude is a channel that we want to keep on. Input -1 to turn everything off'''
        for i in range(self.numChans):
            if not i==exclude:
                fgt.fgt_set_pressure(i,0)
                
    
    def updateReading(self, channum:int, preading:int) -> None:
        '''updates the status box that tells us what pressure this channel is at'''
        self.pchannels[channum].readLabel.setText(preading)
        
    def updateRange(self) -> None:
        '''Update the plot time range'''
        self.fluPlot.updateRange()
        
    def updateRunPressure(self, p) -> None:
        self.pchannels[0].constBox.setText(str(p))
        
    def updateColors(self) -> None:
        '''Update channel colors'''
        self.fluPlot.updateColors()
        for i in range(len(self.pchannels)):
            self.pchannels[i].updateColor(self.colors[i])
            
    def addRowToCalib(self, runPressure:float, runTime:float) -> None:
        '''add pressure and time to the calibration table'''
        self.sbWin.calibDialog.addRowToCalib(runPressure, runTime)
        
        
    #-----------------------------------------
    
    def getFileName(self) -> str:
        try:
            fullfn = self.sbWin.newFile('Fluigent', '.csv')
        except NameError:
            self.fileName = ''
            return
        self.fileName = fullfn
    
    def startRecording(self) -> None:
        '''Start keeping track of pressure readings in a table to be saved to file'''
        if self.savePressure:
            self.saveTable = []
            self.save = True
            self.getFileName() # determine the current file name
        
    def stopRecording(self) -> None:
        '''Save the recorded pressure readings in a csv'''
        dummy = 0
        while dummy<10:
            time.sleep(self.dt/1000)  
            self.fluPlot.update()
            dummy+=1
        if self.savePressure and self.save:
            self.save = False
            with open(self.fileName, mode='w', newline='', encoding='utf-8') as c:
                writer = csv.writer(c, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                writer.writerow(['time(s)']+[f'Channel_{i}_pressure(mbar)' for i in range(self.numChans)]+['x(mm)', 'y(mm)', 'z(mm)']) # header
                for row in self.saveTable:
                    writer.writerow(row)
            self.updateStatus(f'Saved {self.fileName}', True)
            
        
        
    #-----------------------------------------
    
    
    def close(self) -> None:
        '''this runs when the window is closed'''
        # close the fluigent
        if self.connected:      
            try:
                self.fluPlot.close()
                self.resetAllChannels(-1)
                fgt.fgt_close() 
            except:
                pass
            else:
                logging.info('Fluigent closed')  
            # stop the timer used to create the fluigent plot
            