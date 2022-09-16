#!/usr/bin/env python
'''Shopbot GUI functions for setting up the convert window'''

# local packages
from sbgui_general import *
import re
import numpy

######################## Convert window

class convert:
    X_Coord = 0
    Y_Coord = 0
    Z_Coord = 0
    
    def __init__(self, fileName) :
        self.fileName = fileName
        X_Coord, Y_Coord, Z_Coord = 0
    
    def readInFile(self) :
        
        wordsList = [] 
        
        # If the file isn't GCODE, display error and break out of method
        if ".gcode" not in self.fileName:
                print("File must be GCODE")      
   
        fileObject = open(self.fileName, 'r')
        
       # Creating list of each line in file 
        linesArray = fileObject.readlines() #have a list with lines for each element
        fileObject.close()
           
        for i in linesArray : #for each element in list
            lines = i.strip('\n') #strip the newline
            wordsList.append(lines)
        
        array1 = numpy.array(wordsList)
        
        commandsArray = array1.reshape(len(array1), -1) 
        
       # print(commandsArray)
        self.conversion(commandsArray)

        
    def conversion(self, commandsArray) :
        numPattern = re.compile("[0-9]")
        
        switcher = {
            "F" : "MS",
            "G0": "JS",
        }
        SBPArray = numpy.copy(commandsArray)
        
        for ir, row in enumerate(commandsArray) :
            for ic, column in enumerate(row) :
                command = commandsArray[ir][ic]
                if ((command.startswith("X") or command.startswith("Y") or command.startswith("Z")) and command.endswith(numPattern)) :
                    coord = commandsArray[ir][ic].charAt(0)
                    self.changeCoord(command, coord)
                for key, value in switcher.items() :
                    SBPArray[commandsArray == key] = value
                                                        
        print(SBPArray)
        print(X_Coord)
            
    
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
                               

    def writeSBPFile(self, wordsList) :
        # Creating new file and writing conversion
      fileObject = open(self.fileName + "_SBP", 'w')
      fileObject.writelines(wordsList)
      fileObject.close()
        
     
    
 ##################################################### testing output below   
    
        
object = convert("Test.gcode")

object.readInFile()