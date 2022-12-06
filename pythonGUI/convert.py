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

    def __init__(self, fileName, convertShare, reName) :
        self.reName = reName
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
        headerFlag = False
        file = ""
        
        # If the file isn't GCODE, display error and break out of method
        if (".gcode" or ".stl") not in self.fileName:
                print("File must be GCODE or STL") 
        
        dirPath = os.path.dirname(self.fileName)
        
        #copy file so not to override original
        # file = copy.copy(self.fileName)
        
        # change filepath if user requested different save path
        if self.shared.samePath is False :
            # file = file.replace(os.path.dirname(file), self.shared.pathway)
            dirPath = dirPath.replace(os.path.dirname(self.fileName), self.shared.pathway)
        
        file = dirPath + "/" + self.reName + ".sbp"
        
        # replace extension
        # file = file.replace(".gcode", ".sbp")
        
        with open(self.fileName, 'r') as GCodeFile :
            with open(file, 'w+') as SBPFile :
                
                SBPFile.write("VD , , 1\n")
                SBPFile.write("VU, 157.480315, 157.480315, -157.480315\n")
                
                while True :
                    line = GCodeFile.readline()
                    if not line:
                        SBPFile.write("SO, " + self.shared.getRunFlag() + ", 0\n")
                        break
                    
   ##################################################### Setting Variables
                   
                    if line.__contains__(";") :
                        semiSpot = line.find(";")  #if comment in middle of code, get rid of comment
                        if semiSpot != 0 :
                            line = line.partition(";")[0]
                            
                            #getting coordinates
                        if line.__contains__("MIN") or line.__contains__("MAX") :
                            self.getCoord(line)
                            
                            # flagging for once all coordinates are read
                            #Values for limits for Table
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
                            SBPFile.write("SO, " + self.shared.getFluFlag() + ", 1\n")
                            isFlowing = True
                        if isE is False and isFlowing is True :
                            SBPFile.write("SO, " + self.shared.getFluFlag() + ", 0\n")
                            isFlowing = False
                          
   ################################################### G0/G1 command switch to J3/M3 & setting move rate
    
                    if line.__contains__("G0") and not line.__contains__(";") :
                        self.getCoord(line)
                        if line.__contains__("F") :
                                FCommand = line.partition("F")[2]
                                if FCommand[0].isdigit() is True :
                                    SBPFile.write("JS, " + self.moveRate + ", " + self.moveRate + "\n")
                                    
                                    # write in header SO commands one time after first MS
                                    if headerFlag is False :
                                        SBPFile.write("MS, " + self.moveRate + ", " + self.moveRate + "\n")
                                        SBPFile.write("VR,10.06, 10.06, , , 10.06, 10.06, , , 5.08, 5.08, 100, 3.81, 65, , , 5.08\n")
                                        SBPFile.write("SO, " + self.shared.getRunFlag() + ", 1\n")
                                        SBPFile.write("SO, 2, 1\n")
                                        SBPFile.write("SO, 2, 0\n")
                                        headerFlag = True
                                        
                        SBPFile.write("J3, " + self.X_Coord + ", " + self.Y_Coord + ", " + self.Z_Coord + "\n")

                    if line.__contains__("G1") and not line.__contains__(";") :
                        self.getCoord(line)
                        if line.__contains__("F") :
                                FCommand = line.partition("F")[2]
                                if FCommand[0].isdigit() is True :
                                    SBPFile.write("MS, " + self.moveRate + ", " + self.moveRate + "\n")
                                    
                                    # write in header SO commands one time after first MS
                                    if headerFlag is False :
                                        SBPFile.write("JS, " + self.moveRate + ", " + self.moveRate + "\n")
                                        SBPFile.write("VR,10.06, 10.06, , , 10.06, 10.06, , , 5.08, 5.08, 100, 3.81, 65, , , 5.08\n")
                                        SBPFile.write("SO, " + self.shared.getRunFlag() + ", 1\n")
                                        SBPFile.write("SO, 2, 1\n")
                                        SBPFile.write("SO, 2, 0\n")
                                        headerFlag = True
                            
                        SBPFile.write("M3, " + self.X_Coord + ", " + self.Y_Coord + ", " + self.Z_Coord + "\n")
                        
                        #absolute extruder mode
                    if line.__contains__("M82") :
                        SBPFile.write("SA\n")

                        #return to machine zero/go home
                    #if line.__contains__("G28") :
                        #SBPFile.write("MH\n")
                        
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
        
        if convertedSpeed > 40 :
            convertedSpeed = 40
        
        self.moveRate = str(round(convertedSpeed, 2))
                                            
   ###############################################  Conversion Window
    
class convertDialog(QDialog) :
    
    def __init__(self, sbWin) :
        
        #conversion window setup
        super().__init__(sbWin)
        self.sbWin = sbWin
        
        self.shared = sharedConvert(self.sbWin)
        self.addQueue = False
        self.haveSavePath = False
        self.channel0 = True
        self.channel1 = False
        
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
        self.channelLabel = QLabel('Flow channel designated to: ')
        
        self.convertLayout.addWidget(self.GFileLabel, 0,0)
        self.convertLayout.addWidget(self.pathLabel, 3, 0)
        self.convertLayout.addWidget(self.channelLabel, 4, 1)
        
    def loadBox(self) :
        self.pathBox = QCheckBox('Save to file folder')
        self.pathBox.stateChanged.connect(self.updatePathway)
        
        self.queueBox = QCheckBox('load to queue after conversion')
        self.queueBox.stateChanged.connect(self.updateQueue)
        
        self.channel0Box = QCheckBox('Channel 0')
        self.channel0Box.setChecked(True)
        self.channel0Box.stateChanged.connect(self.updateChannel)
        
        self.channel1Box = QCheckBox('Channel 1')
        self.channel1Box.stateChanged.connect(self.updateChannel)
        
        self.convertLayout.addWidget(self.queueBox, 0, 1)
        self.convertLayout.addWidget(self.pathBox, 3, 1)
        self.convertLayout.addWidget(self.channel0Box, 4, 2)
        self.convertLayout.addWidget(self.channel1Box, 4, 3)
        
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
        self.haveSavePath = True
        if self.shared.samePath is False:
            openFolder = r'C:\\'
            self.custFolder = QFileDialog.getExistingDirectory(self, "Choose Directory", openFolder)
            self.shared.pathway = self.custFolder
            self.pathLabel.setText('Pathway to save : ' + self.shared.pathway)
        self.updateButt()
    
    def updateFile(self) -> None :
        self.GFileLabel.setText('File:  ' + self.fileName)
        self.fileEdit.setText(self.fileName.replace('.gcode', ''))
        
        #update pathway for same folder or chosen by user
    def updatePathway(self) -> None :
        self.haveSavePath = True
        if self.filePath[0]: 
            self.shared.samePath = self.pathBox.isChecked()
        
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
       
        self.updateButt()
        
        
    def updateButt(self) -> None :
        if self.haveSavePath is False :
            self.convertButt.setEnabled(False)
            
        else :
            self.convertButt.setEnabled(True)
    
    def updateQueue(self) -> None :
        self.addQueue = self.queueBox.isChecked()
        
    def updateChannel(self) -> None :
        self.channel0 = self.channel0Box.isChecked()
        self.channel1 = self.channel1Box.isChecked()
        
        self.changeChannel()
        
    def changeChannel(self) -> None :
        if self.channel0 is True and self.channel1 is False :
            self.shared.setChannel(0)
            self.updateButt()
            
        if self.channel1 is True and self.channel0 is False :
            self.shared.setChannel(1)
            self.updateButt()
        
        if (self.channel0 is False and self.channel1 is False) or (self.channel0 is True and self.channel1 is True) :
            self.convertButt.setEnabled(False)
        
    def conversion(self) -> None :
        self.newName = self.fileEdit.text()
        
        # if gcode, go to python script above
        if '.gcode' in self.fileName :
            fileObject = convert(self.filePath[0], self.shared, self.newName)
            self.newFile = fileObject.readInFile()
            
        elif '.stl' in self.fileName :
            #otherwise, open the slicer for use
            fileObject = slicerBox(self.filePath[0], self.shared, self.newName)
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
    def __init__(self, sbWin) :
        self.sbWin = sbWin
        
        self.samePath = False
        self.pathway = ""
        self.finished = False
        self.newName = ""
        self.channelNum = self.sbWin.fluBox.pchannels[0]
                                                      
    def getFluFlag(self) :
        return str(self.channelNum.flag1)
                                                      
    def getRunFlag(self) :
        return str(self.sbWin.sbBox.runFlag1)
    
    def setChannel(self, channel) :
        self.channelNum = self.sbWin.fluBox.pchannels[channel]
        
   ################################################### Class for opening Slicer  
class slicerBox :
    
    def __init__(self, file, convertShare, reName) :
        self.shared = convertShare
        stlFile = file
        self.reName = reName
        
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