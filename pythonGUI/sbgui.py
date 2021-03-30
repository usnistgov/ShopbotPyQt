#!/usr/bin/env python
'''Shopbot GUI. 

Coordinating the shopbot with the cameras and Fluigent relies on the output flags that you can see in the Sb3 software. These flags are stored as windows registry keys, usually held in 'Software\\VB and VBA Program Settings\\Shopbot\\UserData'. This is designed for a shopbot with four output flags, a Fluigent with two channels, and three cameras. 

When the shopbot runs a program that sets the output flags, it first turns on output flag 4 (1-indexed). Then, it asks the user to let it turn on the spindle. (You should say yes.) This python GUI will watch those output flags for commands. If flag 3 (1-indexed) is turned on, the checked cameras will take a picture. If flag 1 is turned on, Fluigent channel 1 (1-indexed) will turn on to whatever is inserted into "Run Pressure". If there is a second channel, flag 2 will turn on Fluigent channel 2. When the shopbot is done with the whole file, it will turn off all output flags, and the python GUI will take that as a sign that it is time to stop recording.

'''

import sbgui_layout

__author__ = "Leanne Friedrich"
__copyright__ = "This data is publicly available according to the NIST statements of copyright, fair use and licensing; see https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software"
__credits__ = ["Leanne Friedrich"]
__license__ = "MIT"
__version__ = "1.0.4"
__maintainer__ = "Leanne Friedrich"
__email__ = "Leanne.Friedrich@nist.gov"
__status__ = "Development"
     
        
'''Run the program'''
if __name__ == "__main__":
    sbgui_layout.MainProgram()