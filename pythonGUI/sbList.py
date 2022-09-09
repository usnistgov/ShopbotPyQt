#!/usr/bin/env python
'''Shopbot GUI functions for list of shopbot files'''

# external packages
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAbstractItemView, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton
import os, sys
import winreg
import subprocess
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import csv
import re
import time
import win32gui, win32api, win32con

# local packages
# import Fluigent.SDK as fgt
from config import cfg
from general import *
from sbprint import *
from flags import *


##################################################

def reconnect(signal, newhandler=None, oldhandler=None):        
    try:
        if oldhandler is not None:
            while True:
                signal.disconnect(oldhandler)
        else:
            signal.disconnect()
    except TypeError:
        pass
    if newhandler is not None:
        signal.connect(newhandler)
        

class runButt(QPushButton):
    '''holds run button'''
    
    def __init__(self, sbBox:connectBox, size:int=50):
        super(runButt,self).__init__()
        self.sbBox = sbBox
        self.setFixedSize(size, size)
        self.setEnabled(False)
        self.update(sbBox.runningSBP)
        

    def update(self, running) -> None:
        '''Update the appearance of the run button'''
        if running:
            # become stop button
            # connect to triggerKill
            reconnect(self.clicked, self.sbBox.triggerKill, self.sbBox.runFile)
            self.setStyleSheet("background-color: #de8383; border-radius:10px")
            self.setToolTip('Stop print')
            self.setIcon(icon('stop.png'))
        else:
            # become play button
            # connect to runFile
            reconnect(self.clicked, self.sbBox.runFile, self.sbBox.triggerKill)
            self.setStyleSheet("background-color: #a3d9ba; border-radius:10px")
            self.setToolTip('Start print')
            self.setIcon(icon('play.png'))
        return
    


class sbpNameList(QHBoxLayout):
    '''holds widget and list of shopbot files'''
    
    def __init__(self, sbBox:connectBox, **kwargs):
        super(sbpNameList, self).__init__()
        self.sbBox = sbBox
        self.sbpRealList = []
        
        self.successLayout(**kwargs)        
        
    def successLayout(self, **kwargs):
        '''make the widget'''
        
        self.sbButts = fToolBar(vertical=True)
        self.loadButt = fToolButton(self.sbButts, tooltip='Load shopbot file(s)', icon='open.png', func=self.loadFile)
        self.deleteButt = fToolButton(self.sbButts, tooltip='Remove selected file(s)', icon='delete.png', func=self.removeFiles)
        self.deleteAllButt = fToolButton(self.sbButts, tooltip='Remove all files(s)', icon='deleteAll.png', func=self.removeAllFiles)
        self.breakButt = fToolButton(self.sbButts, tooltip='Add a breakpoint to the list', icon='breakpoint.png', func=self.addBreakPoint)
        
        
        self.listW = QListWidget()
        
        # set dimensions
        if 'height' in kwargs:
            self.listW.setFixedHeight(kwargs['height'])
        if 'width' in kwargs:
            self.listW.setFixedWidth(kwargs['width'])
            
        self.currentFile = cfg.shopbot.currentFile  # the current file
        # add initial files
        for file in cfg.shopbot.sbpFiles:
            self.addFile(file)
        
        if os.path.exists(self.currentFile):
            self.activate(0)
            self.sbBox.enableRunButt()
            self.updateStatus('Ready ... ', False)
        self.listW.itemDoubleClicked.connect(self.activate)
        self.listW.setAcceptDrops(True)
        self.listW.setSelectionMode(QAbstractItemView.MultiSelection)
        self.listW.setDragDropMode(QAbstractItemView.InternalMove)
        self.listW.setDragEnabled(True)
        self.listW.setToolTip('Double click to select the next file to run.\nSingle click to select files to delete.\nClick and drag to reorder.')
        
        self.addWidget(self.sbButts)
        self.addWidget(self.listW)
        self.setSpacing(10)
        
        
    def saveConfig(self, cfg1):
        '''save the current settings to a config Box object'''
        cfg1.shopbot.currentFile = self.getFullPath(self.currentFile)
        l = []
        for x in range(self.listW.count()):
            item  = self.listW.item(x)
            if hasattr(item, 'text'):
                l.append(self.getFullPath(item.text()))
        cfg1.shopbot.sbpFiles = l
        return cfg1
    
    def loadConfig(self, cfg1):
        '''load settings from a config Box object'''
        self.currentFile = cfg1.shopbot.currentFile
        self.sbpRealList = []
        # remove old items
        for i in range(self.listW.count()):
            item = self.listW.item(i)
            logging.info(f'Removing file from queue: {item.text()}')
            fulp = self.getFullPath(item.text())
            if fulp in self.sbpRealList:
                self.sbpRealList.remove(fulp) # remove the file from the list of full paths
            row = self.listW.row(item)
            self.listW.takeItem(row)
            
        # add new items
        for file in cfg1.shopbot.sbpFiles:
            self.addFile(file)

              
    def showFullPath(self) -> bool:
        '''check if we should show the full path'''
        if hasattr(self.sbBox, 'settingsBox'):
            settingsBox = self.sbBox.settingsBox
            if hasattr(settingsBox, 'showFolderCheck'):
                return settingsBox.showFolderCheck.isChecked()
            else:
                return False     
        else:
            return False
            
            
    def reformat(self) -> None:
        '''change the display of the file list'''
        
        logging.info('Reformatting list of files')
        
        for i in range(self.listW.count()):
            item = self.listW.item(i)
            if self.showFullPath():
                item.setText(self.getFullPath(item.text()))
            else:
                item.setText(os.path.basename(item.text()))
                
                
    def sbpNumber(self) -> int:
        '''Determine the index of the current file. Return -1 if it's not in the list.'''
        for i in range(self.listW.count()):
            if self.listW.item(i).data(Qt.UserRole):
                return i
        return -1
    
    
    def updateItem(self, item:QListWidgetItem, active:bool) -> None:
        '''Update the item status to active or inactive'''
        if active:
            item.setIcon(icon('play.png')) # show that this item is next
            item.setData(Qt.UserRole, True)
        else:
            item.setIcon(QIcon()) # show that this item is not next
            item.setData(Qt.UserRole, False)
        return
    
    
    def activate(self, item:Union[int, QListWidgetItem]) -> None:
        '''set the sbp file that the GUI will run next. Input can be item number or the actual item object.'''
        
        # get the actual item if given a number
        if type(item) is int:
            if item>=self.listW.count(): # this item is out of range
                logging.warning(f'Item out of range: requested {item} out of {self.listW.count()}')
            else:
                item = self.listW.item(item)
          
        # make sure this is a real file
        if not os.path.exists(self.getFullPath(item.text())) and not item.text()=='BREAK':
            logging.warning(f'Cannot activate {item.text()}: file not found')
            return
        
        # remove other play icons
        for i in range(self.listW.count()):
            self.updateItem(self.listW.item(i), False)
            
        self.currentFile = self.getFullPath(item.text()) # find the full path name of the item
#         self.currentFile = item.text() # new run file name
        self.updateItem(item, True)
        self.listW.scrollToItem(item, QAbstractItemView.PositionAtTop) # scroll to the current item
        
            
    def activateNext(self) -> None:
        '''Activate the next file in the list'''
        if self.listW.count()==1:
            # there is only one file in the list, so we're done.
            return
        newNum = self.sbpNumber() + 1
        if newNum>=self.listW.count(): 
            # if we're at the end of the list, restart from the beginning
            newNum = 0
        self.activate(newNum)
        
    def addFileList(self, fn) -> bool:
        '''check if this file is a list of files and read in all of the files in the list. return true if it is a list of files'''
        if not (fn.endswith('list.txt') or fn.endswith('List.txt')):
            # this is not a list of files
            return False
        dirname = os.path.dirname(fn)
        with open(fn, mode='r') as f:
            for line0 in f:
                line = line0.strip()
                # iterate through lines in the file and add them to the run list
                if line=='BREAK':
                    self.addFile(line)  # just add the break
                else:
                    # add full path name to list
                    path = os.path.join(dirname, line)
                    if os.path.exists(path):
                        self.addFile(path)
                    else:
                        logging.error(f'Cannot add file in {fn}. File does not exist: {path}')
        return True

    
    def addFile(self, fn, position:int=-1) -> None:
        '''Add this file to the list of files, and remove the original placeholder if it's still there.
        position>=0 to insert at a specific position in the list, otherwise add to end'''
        
        islist = self.addFileList(fn) 
        if islist:
            return       
        
        self.sbpRealList.append(fn)
        
        if fn=='BREAK':
            short=fn
        else:
            short = os.path.basename(fn)
        
        if self.showFullPath():
            # show the full path name
            item = QListWidgetItem(fn) # create an item
        else:
            item = QListWidgetItem(short) # create an item with basename
        item.setData(Qt.UserRole, False)
        if position>=0:
            self.listW.insertItem(position, item)
        else:
            self.listW.addItem(item) # add it to the list
        if self.listW.count()>1: # if there was already an item in the list
            item0 = self.listW.item(0) # take the first item
            if not os.path.exists(self.getFullPath(item0.text())) and not item0.text()=='BREAK': # if the original item isn't a real file
                self.activate(1) # activate the next item in the list
                self.listW.takeItem(0) # remove bad name from the list
                self.sbpRealList.pop(0) # remove bad name from full path list
        return
    
    def getFullPath(self, file:str) -> str:
        '''get the full path name of the file'''
        if file=='BREAK':
            return file
        for fullpath in self.sbpRealList:
            if file in fullpath:
                return fullpath
    
    def removeFiles(self) -> None:
        '''Remove the selected file from the list'''
        for item in self.listW.selectedItems():
            logging.info(f'Removing file from queue: {item.text()}')
            if item.data(Qt.UserRole):
                # we're removing the current file. go to the next file.
                self.activateNext()

            self.sbpRealList.remove(self.getFullPath(item.text())) # remove the file from the list of full paths
            row = self.listW.row(item)
            self.listW.takeItem(row)
            
        if self.listW.count()==0:
            # if we've deleted all the files, go back to placeholder text
            self.currentFile = 'No file selected'
            self.addFile(self.currentFile)
            
    def removeAllFiles(self) -> None:
        '''Remove all files from the list'''
        items = []
        for i in range(self.listW.count()):
            items.append(self.listW.item(i))
        
        for item in items:
            logging.info(f'Removing file from queue: {item.text()}')
            self.sbpRealList.remove(self.getFullPath(item.text())) # remove the file from the list of full paths
            row = self.listW.row(item)
            self.listW.takeItem(row)
            
        if self.listW.count()==0:
            # if we've deleted all the files, go back to placeholder text
            self.currentFile = 'No file selected'
            self.addFile(self.currentFile)
        
        
    def loadFile(self) -> None:
        '''load a shopbot run file using a standard file selection dialog'''
        if os.path.exists(self.currentFile):
            openFolder = os.path.dirname(self.currentFile)
        else:
            openFolder = self.sbBox.sbpFolder
            if not os.path.exists(openFolder):
                openFolder = r'C:\\'
        sbpnList = fileDialog(openFolder, 'Gcode files (*.gcode *.sbp *.txt)', False)
        for sbpn in sbpnList:
            if not os.path.exists(sbpn):
                logging.error(f'{sbpn} does not exist')
            else:
                self.sbBox.enableRunButt()
                self.addFile(sbpn)
                logging.debug(f'Added file to queue: {sbpn}')
                self.updateStatus('Ready ... ', False)
                
    def addBreakPoint(self) -> None:
        '''add a stop point to the list of files, where autoplay will stop'''
        i = -1
        for item in self.listW.selectedItems():
            i = self.listW.row(item) + 1
        self.addFile('BREAK', position=i)
        self.updateStatus('Added break point', False)
        
        
    def updateStatus(self, status:str, log:bool) -> None:
        '''update the status of the shopbot box'''
        self.sbBox.updateStatus(status, log)
    