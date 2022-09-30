#!/usr/bin/env python
'''Shopbot GUI functions for setting up the convert window'''

# local packages
from general import *
import re
import numpy
import copy
import sbList
from PyQt5.QtWidgets import QMainWindow, QDialog, QVBoxLayout, QWidget, QApplication, QAction, QLabel, QCheckBox, QGridLayout, QFileDialog

   ######################## Conversion program

   # Note: GCODE commands that are ignored: M104, M105, M107, M109, M140, 190

class convert:

    def __init__(self, fileName) :
        self.fileName = fileName
        self.X_Coord = self.Y_Coord = self.Z_Coord = "0"
        
        self.ERate = self.moveRate = "0"

        self.minX = self.maxX = self.minY = self.maxY = self.minZ = self.maxZ = "0"
        self.checkMinX = self.checkMinY = self.checkMinZ = self.checkMaxX = self.checkMaxY = self.checkMaxZ = False   
    
    def readInFile(self) :
        isFlowing = False
        isWritten = False
        
        # If the file isn't GCODE, display error and break out of method
        if ".gcode" not in self.fileName:
                print("File must be GCODE") 
                
        file = copy.copy(self.fileName)
        renameFile = file.replace(".gcode", ".sbp")
       
        
        with open(self.fileName, 'r') as GCodeFile :
            with open(renameFile, 'w+') as SBPFile :
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
                            
                        if line.__contains__("MIN") or line.__contains__("MAX") :
                            self.getCoord(line)
                            
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
                                isFlowing = True
                                SBPFile.write("S0, 1, 1\n")                   
                            if isE is False and isFlowing is True :
                                isFlowing = False
                                SBPFile.write("S0, 1, 0\n")
                          
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
                speedInt = int(speed)
                self.getRate(speedInt)
               

    def getRate(self, speed) :  # Conversion of gcode (mm/min) to sbp (mm/sec)
        convertedSpeed = speed / 60
        self.moveRate = str(round(convertedSpeed, 2))
                                            
   ###############################################  Conversion Window
    
class convertDialog(QDialog) :
    
    def __init__(self, sbWin) :
        super().__init__(sbWin)
        self.sbWin = sbWin
        
        self.file = ""
        self.pathway = ""
        self.setWindowTitle("File Conversion")
        
        layout = QGridLayout()
        
        self.GFileLabel = fLabel(layout, title = 'File: ')
        self.pathLabel = fLabel(layout, title = 'Pathway to save: ')
        layout.addWidget(self.GFileLabel, 0,0)
        layout.addWidget(self.pathLabel, 2, 0)
        
        
        self.pathBox = fCheckBox(layout, title = 'Save to same folder as original', checked = False, func = self.temp)
        queueBox = fCheckBox(layout, title = 'load to queue after conversion', checked = False, func = self.temp)
        #will be sbList.py.addFile(file)
        layout.addWidget(self.pathBox, 2, 1)
        layout.addWidget(queueBox, 0, 1)
        
       
        layout.addWidget(fButton(layout, title = 'Choose Save Location',
                tooltip = 'Choose Location to save .sbp file'), 3, 0)
        
        layout.addWidget(fButton(layout, title = 'Load File',
                tooltip = 'Load gcode file to convert to sbp',
                func = self.loadFile), 1, 0)
        
        layout.addWidget( fButton(layout, title = 'Convert File',
                tooltip = 'convert .gcode file to .sbp'), 4, 0)
        #will be convert.readInFile(file)
        
        
        self.setLayout(layout)
        self.resize(500, 500)
        
        self.updateFile()
        
        
        
    def loadFile(self) -> None :
        openFolder = r'C:\\'
        self.file = QtGui.QFileDialog.getOpenFileName(self, "Open File", openFolder, 'Gcode file (*.gcode)')
        self.updateFile()
    
    def updateFile(self) -> None :
        self.GFileLabel.setText('File:  ' + self.file)
        
    def updatePathway(self) -> None :
        self.samePath = self.pathBox.isChecked()
        
    def temp(self) -> None :
        None
        
   
                
    def close(self) :
        self.done(0)






   ################################################### testing output below   