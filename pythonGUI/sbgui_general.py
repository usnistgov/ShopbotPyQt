#!/usr/bin/env python
'''Shopbot GUI general functions. Contains classes and functions that are shared among fluigent, cameras, shopbot.'''


from PyQt5 import QtCore
import PyQt5.QtWidgets as qtw
import sip
import os
import subprocess
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging


__author__ = "Leanne Friedrich"
__copyright__ = "This data is publicly available according to the NIST statements of copyright, fair use and licensing; see https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software"
__credits__ = ["Leanne Friedrich"]
__license__ = "MIT"
__version__ = "1.0.4"
__maintainer__ = "Leanne Friedrich"
__email__ = "Leanne.Friedrich@nist.gov"
__status__ = "Development"


################################################


def fileDialog(startDir:str, fmt:str, isFolder:bool) -> str:
    '''fileDialog opens a dialog to select a file for reading
    startDir is the directory to start in, e.g. r'C:\Documents'
    fmt is a string file format, e.g. 'Gcode files (*.gcode *.sbp)'
    isFolder is bool true to only open folders'''
    dialog = qtw.QFileDialog()
    dialog.setFilter(dialog.filter() | QtCore.QDir.Hidden)

    # ARE WE TALKING ABOUT FILES OR FOLDERS
    if isFolder:
        dialog.setFileMode(qtw.QFileDialog.DirectoryOnly)
    else:
        dialog.setFileMode(qtw.QFileDialog.ExistingFiles)
        
    # OPENING OR SAVING
    dialog.setAcceptMode(qtw.QFileDialog.AcceptOpen)

    # SET FORMAT, IF SPECIFIED
    if fmt != '' and isFolder is False:
        dialog.setDefaultSuffix(fmt)
        dialog.setNameFilters([f'{fmt} (*.{fmt})'])

    # SET THE STARTING DIRECTORY
    if startDir != '':
        dialog.setDirectory(str(startDir))
    else:
        dialog.setDirectory(str(ROOT_DIR))

    if dialog.exec_() == qtw.QDialog.Accepted:
        paths = dialog.selectedFiles()  # returns a list
        return paths
    else:
        return ''

#####################################################

def findFileInFolder(file:str, folder:str) -> str:
    '''findFileInFolder finds the full path name for a file in a folder
    file is the basename string
    folder is the folder to search in
    this searches recursively and returns an exception if it doesn't find the file'''
    f1 = os.path.join(folder, file)
    if os.path.exists(f1):
        return f1
    for subfold in os.listdir(folder):
        subfoldfull = os.path.join(folder, subfold)
        if os.path.isdir(subfoldfull):
            try:
                file = findFileInFolder(file, subfoldfull)
            except:
                pass
            else:
                return file
    raise Exception(file+' not found')


def findSb3Folder() -> str:
    '''find the folder that the Sb3 program files are in'''
    for fold in [r'C:\\Program files', r'C:\\Program files (x86)']:
        for f in os.listdir(fold):
            if 'ShopBot'.lower() in f.lower():
                return os.path.join(fold, f)
    raise Exception('Shopbot folder not found')


def findSb3() -> str:
    '''find the full path name for the Sb3.exe program
    raises an exception if it doesn't find the file'''
    try:
        fold = findSb3Folder()
    except:
        raise Exception('Sb3.exe not found')
    try:
        sb3File = findFileInFolder('Sb3.exe', fold)
        subprocess.Popen([sb3File])
    except:
        raise Exception('Sb3.exe not found')
    else:
        return sb3File

##############################################################

def deleteLayoutItems(layout) -> None:
    '''use this to remove an entire QtLayout and its children from the GUI'''
    if layout is not None:
        try:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    deleteItems(item.layout())
        except:
            return
    sip.delete(layout)
    
    

class connectBox(qtw.QGroupBox):
    '''connectBox is a type of QGroupBox that can be used for cameras and fluigent, which need to be initialized. This gives us the option of showing an error message and reset button if the program doesn't connect'''
    
    def __init__(self):
        super(connectBox, self).__init__()
        self.connectAttempts = 0
        self.connected = False
        self.diag=1
        self.bTitle = ''

    
    def connectingLayout(self) -> None:
        '''if the computer is still trying to connect, show this waiting screen'''
        if self.connectAttempts>0:
            self.resetLayout()
        self.layout = qtw.QVBoxLayout()
        logging.info('Connecting to %s' % self.bTitle)
        self.layout.addWidget(qtw.QLabel('Connecting to '+self.bTitle))
        self.setLayout(self.layout)  

    
    def failLayout(self) -> None:
        '''if the computer fails to connect, show an error message and a button to try again'''
        self.resetLayout()
        self.layout = qtw.QVBoxLayout()
        lstr = self.bTitle+' not connected. Connect attempts: '+str(self.connectAttempts)
        logging.warning(lstr)
        self.label = qtw.QLabel(lstr)            
        self.resetButt = qtw.QPushButton('Connect to ' + self.bTitle)
        self.resetButt.clicked.connect(self.connect) 
            # when the reset button is pressed, try to connect to the fluigent again
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.resetButt)
        self.setLayout(self.layout)
    
    
    def createStatus(self, width:int) -> None:
        '''creates a section for displaying the device status'''
        self.status = qtw.QLabel('Ready')
        self.status.setFixedSize(width, 50)
        self.status.setWordWrap(True)
    
    
    def resetLayout(self) -> None:
        '''delete all the display items from the box'''
        deleteLayoutItems(self.layout)
        
    
    def updateStatus(self, st, log) -> None:
        '''update the displayed device status'''
        try:
            self.status.setText(st)
        except:
            if self.diag>0:
                logging.info(f'{self.bTitle}:{st}')
        else:
            if log and self.diag>0:
                logging.info(f'{self.bTitle}:{st}')
