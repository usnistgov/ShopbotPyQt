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
    
    def __init__(self, fileName) :
        self.fileName = fileName

    
    def readInFile(self) :
        isFlowing = false
        
        
        # If the file isn't GCODE, display error and break out of method
        if ".gcode" not in self.fileName:
                print("File must be GCODE") 
                
        GCodeFile = open(self.fileName, 'r')
        file = copy.copy(self.fileName)
        SBPFile = open(file.replace(".gcode", ".txt"), 'w+')
        
        with GCodeFile as scan :
            line = GCodeFile.readline()
            while line :
                if [(line.contains('E') and re.search(r'\d', line)) and isFlowing == false] :
                    SBPFile.writeline("S0, 1, 1")                   
                if [not (line.contains('E') and re.search(r'\d', line)) and isFlowing == true] :
                    SBPFile.writeline("S0, 1, 0")
               
                if line.contains('G0') :
                    self.getCoord(line)
                if line.contains('G1') :
                    self.getCoord(line)
                    
        SBPFile.close()        

                    
    def getCoords(self, line) :
        if line.contains('X' + re.search(r'\d', line) + ' ') :
            self.getNums(line, 'X', ' ')
        elif line.contains('X' + re.search(r'\d', line) + '\n') :
            self.getNums(line, 'X', '\n')
                    
        if line.contains('Y' + re.search(r'\d', line) + ' ') :
            self.getNums(line, 'Y', ' ')
        elif line.contains('Y' + re.search(r'\d', line) + '\n') :
            self.getNums(line, 'Y', '\n')
                    
        if line.contains('Z' + re.search(r'\d', line) + ' ') :
            self.getNums(line, 'Z', ' ')   
        elif line.contains('Z' + re.search(r'\d', line) + '\n') :
            self.getNums(line, 'Z', '\n')
                    
    def getNums(self, line, char, space) :
        if char == 'X' :
            self.X_Coord = float(line[line.find(char)+1 : line.find(space)]
        if char == 'Y' :
            self.Y_Coord = float(line[line.find(char)+1 : line.find(space)]
        if char == 'Z' :
            self.Z_Coord = float(line[line.find(char)+1 : line.find(space)]
                            
   
    
            
 ##################################################### testing output below   
    
        
object = convert("Test.gcode")
object.readInFile()