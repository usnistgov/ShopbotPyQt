#!/usr/bin/env python
'''Shopbot GUI functions for controlling fluigent mass flow controller'''

from PyQt5 import QtCore, QtGui
import PyQt5.QtWidgets as qtw
import pyqtgraph as pg
import time
import datetime
import numpy as np
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging

import Fluigent.SDK as fgt

from config import cfg
from sbgui_general import *


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
        
        
        for o in [self.label, self.label2, self.readLabel, self.setButton, self.constTimeButton, self.setBox, self.constTimeBox, self.constBox]:
            o.setStyleSheet('color: '+color+';')  
            # this makes the label our input color
        
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

    def __init__(self, numChans):
        self.stop = False          # tells us to stop reading pressures
        self.numChans = numChans   # number of channels
        self.initializePList()
        
            
    def initializePList(self) -> None:
        '''initialize the pressure list and time list'''
        # initialize the time range
        self.dt = 200 # ms
        self.time = list(np.arange(-60*1, 0, self.dt/1000)) 
               
        # initialize pressures. assume 0 before we initialized the gui    
        self.pressures = []
        
        for i in range(self.numChans):
            press = [0 for _ in range(len(self.time))]
            self.pressures.append(press)


def checkPressure(channel:int) -> int:
    '''reads the pressure of a given channel, 0-indexed'''
    pressure = int(fgt.fgt_get_pressure(channel))
    return pressure
            
class plotRunnable(QtCore.QRunnable):
    '''plotRunnable updates the list of times and pressures and allows us to read pressures continuously in a background thread.'''
    
    def __init__(self, pw):
        super(plotRunnable, self).__init__()   
        self.pw = pw                  # plotWatch object (stores pressure list)
        self.numChans = pw.numChans   # number of channels
        self.signals = fluSignals()   # lets us send messages and data back to the GUI
        self.dprev = datetime.datetime.now()  # the last time when we read the pressures

    
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
            time.sleep(200/1000)                         # Update every 200 ms

            
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
        self.graphWidget.setYRange(-10, 7100, padding=0) 
            # set the range from 0 to 7000 mbar
        self.graphWidget.setBackground('w')         
        self.pcolors = pcolors
        
        self.pw = plotWatch(self.numChans)

        self.datalines = []
        for i in range(self.numChans):
            press = self.pw.pressures[i]
            pen = pg.mkPen(color=pcolors[i], width=2)
            cname = 'Channel '+str(i+1)
            dl = self.graphWidget.plot(self.pw.time, press, pen=pen, name=cname)
            self.datalines.append(dl)
        
        self.graphWidget.setLabel('left', 'Pressure (mBar)')
        self.graphWidget.setLabel('bottom', 'Time (s)')

        # create a thread to update the pressure list
        plotThread = plotRunnable(self.pw)
        plotThread.signals.progress.connect(self.update)
        QtCore.QThreadPool.globalInstance().start(plotThread)   

    
    def update(self) -> None:
        '''read the pressure and update the plot display'''
        try:
            # add pressures to table if we're saving
            if self.fluBox.save:
                self.fluBox.saveTable.append([self.pw.time]+self.pw.pressures)
            for i in range(self.numChans):
                # update the plot
                self.datalines[i].setData(self.pw.time, self.pw.pressures[i])
                # update the pressure reading
                self.fluBox.updateReading(i, str(self.pw.pressures[i][-1]))  
        except:
            pass
    
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
        
        layout = QtGui.QVBoxLayout()
        
        self.savePressureCheck = qtw.QCheckBox('Save pressure graph during print')
        self.savePressureCheck.setChecked(False)
        layout.addWidget(self.savePressureCheck)
        
        self.setLayout(layout)

        
        
#--------------------------------------


class fluBox(connectBox):
    '''The GUI box that holds info about the Fluigent pressure controller.'''
    
    
    def __init__(self, sbWin:qtw.QMainWindow):
        '''sbWin is a pointer to the parent window'''
        
        super(fluBox, self).__init__()
        # this box is a QGroupBox. we are going to create a layout to put in the box
        self.bTitle = 'Fluigent'    # box title
        self.setTitle(self.bTitle)
        self.sbWin = sbWin        
        self.pchannels = []         # list of pressure channels as fluChannel objects
        self.connected = False      # connected to the fluigent
        self.connect() 
        self.save = False
        self.fileName = ''
    
    
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
        
        self.createStatus(600)              # 600 px wide status bar
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
        
        self.pcolors = ['#3f8dd1', '#b0401e', '#3e8a5b', '#b8a665'][0:self.numChans]  # preset channel colors
        
        self.pchannels = []                 # pchannels is a list of fluChannel objects
        for i in range(self.numChans):
            pc = fluChannel(i, self.pcolors[i], self)  # channel buttons are added to the layout during initialization
            self.pchannels.append(pc)


        self.layout.addItem(self.fluButts)   # put the buttons in the layout
    
        self.fluPlot = fluPlot(self.pcolors, self)      # create plot
        self.layout.addWidget(self.fluPlot.graphWidget) # add plot to the layout
        
        self.setLayout(self.layout)          # put the whole layout in the box  
        
    #-----------------------------------------

    def resetAllChannels(self, exclude:int) -> None:
        '''Set all of the channels to 0 except for exclude (0-indexed). exclude is a channel that we want to keep on. Input -1 to turn everything off'''
        for i in range(self.numChans):
            if not i==exclude:
                fgt.fgt_set_pressure(i,0)
                
    
    def updateReading(self, channum:int, preading:int) -> None:
        '''updates the status box that tells us what pressure this channel is at'''
        self.pchannels[channum].readLabel.setText(preading)
        
        
    #-----------------------------------------
    
    def getFileName(self) -> str:
        try:
            folder, filename = self.sbWin.newfile()
        except NameError:
            return
        
        filename = filename + ('_' if len(filename)>0 else '')+'Fluigent'
        filename = filename + '_'+time.strftime('%y%m%d_%H%M%S')+'.csv'
        fullfn = os.path.join(folder, filename)
        self.fileName = fullfn
    
    def startRecording(self) -> None:
        '''Start keeping track of pressure readings in a table to be saved to file'''
        if self.settingsBox.savePressureChecked.isChecked():
        
            self.saveTable = []
            self.save = True
            self.getFileName() # determine the current file name
        
    def stopRecording(self) -> None:
        '''Save the recorded pressure readings in a csv'''
        
        if self.settingsBox.savePressureChecked.isChecked():
        
            self.save = False

            with open(self.fileName, mode='w') as c:
                writer = csv.writer(c, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

                writer.writerow(['time (s)']+[f'Channel {i} pressure (mbar)' for i in range(self.numChans)]) # header

                for row in self.saveTable:
                    writer.writerow(row)
        
        
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
            