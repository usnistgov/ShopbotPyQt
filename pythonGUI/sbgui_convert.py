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
                
        file = copy.copy(self.fileName)
        SBPFile = open(file.replace(".gcode", ".txt"), 'w+')
        
        with open(self.fileName, 'r') as scan :
            numPattern = re.compile("[0-9]+[.]")
            
            while True :
                line = GCodeFile.readline()
                
                if not line:
                    break
                
                ECommand = re.search(("E" + str(numPattern)), line)
                print(numPattern)
                
                if [line.__contains__(ECommand.group()) and isFlowing == False] :
                    isFlowing = True
                    SBPFile.writeline("S0, 1, 1")                   
                if [(not line.__contains__(ECommand.group())) and isFlowing == True] :
                    isFlowing = False
                    SBPFile.writeline("S0, 1, 0")
               
                if line.__contains__('G0') :
                    self.getCoord(line)
                if line.__contains__('G1') :
                    self.getCoord(line)
                    
        SBPFile.close()

                    
    def getCoords(self, line) :
        numPattern = re.compile("[0-9]+[.]")
        
        if line.__contains__((re.search("X" + str(numPattern)), line).group()
 + " ") :
            self.getNums(line, 'X', ' ')
        elif line.contains((re.search("X" + str(numPattern)), line).group()
 + "\n") :
            self.getNums(line, 'X', '\n')
                    
        if line.__contains__((re.search("Y" + str(numPattern)), line).group()
 + " ") :
            self.getNums(line, 'Y', ' ')
        elif line.__contains__((re.search("Y" + str(numPattern)), line).group()
 + "\n") :
            self.getNums(line, 'Y', '\n')
                    
        if line.__contains__((re.search("Z" + str(numPattern)), line).group()
 + "\n") :
            self.getNums(line, 'Z', ' ')   
        elif line.__contains__((re.search("Z" + str(numPattern)), line).group()
 + "\n") :
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