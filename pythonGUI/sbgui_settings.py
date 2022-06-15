#!/usr/bin/env python
'''Shopbot GUI functions for setting up the GUI window'''

# external packages
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QMainWindow, QPushButton, QGridLayout, QTabWidget, QAction, QApplication, QCheckBox, QPlainTextEdit, QDesktopWidget
import os, sys
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
import traceback


# local packages
from sbgui_general import *
from config import *


######################## settings window

        
class settingsDialog(QDialog):
    '''Creates a settings window'''
    
    def __init__(self, parent, meta:bool=True, file:bool=True, sb:bool=True, flu:bool=True, cam:bool=True):
        '''This is called by the parent, which is the main SBwindow'''
        
        super().__init__(parent)
        self.parent = parent
        
        self.meta=meta
        self.file=file
        self.sb=sb
        self.flu=flu
        self.cam=cam
        
        self.setStyle(ProxyStyle())
        self.layout = QVBoxLayout()
        
        self.generalBox() # create a layout for general settings
        self.tabs = QTabWidget()       
        self.tabs.setTabBar(TabBar(self))
        self.tabs.setTabPosition(QTabWidget.West)
        for box in [self]+self.parentTabs():
            if hasattr(box, 'settingsBox') and hasattr(box, 'bTitle'):
                self.tabs.addTab(box.settingsBox, box.bTitle)  
#             else:
#                 if not hasattr(box, 'settingsBox'):
#                     logging.debug(f'No settings box in {box}')
#                 else:
#                     logging.debug(f'No bTitle in {box}')
        if file:
            parent.fileBox.checkFormats() # update the initial file format
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)
        
        self.setWindowTitle('Settings')
    
    def parentTabs(self) -> List:
        '''list of settings tabs in the parent'''
        return self.parent.boxes()
        
    def generalBox(self) -> None:
        '''create a tab for settings of settings'''
        self.settingsBox = QWidget()
        self.bTitle = 'Load/save'
        layout = QVBoxLayout()
        
        w = 300
        h = 50
        loadButton = fButton(layout, title='Load settings from file', 
                             icon='open.png', func=self.loadSettings
                             , width=w, height=h)
        saveButton = fButton(layout, title='Save settings to file', 
                             icon='save.png', func=self.saveSettings
                             , width=w, height=h)
        self.alwaysSave = fCheckBox(layout, title='Save settings for next session', 
                                    checked=cfg.layout.save)
        
        layout.addStretch()
        self.settingsBox.setLayout(layout)

        
    def loadSettings(self) -> None:
        '''Load settings from file'''
        sf = fileDialog(getConfigDir(), 'config files (*.yaml *.yml)', False)
        if len(sf)>0:
            sf = sf[0]
        else:
            return 
        if not os.path.exists(sf):
            return
        cfg = loadConfigFile(sf)
        parent = self.parent
        for box in (self.parent.boxes()):
            box.loadConfig(cfg)
        logging.info(f'Loaded settings from {sf}')
        
    def saveCfg(self, file:str):
        '''save the config file to file'''
        parent = self.parent
        cfg1 = cfg.copy()
        for box in (self.parent.boxes()):
            if hasattr(box, 'saveConfig'):
                cfg1 = box.saveConfig(cfg1)
        out = dumpConfigs(cfg1, file)
        if out==0:
            logging.info(f'Saved settings to {file}')
        else:
            logging.info(f'Error saving settings to {file}')
            
    def saveSettings(self):
        '''Save all settings to file'''
        sf = fileDialog(getConfigDir(), 'config files (*.yml)', False, opening=False)
        if len(sf)>0:
            sf = sf[0]
            if sf.endswith(','):
                sf = sf[:-1]
        else:
            return 
        self.saveCfg(sf)
        
        
    def close(self):
        '''Close the window'''
        if self.alwaysSave.isChecked() and not self.parent.test:
            # only save settings if the checkbox is checked and this is not a test
            self.saveCfg(os.path.join(getConfigDir(), 'config.yml'))
        self.done(0)