#!/usr/bin/env python
'''Shopbot GUI general functions. Contains classes and functions that are shared among fluigent, cameras, shopbot.'''

# external packages
from PyQt5.QtCore import pyqtSlot, QDir, Qt, QPoint, QRect
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QButtonGroup, QCheckBox, QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,  QLayout, QLineEdit, QProxyStyle, QPushButton, QRadioButton, QSpacerItem, QStyle, QStyleOptionTab, QStylePainter, QTabBar, QToolBar, QToolButton, QVBoxLayout, QWidget
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

def iconpath(name:str) -> str:
    '''get the path to the actual icon in our project folder'''
    currentdir = os.path.dirname(os.path.realpath(__file__))
    iconfolder = os.path.join(currentdir, 'icons')
    if not os.path.exists(iconfolder):
        iconfolder = os.path.join(os.path.dirname(currendir), 'icons')
    if not os.path.exists(iconfolder):
        raise NameError('No icon folder found')
    iconpath = os.path.join(iconfolder, name)
    if not os.path.exists(iconpath):
        raise NameError('No icon with that name')
    return iconpath

def imlabel(name:str, size:int=0) -> QLabel:
    label = QLabel()
    pixmap = QPixmap(iconpath(name))
    label.setPixmap(pixmap)
    # label.setScaledContents(True)
    if size>0:
        label.resize(size, int(round(size*pixmap.width()/pixmap.height())))
    return label

def icon(name:str) -> QIcon:
    '''Get a QtGui icon given an icon name'''
    return QIcon(iconpath(name))


def fileDialog(startDir:str, fmt:str, isFolder:bool, opening:bool=True) -> str:
    '''fileDialog opens a dialog to select a file for reading
    startDir is the directory to start in, e.g. r'C:\Documents'
    fmt is a string file format, e.g. 'Gcode files (*.gcode *.sbp)'
    isFolder is bool true to only open folders
    opening is true if we are opening a file, false if we are saving'''
    dialog = QFileDialog()
    dialog.setFilter(dialog.filter() | QDir.Hidden)

    # ARE WE TALKING ABOUT FILES OR FOLDERS
    if isFolder:
        dialog.setFileMode(QFileDialog.DirectoryOnly)
    else:
        dialog.setFileMode(QFileDialog.ExistingFiles)
        
    # OPENING OR SAVING
    if opening:
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
    else:
        dialog.setAcceptMode(QFileDialog.AcceptSave)

    # SET FORMAT, IF SPECIFIED
    if fmt != '' and isFolder is False:
        dialog.setDefaultSuffix(fmt)
        dialog.setNameFilters([f'{fmt} (*.{fmt})'])

    # SET THE STARTING DIRECTORY
    if startDir != '':
        dialog.setDirectory(str(startDir))
    else:
        dialog.setDirectory(str(ROOT_DIR))

    if dialog.exec_() == QDialog.Accepted:
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
        while not os.path.exists(folder):
            startFolder = os.path.dirname(folder)
            if startFolder==folder or len(startFolder)==0:
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
        
    
class fileSetOpenRow(QHBoxLayout):
    '''A row of icons and displays that lets the user set a file name using a dialog and open the folder location'''
    
    def __init__(self, width:int=500, title:str='Set folder', tooltip:str='Open folder', initFolder='No folder selected', **kwargs):
        super(fileSetOpenRow, self).__init__()
        self.width = width
        self.title = title
        self.saveFolder = initFolder
        self.tooltip = tooltip
 
        saveButtBar = QToolBar()
        iconw = float(saveButtBar.iconSize().width())
        saveButtBar.setFixedWidth(iconw+4)
            
        saveButt = QToolButton()
        saveButt.setToolTip(self.title)
        saveButt.setIcon(icon('open.png'))
        self.saveButt = saveButt
        saveButtBar.addWidget(saveButt)
        
        self.saveFolderLabel = createStatus(self.width, height=2*iconw, status=self.saveFolder)
        
        saveFolderLink = QToolButton()
        saveFolderLink.setToolTip(self.tooltip)
        saveFolderLink.setIcon(icon('link.png'))
        self.saveFolderLink = saveFolderLink
        saveLinkBar = QToolBar()
        saveLinkBar.setFixedWidth(iconw+4)
        saveLinkBar.addWidget(saveFolderLink)
        
        self.addWidget(saveButtBar)
        self.addWidget(self.saveFolderLabel)
        self.addWidget(saveLinkBar)
        
        self.addStretch()
        
        if 'setFunc' in kwargs:
            self.saveButt.clicked.connect(kwargs['setFunc'])
        if 'openFunc' in kwargs:
            self.saveFolderLink.clicked.connect(kwargs['openFunc'])
        if 'layout' in kwargs:
            kwargs['layout'].addLayout(self)
        
    def updateText(self, sf:str) -> None:
        '''set the folder name display'''
        self.saveFolderLabel.setText(sf)
        
    def disable(self) -> None:
        '''gray out the open button'''
        self.saveButt.setEnabled(False)
        self.saveButt.setIcon(QIcon())
        
        
    def enable(self) -> None:
        '''enable the open button'''
        self.saveButt.setEnabled(True)
        self.saveButt.setIcon(icon('open.png'))
        
        

#############################################

def labelStyle():
    return 'font-weight:bold; color:#31698f'

        
def fAdopt(obj:QWidget, **kwargs):
    if 'text' in kwargs:
        obj.setText(kwargs['text'])
    if 'tooltip' in kwargs:
        obj.setToolTip(kwargs['tooltip'])
    if 'icon' in kwargs:
        obj.setIcon(icon(kwargs['icon']))
    if 'width' in kwargs:
        try:
            obj.setFixedWidth(kwargs['width'])
        except AttributeError:
            obj.setMinimumWidth(kwargs['width'])
            obj.setMaximumWidth(kwargs['width'])
    if 'height' in kwargs:
        try:
            obj.setFixedHeight(kwargs['height'])
        except AttributeError:
            obj.setMinimumHeight(kwargs['height'])
            obj.setMaximumHeight(kwargs['height'])
    if 'maxwidth' in kwargs:
        obj.setMaximumWidth(kwargs['maxwidth'])
    if 'minwidth' in kwargs:
        obj.setMinimumWidth(kwargs['minwidth'])
    if 'maxheight' in kwargs:
        obj.setMaximumHeight(kwargs['maxheight'])
    if 'minheight' in kwargs:
        obj.setMinHeight(kwargs['minheight'])
    if 'validator' in kwargs:
        obj.setValidator(kwargs['validator'])
    if 'layout' in kwargs and hasattr(kwargs['layout'], 'addWidget'):
        kwargs['layout'].addWidget(obj)
    if 'checkable' in kwargs:
        obj.setCheckable(kwargs['checkable'])

#----           

class fButton(QPushButton):
    '''This is a pushbutton style for quick initialization'''
    
    def __init__(self, layout:QLayout, title:str='', **kwargs):
        super(fButton, self).__init__()
        fAdopt(self, layout=layout, text=title, **kwargs)
        if 'func' in kwargs:
            self.clicked.connect(kwargs['func'])
        self.setAutoDefault(False)
        self.clearFocus()
    

#----   
        
class fCheckBox(QCheckBox):
    '''This is a checkbox style for quick initialization'''
    
    def __init__(self, layout:QLayout, title:str='', checked:bool=False, **kwargs):
        super(fCheckBox, self).__init__()
        self.setChecked(checked)
        fAdopt(self, layout=layout, text=title, **kwargs)
        if 'func' in kwargs:
            self.stateChanged.connect(kwargs['func'])

        
#----

class fLabel(QLabel):
    '''This is a label style for quick initialization'''
    
    def __init__(self, layout:QLayout=None, title:str='', style:str='', **kwargs):
        super(fLabel, self).__init__()
        fAdopt(self, layout=layout, text=title, **kwargs)
        if len(style)>0:
            self.setStyleSheet(style)
        
#----

class fLineEdit(QLineEdit):
    '''This is a line edit style that is in a form and triggers the function on editing finished'''
    
    def __init__(self, form:QFormLayout, title:str='', text:str='', **kwargs):
        super(fLineEdit, self).__init__()
        if 'func' in kwargs:
            self.editingFinished.connect(kwargs['func'])
        if 'func' in kwargs:
            self.returnPressed.connect(kwargs['func'])
        fAdopt(self, text=text, **kwargs)
        if hasattr(form, 'addRow'):
            form.addRow(title, self)

            
class fLineCommand(QLineEdit):
    '''this is a line edit style that is not in a form and triggers the function on return pressed'''
    
    def __init__(self, title:str='', text:str='', **kwargs):
        super(fLineCommand, self).__init__()
        if 'func' in kwargs:
            self.returnPressed.connect(kwargs['func'])
        fAdopt(self, text=text, **kwargs)
        
#----
        
class fRadio(QRadioButton):
    '''This is a radio button style for quick initialization'''
    
    def __init__(self, layout:QLayout, group:QButtonGroup, title:str='', i:int=0, **kwargs):
        super(fRadio, self).__init__()
        fAdopt(self, layout=layout, text=title, **kwargs)
        group.addButton(self, i)
        if 'func' in kwargs:
            self.clicked.connect(kwargs['func'])
            
class fRadioGroup:
    '''this class holds a group of radio buttons. 
    layout is the layout we're adding this group to
    title is the title of the group
    nameDict is a dictionary correlating button ids to display names
    valueDict is a dictionary correlating button ids to values given by that button
    initValue is the initial value (as in valueDict) that should be initialized
    tooltip is the message on hover
    col puts the buttons in a column, otherwise row
    headerRow puts the label in the row above, otherwise in line
    '''
    
    def __init__(self, layout:QLayout, title:str, nameDict:dict, valueDict:dict, initValue, tooltip:str='', col:bool=True, headerRow:bool=True, **kwargs):
        
        if headerRow:
            self.layout = QVBoxLayout()
        else:
            self.layout = QHBoxLayout()
        label = fLabel(self.layout, title=title, style=labelStyle())
        if len(tooltip)>0:
            label.setToolTip(tooltip)
        
        if col:
            # put buttons in a column
            self.buttonLayout = QVBoxLayout()
        else:
            # put buttons in a row
            self.buttonLayout = QHBoxLayout()
        
        self.buttons = {}
        self.buttonGroup = QButtonGroup()
        self.buttonGroup.setExclusive(True)
        self.valueDict = valueDict
        for index, name in nameDict.items():
            button = QRadioButton(name)
            if valueDict[index]==initValue:
                button.setChecked(True)
            else:
                button.setChecked(False)
            self.buttons[index]=button
            self.buttonGroup.addButton(button, index)
            self.buttonLayout.addWidget(button)
        
        if 'func' in kwargs:
            self.buttonGroup.buttonClicked.connect(kwargs['func'])
        if len(tooltip)>0:
            self.buttonGroup.setToolTip(tooltip)
        self.layout.addLayout(self.buttonLayout)
        setAlign(self.layout, 'left')
        if hasattr(layout, 'addLayout'):
            layout.addLayout(self.layout)  

        
    def value(self) -> Any:
        '''returns the value of the button that the clicked button corresponds to'''
        bid = self.buttonGroup.checkedId()
        return self.valueDict[bid] 
    
    def setChecked(self, bid:int) -> None:
        '''check the button with the given id'''
        for i,b in self.buttons.items():
            if i==bid:
                b.setChecked(True)
            else:
                b.setChecked(False)
        
#----
        
class fToolBar(QToolBar):
    '''this is a toolbar style for quick initialization'''
    
    def __init__(self, vertical:bool=True, **kwargs):
        super(fToolBar, self).__init__()
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setStyleSheet("QToolBar{spacing:5px;}");
        if vertical:
            self.setOrientation(Qt.Vertical)
        else:
            self.setOrientation(Qt.Horizontal)
        fAdopt(self, **kwargs)
        self.buttons = 0
        
    def addWidget(self, widget):
        '''track number of buttons'''
        super(fToolBar, self).addWidget(widget)
        self.buttons+=1

#----
        
class fToolButton(QToolButton):
    '''This is a toolbutton style for quick initialization'''
    
    def __init__(self, toolbar, title:str='', **kwargs):
        super(fToolButton, self).__init__()
        fAdopt(self, layout=toolbar, text=title, **kwargs)
        if 'func' in kwargs:
            self.clicked.connect(kwargs['func'])
            
#---
            
def addArgsToLayout(l:QLayout, *args, **kwargs):
    '''generic value for initializing an fHBoxLayout or fVBoxlayout'''
    for arg in args:
        if arg.isWidgetType():
            l.addWidget(arg)
        else:
            l.addLayout(arg)
    if 'spacing' in kwargs:
        l.setSpacing(kwargs['spacing'])
        
def setAlign(l:QLayout, alignment:str) -> None:
    '''set the alignment on the layout'''
    for s in ['Left', 'Right', 'Bottom', 'Top', 'Center', 'HCenter', 'VCenter']:
        if alignment.lower()==s.lower():
            l.setAlignment(getattr(Qt, f'Align{s}'))
        
        
class fGridLayout(QGridLayout):
    '''quick way to initialize a grid'''
    
    def __init__(self, **kwargs):
        super(fGridLayout, self).__init__()
        if 'spacing' in kwargs:
            self.setSpacing(kwargs['spacing'])
        if 'alignment' in kwargs:
            setAlign(self, kwargs['alignment'])
                    
            
class fHBoxLayout(QHBoxLayout):
    '''quick way to initialize a row of layout elements'''
    
    def __init__(self, *args, **kwargs):
        super(fHBoxLayout, self).__init__()
        addArgsToLayout(self, *args, **kwargs)
        
                
class fVBoxLayout(QVBoxLayout):
    '''quick way to initialize a column of layout elements'''
    
    def __init__(self, *args, **kwargs):
        super(fVBoxLayout, self).__init__()
        addArgsToLayout(self, *args, **kwargs)
        
        



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
    
def createStatus(width:int, height:int=70, status:str='Ready') -> QLabel:
    '''creates a section for displaying the device status'''
    status = QLabel(status)
    status.setMinimumWidth(width)
    status.setMinimumHeight(height)
    status.setWordWrap(True)
    return status
    

class connectBox(QGroupBox):
    '''connectBox is a type of QGroupBox that can be used for cameras and fluigent, which need to be initialized. This gives us the option of showing an error message and reset button if the program doesn't connect'''
    
    def __init__(self):
        super(connectBox, self).__init__()
        self.connectAttempts = 0
        self.connected = False
        self.diag=1
        self.bTitle = ''
        self.flag1 = -1

    
    def connectingLayout(self) -> None:
        '''if the computer is still trying to connect, show this waiting screen'''
        if self.connectAttempts>0:
            self.resetLayout()
        self.layout = QVBoxLayout()
        logging.info(f'Connecting to {self.bTitle}')
        self.layout.addWidget(QLabel(f'Connecting to {self.bTitle}'))
        self.setLayout(self.layout)  

    
    def failLayout(self) -> None:
        '''if the computer fails to connect, show an error message and a button to try again'''
        self.resetLayout()
        self.layout = QVBoxLayout()
        lstr = f'{self.bTitle} not connected. Connect attempts: {self.connectAttempts}'
        logging.warning(lstr)
        self.label = QLabel(lstr)            
        self.resetButt = QPushButton(f'Connect to {self.bTitle}')
        self.resetButt.clicked.connect(self.connect) 
            # when the reset button is pressed, try to connect to the fluigent again
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.resetButt)
        self.setLayout(self.layout)
    
    
    def createStatus(self, width:int, height:int=70, status:str='Ready') -> None:
        '''creates a section for displaying the device status'''
        self.status = createStatus(width, height=height, status=status)
    
    
    def resetLayout(self) -> None:
        '''delete all the display items from the box'''
        deleteLayoutItems(self.layout)
        
    @pyqtSlot(str,bool)
    def updateStatus(self, st:str, log:bool) -> None:
        '''update the displayed device status'''
        try:
            self.status.setText(st)
        except:
            if self.diag>0:
                logging.info(f'{self.bTitle}:{st}')
        else:
            if log and self.diag>0:
                logging.info(f'{self.bTitle}:{st}')
                
    def startRecording(self) -> None:
        '''empty function, defined in camBox, fluBox'''
        return
    
    def stopRecording(self) -> None:
        '''empty function, defined in camBox, fluBox'''
        return
            
    def close(self) -> None:
        '''close the box'''
        return

                
class QHLine(QFrame):
    def __init__(self):
        super(QHLine, self).__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
     

    
class TabBar(QTabBar):
    '''for vertical tabs. https://stackoverflow.com/questions/51404102/pyqt5-tabwidget-vertical-tab-horizontal-text-alignment-left'''
    
    def tabSizeHint(self, index):
        s = QTabBar.tabSizeHint(self, index)
        s.transpose()
        return s

    def paintEvent(self, event):
        painter = QStylePainter(self)
        opt = QStyleOptionTab()

        for i in range(self.count()):
            self.initStyleOption(opt, i)
            painter.drawControl(QStyle.CE_TabBarTabShape, opt)
            painter.save()

            s = opt.rect.size()
            s.transpose()
            s.setHeight(s.height()+20)
            r = QRect(QPoint(), s)
            r.moveCenter(opt.rect.center())
            opt.rect = r

            c = self.tabRect(i).center()
            painter.translate(c)
            painter.rotate(90)
            painter.translate(-c)
            painter.drawControl(QStyle.CE_TabBarTabLabel, opt);
            painter.restore()
            
        
class ProxyStyle(QProxyStyle):
    '''for vertical tabs. https://stackoverflow.com/questions/51404102/pyqt5-tabwidget-vertical-tab-horizontal-text-alignment-left'''
    
    def drawControl(self, element, opt, painter, widget):
        if element == QStyle.CE_TabBarTabLabel:
            ic = self.pixelMetric(QStyle.PM_TabBarIconSize)
            r = QRect(opt.rect)
            w =  0 if opt.icon.isNull() else opt.rect.width() + self.pixelMetric(QStyle.PM_TabBarIconSize)
            r.setHeight(opt.fontMetrics.width(opt.text) + w + 50) # needed to add 50 to not cut off words
            r.moveBottom(opt.rect.bottom())
            opt.rect = r
        QProxyStyle.drawControl(self, element, opt, painter, widget)