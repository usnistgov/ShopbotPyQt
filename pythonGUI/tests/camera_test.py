#!/usr/bin/env python
'''Shopbot GUI. '''

# external packages
import os, sys

# local packages
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(currentdir)
sys.path.append(parentdir)
import layout

    
##################################################  
        
'''Run the program'''
if __name__ == "__main__":
    layout.MainProgram(meta=False, sb=False, flu=False, cam=True, test=True, file=True, calib=False, convert=False)