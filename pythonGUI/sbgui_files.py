#!/usr/bin/env python
'''Shopbot GUI file handling functions. Refers to top box in GUI.'''


from PyQt5 import QtGui
import PyQt5.QtWidgets as qtw
import os, sys
import subprocess
import time
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging

# currentdir = os.path.dirname(os.path.realpath(__file__))
# sys.path.append(currentdir)
# sys.path.append(os.path.join(currentdir, 'icons'))

from config import cfg
from sbgui_general import fileDialog, connectBox, icon

__author__ = "Leanne Friedrich"
__copyright__ = "This data is publicly available according to the NIST statements of copyright, fair use and licensing; see https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software"
__credits__ = ["Leanne Friedrich"]
__license__ = "MIT"
__version__ = "1.0.4"
__maintainer__ = "Leanne Friedrich"
__email__ = "Leanne.Friedrich@nist.gov"
__status__ = "Development"

INITSAVEFOLDER = os.path.abspath(cfg.vid)
if not os.path.exists(INITSAVEFOLDER):
    INITSAVEFOLDER = r'C:\\'



###############################################################

def formatExplorer(fn:str) -> str:
    '''Format the file name for use in subprocess.Popen(explorer)'''
    return fn.replace(r"/", "\\")

class fileSettingsBox(qtw.QWidget):
    '''This opens a window that holds settings about logging for files.'''
    
    
    def __init__(self, parent:connectBox):
        '''parent is the connectBox that this settings dialog belongs to.'''
        
        super().__init__(parent)  
        self.parent = parent
        
        layout = QtGui.QVBoxLayout()
        
        self.newFolderCheck = qtw.QCheckBox('Create new folder for each sample')
        self.newFolderCheck.setChecked(True)
        self.newFolderCheck.clicked.connect(self.changeNewFolder)
        layout.addWidget(self.newFolderCheck)
        
        self.iDateRow = qtw.QVBoxLayout()
        self.iDateLabel = qtw.QLabel('Date')
        self.iDateRow.addWidget(self.iDateLabel)
        self.iDate1 = qtw.QRadioButton('Include date in sample folder name')
        self.iDate2 = qtw.QRadioButton('Include date in sample subfolder name')
        self.iDate3 = qtw.QRadioButton('Do not include date')
        self.iDateGroup = qtw.QButtonGroup()
        self.iDateList = [self.iDate1, self.iDate2, self.iDate3]
        for i,b in enumerate(self.iDateList):
            self.iDateGroup.addButton(b, i)
            self.iDateRow.addWidget(b)
        self.iDate1.setChecked(True)
        layout.addLayout(self.iDateRow)
        
        self.iSBRow = qtw.QVBoxLayout()
        self.iSBLabel = qtw.QLabel('SB file name')
        self.iSBRow.addWidget(self.iSBLabel)
        self.iSB1 = qtw.QRadioButton('Include SB file in sample folder name')
        self.iSB2 = qtw.QRadioButton('Include SB file in sample subfolder name')
        self.iSB3 = qtw.QRadioButton('Do not include SB file')
        self.iSBGroup = qtw.QButtonGroup()
        self.iSBList = [self.iSB1, self.iSB2, self.iSB3]
        for i,b in enumerate(self.iSBList):
            self.iSBGroup.addButton(b, i)
            self.iSBRow.addWidget(b)
        self.iSB3.setChecked(True)
        layout.addLayout(self.iSBRow)
        self.setLayout(layout)

        
    def changeNewFolder(self):
        '''When the create folder box is checked, enable or disable the related boxes'''
        check = self.newFolderCheck.isChecked()
        for l in [self.iDateList, self.iSBList, [self.iDateLabel, self.iSBLabel]]:
            for box in l:
                box.setEnabled(check)

class fileBox(connectBox):
    '''this is a gui box for managing files. It goes at the top of the window'''
    
    def __init__(self, sbWin:qtw.QMainWindow):
        super(fileBox, self).__init__()
        self.bTitle = 'Export'
        self.sbWin = sbWin
        
        self.successLayout()
        
    def successLayout(self):
        '''This is the main layout for file management. There is no fail layout'''
        self.settingsBox = fileSettingsBox(self)
        self.resetLayout()
        self.layout = qtw.QVBoxLayout()  
        self.setTitle('Export settings')
        
        self.saveButtBar = qtw.QToolBar()
        iconw = float(self.saveButtBar.iconSize().width())
        self.saveButtBar.setFixedWidth(iconw+4)
        
        
#         self.saveLabel = qtw.QLabel('Export to')
#         self.saveLabel.setFixedSize(100, iconw)
            
        self.saveButt = qtw.QToolButton()
        self.saveButt.setToolTip('Set video folder')
        self.saveButt.setIcon(icon('open.png'))
        self.saveButt.clicked.connect(self.setSaveFolder)
        self.saveButtBar.addWidget(self.saveButt)
        
        
        self.saveFolder = INITSAVEFOLDER
        self.saveFolderLabel = qtw.QLabel(self.saveFolder)
        self.saveFolderLabel.setFixedHeight(iconw)
        
        self.saveFolderLink = qtw.QToolButton()
        self.saveFolderLink.setToolTip('Open video folder')
        self.saveFolderLink.setIcon(icon('link.png'))
        self.saveFolderLink.clicked.connect(self.openSaveFolder)
        self.saveLinkBar = qtw.QToolBar()
        self.saveLinkBar.setFixedWidth(iconw+4)
        self.saveLinkBar.addWidget(self.saveFolderLink)
        
        self.folderRow = qtw.QHBoxLayout()
#         self.folderRow.addWidget(self.saveLabel)
        self.folderRow.addWidget(self.saveButtBar)
        self.folderRow.addWidget(self.saveFolderLabel)
        self.folderRow.addWidget(self.saveLinkBar)

        self.appendName = qtw.QLineEdit()
        self.appendName.setText('')
        self.appendName.setFixedHeight(iconw)
        self.appendName.setToolTip('This gets added to the file names')
        
        appendForm = qtw.QFormLayout()
        appendForm.addRow('Export to', self.folderRow)
        appendForm.addRow('Sample name', self.appendName)
        appendForm.setSpacing(5)
        
        for camBox in self.sbWin.camBoxes:
            appendForm.addRow(qtw.QLabel(camBox.camObj.cameraName), camBox.camInclude)
            
        self.layout.addItem(appendForm)
        self.layout.setSpacing(5)
       
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
                self.saveFolderLabel.setText(self.saveFolder)
            
    def openSaveFolder(self) -> None:
        '''Open the save folder in windows explorer'''
        
        if not os.path.exists(self.saveFolder):
            logging.debug(f'Save folder does not exist: {self.saveFolder}')
            return
        logging.debug(f'Opening {self.saveFolder}')
        cmd = ['explorer',  formatExplorer(self.saveFolder)]
        
        subprocess.Popen(cmd, shell=True)
        
    def newFile(self) -> Tuple[str, str]:
        '''Get a filename and folder for a new file. First return is the sample name. Second is the folder name. If subfolder creation is off, just return the save folder. If it is on, create subfolders and return the subfolder.'''
        
        # determine the folder to save to
        folder = self.saveFolder
        if not os.path.exists(self.saveFolder):
            # open a save dialog if the folder does not exist
            self.setSaveFolder()
        if not os.path.exists(self.saveFolder):
            self.updateStatus('Invalid folder name. File not saved.', True)
            raise NameError('Invalid folder name. File not saved.')
            
        t1 = self.appendName.text()
        if self.settingsBox.newFolderCheck.isChecked():
            # use subfolder
            subfolder = t1
            subsubfolder = ''
            
            # add date?
            bid = self.settingsBox.iDateGroup.checkedId()
            if bid==0 or bid==1:
                # use date
                date = time.strftime('%y%m%d')
                if bid==0:
                    # include date in folder name
                    subfolder = subfolder+'_'+date
                elif bid==1:
                    # make date subfolder
                    subsubfolder = subsubfolder+'_'+date
                    
            # add SB?
            sb = self.settingsBox.iSBGroup.checkedId()
            if (sb==0 or sb==1) and self.sbWin.sbBox.runningSBP:
                # add SB is selected in settings, and we're running a SB file
                sbname = os.path.basename(self.sbWin.sbBox.sbpName)
                sbname = os.path.splitext(sbname)[0]
                if sb==0:
                    subfolder = subfolder+'_'+sbname
                elif sb==1:
                    subsubfolder = subsubfolder+'_'+sbname
                    
            subfolder = removeUnderScore(subfolder)
            subsubfolder = removeUnderScore(subsubfolder)
                    
            if len(subfolder)>0:
                # make the subfolder if it doesn't already exist
                subfolder = os.path.join(folder, subfolder)
                if not os.path.exists(subfolder):
                    os.makedirs(subfolder, exist_ok=True)
                folder = subfolder
            if len(subsubfolder)>0:
                # make the subsubfolder if it doesn't already exist
                # if subfolder is empty, subsubfolder becomes the subfolder
                subsubfolder = os.path.join(folder, subsubfolder)
                if not os.path.exists(subsubfolder):
                    os.makedirs(subsubfolder, exist_ok=True)
                folder = subsubfolder # return the subsubfolder 
                
                
        if self.sbWin.sbBox.runningSBP:
            sbname = os.path.basename(self.sbWin.sbBox.sbpName)
            filename = os.path.splitext(sbname)[0]+'_'
        else:
            filename = ""
            
        t1 = t1 + '_' + filename
        t1 = removeUnderScore(t1)
        return folder, t1
                
def removeUnderScore(s:str) -> str:
    '''remove the underscore from the front of a string'''
    if len(s)==0:
        return s
    while s[0]=='_':
        if len(s)>1:
            s = s[1:]
        else:
            s = ''
            return s
    while s[-1]=='_':
        if len(s)>1:
            s = s[0:-1]
        else:
            s = ''
            return s
    return s
