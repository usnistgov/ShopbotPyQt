#!/usr/bin/env python
'''Shopbot GUI functions for the pressure calibration tool'''

# external packages
from PyQt5 import QtGui
import PyQt5.QtWidgets as qtw
import pyqtgraph as pg
import os, sys
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import csv
import numpy as np
import traceback

# local packages
from sbgui_general import *
from config import *


################################################


def polyfit(x:List[float], y:List[float], degree:int) -> Dict:
    '''fit polynomial'''
    results = {}
    coeffs = np.polyfit(x, y, degree)
    p = np.poly1d(coeffs)
    #calculate r-squared
    yhat = p(x)
    ybar = np.sum(y)/len(y)
    ssreg = np.sum((yhat-ybar)**2)
    sstot = np.sum((y - ybar)**2)
    results['r2'] = ssreg / sstot
    results['coeffs'] = list(coeffs)

    return results

def findFit(x:List[float], y:List[float]) -> Dict:
    if len(x)>2:
        quad = polyfit(x,y,2)
    else:
        quad = {'r2':0, 'coeffs':[0,0,0]}
    lin = polyfit(x,y,1)
    if quad['coeffs'][0]>10**-8 and quad['r2']>lin['r2']:
        coeffs = dict([[['a','b','c'][i], coeff] for i,coeff in enumerate(quad['coeffs'])])
    else:
        coeffs = {'a':0, 'b':lin['coeffs'][0], 'c':lin['coeffs'][1]}
    return coeffs


#---------------------------------

class okDialog(qtw.QDialog):
    '''ok/cancel to clear calibration'''
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.setWindowTitle('Clear calibration')

        QBtn = qtw.QDialogButtonBox.Ok | qtw.QDialogButtonBox.Cancel

        self.buttonBox = qtw.QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = qtw.QVBoxLayout()
        message = qtw.QLabel("Calibration not saved. Are you sure you want to clear?")
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

#---------------------------------

class calibPlot:
    '''Pressure calibration plot'''
    
    def __init__(self, parent):
        '''this is called by the parent, which is the pCalibration dialog'''
        self.parent = parent
        self.graph = pg.PlotWidget()
        self.graph.setBackground('w')
        self.graph.setLabel('left', 'Flow speed (mm/s)')
        self.graph.setLabel('bottom', 'Pressure (mBar)')
        self.horizPen =  pg.mkPen(color='#888888', width=2)
        self.prange = [0,10]
        self.horizLine = self.graph.plot(self.prange, [self.parent.targetSpeed(), self.parent.targetSpeed()], pen=self.horizPen)
        self.dataline = pg.ScatterPlotItem([], [], brush='b', symbol='o', name=self.parent.sample())
        self.graph.addItem(self.dataline)
        self.fitPoint = pg.ScatterPlotItem([], [], brush='r',  symbol='s')
        self.graph.addItem(self.fitPoint)
        self.fitPen =  pg.mkPen(color='#000000', width=2)
        self.fitline = self.graph.plot([], [], pen=self.fitPen)
        self.graph.setFixedSize(400, 300)
        self.display()
        self.a = 0
        self.b = 0
        self.c = 0
        self.updateEq()
        
    def display(self) -> None:
        '''establish the layout for the plot'''
        self.layout = qtw.QVBoxLayout()
        self.eqLabel = fLabel(self.layout, title='')
        self.layout.addWidget(self.graph)
        
    def updateTargetSpeed(self) -> None:
        '''update the target speed line on the plot'''
        p,_ = self.getPS()
        if len(p)>1:
            self.prange = [min(p), max(p)]
            self.horizLine.setData(self.prange, [self.parent.targetSpeed(), self.parent.targetSpeed()], pen=self.horizPen)
            self.calcPressure()
        
    def updateEq(self) -> None:
        '''update the displayed equation'''
        self.eqLabel.setText('v = {a:.6f}p^2 + {b:.6f}p + {c:.6f}'.format(a=self.a,b=self.b,c=self.c))
        
    def getPS(self) -> Tuple:
        '''Get the pressure and speed, with only valid data, as floats'''
        p = self.parent.data['pressure']
        s = self.parent.data['speed']
        ps = (np.array([p,s])).transpose()
        ps3 = []
        for row in ps:
            try:
                row1 = [float(row[0]), float(row[1])]
            except:
                pass
            else:
                ps3.append(row1)
        if len(ps3)==0:
            return [], []
        ps3 = np.array(ps3)
        ps3 = (ps3[ps3[:, 0].argsort()]).transpose()
        return list(ps3[0]), list(ps3[1])
    
    def calcPressure(self) -> None:
        a = self.a
        b = self.b
        c = self.c
        s = self.parent.targetSpeed()
        if abs(a)>0:
            d = b**2-4*a*(c-s)
            if d>0:
                p = (-b+np.sqrt(d))/(2*a)
            else:
                logging.warning('Speed cannot be reached')
                p = 0
        elif abs(b)>0:
            p = (s-c)/b
        else:
            p = c
        self.parent.updatePressure(p)
        self.fitPoint.setData([p], [self.parent.targetSpeed()]) # put a point on the plot
            
        
    def update(self) -> None:
        '''Update the plot with data from the current table'''
        # plot x,y
        p,s = self.getPS()
        self.dataline.setData(p, s)
        
        if len(p)>1:
            # fit x,y
            coeffs = findFit(p,s)
            self.a = coeffs['a']
            self.b = coeffs['b']
            self.c = coeffs['c']

            # plot fit
            plist = [min(p)+i for i in range(int(max(p)-min(p))+1)]
            slist = [self.a*p**2+self.b*p+self.c for p in plist]
            self.fitline.setData(plist,slist, pen=self.fitPen)
        else:
            self.a=0
            self.b=0
            self.c=0
        # update fit and pressure
        self.updateEq()
        self.calcPressure()
        self.updateTargetSpeed()


#-------------------------------------------------------------

class calibTable(qtw.QTableWidget):
    def __init__(self, parent, *args):
        w = parent.numCols()
        h = parent.numRows()
        qtw.QTableWidget.__init__(self, h,w, *args)
        self.parent = parent
        self.updateData() 
        self.itemChanged.connect(self.parent.updateTable)
        self.setFixedHeight(400)
 
    def setData(self): 
        '''copy the data dict to the displayed table'''
        horHeadersDict=self.parent.headerDict
        horHeaders = []
        for n, key in enumerate(self.parent.data.keys()):
            horHeaders.append(horHeadersDict[key])
            for m, item in enumerate(self.parent.data[key]):
                newitem = qtw.QTableWidgetItem(str(item))
                self.setItem(m, n, newitem)
        self.setHorizontalHeaderLabels(horHeaders)
        
    def updateData(self) -> None:
        '''update the data display'''
        self.setData()
        self.resizeColumnsToContents()
        self.resizeRowsToContents()  
        
    def itemF(self, m:int, n:int) -> Union[float, str]:
        '''get the item value as a float, if possible'''
        it = self.item(m,n).text()
        try:
            it1 = float(it)
        except:
            return it
        else:
            return it1

    def readData(self) -> None:
        '''copy the displayed table to the data dict'''
        newdict = []
        for n,key in enumerate(list(self.parent.data.keys())):
            numcols = len(self.parent.data[key])
            newdict.append([key, [self.itemF(m,n) for m in range(numcols)]])
        newdict = dict(newdict)
        self.parent.data = newdict
                

#------------------------------------------------------------
        

class pCalibrationTab(qtw.QWidget):
    '''creates a window with pressure calibration tools'''
    
    def __init__(self, sbWin, channel:int):
        '''This is called by the parent, which is the popup called by SBwindow'''
        
        super().__init__(sbWin)
        self.bTitle=f'Channel {channel+1}'
        self.sbWin = sbWin
        self.flowRateFolder = checkPath(cfg.calibration.flowRateFolder)
        self.saved=True
        self.initTable()
        self.plot = calibPlot(self)
        self.grid = calibTable(self)
        self.channel = channel
        self.successLayout()
        
    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        cfg1.calibration.initSpeed = self.speedBox.text()
        cfg1.calibration.initDiam = self.diamBox.text()
        cfg1.calibration.flowRateFolder = self.flowRateFolder
        return cfg1
    
    def loadConfig(self, cfg1):
        '''load settings from a config Box object'''
        self.speedBox.setText(cfg1.calibration.initSpeed)
        self.diamBox.setText(cfg1.calibration.initDiam)
        self.flowRateFolder = cfg1.calibration.flowRateFolder
        
    def successLayout(self) -> None:
        '''Create the layout'''
        
        self.layout = qtw.QVBoxLayout()
        self.status = createStatus(700) 
        self.layout.addWidget(self.status)
        topRow = qtw.QHBoxLayout()
        leftcol = qtw.QVBoxLayout()
        
        fButton(leftcol, title='Save', tooltip='Save current configuration to csv file', func=self.saveTable)
        fButton(leftcol, title='Clear', tooltip='Clear the display', func=self.clear)
        fButton(leftcol, title='Load calibration', tooltip='Clear display and load previous calibration', func=self.loadCalibration)
        self.densityDropdown()
        leftcol.addWidget(self.densityDropdown)
        form = qtw.QFormLayout()
        self.sampleBox = fLineEdit(form, title='Sample', text='', tooltip='Name of the fluid you are calibrating', func=self.updateDensityDropdown)
        self.densityBox = fLineEdit(form, title='Density (g/mL)', text=str(cfg.calibration.initDensity), tooltip='Fluid density in g/mL', func=self.updateConsts)
        self.diamBox = fLineEdit(form, title='Nozzle diameter (mm)', text=str(cfg.calibration.initDiam), tooltip='Nozzle inner diameter (mm)', func=self.updateConsts)
        self.speedBox = fLineEdit(form, title='Target speed (mm/s)', text=str(cfg.calibration.initSpeed), tooltip='Flow speed you are trying to achieve in mm/s', func=self.updateTargetSpeed)
        self.pressureLabel = qtw.QLabel('0')
        form.addRow('Pressure (mBar)', self.pressureLabel)
        leftcol.addLayout(form)
        fButton(leftcol, title='Use this pressure', tooltip='Copy this pressure to the channel 1 Pressure During Print box in the main window', func=self.copyPressure)
        topRow.addLayout(leftcol)
        topRow.addLayout(self.plot.layout)
        self.layout.addLayout(topRow)
        self.layout.addWidget(self.grid)       
        self.setLayout(self.layout)
        
        
    #-------------------------------------

    
    def initTable(self, size:int=20) -> None:
        self.columns = ['initwt', 'finalwt', 'pressure', 'time', 'speed']
        self.headerDict = {'initwt':'init wt (g)', 'finalwt':'final wt (g)', 'pressure':'pressure (mBar)', 'time':'time (s)', 'speed':'speed (mm/s)'}
        blank = ['' for i in range(size)]
        self.data = dict([[s, blank.copy()] for s in self.columns])
        
    def numCols(self) -> int:
        '''number of cols in the table'''
        return len(self.data)
    
    def numRows(self) -> int:
        '''number of rows in the table'''
        return len(self.data[list(self.data.keys())[0]])

        
    #------------
    
    def sample(self) -> str:
        try:
            s = self.sampleBox.text()
        except:
            s = ''
        return s
    
    def density(self) -> float:
        try:
            d = float(self.densityBox.text())
        except:
            d = cfg.calibration.initDensity
        return d
    
    def pressure(self) -> int:
        try:
            p = int(self.pressureLabel.text())
        except:
            logging.warning('Error reading pressure')
            p = 0
        return p
    
    def targetSpeed(self) -> float:
        '''get the target speed from the gui'''
        try:
            f = float(self.speedBox.text())
        except:
            f = float(cfg.calibration.initSpeed)
        return f
    
    #--------------------------
    
    def updateTargetSpeed(self) -> None:
        '''update save status and plot'''
        self.notSaved()
        self.plot.updateTargetSpeed()
        
    def updateConsts(self) -> None:
        '''update grid'''
        self.notSaved()
        self.updateTable([])
        
    #--------------------------
    
    def updateSpeed(self, s) -> None:
        '''update the speed label'''
        self.speedBox.setText(str(s))
        
    def updateDiam(self, d) -> None:
        '''update the diameter label'''
        self.diamBox.setText(str(d))
        
    def updatePressure(self, p) -> None:
        '''update the pressure label'''
        self.pressureLabel.setText(str(int(p)))
    
    def updateDensity(self, d) -> None:
        '''Update the density label'''
        self.densityBox.setText(str(d))
        
    def updateSample(self, sample:str) -> None:
        '''update the sample label'''
        self.sampleBox.setText(str(sample))
       
    def updateGrid(self) -> None:
        self.grid.blockSignals(True)
        self.grid.updateData() # update display
        self.grid.blockSignals(False)
        
    #------------------------

    def addRowToCalib(self, runPressure:float, runTime:float) -> None:
        '''add pressure and time to the calibration table'''
        i = 0
        while not (self.data['time'][i]=='' and self.data['pressure'][i]==''):
            i+=1
        self.data['time'][i]=runTime
        self.data['pressure'][i]=runPressure
        self.updateGrid()
        
    def constants(self, short:bool) -> None:
        '''Get sample constants. if short, only get constants needed for calculating speed. otherwise, report everything'''
        try:
            diam = float(self.diamBox.text()) # in mm
            area = np.pi*(diam/2)**2 # in mm^2
            density = self.density() # in g/cm^3
            densitymm = density/1000 # in g/mm^3
            shortret = {'diam':[diam, 'mm'], 'area':[area, 'mm^2'], 'density':[density, 'g/cm^3'], 'densitymm':[densitymm, 'g/mm^3']}
            if not short:
                sample = self.sample()
                speed = self.targetSpeed()
                pressure = self.pressure()
                moreret = {'sample':[sample, ''], 'target speed':[speed, 'mm/s'], 'target pressure':[pressure, 'mBar']}
                ret = {**shortret, **moreret}
            else:
                ret = shortret
            return ret
        except Exception as e:
            logging.warning('Failed to collect constants')
            raise e
            
    #------------
    
    def getSpeed(self, i:int, densitymm:float, area:float) -> None:
        '''calculate the speed for row i '''
        try:
            initwt = float(self.data['initwt'][i]) # g
            finalwt = float(self.data['finalwt'][i]) # g
            time = float(self.data['time'][i]) # s
        except:
            return
        else:
            if time==0:
                return

        wt = finalwt-initwt # g
        vol = wt/densitymm # mm^3
        flux = vol/time # mm^3/s
        speed = flux/area # mm/s
        self.updateVal('speed', i, speed)
    
        
    def updateTable(self, item) -> None:
        '''Calculate speeds and update display table'''
        try:
            consts = self.constants(True)
        except Exception as e:
            logging.warning('Failed to update table')
            return
        area = consts['area'][0]
        densitymm = consts['densitymm'][0]
        if area==0:
            logging.warning('Area cannot be 0')
            return
        if densitymm==0:
            logging.warning('Density cannot be 0')
            return
        
        self.grid.readData()
        if type(item) is list:
            ilist = range(self.numRows())
        else:
            ilist = [item.row()]
        for i in ilist:
            self.getSpeed(i, densitymm, area)
        self.updateGrid()
        self.plot.update()
        self.notSaved()
        
    #------------

    def notSaved(self) -> None:
        '''set the current calibration to unsaved'''
        self.saved=False
        
    #------------
        
    def saveTable(self) -> None:
        '''save current calibration to csv file'''
        if self.saved:
            # don't export duplicate files
            return
        consts = self.constants(False)
        self.saveDensity()
        if not os.path.exists(self.flowRateFolder):
            folder = fileDialog(self.flowRateFolder, '', True)
            if len(folder)==0:
                return
            folder = folder[0]
            self.flowRateFolder = folder
        
        time = self.sbWin.fileBox.settingsBox.time()
        fileName = os.path.join(self.flowRateFolder, consts['sample'][0]+'_'+time+'.csv')
        with open(fileName, mode='w', newline='', encoding='utf-8') as c:
            writer = csv.writer(c, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            
            # metadata
            for key,val in consts.items():
                writer.writerow([key, val[1], val[0]])
            writer.writerow(['a', 'mm/s/mbar^2', self.plot.a])
            writer.writerow(['b', 'mm/s/mbar', self.plot.b])
            writer.writerow(['c', 'mm/s', self.plot.c])
                
            writer.writerow([''])
            
            # data table
            writer.writerow([self.headerDict[s] for s in self.data]) # header
            for i in range(self.numRows()):
                row = [self.data[k][i] for k in self.data]
                writer.writerow(row)
        
        self.updateStatus(f'Saved calibration to {fileName}', True)
        self.saved=True
        
    #------------
    
    def clear(self) -> None:
        '''clear current calibration'''
        
        # if not saved, open an alert dialog
        if not self.saved:
            dlg = okDialog() 
            if not dlg.exec_():
                return
        
        # clear calibration
        self.initTable()
        self.updateGrid()
        self.plot.update()
        self.saved=True
      
    #------------
    
    def loadFile(self) -> str:
        file = fileDialog(self.flowRateFolder, '(*.csv)', False)
        if len(file)==0:
            return ''
        file = file[0]
        return file
    
    def updateVal(self, header, row, val) -> None:
        '''update value in the table'''
        self.data[header][row] = val
        
    def loadCalibration(self) -> None:
        '''Load a previous calibration to the whole window'''
        # if not saved, open an alert dialog
        if not self.saved:
            dlg = okDialog() 
            if not dlg.exec_():
                return
        
        # load file
        file = self.loadFile()
        
        self.updateVal('initwt', 0, 100)

        # read the file
        with open(file) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            dictrev = {v: k for k, v in self.headerDict.items()}
            columndict = []
            for row in csv_reader:
                if len(row)==0:
                    pass
                elif row[0]=='':
                    pass
                elif len(row)>3:
                    # we're in the table
                    try:
                        f = float(row[0])
                    except:
                        # this is a header
                        tablerow = 0
                        for j, item in enumerate(row):
                            shortname = dictrev[item]
                            columndict.append([j, shortname])
                        columndict = dict(columndict) # {1:'initwt', 2:'finalwt'...}
                    else:
                        # this is a table row
                        for j, item in enumerate(row):
                            self.updateVal(columndict[j], tablerow, item)
                        tablerow+=1
                else:
                    # we're in metadata
                    name = row[0]
                    if name=='diam':
                        self.updateDiam(row[2])
                    elif name=='density':
                        self.updateDensity(row[2])
                    elif name=='sample':
                        self.updateSample(row[2])
                    elif name=='target speed':
                        self.updateSpeed(row[2])
                    elif name=='target pressure':
                        self.updatePressure(float(row[2]))
                    elif name=='a':
                        self.plot.a=float(row[2])
                    elif name=='b':
                        self.plot.b=float(row[2])
                    elif name=='c':
                        self.plot.c=float(row[2])

        # update table
        self.updateGrid()
        
        # update plot
        self.plot.update()
        
        self.saved=True
        self.updateStatus(f'Loaded {file}', True)

    #------------

            
    def densityDropdown(self) -> qtw.QComboBox:
        self.densityDropdown = qtw.QComboBox()
        densityDict = loadConfigFile(self.densityFile())
        self.densityDropdown.addItem('Load density', ['',0])
        for sample, density in densityDict.items():
            title = str(sample)+': '+str(density)+' g/mL'
            self.densityDropdown.addItem(title, [sample, density])
        self.densityDropdown.currentIndexChanged.connect(self.loadDensity)
            
    def updateDensityDropdown(self) -> None:
        self.densityDropdown.blockSignals(True)  # don't let the dropdown send signals while updating list
        sample = self.sample()
        removed = []
        kept = []
        for i in range(self.densityDropdown.count()):
            # only keep entries that have sample names that match the sample name
            isample = self.densityDropdown.itemData(i)[0]
            if not sample.lower() in isample.lower() and not isample=='':
                removed.append(i)
            else:
                kept.append(isample)
        removed.reverse() # go from back to front
        for i in removed:
            self.densityDropdown.removeItem(i) # remove items
        # add other items    
        densityDict = loadConfigFile(self.densityFile())
        for isample, density in densityDict.items():
            if not isample in kept and sample.lower() in isample.lower():
                title = str(isample)+': '+str(density)+' g/mL'
                self.densityDropdown.addItem(title, [isample, density])
        self.notSaved()
        self.densityDropdown.blockSignals(False)
        
    def densityFile(self) -> None:
        '''get the list of saved densities from the config file'''
        configdir = getConfigDir()
        file = os.path.join(configdir, 'densities.yml')
        if not os.path.exists(file):
            dumpConfigs({'empty':''}, file)
        return file
    
        
    def saveDensity(self) -> None:
        '''save the current density to the density file'''
        densityFile = self.densityFile()
        densities = loadConfigFile(densityFile)
        sample = self.sample()
        if len(sample)==0:
            # don't save an empty sample
            return
        density = self.density()
        newrow ={sample:density}
        if not sample in densities:
            densities = {**densities, **newrow}
        dumpConfigs(densities, densityFile)
        logging.info(f'Saved density to {densityFile}')
        
        
    def loadDensity(self) -> None:
        '''Load a previously saved density from a table'''
        item = self.densityDropdown.currentData()
        sample = item[0]
        density = item[1]
        if density>0:
            self.updateSample(sample)
            self.updateDensity(density)
        
     #------------
        
    def copyPressure(self) -> None:
        self.sbWin.fluBox.updateRunPressure(self.pressure(), self.channel)
        
    #-------------
    
    def updateStatus(self, st, log) -> None:
        '''update the displayed device status'''
        try:
            self.status.setText(st)
        except:
            logging.info(f'{self.bTitle}:{st}')
        else:
            if log:
                logging.info(f'{self.bTitle}:{st}')
    
    def close(self):
        '''Close the window'''
        self.done(0)
        
        
        
        
class pCalibration(QDialog):
    '''Creates a calibration window with tabs for each pressure channel'''
    
    def __init__(self, parent):
        '''This is called by the parent, which is the main SBwindow'''
        
        super().__init__(parent)
        self.sbWin = parent
        self.setWindowTitle('Pressure calibration tool')
        self.layout = qtw.QVBoxLayout()
        
        self.tabs = qtw.QTabWidget()       
        self.tabs.setTabBar(qtw.QTabBar(self))
        self.tabs.setTabPosition(qtw.QTabWidget.North)
        
        channels = self.sbWin.fluBox.numChans
        self.calibWidgets = [pCalibrationTab(self.sbWin, i) for i in range(channels)]
        for w in self.calibWidgets:
            self.tabs.addTab(w, w.bTitle)    
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)

        
    def close(self):
        '''Close the window'''
        self.done(0)
        
        
    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        for tab in self.calibWidgets:
            cfg1 = tab.saveConfig(cfg1)
        return cfg1
    
    def loadConfig(self, cfg1):
        '''load settings from a config Box object'''
        for tab in self.calibWidgets:
            tab.loadConfig(cfg1)
        
    def addRowToCalib(self, runPressure:float, runTime:float, chanNum:int) -> None:
        '''add the row to the calibration table'''
        self.calibWidgets[chanNum].addRowToCalib(runPressure, runTime)
        
        
        
        