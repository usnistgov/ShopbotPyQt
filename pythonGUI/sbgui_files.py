#!/usr/bin/env python
'''Shopbot GUI file handling functions. Refers to top box in GUI.'''

# external packages
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QButtonGroup, QFormLayout, QMainWindow, QLineEdit, QLabel
import os, sys
import subprocess
import time
import datetime
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging

# local packages
from config import cfg
from sbgui_general import *


###############################################################

        
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


#----------------------------------------------------


        

class fileSettingsBox(QWidget):
    '''This opens a window that holds settings about logging for files.'''
    
    
    def __init__(self, parent:connectBox):
        '''parent is the connectBox that this settings dialog belongs to.'''
        
        super().__init__(parent)  
        self.parent = parent
        
        layout = QVBoxLayout()
        
        labelStyle = 'font-weight:bold; color:#31698f'
        
        # folder creation
        self.newFolderCheck = fCheckBox(layout, title='Create folders'
                                        , tooltip='Create folders for samples, dates'
                                        , checked=cfg.files.createSubfolders
                                        , func=self.changeNewFolder)
                
        # include sample
        iSampleRow = QVBoxLayout()
        fLabel(iSampleRow, title='Include sample:', style=labelStyle)
        self.iSampleFileCheck = fCheckBox(iSampleRow, title='In file name'
                                          , tooltip = 'Include the sample in the file name'
                                          , checked=cfg.files.includeSampleInFile)   
        self.iSampleFolderCheck = fCheckBox(iSampleRow, title='In folder name'
                                            , tooltip='Include the sample in the file name'
                                            , checked=cfg.files.includeSampleInFolder)
        layout.addLayout(iSampleRow)
    
        
        # include date
        iDateRow = QVBoxLayout()
        self.iDateGroup = QButtonGroup()
        fLabel(iDateRow, title='Include date:', style=labelStyle)
        self.iDate1 = fRadio(iDateRow, self.iDateGroup, title='In sample folder name'
                             , tooltip='Append the date to the name of the folder for this sample'
                             , func=self.checkFormats, i=0)
        self.iDate2 = fRadio(iDateRow, self.iDateGroup, title='As sample subfolder name'
                             , tooltip='Create a subfolder inside of the sample folder with the date'
                             , func=self.checkFormats, i=1)
        self.iDate3 = fRadio(iDateRow, self.iDateGroup, title='In no folder name'
                             , tooltip='Do not create a specific folder for this date'
                             , func=self.checkFormats, i=2)
        self.iDateList = [self.iDate1, self.iDate2, self.iDate3]
        self.iDateList[cfg.files.includeDateRadio].setChecked(True)
        layout.addLayout(iDateRow)
        
        # include time
        iTimeRow = QVBoxLayout()
        fLabel(iTimeRow, title='Include time:', style=labelStyle)
        self.iTimeCheck = fCheckBox(iTimeRow, title='In file name'
                                    , tooltip = 'Include the time in the file name'
                                    , checked=cfg.files.includeTimeInFile
                                    , func=self.checkFormats)
        layout.addLayout(iTimeRow)
        
        # include Shopbot file name
        iSBRow = QVBoxLayout()
        self.iSBGroup = QButtonGroup()
        fLabel(iSBRow, title='Include SB file name:', style=labelStyle)
        self.iSB1 = fRadio(iSBRow, self.iSBGroup, title='In sample folder name'
                           , tooltip='Append the shopbot file name to the name of the folder for this sample'
                           , func=self.checkFormats, i=0)
        self.iSB2 = fRadio(iSBRow, self.iSBGroup, title='As sample subfolder name'
                           , tooltip='Create a subfolder inside of the sample folder with the shopbot file name'
                           , func=self.checkFormats, i=1)
        self.iSB3 = fRadio(iSBRow, self.iSBGroup, title='In no folder name'
                           , tooltip='Do not create a specific folder for this shopbot file name '
                           , func=self.checkFormats, i=2)
        self.iSBList = [self.iSB1, self.iSB2, self.iSB3]
        self.iSBList[cfg.files.includeSBRadio].setChecked(True)
        self.iSBCheck = fCheckBox(iSBRow, title='In file name'
                                  , tooltip='Include the shopbot file name in exported file names'
                                  , checked=cfg.files.includeSBInFile)
        layout.addLayout(iSBRow)

        # formatting
        fLabel(layout, title='Formatting options:', style=labelStyle)
        fileForm = QFormLayout()
        w = 300
        self.dateFormatBox = fLineEdit(fileForm, title='Date format'
                                       , text=cfg.files.dateFormat
                                       , tooltip='Format for date: use Python strftime format (https://strftime.org/)'
                                       , func=self.checkFormats
                                      , width=w)
        self.timeFormatBox = fLineEdit(fileForm, title='Time format', text=cfg.files.timeFormat
                                       , tooltip='Format for time: use Python strftime format (https://strftime.org/)'
                                       , func=self.checkFormats
                                      , width=w)
        self.duplicateFormatBox = fLineEdit(fileForm, title='Duplicate suffix'
                                            , text=cfg.files.duplicateFormat
                                            , tooltip='Format for number to add if file already exists. Use python string format'
                                            , func=self.checkFormats
                                           , width=w)
        self.separatorBox = fLineEdit(fileForm, title='Separator'
                                      , text=cfg.files.separator
                                      , tooltip='Format for number to add if file already exists. Use python string format'
                                      , func=self.checkFormats
                                     , width=w)
        layout.addLayout(fileForm)

        self.status = createStatus(500, height=200, status='')
        layout.addWidget(self.status)
        
        for b in (self.iDateList + self.iSBList):
            b.clicked.connect(self.checkFormats)
        for b in [self.iSampleFileCheck, self.iSampleFolderCheck, self.iSBCheck]:
            b.stateChanged.connect(self.changeNewFolder)
        self.setLayout(layout)
        self.changeNewFolder()
        
    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        cfg1.files.createSubfolders = self.newFolderCheck.isChecked()
        cfg1.files.includeSampleInFile = self.iSampleFileCheck.isChecked()
        cfg1.files.includeSampleInFolder = self.iSampleFolderCheck.isChecked()
        cfg1.files.includeDateRadio = self.iDateGroup.checkedId()
        cfg1.files.includeTimeInFile = self.iTimeCheck.isChecked()
        cfg1.files.includeSBRadio = self.iSBGroup.checkedId()
        cfg1.files.includeSBInFile = self.iSBCheck.isChecked()
        cfg1.files.dateFormat = self.dateFormat()
        cfg1.files.timeFormat = self.timeFormat()
        cfg1.files.duplicateFormat = self.dupFormat()
        cfg1.files.separator = self.sep()
        return cfg1
    
    def loadConfig(self, cfg1) -> None:
        '''load a configuration from config Box object'''
        self.newFolderCheck.setChecked(cfg1.files.createSubfolders)
        self.iSampleFileCheck.setChecked(cfg1.files.includeSampleInFile)
        self.iSampleFolderCheck.setChecked(cfg1.files.includeSampleInFolder)
        self.iDateList[cfg1.files.includeDateRadio].setChecked(True)
        self.iTimeCheck.setChecked(cfg1.files.includeTimeInFile)
        self.iSBList[cfg1.files.includeSBRadio].setChecked(True)
        self.iSBCheck.setChecked(cfg1.files.includeSBInFile)
        self.dateFormatBox.setText(cfg1.files.dateFormat)
        self.timeFormatBox.setText(cfg1.files.timeFormat)
        self.duplicateFormatBox.setText(cfg1.files.duplicateFormat)
        self.separatorBox.setText(cfg1.files.separator)
        self.checkFormats()
        self.changeNewFolder()
        
    def changeNewFolder(self) -> None:
        '''When the create folder box is checked, enable or disable the related boxes'''
        check = self.newFolderCheck.isChecked()
        for l in [self.iDateList, self.iSBList, [self.iSampleFolderCheck, self.dateFormatBox]]:
            for box in l:
                box.setEnabled(check)
        try:
            self.checkFormats()
        except:
            pass
                
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
#             return time.strftime(self.timeFormat())
            tf = self.timeFormat()
            dt = datetime.datetime.now().strftime(tf)
            if tf[-1]=='f':
                dt = dt[:-5]
            return dt
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
                
    def warnBox(self, box:QWidget, status:str) -> str:
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
        secondStrings = ['%S', '%-S', '%c', '%f', '%X']
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
            newfile = self.parent.newFile('[DEVICE]', '[EXT]', demoMode=True)
            status = f'File format: {newfile}' # create a dummy status showing file format
        self.status.setText(status)
        
        
#------------------------------------------------------------
        

class fileBox(connectBox):
    '''this is a gui box for managing files. It goes at the top of the window'''
    
    def __init__(self, sbWin:QMainWindow, connect:bool=True):
        super(fileBox, self).__init__()
        self.bTitle = 'Export'
        self.sbWin = sbWin
        if connect:
            self.connect()
            
    def connect(self) -> None:
        '''load configs and display layout'''
        self.settingsBox = fileSettingsBox(self)
        self.successLayout()
        self.loadConfig(cfg)
        
        
    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        cfg1.files.save = self.saveFolder
        cfg1.files.tag = self.appendName.text()
        cfg1 = self.settingsBox.saveConfig(cfg1)
        return cfg1
    
    def loadConfigMain(self, cfg1)-> None:
        '''load settings for the main window'''
        self.saveFolder = checkPath(cfg1.files.save)
        self.appendName.setText(cfg1.files.tag)
    
    def loadConfig(self, cfg1):
        '''load settings from a config Box object'''
        self.loadConfigMain(cfg1)
        self.settingsBox.loadConfig(cfg1)
        
    def successLayout(self):
        '''This is the main layout for file management. There is no fail layout'''
        self.resetLayout()
        self.layout = QVBoxLayout()  
        self.setTitle('Export settings')
        
        appendForm = QFormLayout()
        appendForm.setSpacing(5)
        self.folderRow = fileSetOpenRow(width=450, title='Set video folder', 
                                   initFolder=cfg.files.save, 
                                   tooltip='Open video folder',
                                  setFunc = self.setSaveFolder,
                                   openFunc = self.openSaveFolder
                                  )
        appendForm.addRow('Export to', self.folderRow)
        self.appendName = fLineEdit(appendForm, title='Sample name', text=cfg.files.tag, tooltip='This gets added to the file names', func=self.checkFormats)
        
        self.layout.addItem(appendForm)

        qhl = QVBoxLayout()
        qhl.addLayout(self.sbWin.camBoxes.autoSaveLayout())
        qhl.addItem(self.sbWin.flagBox)
        qhl.setSpacing(15)
        
        self.layout.addItem(qhl)
        
        self.layout.setSpacing(5)
       
        self.setLayout(self.layout)
        

    def checkFormats(self) -> None:
        if hasattr(self, 'settingsBox'):
            self.settingsBox.checkFormats()
        
        
    #-------------------------------------------
    
    def setSaveFolder(self) -> None:
        '''set the folder to save all the files we generate from the whole gui'''
        self.saveFolder = setFolder(self.saveFolder)        
        logging.info('Changed save folder to %s' % self.saveFolder)
        self.fsor.updateText(self.saveFolder)
        self.settingsBox.checkFormats()
            
    def openSaveFolder(self) -> None:
        '''Open the save folder in windows explorer'''
        openFolder(self.saveFolder)
        
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
        sbpPath = self.sbWin.sbBox.sbpName()
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

