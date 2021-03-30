#!/usr/bin/env python
'''Shopbot GUI file handling functions. Refers to top box in GUI.'''


from PyQt5 import QtGui
import PyQt5.QtWidgets as qtw
import os
import subprocess
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging

from config import cfg

__author__ = "Leanne Friedrich"
__copyright__ = "This data is publicly available according to the NIST statements of copyright, fair use and licensing; see https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software"
__credits__ = ["Leanne Friedrich"]
__license__ = "MIT"
__version__ = "1.0.4"
__maintainer__ = "Leanne Friedrich"
__email__ = "Leanne.Friedrich@nist.gov"
__status__ = "Development"

INITSAVEFOLDER = cfg.vid
if not os.path.exists(INITSAVEFOLDER):
    INITSAVEFOLDER = r'C:\\'


###############################################################

def formatExplorer(fn:str) -> str:
    '''Format the file name for use in subprocess.Popen(explorer)'''
    return fn.replace(r"/", "\\")

class genBox(qtw.QGroupBox):
    '''this is a gui box for managing files. It goes at the top of the window'''
    def __init__(self, sbWin:qtw.QMainWindow):
        super(genBox, self).__init__()
        self.sbWin = sbWin
        self.layout = qtw.QGridLayout()        

        self.appendName = qtw.QLineEdit()
        self.appendName.setText('')
        
        self.appendLabel = qtw.QLabel('Append to output file names:')
        self.appendLabel.setBuddy(self.appendName)
        
        self.saveButt = qtw.QPushButton('Set video folder')
        self.saveButt.setIcon(QtGui.QIcon('icons/open.png'))
        self.saveButt.clicked.connect(self.setSaveFolder)
        
        self.saveFolder = INITSAVEFOLDER
        self.saveFolderLabel = qtw.QLabel('Export to ' + self.saveFolder)
        
        self.layout.addWidget(self.saveButt, 1, 0)
        self.layout.addWidget(self.saveFolderLabel, 1, 1)
        self.layout.addWidget(self.appendLabel, 2, 0)
        self.layout.addWidget(self.appendName, 2, 1)
       
        self.setLayout(self.layout)
    
    
    def setSaveFolder(self) -> None:
        '''set the folder to save all the files we generate from the whole gui'''
        if os.path.exists(self.saveFolder):
            startFolder = os.path.dirname(self.saveFolder)
        else:
            startFolder = INITSAVEFOLDER
        sf = fileDialog(startFolder, '', True)
        if len(sf)>0:
            sf = sf[0]
            if os.path.exists(sf):
                self.saveFolder = formatExplorer(sf)
                
                logging.info('Changed save folder to %s' % self.saveFolder)
                self.saveFolderLabel.setText('Export to ' + self.saveFolder)
            
    def openSaveFolder(self) -> None:
        '''Open the save folder in windows explorer'''
        
        if not os.path.exists(self.saveFolder):
            logging.debug(f'Save folder does not exist: {self.saveFolder}')
            return
        logging.debug(f'Opening {self.saveFolder}')
        cmd = ['explorer',  formatExplorer(self.saveFolder)]
        
        subprocess.Popen(cmd, shell=True)
