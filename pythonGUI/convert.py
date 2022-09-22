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
        self.X_Coord = ""
        self.Y_Coord = ""
        self.Z_Coord = ""

    
    def readInFile(self) :
        isFlowing = False
        
        # If the file isn't GCODE, display error and break out of method
        if ".gcode" not in self.fileName:
                print("File must be GCODE") 
                
        file = copy.copy(self.fileName)
        renameFile = file.replace(".gcode", ".sbp")
       
        
        with open(self.fileName, 'r') as GCodeFile :
            with open(renameFile, 'w+') as SBPFile :
                while True :
                    isE = False
                    line = GCodeFile.readline()
                    if not line:
                        break
                
                    if line.find("E") != -1 :
                        EChar = int(line.find("E"))
                        ECommand = line[EChar : -1]
                        isE = True
                    
                    if isE is True and isFlowing is False :
                        isFlowing = True
                        SBPFile.write("S0, 1, 1\n")                   
                    if isE is False and isFlowing is True :
                        isFlowing = False
                        SBPFile.write("S0, 1, 0\n")
               
                    if line.__contains__("G0") :
                        self.getCoord(line)
                        SBPFile.write("J3, " + str(self.X_Coord) + ", " + str(self.Y_Coord) + ", " + str(self.Z_Coord) + "\n")
                        f'J3,{self.x_coord}'

                    if line.__contains__("G1") :
                        self.getCoord(line)
                        SBPFile.write("M3, " + str(self.X_Coord) + ", " + str(self.Y_Coord) + ", " + str(self.Z_Coord) + "\n")
                        
                    
    def getCoord(self, line) :
        
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

   
 ##################################################### testing output below   
    
        
object = convert("Test.gcode")
object.readInFile()