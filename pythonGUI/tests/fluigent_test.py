#!/usr/bin/env python
'''Shopbot GUI. '''

# external packages
import os, sys

# local packages
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(currentdir)
sys.path.append(parentdir)
import sbgui_layout

    
##################################################  
        
'''Run the program'''
if __name__ == "__main__":
    sbgui_layout.MainProgram(meta=False, sb=False, flu=True, cam=False, test=True, file=True)