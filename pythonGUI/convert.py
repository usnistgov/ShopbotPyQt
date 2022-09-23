#!/usr/bin/env python
'''Shopbot GUI functions for setting up the convert window'''

# local packages
from general import *
import re
import numpy
import copy

   ######################## Convert window

class convert:
    
    def __init__(self, fileName) :
        self.fileName = fileName
        self.X_Coord = self.Y_Coord = self.Z_Coord = "0"
        
        self.ERate = self.moveRate = "0"

        self.minX = self.maxX = self.minY = self.maxY = self.minZ = self.maxZ = ""
      
    
    def readInFile(self) :
        isFlowing = False
        isWritten = False
        checkMinX = checkMinY = checkMinZ = checkMaxX = checkMaxY = checkMaxZ = False
        
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
                        break
                    
   ##################################################### Setting Variables
                    if checkMinX is True and checkMinY is True and checkMin Z is True and checkMaxX is True and checkMaxY is True and checkMaxZ is True and isWritten is False :
                        SBPFile.write("")
                        isWritten = True
                
                    if line.__contains__(";") :
                        semiSpot = line.find(";")  #if comment in middle of code, get rid of comment
                        if semiSpot != 0 :
                            line = line.partition(";")[0]
                            
                        if line.__contains__("MIN") :
                            if line.__contains__("Y") :
                                self.minY = line.partition(":")[2]
                                checkMinY = True
                            elif line.__contains__("Z") :
                                self.minZ = line.partition(":")[2]
                                checkMinZ = True
                            else :
                                self.minX = line.partition(":")[2]
                                checkMinX = True
                                
                        if line.__contains__("MAX") :
                            if line.__contains__("Y") :
                                self.maxY = line.partition(":")[2]
                                checkMaxY = True
                            elif line.__contains__("Z") :
                                self.maxZ = line.partition(":")[2]
                                checkMaxZ = True
                            else :
                                self.maxX = line.partition(":")[2]
                                checkMaxX = True
                                               
                                            
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
        
        SBPFile.write("SO, 12, 0")
        SBPFile.write("SO, 2, 0")
         
        
   ###################################################
                            
                            


   ######################################################################                    
    def getCoord(self, line) :  # Retrieving values after key characters
        
        if line.__contains__("X") :
            XCommand = line.partition("X")[2]
            specChar = XCommand.find(" ")
            self.X_Coord = (XCommand[0 : specChar])
                    
        if line.__contains__("Y") :
            YCommand = line.partition("Y")[2]
            specChar = YCommand.find(" ")
            self.Y_Coord = (YCommand[0 : specChar])            
            
        if line.__contains__("Z") :
            ZCommand = line.partition("Z")[2]
            specChar = ZCommand.find(" ")
            self.Z_Coord = (ZCommand[0 : specChar])            
            
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
                                            
   
   ################################################### testing output below   
    
        
object = convert("STARTTest.gcode")
object.readInFile()