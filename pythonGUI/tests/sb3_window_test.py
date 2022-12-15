#!/usr/bin/env python
'''Shopbot GUI. '''

# external packages
import os, sys
import time
import win32gui
import win32con
import pyscreenshot

# local packages
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(currentdir)
sys.path.append(parentdir)
import flags
    
##################################################  
        
'''Run the program'''



class windowFinder:
    
    def __init__(self):
        self.window = 0
            
    def winEnumHandler(self,  hwnd, ctx ):
        '''get a dictionary of window handles and titles'''
        
        if win32gui.IsWindowVisible( hwnd ):
            self.windows[hwnd] = win32gui.GetWindowText( hwnd )

    def findWindow(self):
        self.window=0
        self.title=''
        self.windows = {}
        win32gui.EnumWindows( lambda hwnd,ctx:self.winEnumHandler(hwnd, ctx), None )
        for handle,title in self.windows.items():
            if title.startswith('ShopBotEASY') or title.endswith('.sbp'):
                self.window = handle
                self.title = title
                
    def getChildText(self, hwnd, param):
<<<<<<< Updated upstream
        print(hex(hwnd))
        title = win32gui.GetWindowText(hwnd)
        
        # t2 = self.getText(hwnd, diag=True)
        # print(t2)
        if len(text)>0:
            self.child_handles[hwnd]=text
=======
        
        title = win32gui.GetWindowText(hwnd)
        
        t2 = self.getText(hwnd, diag=True)
        print(t2)
        print(f'{title}:{hex(hwnd)}')
        if len(title)>0:
            self.child_handles[hwnd]=title
>>>>>>> Stashed changes
        
    def getText(self, hnd, diag:bool=False):
        if hnd>0:
            buf = win32gui.PyMakeBuffer(255)
<<<<<<< Updated upstream
            length = win32gui.SendMessage(btnHnd, win32con.WM_GETTEXT, 255, buf)
            result = buf[0:length*2]
            text = bytes(result)
=======
            length = win32gui.SendMessage(hnd, win32con.WM_GETTEXT, 255, buf)
            result = buf[0:length*2]
            text = result.tobytes().replace(b'\x00', b'').decode('utf-8')
>>>>>>> Stashed changes
            if diag:
                print(f"Copied {length} characters.  Contents: {text}\n")
            return text

                
    def printWindowValues(self):
        if self.window>0:
            self.child_handles = {}
            # win32gui.EnumChildWindows(self.window, lambda hwnd,ctx:self.getChildText(hwnd,ctx), None)
<<<<<<< Updated upstream
=======
            print('window:', hex(self.window))
>>>>>>> Stashed changes
            
            # find button group that holds text box
            btnHnd= win32gui.FindWindowEx(self.window, 0 , "Button", "")
            print('button:', hex(btnHnd))
<<<<<<< Updated upstream
            win32gui.EnumChildWindows(btnHnd, lambda hwnd,ctx:self.getChildText(hwnd,ctx), None)
            
            # # find text box
            # boxHnd= win32gui.FindWindowEx(btnHnd, 1 , "ThunderRT6UserControlDC", "")
            # print(hex(boxHnd))
=======
            # win32gui.EnumChildWindows(btnHnd, lambda hwnd,ctx:self.getChildText(hwnd,ctx), None)
            
            # find text box
            boxHnd1= win32gui.FindWindowEx(btnHnd, 0 , "ThunderRT6UserControlDC", "")
            boxHnd= win32gui.FindWindowEx(btnHnd, boxHnd1 , "ThunderRT6UserControlDC", "")
            print('box:', hex(boxHnd))
>>>>>>> Stashed changes
            
            
            
            # self.getText(boxHnd, diag=True)
            print(self.title, self.child_handles.values())
        else:
            print('No window found')
            print(self.windows.values())
            
            child = '0002044E'
            parent = '0003033E'
    

if __name__ == "__main__":
    
    wf= windowFinder()
    # while True:
    wf.findWindow()
    wf.printWindowValues()
    print(wf.window)
    time.sleep(0.1)