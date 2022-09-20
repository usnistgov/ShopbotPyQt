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
    isFlowing = False
    
    def __init__(self, fileName) :
        self.fileName = fileName

    
    def readInFile(self) :
        
        # If the file isn't GCODE, display error and break out of method
        if ".gcode" not in self.fileName:
                print("File must be GCODE") 
                
        GCodeFile = open(self.fileName, 'r')
        file = copy.copy(self.fileName)
        SBPFile = open(file.replace(".gcode", ".sbp"), 'w+')
        
        line = GCodeFile.readline()
          #  print (line)
            
        while line :
            if line.__contains__(";") :
                SBPFile.writeline("#" + line)
                line = line.readline()

            commandList = list(line.split(" "))
            print (commandList)

            if commandList[-1].__contains__("E") and self.isFlowing is False :
                isFlowing = True
                SBPFile.write("S0, 1, 1")    
            if [not commandList[-1].__contains__("E")] and self.isFlowing is True :
                isFlowing = False
                SBPFile.write("S0, 1, 0")

            for command in commandList :
                if command.__contains__('G0') :
                    self.getCoord(command)
                    SBPFile.write("J3, " + str(self.X_Coord) + ", " + str(self.Y_Coord) + ", " + str(self.Z_Coord))
                if command.__contains__('G1') :
                    self.getCoord(command)
                    SBPFile.write("M3, " + str(self.X_Coord) + ", " + str(self.Y_Coord) + ", " + str(self.Z_Coord))
            
            line = GCodeFile.readline()
           
        GCodeFile.close()
        
        print(SBPFile.readline())
        SBPFile.close()        

                    
    def getCoord(self, command) :
        
        if command.__contains__("X") :
            if command.__contains__("\n") :
                self.getNums(command, 'X', '\n')
            else :
                self.getNums(command, 'X')
        if command.__contains__("Y") :
            if command.__contains__("\n") :
                self.getNums(command, 'Y', '\n')
            else :
                self.getNums(command, 'Y')
        if command.__contains__("Z") :
            if command.__contains__("\n") :
                self.getNums(command, 'Z', '\n')
            else :
                self.getNums(command, 'Z')
                    
                
    #Method of getting numbers with newline in sequence            
    def getNums(self, command, char, space) :
            
        if char == 'X' :
            X_Coord = float(command[1:-1])
        if char == 'Y' :
            Y_Coord = float(command[1:-1])
        if char == 'Z' :
            Z_Coord = float(command[1:-1])
    
    
    #Method of getting numbers from string
    def getNums(self, command, char) :
        
        if char == 'X' :
            X_Coord = float(command[1:])
        if char == 'Y' :
            Y_Coord = float(command[1:])
        if char == 'Z' :
            Z_Coord = float(command[1:])
                            
   
    
            
 ##################################################### testing output below   
    
        
object = convert("Test.gcode")
object.readInFile()