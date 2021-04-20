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

        
def un(*args, separator:str='_') -> str:
    '''Give an underscore if every string in the args is longer than 0. Change the given separator with kwargs'''
    for arg in args:
        if len(arg)==0:
            return ''
    return separator

def riffle(*args, separator:str='_') -> str:
    '''Given a list of strings, put all the non-empty strings together in order, with separator in between'''
    s = ''
    for arg in args:
        if len(arg)>0:
            s = s + arg + separator
    if len(s)>0 and len(separator)>0:
        s = s[0:-len(separator)]
    return s

                
# def removeUnderScore(s:str) -> str:
#     '''remove the underscore from the front of a string'''
#     if len(s)==0:
#         return s
#     while s[0]=='_':
#         if len(s)>1:
#             s = s[1:]
#         else:
#             s = ''
#             return s
#     while s[-1]=='_':
#         if len(s)>1:
#             s = s[0:-1]
#         else:
#             s = ''
#             return s
#     return s

#----------------------------------------------------

class fileSettingsBox(qtw.QWidget):
    '''This opens a window that holds settings about logging for files.'''
    
    
    def __init__(self, parent:connectBox):
        '''parent is the connectBox that this settings dialog belongs to.'''
        
        super().__init__(parent)  
        self.parent = parent
        
        layout = QtGui.QVBoxLayout()
        
        labelStyle = 'font-weight:bold; color:#31698f'
        
        # folder creation
        self.newFolderCheck = qtw.QCheckBox('Create subfolders')
        self.newFolderCheck.setChecked(True)
        self.newFolderCheck.stateChanged.connect(self.changeNewFolder)
        layout.addWidget(self.newFolderCheck)
                
        # include sample
        self.iSampleRow = qtw.QVBoxLayout()
        iSampleLabel = qtw.QLabel('Include sample:')
        iSampleLabel.setStyleSheet(labelStyle)
        self.iSampleRow.addWidget(iSampleLabel)
        self.iSampleFileCheck = qtw.QCheckBox('In file name')
        self.iSampleFileCheck.setToolTip('Include the sample in the file name')
        self.iSampleFileCheck.setChecked(True)
        self.iSampleRow.addWidget(self.iSampleFileCheck)
        self.iSampleFolderCheck = qtw.QCheckBox('In folder name')
        self.iSampleFolderCheck.setToolTip('Include the sample in the file name')
        self.iSampleFolderCheck.setChecked(True)
        self.iSampleRow.addWidget(self.iSampleFolderCheck)
        layout.addLayout(self.iSampleRow)
    
        
        # include date
        self.iDateRow = qtw.QVBoxLayout()
        iDateLabel = qtw.QLabel('Include date:')
        iDateLabel.setStyleSheet(labelStyle)
        self.iDateRow.addWidget(iDateLabel)
        self.iDate1 = qtw.QRadioButton('In sample folder name')
        self.iDate1.setToolTip('Append the date to the name of the folder for this sample')
        self.iDate1.setChecked(True)
        self.iDate2 = qtw.QRadioButton('As sample subfolder name')
        self.iDate2.setToolTip('Create a subfolder inside of the sample folder with the date')
        self.iDate3 = qtw.QRadioButton('In no folder name')
        self.iDate3.setToolTip('Do not create a specific folder for this date')
        self.iDateGroup = qtw.QButtonGroup()
        self.iDateList = [self.iDate1, self.iDate2, self.iDate3]
        for i,b in enumerate(self.iDateList):
            self.iDateGroup.addButton(b, i)
            self.iDateRow.addWidget(b)
            b.clicked.connect(self.checkFormats)
        layout.addLayout(self.iDateRow)
        
        # include time
        self.iTimeRow = qtw.QVBoxLayout()
        iTimeLabel = qtw.QLabel('Include time:')
        iTimeLabel.setStyleSheet(labelStyle)
        self.iTimeRow.addWidget(iTimeLabel)
        self.iTimeCheck = qtw.QCheckBox('In file name')
        self.iTimeCheck.setToolTip('Include the time in the file name')
        self.iTimeCheck.setChecked(True)
        self.iTimeCheck.clicked.connect(self.checkFormats)
        self.iTimeRow.addWidget(self.iTimeCheck)
        layout.addLayout(self.iTimeRow)
        
        # include Shopbot file name
        self.iSBRow = qtw.QVBoxLayout()
        iSBLabel = qtw.QLabel('Include SB file name:')
        iSBLabel.setStyleSheet(labelStyle)
        self.iSBRow.addWidget(iSBLabel)
        self.iSB1 = qtw.QRadioButton('In sample folder name')
        self.iSB2 = qtw.QRadioButton('As sample subfolder name')
        self.iSB3 = qtw.QRadioButton('In no folder name')
        self.iSB3.setChecked(True)
        self.iSBGroup = qtw.QButtonGroup()
        self.iSBList = [self.iSB1, self.iSB2, self.iSB3]
        for i,b in enumerate(self.iSBList):
            self.iSBGroup.addButton(b, i)
            self.iSBRow.addWidget(b)
            b.clicked.connect(self.checkFormats)
        self.iSBCheck = qtw.QCheckBox('In file name')
        self.iSBCheck.setChecked(True)
        self.iSBRow.addWidget(self.iSBCheck)
        layout.addLayout(self.iSBRow)

        # formatting
        formatLabel = qtw.QLabel('Formatting options:')
        formatLabel.setStyleSheet(labelStyle)
        layout.addWidget(formatLabel)
        fileForm = qtw.QFormLayout()
        self.dateFormatBox = qtw.QLineEdit()
        self.dateFormatBox.setText('%y%m%d')
        self.dateFormatBox.setToolTip('Format for date: use Python strftime format (https://strftime.org/)')
        self.dateFormatBox.editingFinished.connect(self.checkFormats)
        fileForm.addRow('Date format', self.dateFormatBox)
        self.timeFormatBox = qtw.QLineEdit()
        self.timeFormatBox.setText('%y%m%d_%H%M%S')
        self.timeFormatBox.setToolTip('Format for time: use Python strftime format (https://strftime.org/)')
        self.timeFormatBox.editingFinished.connect(self.checkFormats)
        fileForm.addRow('Time format', self.timeFormatBox)
        self.duplicateFormatBox = qtw.QLineEdit()
        self.duplicateFormatBox.setText("{0:0=3d}")
        self.duplicateFormatBox.setToolTip('Format for number to add if file already exists. Use python string format')
        self.duplicateFormatBox.editingFinished.connect(self.checkFormats)
        fileForm.addRow('Duplicate suffix', self.duplicateFormatBox)
        self.separatorBox = qtw.QLineEdit()
        self.separatorBox.setText('_')
        self.separatorBox.setToolTip('Put this character between each part of the file name')
        self.separatorBox
        fileForm.addRow('Separator', self.separatorBox)
        layout.addLayout(fileForm)

        self.status = qtw.QLabel('')
        self.status.setFixedWidth(500)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        
        for b in (self.iDateList + self.iSBList):
            b.clicked.connect(self.checkFormats)
        for b in [self.iSampleFileCheck, self.iSampleFolderCheck, self.iSBCheck]:
            b.stateChanged.connect(self.changeNewFolder)
        for b in [self.dateFormatBox, self.timeFormatBox, self.duplicateFormatBox, self.separatorBox]:
            b.editingFinished.connect(self.checkFormats)

        self.setLayout(layout)

        
    def changeNewFolder(self) -> None:
        '''When the create folder box is checked, enable or disable the related boxes'''
        check = self.newFolderCheck.isChecked()
        for l in [self.iDateList, self.iSBList, [self.iSampleFolderCheck, self.dateFormatBox]]:
            for box in l:
                box.setEnabled(check)
        self.checkFormats()
                
    def dateFormat(self) -> str:
        '''Get the date format'''
        return self.dateFormatBox.text()
    
    def date(self) -> str:
        '''Get the current date. This should only be used for folders'''
        bid = self.iDateGroup.checkedId()
        if bid in [0,1]:
            return time.strftime(self.dateFormat())
        else:
            return ''
    
    def timeFormat(self) -> str:
        '''Get the time format'''
        return self.timeFormatBox.text()
    
    def time(self) -> str:
        '''Get the current time. This should only be used for files.'''
        if self.iTimeCheck.isChecked():
            return time.strftime(self.timeFormat())
        else:
            return ''
    
    def dupFormat(self) -> str:
        '''Get the duplicate file format'''
        return self.duplicateFormatBox.text()
    
    def dupNum(self, num:float) -> str:
        dup = self.dupFormat()
        if len(dup)==0:
            # if the duplicate format is empty, use this default
            dup = "{0:0=3d}"
        return dup.format(num)
    
    def sep(self) -> str:
        return self.separatorBox.text()
                
    #---------------------
    # error checking
                
    def warnBox(self, box:qtw.QWidget, status:str) -> str:
        '''Set the widget to warning status if the status is not empty'''
        if len(status)>0:
            logging.warning(status)
            box.setStyleSheet("background-color: red;")
        else:
            box.setStyleSheet("")
        return status
                
    def checkDateFormat(self) -> str:
        '''check if the date format is reasonable based on a list of time string formats'''
        status = ''
        secondStrings = ['%S', '%-S', '%f', '%c', '%X']
        timeStrings = ['%H', '%-H', '%I', '%-I', '%p', '%M', '%-M', '%z', '%Z']+secondStrings
        dateformat = self.dateFormat()
        dcheck = self.iDateGroup.checkedId()
        timeError = 'The time is in the date format box. This might cause many folders to be generated.'
        if dcheck in [0,1]:
            for s in timeStrings:
                if s in dateformat:
                    if not timeError in status:
                        status = status + timeError
                    status = status+ f' Consider removing {s} from date format.'
        # if there is a warning, turn the box red and log the warning
        return self.warnBox(self.dateFormatBox, status)
    
    def checkTimeFormat(self) -> str:
        '''Check if the time format is reasonable based on a list of seconds string formats'''
        # check if the date format is reasonable
        timeformat = self.timeFormat()
        secondStrings = ['%S', '%-S', '%f', '%c', '%X']
        if len(timeformat)==0:
            status = 'Time string is empty. This may generate many duplicate file names.'
        else:
            timeError = f'There are no seconds in the time string. This may generate many duplicate file names. Consder adding one of the following: {secondStrings}'
            status = timeError
            i = 0
            while i<len(secondStrings):
                s = secondStrings[i]
                if s in timeformat:
                    i = len(secondStrings)
                    status = ''
            # if there is a warning, turn the box red and log the warning
        return self.warnBox(self.timeFormatBox, status)
    
    def checkDuplicateFormat(self) -> str:
        '''Check that the duplicate file formatting is valid'''
        dupformat = self.dupFormat()
        if len(dupformat)==0:
            status = 'Duplicate format is empty. Value will default to "{0:0=3d}".'
        else:
            status = ''
        return self.warnBox(self.duplicateFormatBox, status)
    
    def checkSeparator(self) -> str:
        '''Check that the separator is valid'''
        sep = self.sep()
        if len(sep)==0:
            status = 'Separator is empty. File names may be confusing.'
        else:
            status = ''
        return self.warnBox(self.separatorBox, status)
        
    
    def checkFormats(self) -> None:
        '''When the date and time formats are changed, check to make sure they make sense'''

        status = riffle(self.checkDateFormat(), self.checkTimeFormat(), self.checkDuplicateFormat(), self.checkSeparator(), separator='\n')
        if len(status)==0:
            status = 'File format: '+self.parent.newFile('[DEVICE]', '[EXT]', demoMode=True) # create a dummy status showing file format
        self.status.setText(status)
        
        
#------------------------------------------------------------
        

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
        self.folderRow.addWidget(self.saveButtBar)
        self.folderRow.addWidget(self.saveFolderLabel)
        self.folderRow.addWidget(self.saveLinkBar)

        self.appendName = qtw.QLineEdit()
        self.appendName.setText('')
        self.appendName.setFixedHeight(iconw)
        self.appendName.setToolTip('This gets added to the file names')
        self.appendName.textChanged.connect(self.settingsBox.checkFormats)
        
        appendForm = qtw.QFormLayout()
        appendForm.addRow('Export to', self.folderRow)
        appendForm.addRow('Sample name', self.appendName)
        appendForm.setSpacing(5)
        
        for camBox in self.sbWin.camBoxes:
            appendForm.addRow(qtw.QLabel(camBox.camObj.cameraName), camBox.camInclude)
            
        self.layout.addItem(appendForm)
        self.layout.setSpacing(5)
       
        self.setLayout(self.layout)

        
        
    #-------------------------------------------
    
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
                self.settingsBox.checkFormats()
            
    def openSaveFolder(self) -> None:
        '''Open the save folder in windows explorer'''
        
        if not os.path.exists(self.saveFolder):
            logging.debug(f'Save folder does not exist: {self.saveFolder}')
            return
        logging.debug(f'Opening {self.saveFolder}')
        cmd = ['explorer',  formatExplorer(self.saveFolder)]
        
        subprocess.Popen(cmd, shell=True)
        
    #-------------------------------------------
    
    def sbBase(self, file:bool, demoMode:bool=False) -> str:
        '''Get the base name with no extension of the shopbot file. If file=True, we are getting the name for a file. If false, we're getting it for a folder.'''
        if file and not self.settingsBox.iSBCheck.isChecked():
            # if we're getting it for a file and we don't want to include the shopbot name in the file, return empty
            return ''
        if not self.sbWin.sbBox.runningSBP and not demoMode:
            # if we're not running a shopbot file, return empty
            return ''
        # get the path name
        sbpPath = self.sbWin.sbBox.sbpName
        if os.path.exists(sbpPath):
            return os.path.splitext(os.path.basename(sbpPath))[0]
        else:
            return ''
        
    def sample(self, file:bool) -> str:
        '''Get the sample name. If file=True, we are getting the name for a file. If false, we're getting it for a folder.'''
        if file and not self.settingsBox.iSampleFileCheck.isChecked():
            return ''
        if not file and not self.settingsBox.iSampleFolderCheck.isChecked():
            return ''
        return self.appendName.text()
            
        
    def makeSubFolders(self, demoMode:bool=False) -> str:
        '''Make subfolders for this file. Returns the folder that the file goes into. demoMode=True to not export folders'''
        # make subfolders
        
        # determine the folder to save to
        folder = self.saveFolder
        if not os.path.exists(self.saveFolder):
            # open a save dialog if the folder does not exist
            self.setSaveFolder()
        if not os.path.exists(self.saveFolder):
            self.updateStatus('Invalid folder name. File not saved.', True)
            raise NameError('Invalid folder name. File not saved.')

        sep = self.settingsBox.sep()
        
        if self.settingsBox.newFolderCheck.isChecked():
            # use subfolder
            subfolder = self.sample(False)
            subsubfolder = ''
            
            # add date?
            bid = self.settingsBox.iDateGroup.checkedId()
            if bid==0 or bid==1:
                # use date
                date = self.settingsBox.date()
                if bid==0:
                    # include date in folder name
                    subfolder = riffle(subfolder, date, separator=sep)
                elif bid==1:
                    # make date subfolder
                    subsubfolder = riffle(subsubfolder, date, separator=sep)
                    
            # add SB?
            sb = self.settingsBox.iSBGroup.checkedId()
            if (sb==0 or sb==1) and (self.sbWin.sbBox.runningSBP or demoMode):
                # add SB is selected in settings, and we're running a SB file
                if sb==0:
                    subfolder = riffle(subfolder, self.sbBase(False, demoMode=demoMode), separator=sep)
                elif sb==1:
                    subsubfolder = riffle(subsubfolder, self.sbBase(False, demoMode=demoMode), separator=sep)

            if len(subfolder)>0:
                # make the subfolder if it doesn't already exist
                subfolder = os.path.join(folder, subfolder)
                if not os.path.exists(subfolder) and not demoMode:
                    os.makedirs(subfolder, exist_ok=True)
                folder = subfolder
            if len(subsubfolder)>0:
                # make the subsubfolder if it doesn't already exist
                # if subfolder is empty, subsubfolder becomes the subfolder
                subsubfolder = os.path.join(folder, subsubfolder)
                if not os.path.exists(subsubfolder) and not demoMode:
                    os.makedirs(subsubfolder, exist_ok=True)
                folder = subsubfolder # return the subsubfolder 
        
        return folder
            
        
        
    def newFile(self, deviceName:str, ext:str, demoMode:bool=False) -> Tuple[str, str]:
        '''Get a filename and folder for a new file. First return is the sample name. Second is the folder name. If subfolder creation is off, just return the save folder. If it is on, create subfolders and return the subfolder. The device name indicates what device is generating data for this file. ext is the extension'''
        
        folder = self.makeSubFolders(demoMode=demoMode)
        

        # entries for files
        sbBase = self.sbBase(True, demoMode=demoMode)
        sample = self.sample(True)
        time = self.settingsBox.time()
        sep = self.settingsBox.sep()
        baseBare = riffle(sbBase, deviceName, sample, time, separator=sep) # file name, no path, no extension
        
        if not ext[0]=='.':
            ext = '.'+ext
        fullfn = os.path.join(folder, baseBare + ext)
        
        filenum = 1
        # if there is already a file with this name, add a number (e.g. _002) to the end
        while os.path.exists(fullfn):
            num = self.settingsBox.dupNum(filenum)
            fullfn = os.path.join(folder, riffle(baseBare, num, separator=sep) + ext)
            filenum+=1   
        
        return fullfn

