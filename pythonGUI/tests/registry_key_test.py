#!/usr/bin/env python
'''Shopbot GUI. '''

# external packages
import os, sys
import time

# local packages
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(currentdir)
sys.path.append(parentdir)
import flags
    
##################################################  
        
'''Run the program'''
if __name__ == "__main__":
    sbk = flags.SBKeys(2)
    while True:
        sbk.printChangingKeys()
        time.sleep(0.1)