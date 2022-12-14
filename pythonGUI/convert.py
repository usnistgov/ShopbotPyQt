#!/usr/bin/env python
'''Shopbot GUI functions for setting up the convert window'''

# external packages
import sys
import re
import os
import subprocess
import winreg
import numpy
import logging
import copy
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QDialog, QVBoxLayout, QWidget, QApplication, QAction, QLabel, QCheckBox, QGridLayout, QFileDialog, QPushButton, QLineEdit, QRadioButton

# local packages
from general import *
import sbList
from config import cfg


   ######################## Conversion program

   # Note: GCODE commands that are ignored: M104, M105, M107, M109, M140, 190

class convert:

    def __init__(self, gfileName:str, convertShare, reName:str) :
        self.reName = reName     # name of the new file
        self.gfileName = gfileName
        self.shared = convertShare
        self.runFlag = self.shared.getRunFlag()
        self.pFlag = self.shared.getFluFlag()
        self.unusedFlag = self.shared.getUnusedFlag()
        
        # Make everything default/0/null/false
        self.X_Coord = self.Y_Coord = self.Z_Coord = "0"
        self.ERate = self.moveRate = "0"

       # self.minX = self.maxX = self.minY = self.maxY = self.minZ = self.maxZ = "0"
       # self.checkMinX = self.checkMinY = self.checkMinZ = self.checkMaxX = self.checkMaxY = self.checkMaxZ = False
        
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
        
    def writeHeader(self, SBPFile):
        '''write the header into the file'''
        SBPFile.write(f'&runFlag={self.runFlag}\n')
        SBPFile.write(f'&pFlag={self.pFlag}\n')
        SBPFile.write(f'&unusedFlag={self.unusedFlag}\n')
        SBPFile.write("VD , , 1\n")  # mm
        SBPFile.write("VU, 157.480315, 157.480315, -157.480315\n")   # mm, negative z is up
        SBPFile.write("VR,10.06, 10.06, , , 10.06, 10.06, , , 5.08, 5.08, 100, 3.81, 65, , , 5.08\n")
        
    def writeHeaderFlagTriggers(self, SBPFile):
        '''turn on run flag and trigger the dummy flag'''
        self.setSpeed(SBPFile, 'M')
        self.setSpeed(SBPFile, 'J')
        SBPFile.write("SO, &runFlag, 1\n")
        SBPFile.write("SO, &unusedFlag, 1\n")
        SBPFile.write("SO, &unusedFlag, 0\n")
        self.headerFlag = True
        
    def writeFooter(self, SBPFile):
        '''write the footer into the file'''
        SBPFile.write("SO, &runFlag, 0\n")
    
    def setSpeed(self, SBPFile, m:str):
        '''set the speed. m should be "M" or "J"'''
        SBPFile.write(f"{m}S, {self.moveRate}, {self.moveRate}\n")
        
    def setPressure(self, SBPFile, line:str) -> None:
        '''turn the pressure on or off'''
        if line.__contains__("E") and not line.__contains__(";") :
            self.getCoord(line)

            ECommand = line.partition("E")[2]
            isE = ECommand[0].isdigit()

            if isE and not self.isFlowing:
                SBPFile.write("SO, &pFlag, 1\n")
                self.isFlowing = True
            if not isE and self.isFlowing:
                SBPFile.write("SO, &pFlag, 0\n")
                self.isFlowing = False
    
    def readInFile(self) :
        self.isFlowing = False
      #  isWritten = False
        self.headerFlag = False
        file = ""
        
        # If the file isn't GCODE, display error and break out of method
        if (".gcode" or ".stl") not in self.gfileName:
                print("File must be GCODE or STL") 
        
        file = os.path.join(self.shared.SBPFolder, self.reName)
        
        with open(self.gfileName, 'r') as GCodeFile :
            with open(file, 'w+') as SBPFile :
                self.writeHeader(SBPFile)

                while True :
                    line = GCodeFile.readline()
                    if not line:
                        self.writeFooter(SBPFile)
                        break
                    
                    ## Setting Variables
                   
                    if line.__contains__(";") :
                        semiSpot = line.find(";")  #if comment in middle of code, get rid of comment
                        if semiSpot != 0 :
                            line = line.partition(";")[0]
                            
                            #getting coordinates
                        if line.__contains__("MIN") or line.__contains__("MAX") :
                            self.getCoord(line)
                            
                            # flagging for once all coordinates are read
                            #Values for limits for Table
                            
                  #  if ((self.checkMinX and self.checkMinY and self.checkMinZ and self.checkMaxX and self.checkMaxY and self.checkMaxZ) and not isWritten) :
                         #   SBPFile.write("VL, " + self.minX + ", " + self.maxX + ", " + self.minY + ", " + self.maxY + ", " + self.minZ + ", " + self.maxZ + ", , , , , \n")
                         #   isWritten = True
                                                                                
                    ## E command switch to S0, 1, 1/0                          
                    self.setPressure(SBPFile, line)
                          
                    ## G0/G1 command switch to J3/M3 & setting move rate
    
                    if line.__contains__("G0") and not line.__contains__(";") :
                        self.getCoord(line)
                        if line.__contains__("F") :
                                FCommand = line.partition("F")[2]
                                if FCommand[0].isdigit() is True :
                                    self.setSpeed(SBPFile, 'J')
                                    
                                    # write in header SO commands one time after first MS
                                    if not self.headerFlag:
                                        self.writeHeaderFlagTriggers(SBPFile)
                                        
                                        
                        SBPFile.write(f"J3, {self.X_Coord}, {self.Y_Coord}, {self.Z_Coord}\n")

                    if line.__contains__("G1") and not line.__contains__(";") :
                        self.getCoord(line)
                        if line.__contains__("F") :
                                FCommand = line.partition("F")[2]
                                if FCommand[0].isdigit() is True :
                                    if self.headerFlag:
                                        SBPFile.write(f"'ink_speed_{self.shared.channel}={self.moveRate}\n") 
                                    else:
                                        # write in header SO commands one time after first MS
                                        self.writeHeaderFlagTriggers(SBPFile)
                        SBPFile.write(f"M3, {self.X_Coord}, {self.Y_Coord}, {self.Z_Coord}\n")   
                        
                        #absolute extruder mode
                    if line.__contains__("M82") :
                        SBPFile.write("SA\n")

                        #return to machine zero/go home
                    if line.__contains__("G28") :
                        SBPFile.write("MH\n")
                        
        self.shared.finished = True
        logging.info(f'Converted gcode file {self.gfileName} to {file}')
        
        return file
               

                                            
   ###############################################  Conversion Window

    
class convertDialog(QDialog) :
    
    def __init__(self, sbWin) :
        
        #conversion window setup
        super().__init__(sbWin)
        self.sbWin = sbWin
        
        self.shared = sharedConvert(self.sbWin)
        self.addToQueue = False
        self.haveSavePath = False
        self.channel0 = True
        self.channel1 = False
        
        self.newFile = ""
        self.filePath = ""
        self.gcodeFileName = ""
        self.custFolder = ""
        self.setWindowTitle("Convert gcode to SBP")
        self.loadConfig(cfg)
        
        self.successLayout()

        self.updateFile()
        self.updateButt()
        
        if self.shared.finished is True :
            self.close()
            
    def loadConfig(self, cfg1) -> None:
        self.gcodeFolder = cfg1.convert.gcodeFolder
        self.sbpDir = cfg1.convert.sbpFolder
        self.sameFolder = cfg1.convert.sameFolder
        self.addToQueue = cfg1.convert.addToQueue
        self.closeWhenDone = cfg1.convert.closeWhenDone
        
    def saveConfig(self, cfg1):
        cfg1.convert.gcodeFolder = self.gcodeFolder
        cfg1.convert.sbpFolder = self.sbpDir
        cfg1.convert.sameFolder = self.sameFolder
        cfg1.convert.addToQueue = self.addToQueue
        cfg1.convert.closeWhenDone = self.closeWhenDone
        return cfg1
            
    def successLayout(self):
        self.convertLayout = QVBoxLayout()
        w = 600
        appendForm = QFormLayout()
        appendForm.setSpacing(20)
        self.gcodeRow = fileSetOpenRow(width=w, title='Set gcode file', 
                                   initFolder='No file selected', 
                                   tooltip='Open G-Code folder',
                                  setFunc = self.setGCodeFile,
                                   openFunc = self.openGCodeFolder
                                  )
        appendForm.addRow('G-Code file', self.gcodeRow)
        
        self.stlFileEdit = QLineEdit()
        appendForm.addRow('SBP name', self.stlFileEdit)
        
        self.SBPFolderGroup = fRadioGroup(None, '', 
                                  {0:'Same folder as G-Code file', 1:'Different folder'}, 
                                  {0:True, 1:False},
                                 {True:0,False:1}[self.sameFolder], col=False, headerRow=False,
                                  func=self.updateSBPFolder)
        appendForm.addRow('SBP folder', self.SBPFolderGroup.layout)
        
        self.SBPFolderRow = fileSetOpenRow(width=w, title='Set SBP folder', 
                                   initFolder=self.sbpDir, 
                                   tooltip='Open SBP folder',
                                  setFunc = self.setSBPFolder,
                                   openFunc = self.openSBPFolder
                                  )
        appendForm.addRow('', self.SBPFolderRow)
        self.queueBox = fCheckBox(None, title='Add sbp file to queue', tooltip='Add converted file to the play queue'
                                 , checked=self.addToQueue, func=self.updateQueue)
        appendForm.addRow('Queue', self.queueBox)
        self.closeWhenDoneBox = fCheckBox(None, title='Close this window when done', tooltip='Close this window when done converting'
                                 , checked=self.closeWhenDone, func=self.updateCloseWhenDone)
        appendForm.addRow('Close', self.closeWhenDoneBox)

        self.channelRow = fRadioGroup(None, '', 
                              dict([[i,f'Channel {i}'] for i in range(self.sbWin.fluBox.numChans)]), 
                              dict([[i,i] for i in range(self.sbWin.fluBox.numChans)]),
                             0, col=False, headerRow=False,
                              func=self.changeChannel)
        appendForm.addRow('Flow channel', self.channelRow.layout)
        self.convertLayout.addItem(appendForm)
        self.convertButt = QPushButton('Convert G-Code to SBP')
        self.convertButt.clicked.connect(self.conversion)
        self.convertLayout.addWidget(self.convertButt)
        
        self.setLayout(self.convertLayout)
        # self.resize(900, 500)

        
           
    def setGCodeFile(self) -> None :
        '''set a new value for the gcode file'''
        if os.path.exists(self.gcodeFolder):
            openFolder = self.gcodeFolder
        else:
            openFolder = r'C:\\'
        tempPath = QFileDialog.getOpenFileName(self, "Open File", openFolder, 'G-Code file (*.gcode *.stl)')
        if len(tempPath)==0:
            return
        if not os.path.exists(tempPath[0]):
            return
        
        tempPath = tempPath[0]
        self.gcodeFolder = os.path.dirname(tempPath)
        self.gcodeFileName = tempPath
        self.updateFile()
            
    def updateFile(self) -> None :
        '''update the display to reflect the new gcode file'''
        self.gcodeRow.updateText(self.gcodeFileName)
        self.stlFileEdit.setText(os.path.basename(self.gcodeFileName).replace('.gcode', '.sbp'))
        self.updateSBPFolder()
        self.updateButt()
        
    def openGCodeFolder(self):
        '''open the gcode folder'''
        openFolder(self.gcodeFolder)
        
    def updateSBPFolder(self):
        '''change the shopbot folder mode'''
        self.sameFolder = self.SBPFolderGroup.value()
        if self.sameFolder:
            self.shared.SBPFolder = self.gcodeFolder
            self.SBPFolderRow.disable()
        else:
            self.shared.SBPFolder = self.sbpDir
            self.SBPFolderRow.enable()
        self.SBPFolderRow.updateText(self.shared.SBPFolder)

        
    def setSBPFolder(self):
        '''change the directory to save the sbp file to'''
        if self.sameFolder:
            return
        openFolder = self.sbpDir
        custFolder = QFileDialog.getExistingDirectory(self, "Choose Directory", openFolder)
        if os.path.exists(custFolder):
            self.shared.SBPFolder = custFolder
            self.sbpDir = custFolder
            self.updateSBPFolder()
            self.updateButt()
            
    def openSBPFolder(self):
        '''open the SBP save folder'''
        openFolder(self.sbpDir)
        
    def updateQueue(self) -> None :
        '''read the checkbox and decide whether to add the file to queue when done'''
        self.addToQueue = self.queueBox.isChecked()
        
    def changeChannel(self) -> None:
        '''store the selected channel in the shared object'''
        self.shared.setChannel(self.channelRow.value())
        
    def updateCloseWhenDone(self) -> None:
        '''read the checkbox and decide whether to close the window when done'''
        self.closeWhenDone = self.closeWhenDoneBox.isChecked()
        
    def updateButt(self) -> None:
        '''disable or enable the convert button'''
        if os.path.exists(self.gcodeFileName) and os.path.exists(self.sbpDir):
            self.convertButt.setEnabled(True)
            self.convertButt.setToolTip('Convert G-Code to SBP')
        else:
            self.convertButt.setEnabled(False)
            err = 'Cannot convert: '
            if not os.path.exists(self.gcodeFileName):
                print(self.gcodeFileName)
                err+='G-Code file does not exist'
            if not os.path.exists(self.sbpDir):
                if len(err)>0:
                    err+=', '
                err+='SBP folder does not exist'
            self.convertButt.setToolTip(err)
        
    def conversion(self) -> None :
        '''convert the file'''
        self.newName = self.stlFileEdit.text()
        if not self.newName.endswith('.sbp'):
            self.newName = self.newName + '.sbp'
        
        # if gcode, go to python script above
        if '.gcode' in self.gcodeFileName :
            fileObject = convert(self.gcodeFileName, self.shared, self.newName)
            self.newFile = fileObject.readInFile()
            
        elif '.stl' in self.gcodeFileName :
            #otherwise, open the slicer for use
            fileObject = slicerBox(self.gcodeFileName, self.shared, self.newName)
            temp = fileObject.findSlicer()
        
        #if user requested file to be added to queue
        if self.addToQueue:
            self.sbWin.sbBox.enableRunButt()
            self.sbWin.sbBox.sbList.addFile(self.newFile)
            logging.debug(f'Added file to queue: {self.newFile}')
            self.sbWin.sbBox.updateStatus('Ready ... ', False)
        
        if self.closeWhenDone:
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
        self.channel = 0
                                                      
    def getFluFlag(self) :
        return str(self.channelNum.flag1)
                                                      
    def getRunFlag(self) :
        return str(self.sbWin.sbBox.runFlag1)
    
    def getUnusedFlag(self):
        return str(self.sbWin.flagBox.unusedFlag0()+1)
    
    def setChannel(self, channel) :
        self.channelNum = self.sbWin.fluBox.pchannels[channel]
        self.channel = channel
        
   ################################################### Class for opening Slicer  
class slicerBox :
    
    def __init__(self, file, convertShare, reName:str) :
        self.shared = convertShare
        stlFile = file
        self.reName = reName   # name of the new file
        
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