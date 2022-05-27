#!/usr/bin/env python
'''Shopbot GUI general functions. Contains classes and functions that are shared among fluigent, cameras, shopbot.'''

# external packages
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QDialog
import PyQt5.QtWidgets as qtw
import sip
import os, sys
import subprocess
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging


################################################

def checkPath(path:str) -> str:
    '''check if the path is formatted correctly and exists'''
    path0 = os.path.abspath(path)
    if not os.path.exists(path):
        path = r'C:\\'
    return path

def icon(name:str) -> QtGui.QIcon:
    '''Get a QtGui icon given an icon name'''
    currentdir = os.path.dirname(os.path.realpath(__file__))
    iconfolder = os.path.join(currentdir, 'icons')
    if not os.path.exists(iconfolder):
        iconfolder = os.path.join(os.path.dirname(currendir), 'icons')
    if not os.path.exists(iconfolder):
        raise NameError('No icon folder found')
    iconpath = os.path.join(iconfolder, name)
    if not os.path.exists(iconpath):
        raise NameError('No icon with that name')
    return QtGui.QIcon(iconpath)


def fileDialog(startDir:str, fmt:str, isFolder:bool, opening:bool=True) -> str:
    '''fileDialog opens a dialog to select a file for reading
    startDir is the directory to start in, e.g. r'C:\Documents'
    fmt is a string file format, e.g. 'Gcode files (*.gcode *.sbp)'
    isFolder is bool true to only open folders
    opening is true if we are opening a file, false if we are saving'''
    dialog = qtw.QFileDialog()
    dialog.setFilter(dialog.filter() | QtCore.QDir.Hidden)

    # ARE WE TALKING ABOUT FILES OR FOLDERS
    if isFolder:
        dialog.setFileMode(qtw.QFileDialog.DirectoryOnly)
    else:
        dialog.setFileMode(qtw.QFileDialog.ExistingFiles)
        
    # OPENING OR SAVING
    if opening:
        dialog.setAcceptMode(qtw.QFileDialog.AcceptOpen)
    else:
        dialog.setAcceptMode(qtw.QFileDialog.AcceptSave)

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
    
    
def formatExplorer(fn:str) -> str:
    '''Format the file name for use in subprocess.Popen(explorer)'''
    return fn.replace(r"/", "\\")

def setFolder(folder:str) -> str:
    '''Check and format the folder'''
    if os.path.exists(folder):
        startFolder = folder
    else:
        startFolder = "C:\\"
    sf = fileDialog(startFolder, '', True)
    if len(sf)>0:
        sf = sf[0]
        if os.path.exists(sf):
            return formatExplorer(sf)
    return ''

def openFolder(folder:str) -> None:
    '''Open the folder in windows explorer'''
    if not os.path.exists(folder):
        logging.debug(f'Folder does not exist: {folder}')
        return
    logging.debug(f'Opening {folder}')
    cmd = ['explorer',  formatExplorer(folder)]

    subprocess.Popen(cmd, shell=True)
        
    
class fileSetOpenRow:
    '''A row of icons and displays that lets the user set a file name using a dialog and open the folder location'''
    
    def __init__(self, parent, width:int=500, title:str='Set folder', tooltip:str='Open folder', initFolder='No folder selected') -> None:
        '''Make the display row. Return a layout'''
        self.width = width
        self.title = title
        self.saveFolder = initFolder
        self.tooltip = tooltip
        self.parent = parent
        
    def makeDisplay(self) -> qtw.QHBoxLayout:
        '''Make the display row. Return a layout'''
        saveButtBar = qtw.QToolBar()
        iconw = float(saveButtBar.iconSize().width())
        saveButtBar.setFixedWidth(iconw+4)
            
        saveButt = qtw.QToolButton()
        saveButt.setToolTip(self.title)
        saveButt.setIcon(icon('open.png'))
#         saveButt.clicked.connect(self.setSaveFolder)
        self.saveButt = saveButt
        saveButtBar.addWidget(saveButt)
        
        self.saveFolderLabel = createStatus(self.width, height=2*iconw, status=self.saveFolder)
        
        saveFolderLink = qtw.QToolButton()
        saveFolderLink.setToolTip(self.tooltip)
        saveFolderLink.setIcon(icon('link.png'))
#         saveFolderLink.clicked.connect(self.openSaveFolder)
        self.saveFolderLink = saveFolderLink
        saveLinkBar = qtw.QToolBar()
        saveLinkBar.setFixedWidth(iconw+4)
        saveLinkBar.addWidget(saveFolderLink)
        
        folderRow = qtw.QHBoxLayout()
        folderRow.addWidget(saveButtBar)
        folderRow.addWidget(self.saveFolderLabel)
        folderRow.addWidget(saveLinkBar)
        
        return folderRow
        
    def updateText(self, sf:str) -> None:
        '''set the folder name display'''
        self.saveFolderLabel.setText(sf)

#############################################


class fCheckBox(qtw.QCheckBox):
    '''This is a checkbox style for quick initialization'''
    
    def __init__(self, layout:qtw.QLayout, title:str='', tooltip:str='', checked:bool=False, **kwargs):
        super().__init__()
        self.setText(title)
        if len(tooltip)>0:
            self.setToolTip(tooltip)
        self.setChecked(checked)
        layout.addWidget(self)
        if 'func' in kwargs:
            self.stateChanged.connect(kwargs['func'])
        
class fLabel(qtw.QLabel):
    '''This is a label style for quick initialization'''
    
    def __init__(self, layout:qtw.QLayout, title:str='', style:str=''):
        super().__init__()
        self.setText(title)
        if len(style)>0:
            self.setStyleSheet(style)
        layout.addWidget(self)
        
class fRadio(qtw.QRadioButton):
    '''This is a radio button style for quick initialization'''
    
    def __init__(self, layout:qtw.QLayout, group:qtw.QButtonGroup, title:str='', tooltip:str='', i:int=0, **kwargs):
        super().__init__()
        self.setText(title)
        if len(tooltip)>0:
            self.setToolTip(tooltip)
        group.addButton(self, i)
        layout.addWidget(self)
        if 'func' in kwargs:
            self.clicked.connect(kwargs['func'])
            
class fLineEdit(qtw.QLineEdit):
    '''This is a line edit style for quick initialization'''
    
    def __init__(self, form:qtw.QFormLayout, title:str='', text:str='', tooltip:str='', **kwargs):
        super().__init__()
        self.setText(text)
        if len(tooltip)>0:
            self.setToolTip(tooltip)
        if 'func' in kwargs:
            self.editingFinished.connect(kwargs['func'])
        form.addRow(title, self)
        
class fButton(qtw.QPushButton):
    '''This is a pushbutton style for quick initialization'''
    
    def __init__(self, layout:qtw.QLayout, title:str='', tooltip:str='', **kwargs):
        super().__init__()
        self.setText(title)
        if len(tooltip)>0:
            self.setToolTip(tooltip)
        if 'func' in kwargs:
            self.clicked.connect(kwargs['func'])
        self.setAutoDefault(False)
        self.clearFocus()
        layout.addWidget(self)
    

#####################################################

# def findFileInFolder(file:str, folder:str) -> str:
#     '''findFileInFolder finds the full path name for a file in a folder
#     file is the basename string
#     folder is the folder to search in
#     this searches recursively and returns an exception if it doesn't find the file'''
#     f1 = os.path.join(folder, file)
#     if os.path.exists(f1):
#         return f1
#     for subfold in os.listdir(folder):
#         subfoldfull = os.path.join(folder, subfold)
#         if os.path.isdir(subfoldfull):
#             try:
#                 file = findFileInFolder(file, subfoldfull)
#             except:
#                 pass
#             else:
#                 return file
#     raise Exception(file+' not found')


# def findSb3Folder() -> str:
#     '''find the folder that the Sb3 program files are in'''
#     for fold in [r'C:\\Program files', r'C:\\Program files (x86)']:
#         for f in os.listdir(fold):
#             if 'ShopBot'.lower() in f.lower():
#                 return os.path.join(fold, f)
#     raise Exception('Shopbot folder not found')


# def findSb3() -> str:
#     '''find the full path name for the Sb3.exe program
#     raises an exception if it doesn't find the file'''
#     try:
#         fold = findSb3Folder()
#     except:
#         logging.warning('Sb3.exe not found')
#         return ''
#     try:
#         sb3File = findFileInFolder('Sb3.exe', fold)
#         subprocess.Popen([sb3File])
#     except:
#         raise Exception('Sb3.exe not found')
#     else:
#         return sb3File

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
    
def createStatus(width:int, height:int=70, status:str='Ready') -> qtw.QLabel:
    '''creates a section for displaying the device status'''
    status = qtw.QLabel(status)
    status.setFixedSize(width, height)
    status.setWordWrap(True)
    return status
    

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
    
    
    def createStatus(self, width:int, height:int=70, status:str='Ready') -> None:
        '''creates a section for displaying the device status'''
#         self.status = qtw.QLabel('Ready')
#         self.status.setFixedSize(width, height)
#         self.status.setWordWrap(True)
        self.status = createStatus(width, height=height, status=status)
    
    
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
                
        
#     def openSettings(self) -> None:
#         '''Open the camera settings dialog window'''
#         self.settingsDialog.show()
#         self.settingsDialog.raise_()

                
                
class QHLine(qtw.QFrame):
    def __init__(self):
        super(QHLine, self).__init__()
        self.setFrameShape(qtw.QFrame.HLine)
        self.setFrameShadow(qtw.QFrame.Sunken)