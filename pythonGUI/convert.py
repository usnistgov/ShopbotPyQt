#!/usr/bin/env python
'''Shopbot GUI functions for setting up the convert window'''

# local packages
from general import *
import sbList

import sys
import re
import os
import subprocess
import winreg

import numpy
import logging
import copy

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QDialog, QVBoxLayout, QWidget, QApplication, QAction, QLabel, QCheckBox, QGridLayout, QFileDialog, QPushButton, QLineEdit

   ######################## Conversion program

   # Note: GCODE commands that are ignored: M104, M105, M107, M109, M140, 190

class convert:

    def __init__(self, fileName, convertShare) :
        self.fileName = fileName
        self.shared = convertShare
        
        # Make everything default/0/null/false
        self.X_Coord = self.Y_Coord = self.Z_Coord = "0"
        self.ERate = self.moveRate = "0"

        self.minX = self.maxX = self.minY = self.maxY = self.minZ = self.maxZ = "0"
        self.checkMinX = self.checkMinY = self.checkMinZ = self.checkMaxX = self.checkMaxY = self.checkMaxZ = False
    
    
    def readInFile(self) :
        isFlowing = False
        isWritten = False
        
        # If the file isn't GCODE, display error and break out of method
        if (".gcode" or ".stl") not in self.fileName:
                print("File must be GCODE or STL") 
        
        #copy file so not to override original
        file = copy.copy(self.fileName)
        
        # change filepath if user requested different save path
        if self.shared.samePath is False :
            file = file.replace(os.path.dirname(file), self.shared.pathway)
        
        # replace extension
        file = file.replace(".gcode", ".sbp")
    
        
        with open(self.fileName, 'r') as GCodeFile :
            with open(file, 'w+') as SBPFile :
                # add in header for every file
                SBPFile.write("SO, 12, 1\n")
                SBPFile.write("SO, 2, 1\n")
                while True :
                    line = GCodeFile.readline()
                    if not line:
                        SBPFile.write("SO, 12, 0\n")
                        SBPFile.write("SO, 2, 0\n")
                        break
                    
   ##################################################### Setting Variables
                   
                    if line.__contains__(";") :
                        semiSpot = line.find(";")  #if comment in middle of code, get rid of comment
                        if semiSpot != 0 :
                            line = line.partition(";")[0]
                            
                            #getting coordinates
                        if line.__contains__("MIN") or line.__contains__("MAX") :
                            self.getCoord(line)
                            
                            # flaggin for once all coordinates are read
                    if ((self.checkMinX and self.checkMinY and self.checkMinZ and self.checkMaxX and self.checkMaxY and self.checkMaxZ) and not isWritten) :
                            SBPFile.write("VL, " + self.minX + ", " + self.maxX + ", " + self.minY + ", " + self.maxY + ", " + self.minZ + ", " + self.maxZ + ", , , , , \n")
                            isWritten = True
                                                                                
   ################################################## E command switch to S0, 1, 1/0                          
                    isE = False
                    if line.__contains__("E") and not line.__contains__(";") :
                        self.getCoord(line)
                
                        ECommand = line.partition("E")[2]
                        if ECommand[0].isdigit() is True :
                            isE = True
                    
                        if isE is True and isFlowing is False :
                            SBPFile.write("S0, 1, 1\n")
                            isFlowing = True
                        if isE is False and isFlowing is True :
                            SBPFile.write("S0, 1, 0\n")
                            isFlowing = False
                          
   ################################################### G0/G1 command switch to J3/M3 & setting move rate
    
                    if line.__contains__("G0") and not line.__contains__(";") :
                        self.getCoord(line)
                        if line.__contains__("F") :
                                FCommand = line.partition("F")[2]
                                if FCommand[0].isdigit() is True :
                                    SBPFile.write("MS, " + self.moveRate + ", " + self.moveRate + "\n")
                        SBPFile.write("J3, " + self.X_Coord + ", " + self.Y_Coord + ", " + self.Z_Coord + "\n")

                    if line.__contains__("G1") and not line.__contains__(";") :
                        self.getCoord(line)
                        if line.__contains__("F") :
                                FCommand = line.partition("F")[2]
                                if FCommand[0].isdigit() is True :
                                    SBPFile.write("MS, " + self.moveRate + ", " + self.moveRate + "\n")
                        SBPFile.write("M3, " + self.X_Coord + ", " + self.Y_Coord + ", " + self.Z_Coord + "\n")
                        
                    if line.__contains__("M82") :
                        SBPFile.write("SA\n")

                    if line.__contains__("G28") :
                        SBPFile.write("MH\n")
                        
        self.shared.finished = True
        
        return file
   ######################################################################                    
    def getCoord(self, line) :  # Retrieving values after key characters
        
        if line.__contains__("X") :
            if line.__contains__("G0") or line.__contains__("G1") :
                XCommand = line.partition("X")[2]
                specChar = XCommand.find(" ")
                self.X_Coord = (XCommand[0 : specChar])
                
            XCommand = line.partition(":")[2]
            specChar = XCommand.find(" ")
            if line.__contains__("MAX") :
                self.maxX = (XCommand[0 : specChar])
                self.checkMaxX = True
            if line.__contains__("MIN") :
                self.minX = (XCommand[0 : specChar])
                self.checkMinX = True
                    
        if line.__contains__("Y") :
            if line.__contains__("G0") or line.__contains__("G1") :
                YCommand = line.partition("Y")[2]
                specChar = YCommand.find(" ")
                self.Y_Coord = (YCommand[0 : specChar])
                
            YCommand = line.partition(":")[2]
            specChar = YCommand.find(" ")
            if line.__contains__("MAX") :
                self.maxY = (YCommand[0 : specChar])
                self.checkMaxY = True
            if line.__contains__("MIN") :
                self.minY = (YCommand[0 : specChar])
                self.checkMinY = True
            
        if line.__contains__("Z") :
            if line.__contains__("G0") or line.__contains__("G1") :
                ZCommand = line.partition("Z")[2]
                specChar = ZCommand.find(" ")
                self.Z_Coord = (ZCommand[0 : specChar])
 
            ZCommand = line.partition(":")[2]
            specChar = ZCommand.find(" ")
            if line.__contains__("MAX") :
                self.maxZ = (ZCommand[0 : specChar])
                self.checkMaxZ = True
            if line.__contains__("MIN") :
                self.minZ = (ZCommand[0 : specChar])
                self.checkMinZ = True
            
        if line.__contains__("E") :
            ECommand = line.partition("E")[2]
            specChar = ECommand.find(" ")
            speed = ECommand[0 : specChar]
            if speed[0].isdigit() is True :
                self.ERate = speed
      
        if line.__contains__("F") :
            FCommand = line.partition("F")[2]
            specChar = FCommand.find(" ")
            speed = FCommand[0 : specChar]
            if speed[0].isdigit() is True :
                speedInt = int(float(speed))
                self.getRate(speedInt)
               

    def getRate(self, speed) :  # Conversion of gcode (mm/min) to sbp (mm/sec)
        convertedSpeed = speed / 60
        self.moveRate = str(round(convertedSpeed, 2))
                                            
   ###############################################  Conversion Window
    
class convertDialog(QDialog) :
    
    def __init__(self, sbWin) :
        
        #conversion window setup
        super().__init__(sbWin)
        self.sbWin = sbWin
        
        self.shared = sharedConvert()
        self.addQueue = False
        self.haveSavePath = False
        
        self.newFile = ""
        self.filePath = ""
        self.fileName = ""
        self.custFolder = ""
        self.setWindowTitle("File Conversion")
        
        self.convertLayout = QGridLayout()
        
        self.loadLabel()
        self.loadBox()
        self.loadButt()
        self.loadFileEdit()
        
        self.setLayout(self.convertLayout)
        self.resize(900, 500)
        
        self.updateFile()
        self.updateButt()
        
        if self.shared.finished is True :
            self.close()
        
    def loadFileEdit(self) :
        self.nameChangeLabel = QLabel('Saving file under name of: ')
        self.fileEdit = QLineEdit()
        
        self.convertLayout.addWidget(self.nameChangeLabel, 2, 0)
        self.convertLayout.addWidget(self.fileEdit, 2, 1)
        
    def loadLabel(self) :
        self.GFileLabel = QLabel('File: ')
        self.pathLabel = QLabel('Pathway to Save: ')
        
        self.convertLayout.addWidget(self.GFileLabel, 0,0)
        self.convertLayout.addWidget(self.pathLabel, 3, 0)
        
    def loadBox(self) :
        self.pathBox = QCheckBox('Save to file folder')
        self.pathBox.stateChanged.connect(self.updatePathway)
        
        self.queueBox = QCheckBox('load to queue after conversion')
        self.queueBox.stateChanged.connect(self.updateQueue)
        
        self.convertLayout.addWidget(self.queueBox, 0, 1)
        self.convertLayout.addWidget(self.pathBox, 3, 1)
        
    def loadButt(self) :
        self.locButt = QPushButton('Choose Save Location')
        self.locButt.clicked.connect(self.loadDir)
        
        self.loadButt = QPushButton('Load File')
        self.loadButt.clicked.connect(self.loadFile)
        
        self.convertButt = QPushButton('Convert File')
        self.convertButt.clicked.connect(self.conversion)
        
        self.convertLayout.addWidget(self.loadButt, 1, 0)
        self.convertLayout.addWidget(self.locButt, 4, 0)
        self.convertLayout.addWidget(self.convertButt, 5, 0)
        
        #load in chosen file for conversion with gcode/stl extensions only
    def loadFile(self) -> None :
        openFolder = r'C:\\'
        tempPath = QFileDialog.getOpenFileName(self, "Open File", openFolder, 'Gcode file (*.gcode *.stl)')
        tempFile = os.path.basename(tempPath[0])
        
        if tempFile :
            self.filePath = tempPath
            self.fileName = tempFile
            self.updateFile()
        
        #load up directory to save
    def loadDir(self) -> None :
        if self.shared.samePath is False:
            openFolder = r'C:\\'
            self.custFolder = QFileDialog.getExistingDirectory(self, "Choose Directory", openFolder)
            self.shared.pathway = self.custFolder
            self.pathLabel.setText('Pathway to save : ' + self.shared.pathway)
    
    def updateFile(self) -> None :
        self.GFileLabel.setText('File:  ' + self.fileName)
        self.fileEdit.setText(self.fileName.replace('.gcode', ''))
        
        #update pathway for same folder or chosen by user
    def updatePathway(self) -> None :
        if self.filePath[0]: 
            self.shared.samePath = self.pathBox.isChecked()
            self.haveSavePath = True
            self.updateButt()
        
            if self.shared.samePath is True :
                self.locButt.setEnabled(False)
                self.shared.pathway = os.path.dirname(self.filePath[0])
                self.pathLabel.setText('Pathway to save : ' + self.shared.pathway)

            else :
                self.locButt.setEnabled(True)
                if not self.custFolder :
                    self.pathLabel.setText('Pathway to save : ' + self.shared.pathway)
                else :
                    self.pathLabel.setText('Pathway to save : ' + self.custFolder)     
        
    def updateButt(self) -> None :
        if self.haveSavePath is False :
            self.convertButt.setEnabled(False)
            
        else :
            self.convertButt.setEnabled(True)
    
    def updateQueue(self) -> None :
        self.addQueue = self.queueBox.isChecked()
        
    def conversion(self) -> None :
        self.newName = self.fileEdit.text()
        
        # if gcode, go to python script above
        if '.gcode' in self.fileName :
            fileObject = convert(self.filePath[0], self.shared)
            self.newFile = fileObject.readInFile()
            
        elif '.stl' in self.fileName :
            #otherwise, open the slicer for use
            fileObject = slicerBox(self.filePath[0], self.shared)
            temp = fileObject.findSlicer()
        
        #if user requested file to be added to queue
        if self.addQueue is True :
            self.sbWin.sbBox.enableRunButt()
            self.sbWin.sbBox.sbList.addFile(self.newFile)
            logging.debug(f'Added file to queue: {self.newFile}')
            self.sbWin.sbBox.updateStatus('Ready ... ', False)
        
        self.close()
        
    def close(self) :
        self.done(0)

   #################################################### Shared class for convert & convertDialog
class sharedConvert :
    
    #to get shared variables between all classes working
    def __init__(self) :
        self.samePath = False
        self.pathway = ""
        self.finished = False
        self.newName = ""
        
   ################################################### Class for opening Slicer  
class slicerBox :
    
    def __init__(self, file, convertShare) :
        self.shared = convertShare
        stlFile = file
        
        self.foundFolder = False
        
        self.slicerPath = ""
        self.slicerFile = "Ultimaker-Cura.exe"
        self.slicerFolder = "Ultimaker Cura"
        self.startDir = "\Program Files"
        
    #find where the slicer is located within the computer
    def findSlicer(self) :
        dir_list = os.listdir(self.startDir)
        
        for folder in dir_list :
            if folder.__contains__(self.slicerFolder) :
                self.foundFolder = True
                self.slicerFolder = folder
                self.slicerPath = os.path.join(self.startDir, self.slicerFolder, self.slicerFile)
                
        if self.foundFolder is True :
            self.openSlicer()
        
    
    def openSlicer(self) :
            subprocess.Popen([self.slicerPath])