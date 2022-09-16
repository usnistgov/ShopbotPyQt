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
        
        # If the file isn't GCODE, display error and break out of method
        if ".gcode" not in self.fileName:
                print("File must be GCODE")  
        file = copy.copy(self.fileName)
        txtFile = open(file.replace(".gcode", ".txt"), 'w+')
        
        with open(self.fileName, 'r') as scan:
            txtFile.write(scan.read())
        txtFile.close()
        
        
        #fileObject = open(self.fileName, 'r')
        commandsArray = numpy.genfromtxt(file, dtype=str, encoding=None, delimiter=" ")
        
        print(commandsArray)
        self.conversion(commandsArray)

        
    def conversion(self, commandsArray) :
        numPattern = re.compile("[0-9]+")
        
        switcher = {
            "F" : "MS",
            ("X" + str(numPattern)) : "",
            ("Y" + str(numPattern)) : "",
            ("Z" + str(numPattern)) : "",
            "G0": "JS"
        }
        old = switcher.keys()
        new = switcher.values()
        SBPArray = numpy.copy(commandsArray)
        
        for ir, row in enumerate(commandsArray) :
            for ic, column in enumerate(row) :
                command = commandsArray[ir][ic]
                if ((command.startswith("X") or command.startswith("Y") or command.startswith("Z")) and command.endswith(numPattern)) :
                    coord = commandsArray[ir][ic].charAt(0)
                    self.changeCoord(command, coord)
              
                for key, value in switcher.items() :
                     if (command.__contains__(key)) :
                        SBPArray[ir][ic].replace(key, value)
       # print(commandsArray[0][0])                                               
       # print(SBPArray)
        print(self.X_Coord)
            
    
    # To change the placeholder coordinates between the two file types
    def changeCoord(self, command, coord) :
        temp = coord
        command.replace(temp, "")
        if coord == "X" :
            self.X_Coord = int(coord)
            
        if coord == "Y" :
            self.Y_Coord = int(coord)
            
        if coord == "Z" :
            self.Z_Coord = int(coord)
            
            
    def map_func(value, dictionary) :
        return dictionary[value] if value in dictionary else value
                               

    def writeSBPFile(self, wordsList) :
        # Creating new file and writing conversion
      fileObject = open(self.fileName + "_SBP", 'w')
      fileObject.writelines(wordsList)
      fileObject.close()
        
     
    
 ##################################################### testing output below   
    
        
object = convert("Test.gcode")
object.readInFile()