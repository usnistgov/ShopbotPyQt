#!/usr/bin/env python
'''Shopbot GUI functions for setting up the convert window'''

# local packages
from general import *
import re
import numpy
import copy

######################## Convert window

class convert:
    X_Coord = 0
    Y_Coord = 0
    Z_Coord = 0
    numPattern = re.compile("[0-9]+[.]")
    
    def __init__(self, fileName) :
        self.fileName = fileName

    
    def readInFile(self) :
        isFlowing = False
        
        
        # If the file isn't GCODE, display error and break out of method
        if ".gcode" not in self.fileName:
                print("File must be GCODE") 
                
        GCodeFile = open(self.fileName, 'r')
        file = copy.copy(self.fileName)
        SBPFile = open(file.replace(".gcode", ".txt"), 'w+')
        
        with GCodeFile as scan :
            line = GCodeFile.readline()
            while line :
                if [(line.__contains__("E" + str(numPattern))) and isFlowing == False] :
                    isFlowing = True
                    SBPFile.writeline("S0, 1, 1")                   
                if [not (line.__contains__("E" + str(numPattern))) and isFlowing == True] :
                    isFlowing = False
                    SBPFile.writeline("S0, 1, 0")
               
                if line.__contains__('G0') :
                    self.getCoord(line)
                if line.__contains__('G1') :
                    self.getCoord(line)
                    
        SBPFile.close()        

                    
    def getCoords(self, line) :
        if line.__contains__("X" + str(numPattern) + " ") :
            self.getNums(line, 'X', ' ')
        elif line.contains("X" + str(NumPattern) + "\n") :
            self.getNums(line, 'X', '\n')
                    
        if line.__contains__("Y" + str(NumPattern) + " ") :
            self.getNums(line, 'Y', ' ')
        elif line.__contains__('Y' + str(NumPattern) + "\n") :
            self.getNums(line, 'Y', '\n')
                    
        if line.__contains__("Z" + str(NumPattern) + " ") :
            self.getNums(line, 'Z', ' ')   
        elif line.__contains__("Z" + str(NumPattern) + "\n") :
            self.getNums(line, 'Z', '\n')
                    
    def getNums(self, line, char, space) :
        if char == 'X' :
            X_Coord = float(line[line.find(char)+1 : line.find(space)])
        if char == 'Y' :
            Y_Coord = float(line[line.find(char)+1 : line.find(space)])
        if char == 'Z' :
            Z_Coord = float(line[line.find(char)+1 : line.find(space)])
                            
   
    
            
 ##################################################### testing output below   
    
        
object = convert("Test.gcode")
object.readInFile()