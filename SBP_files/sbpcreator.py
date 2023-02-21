#!/usr/bin/env python
'''Functions for creating shopbot files'''

# external packages
import math
import numpy as np
import os
import sys
import re
from typing import List, Dict, Tuple, Union, Any, TextIO
import matplotlib
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import sympy as sy
import copy

# local packages
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(currentdir)
sys.path.append(parentdir)
sys.path.append(os.path.join(parentdir, 'pythonGUI'))  # add GUI folder
from config import cfg

# plotting
matplotlib.rcParams['svg.fonttype'] = 'none'
matplotlib.rc('font', family='Arial')
matplotlib.rc('font', size='8')


# local files
from sbpRead import *


#------------------------------------------

      


#############-----------------------------------

class sbpCreator:
    '''Holds functions necessary for making .sbp files'''
    
    def __init__(self, diam:float=0.603, **kwargs):
        '''diam is the filament diameter in mm'''
        self.diam=diam
        self.channel = 0    # channel is the pressure channel to turn on
        self.file = ''
        self.cp = [0,0,0] # current point
        self.positions = []
        self.stepPoints = []
        self.snapPoints = []
        self.written = [] # moves with extrusion on, as list of pairs of points
        self.jogs = [] # jogs, as list of pairs of points
        self.unwritten = [] # moves with extrusion off, as list of pairs of points
        self.vardefs = {}
        self.volume = 0 # volume of fluid extruded in mm^3
        self.time = 0 # total time in print, in s
        self.MS = 0
        self.JS = 0
        self.pOn = False
        self.created=False
        if 'lastPt' in kwargs:
            self.takeLastPt(kwargs['lastPt'])
    

    def __add__(self, other):
        '''function for adding two sbpcreators together'''
        scout = sbpCreator()
        self.sbp()
        other.sbp()
        scout.file = self.file + other.file
        scout.cp = other.cp
        scout.positions = self.positions + other.positions
        scout.written = self.written + other.written
        scout.jogs = self.jogs + other.jogs
        scout.unwritten = self.unwritten + other.unwritten
        scout.stepPoints = self.stepPoints + other.stepPoints
        scout.snapPoints = self.snapPoints + other.snapPoints
        scout.vardefs = {**self.vardefs, **other.vardefs}
        scout.volume = self.volume + other.volume
        scout.time = self.time + other.time
        scout.MS = self.MS
        scout.JS = self.JS
        return scout
    
    def printVolume(self):
        print('{:0.3f}'.format(self.volume/1000), 'mL,', int(np.floor(self.time/60)), 'min', int(self.time%60), 's')
        
    def prime(self, channel:int=0, runFlag1:Union[int, str]=cfg.shopbot.flag1):
        self.turnOn(runFlag1)
        self.turnOn(channel)
        self.turnOff(channel)
     
    def takeLastPt(self, other) -> int:
        '''return 1 if the last point is not valid'''
        self.vardefs = {**self.vardefs, **other.vardefs}
        self.MS = other.MS
        self.JS = other.JS
        if len(other.positions)>0:
            lp = other.positions[-1]
            self.cp = lp.copy()
        else:
            return 1
        return 0
    
    def whichPlus(self, longdir:str) -> int:
        '''Determine if the initial direction should be positive or negative'''
        if longdir[0]=='-':
            return -1
        else:
            return 1  
    
    def which0(self, longdir:str) -> Tuple[float, int]:
        '''determine the endpoints of the long lines'''
        if longdir[1]=='x':
            long0 = self.x0
        elif longdir[1]=='y':
            long0 = self.y0
        else:
            long0 = self.z0
        plus = self.whichPlus(longdir) 
        return long0, plus
    
    def altsp(self, p0, plus, i):
        '''function used for alternating direction. p0 is a start position, plus is -1 or 1, i is the line number'''
        p1 = t(plus, self.spacing1, np.floor(i/2))
        p2 = t(plus, self.spacing2, np.ceil(i/2))
        return p(p0, p1, p2)
    
 
    def updateReps(self, slideH:float, margin:float, divisible:int) -> None:
        '''Determine the number of repeats to do in this zigzag. NOTE: the number of reps in the zigzag is fixed and cannot change if you go back and change the header variables (e.g. '&spacing'), so you can either set it using this function or set it manually, but if you want the number of reps to be responsive to '&spacing', etc., you need to rebuild the whole file'''
        s1 = self.floatSC(self.spacing1)
        s2 = self.floatSC(self.spacing2)
        r = np.floor((slideH - 2*margin) / (s1 + s2) * 2)
        r = np.floor(r/divisible)*divisible
        self.reps = int(r)
    
    def reset(self):
        '''Clear the file and list of positions'''
        self.file = ''
        if len(self.positions)>1:
            self.cp = self.positions[0]
        self.positions = []
        self.stepPoints = []
        self.snapPoints = []
        self.written = [] # moves with extrusion on, as list of pairs of points
        self.jogs = [] # jogs, as list of pairs of points
        self.unwritten = [] # moves with extrusion off, as list of pairs of points
    
    def sbp(self):
        '''Just the sbp file string'''
        return self.file
    
    
    def floatSC(self, vi:str) -> float:
        '''Evaluate the expression vi with the values of all variables'''
        return floatSC(vi, self.vardefs)
    
    def strSimplify(self, vi:str, *args) ->str:
        '''Simplify the expression, and evaluate it with any variables requested in *args. If you don't want to evaluate any variables, vi=[0] or any list w/ values that are not in the defined variables. If you want to evaluate all variables, vi=[]. If you want to use a specific list of variables, e.g. use ['&margin', '&spacing'] '''
        if len(args)==0:
            defdict = self.vardefs
        else:
            defdict = {key: value for key, value in self.vardefs.items() if key in args[0]} 
        strSimplify(vi, defdict)
   
        
    
    #------------
    
    
    def updatePtsXYZ(self, dic:Dict, st:str): 
        '''search the dictionary for the string (e.g. 'x', 'y', 'z'). If it's not there, return the coord from the point cp'''
        if st in dic:
            val = dic[st]
        else:
            idx = ['x','y','z'].index(st)
            val = self.cp[idx]
        return val
        
    def updatePts(self, ms:str='m', **kwargs):
        '''Add point to list of points. e.g. if you are going to z=5, input z=5. If you are going to x=5,y=4, then input x=5,y=4.
        pOn if extrusion pressure is on
        ms = m for a move, j for a jog'''
        x = self.updatePtsXYZ(kwargs, 'x')
        y = self.updatePtsXYZ(kwargs, 'y')
        z = self.updatePtsXYZ(kwargs, 'z')
        if self.floatSC(x)==self.floatSC(self.cp[0]) and self.floatSC(y)==self.floatSC(self.cp[1]) and self.floatSC(z)==self.floatSC(self.cp[2]):
            # already at that point
            return
        
        lastpt = self.cp
        lastpt = [self.floatSC(i) for i in lastpt]
        xf = self.floatSC(x)
        yf = self.floatSC(y)
        zf = self.floatSC(z)
        distance = np.sqrt((xf-lastpt[0])**2+(yf-lastpt[1])**2+(zf-lastpt[2])**2) # distance traveled
        try:
            if ms=='m':
                s = self.MS
            else:
                s = self.JS
        except Exception as e:
            pass
        else:
            self.time = self.time + distance/s # time traveled
        if self.pOn:
            # update total extruded
            self.volume = self.volume + distance*np.pi*(self.diam/2)**2 # total volume
            self.written.append([self.cp, [x,y,z]])
        else:
            if ms=='m':
                self.unwritten.append([self.cp, [x,y,z]])
            else:
                self.jogs.append([self.cp, [x,y,z]])  

        self.cp = [x,y,z]
        self.positions.append([x,y,z])
        
    def pause(self, time):
        '''pause in the file'''
        self.file+=f'PAUSE {time}\n'
        self.time = self.time+self.floatSC(time)
        
        
    
                
    #------------
    # move commands
    #------------
    # direc is a direction (e.g. '+x')
    # position is a coordinate (e.g. 5.0)
    # ms is move string ('M' or 'J')
    
    #-----
    def mj3(self, x:Union[float, str], y:Union[float, str], z:Union[float, str], ms:str, pOn:bool=False) -> str:
        '''Move or jump in 3D. ms='M' or 'J' '''
        s = ms.upper() + '3, ' + fsss(x) + ', ' + fsss(y) + ', ' + fsss(z) + '\n'
        self.updatePts(x=x, y=y, z=z, pOn=pOn, ms=ms.lower())
        self.file+=s
        return s
    
    def m3(self, x:Union[float, str], y:Union[float, str], z:Union[float, str], pOn:bool=False) -> str:
        '''Move in 3D'''
        return self.mj3(x,y,z,'M', pOn=pOn)
    
    def m0(self) -> str:
        return self.m3(self.cp[0], self.cp[1], self.cp[2])
    
    def j3(self, x:Union[float, str], y:Union[float, str], z:Union[float, str], pOn:bool=False) -> str:
        '''Jump in 3D'''
        return self.mj3(x,y,z,'J', pOn=pOn)
    
    #-----
    def mj2(self, x:Union[float, str], y:Union[float, str], ms:str, pOn:bool=False) -> str:
        '''Move or jump in 2D'''
        s = ms.upper() + '2, ' + fsss(x) + ', ' + fsss(y) + '\n'
        self.updatePts(x=x, y=y, pOn=pOn, ms=ms.lower())
        self.file+=s
        return s

    def m2(self, x:Union[float, str], y:Union[float, str], pOn:bool=False) -> str:
        '''Move in 2D'''
        return self.mj2(x, y, 'M', pOn=pOn)
    
    def j2(self, x:Union[float, str], y:Union[float, str], pOn:bool=False) -> str:
        '''Jump in 2D'''
        return self.mj2(x, y, 'J', pOn=pOn)
    
    #-----
    def mj1(self, direc:str, position:Union[float, str], ms:str, pOn:bool=False) -> str:
        '''Move or jump in 1D'''
        if len(direc)>1:
            dire = direc[-1]
        else:
            dire = direc
        s = ms.upper() + dire.upper() + ', ' + fsss(position) + '\n'
        if dire.lower()=='x':
            self.updatePts(x=position, pOn=pOn, ms=ms.lower())
        elif dire.lower()=='y':
            self.updatePts(y=position, pOn=pOn, ms=ms.lower())
        else:
            self.updatePts(z=position, pOn=pOn, ms=ms.lower())
        self.file+=s
        return s
    
    def m1(self, direc:str, position:Union[float, str], pOn:bool=False) -> str:
        '''Move in 1D'''
        return self.mj1(direc, position, 'M', pOn=pOn)
    
    def mx(self, x:Union[float, str], pOn:bool=False) -> str:
        '''Move in x'''
        return self.mj1('X', x, 'M', pOn=pOn)
    
    def my(self, y:Union[float, str], pOn:bool=False) -> str:
        '''Move in y'''
        return self.mj1('Y', y, 'M', pOn=pOn)
    
    def mz(self, z:Union[float, str], pOn:bool=False) -> str:
        '''Move in z'''
        return self.mj1('Z', z, 'M', pOn=pOn)
    
    def j1(self, direc:str, position:Union[float, str], pOn:bool=False) -> str:
        '''Jump in 1D'''
        return self.mj1(direc, position, 'J', pOn=pOn)
    
    def jx(self, x:Union[float, str], pOn:bool=False) -> str:
        '''Jump in x'''
        return self.mj1('X', x, 'J', pOn=pOn)
    
    def jy(self, y:Union[float, str], pOn:bool=False) -> str:
        '''Jump in y'''
        return self.mj1('Y', y, 'J', pOn=pOn)

    def jz(self, z:Union[float, str], pOn:bool=False) -> str:
        '''Jump in z'''
        return self.mj1('Z', z, 'J', pOn=pOn)
    

    
    def withdraw(self, pOn=False) -> None:
        '''Go back to the loading zone'''
        self.mj1('Z', 10, 'J', pOn=pOn)  # down
        self.mj1('Y', 180, 'J', pOn=pOn) # back
        self.mj1('X', 30, 'J', pOn=pOn) # right
        return 

    #------------
    
    def turnOnSpindle(self) -> str:
        '''Turn on the spindle'''
        s = 'SetSpindleStatus,1\n'
        self.file+=s
        return s
    
    def setInkSpeed(self, channel:int, speed:float) -> str:
        '''set the ink extrusion speed'''
        s = f'\'ink_speed_{channel}={speed}\n'
        self.file+=s
        return s
    
    def convertFlag(self, flag0:int) -> str:
        if type(flag0) is int:
            f = flag0+1
        else:
            if flag0[-1]=='1':
                # this flag is actually 1 indexed
                f = flag0
            else:
                # assume the flag is 0 indexed
                print('flag not found: ', flag0)
                flag0 = self.floatSC(flag0)+1
        return f
    
    def turnOn(self, flag0:int) -> str:
        '''Turn on an output flag. Input is 0-indexed, but SBP is 1-indexed.'''
        f = self.convertFlag(flag0)
        s = f'SO, {f}, 1\n'
        self.file+=s
        self.pOn = True
        return s
    
    def turnOff(self, flag0:int) -> str:
        '''Turn off an output flag. Input is 0-indexed, but SBP is 1-indexed.'''
        f = self.convertFlag(flag0)
        s = f'SO, {f}, 0\n'
        self.file+=s
        self.pOn = False
        return s
    
    def snap(self, zeroJog:bool=False, wait1:Union[float,str]=0.5, wait2:Union[float,str]=0.5, camFlag:int=2):
        '''go to the point and snap a picture'''
        if zeroJog:
            self.m3(self.cp[0], self.cp[1], self.cp[2]) # add a zero move to fix timing issue
        self.snapPoints.append(self.cp)
        self.pause(wait1)
        self.turnOn(camFlag)
        self.pause(wait2)
        self.turnOff(camFlag)   
    
    #------------
    
    def convertFile(self, keys) -> str:
        '''Convert the file with any requested variables evaluated. e.g. if &spacing is defined in this file, and you want to evaluate it with &spacing=5, it will make those replacements and simplify. Use keys=['spacing']. Use a list of [] to make no replacements. '''
        if len(keys)==0:
            return self.file
        newfile = ''
        filelist = re.split('\n', self.file)
        for line in filelist:
            if line.startswith('&'):
                # this is a variable definition
                key = re.split('&|=| ', line)[1]
                if key in keys:
                    newline = ''
                else:
                    newline = line+'\n'
            else:
                coords = re.split(',', line)
                newline = ''
                for c in coords:
                    newline = newline + self.strSimplify(c, keys) + ', '
                newline = newline[:-2]
                newline+='\n'
            newfile+=newline
        return newfile
    
    
    #------------
    
    
    def convertPts(self, pts) -> np.ndarray:
        '''convert positions list to a list of float coordinates'''
        ptsout = []
        for p in pts:
            if type(p) is list:
                p2 = []
                for i in p:
                    try:
                        i2 = self.floatSC(i)
                    except:
                        raise ValueError('Cannot convert array to floats')
                    else:
                        p2.append(i2)
            else:
                try:
                    i2 = self.floatSC(p)
                except:
                    raise ValueError('Cannot convert array to floats')
                else:
                    p2 = i2
            ptsout.append(p2)
        try:
            out = np.array(ptsout)
        except:
            raise ValueError('Cannot convert list of pts to array')
        return out
    
    def convertAllPts(self) -> np.ndarray:
        return self.convertPts(self.positions)
    
    
    def plot(self, ele:float = 70, azi:float=35, export:bool=False, fn:str='', grids:bool=False) -> None:
        '''plot the toolpath'''
        self.sbp()
            
        xdim = 25
        ydim = 75
        zdim = 25
        mindim = min([xdim, ydim, zdim])
        x_scale=xdim/mindim
        y_scale=ydim/mindim
        z_scale=zdim/mindim
        if export:
            figsize = 6.5*zdim/ydim
        else:
            figsize=9.5
        fig = plt.figure(figsize=(figsize, figsize))
        ax = fig.add_subplot(111, projection='3d', proj_type = 'ortho')
        ax.view_init(elev=ele, azim=azi)
        plt.rc('font', size=16) 
        
        # set limits of the axes
        ax.set_xlim3d(0, xdim)
        ax.set_ylim3d(0, ydim)
        ax.set_zlim3d(-zdim, 0)

        # set dimensions of all axes to same scale
        scale=np.diag([x_scale, y_scale, z_scale, 1.0])
        scale=scale*(1.0/z_scale)
#         scale[3,3]=1.0
        ax.get_proj=lambda: np.dot(Axes3D.get_proj(ax), scale)

        if grids:
            lw = 4
        else:
            lw = 1
        
        for rowi in self.jogs:
            row = self.convertPts(rowi)
            if row[1,0]<xdim and row[1,1]<ydim and row[1,2]>-zdim and row[1,0]>0 and row[1,1]>0 and row[1,2]<0:
                ax.plot(row[:,0], row[:,1], zs=row[:,2], c='#a1a1a1', linestyle='dashed', linewidth=lw, clip_on=False)
        for rowi in self.unwritten:
            row = self.convertPts(rowi)
            if row[1,0]<xdim and row[1,1]<ydim and row[1,2]>-zdim and row[1,0]>0 and row[1,1]>0 and row[1,2]<0:
                ax.plot(row[:,0], row[:,1], zs=row[:,2], c='#f7b2d6', linewidth=lw, clip_on=False)
        for rowi in self.written:
            row = self.convertPts(rowi)
            ax.plot(row[:,0], row[:,1], zs=row[:,2], c='#3374a0', linewidth=lw*1.5, clip_on=False)
        
        if len(self.snapPoints)>0:
            snaps = self.convertPts(self.snapPoints)
            ax.scatter(snaps[:,0], snaps[:,1], zs=snaps[:,2], c='#90db74', s = lw*50, clip_on=False)
        
        
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1, wspace=0)
        ax.grid(grids)
        
        if not grids:
            ax.set_xlabel('')
            ax.set_ylabel('')
            ax.set_zlabel('')
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_zticks([])
        else:
            ax.set_xlabel('$X$')
            ax.set_ylabel('$Y$')
            ax.set_zlabel('$Z$')
        
        if export:
            if len(fn)>0 and len(os.path.dirname(fn))>0 and os.path.exists(os.path.dirname(fn)):
                fig.savefig(fn, bbox_inches='tight', dpi=300, transparent=True)
                print(f'Exported {fn}')
            plt.close()
        
        return
    
    def export(self, filename:str, *args) -> None:
        '''Export the .sbp file'''
        fout = self.convertFile(*args)
        File_object = open(filename,"w")
        File_object.write(fout)
        File_object.close()
        print("Exported file %s" % filename)
        sp = SBPPoints(filename)
        sp.export()
        
    def addVar(self, key:str, val:float) -> None:
        '''add the variable to the file and store the definition'''
        self.file+=f'&{key} = {fs(val)}\n'
        self.vardefs[key] = val
        
    def setSpeeds(self, **kwargs):
        '''Set move and jump speeds. Inputs could be m=5, j=20'''
        for i in kwargs:
            self.file+= f'{i.upper()}S, {kwargs[i]}, {kwargs[i]}\n'
            setattr(self, f'{i.upper()}S', kwargs[i]) # store speed
            
    def setRamps(self, mr:float=10.060, jr:float=10.060, rate:float=5.080, thresh:float=100, dist:float=3.810, corner:int=65):
        '''Set move and jump ramp speeds. Inputs could be m=5, j=20'''
        self.file+=f'VR,{mr}, {mr}, , , {jr}, {jr}, , , {rate}, {rate}, {thresh}, {dist}, {corner}, , , {rate}\n'
        
    def setUnits(self, **kwargs):
        '''Set the units to mm'''
        self.file+='VD , , 1\nVU, 157.480315, 157.480315, -157.480315\n'  # set mm, negative z is up
        self.file+='SA\n'  # set absolute
    
    
############---------------------------------
    
class defVars(sbpCreator):
    '''Holds onto variables defined in the .sbp file'''
    
    def __init__(self, **kwargs):
        super(defVars, self).__init__()
        for key, val in kwargs.items():
            self.addVar(key, val)
    
            
    

############---------------------------------

class startingPoint(sbpCreator):
    '''Creates an initial point'''
    
    def __init__(self, x, y, z):
        super(startingPoint, self).__init__()
        self.cp = [x,y,z]
        self.positions = [[x,y,z]]
        self.stepPoints = [[x,y,z]]
        
    def sbp(self) -> str:
        return self.file

############---------------------------------
    
class zigzag(sbpCreator):
    '''Creates a zigzag. flag0 is 0-indexed'''
    
    def __init__(self, flag0:int=0, **kwargs):
        super(zigzag, self).__init__(**kwargs)
        self.flag0 = flag0
        self.x0 = 0         # x0, y0, z0 are the corner of the zigzag
        self.y0 = 0
        self.z0 = 0
        self.spacing1 = 5   # mm # spacing1 is the spacing after odd passes
        self.spacing2 = 6   # mm # spacing2 is the spacing after even passes
        self.reps = 5       # reps is the number of passes
        self.width = 15     # width is the length of each pass
        self.longdir = '+x'  # longdir is the direction of the long lines
        self.shortdir = '+y' # shortdir is the direction of the short lines
            # directions can be '-x', '+x', '-y', '+y', '-z', '+z'
        for key,val in kwargs.items():
            if key in self.__dict__.keys():
                setattr(self, key, val)
        if 'lastPt' in kwargs:
            self.takeLastPt(kwargs['lastPt'])
        if 'killZigs' in kwargs:
            # killZigs true to turn off flow in between lines
            self.killZigs = kwargs['killZigs']
            
    def takeLastPt(self, other:sbpCreator) -> None:
        '''Take the last point from the previous drawing and set it as our new current point'''
        out = super(zigzag, self).takeLastPt(other)
        if out==0:
            self.x0 = self.cp[0]
            self.y0 = self.cp[1]
            self.z0 = self.cp[2]          
    
    
    def getLongList(self) -> List[float]:
        '''Get a list of coordinates in the long direction'''
        long0, plus = self.which0(self.longdir)  
        longlist = [long0, p(long0, t(plus, self.width))]
        self.longlist = longlist
        return longlist
    
    def getShortList(self) -> List[float]:
        '''Get a list of coordinates in the short direction'''
        short0, plus = self.which0(self.shortdir)
        shortlist = [p(short0, t(plus, self.spacing1, np.floor(i/2)), t(plus, self.spacing2, np.ceil(i/2))) for i in range(self.reps)]
        self.shortlist = shortlist
        return shortlist
        
    def sbp(self, zeroJog:bool=False) -> str:
        '''Create the sbp file. 
        If zeroJog=True, we add a zero jog just before the end of the line to fix the shopbot timing error. This method has been superceded by the wrapper in sbgui_print.py'''
        
        if self.created:
            # if already created, use the existing file
            return self.file
        self.created=True

        longlist = self.getLongList()
        shortlist = self.getShortList()
        
        self.reset()  # reset the file and position lists
        self.j2(self.x0, p(self.y0,-0.1), pOn=False) # go next to first xy position
        self.mz(self.z0) # go to first z position
        self.j2(self.x0, self.y0, pOn=False) # go to first xy position
        self.turnOn(self.flag0)
        llpos = 1

        if zeroJog:
            llf = [self.floatSC(longlist[0]), self.floatSC(longlist[1])]
            # linelen = p(max(llf),t(-1,min(llf)))
            if llf[0]<llf[1]:
                mids = [p(longlist[0],2),p(longlist[1],-2)]
            else:
                mids = [p(longlist[1],2),p(longlist[0],-2)]
        
            self.m1(self.longdir[1], mids[llpos], pOn=True) # write first part of first line
            self.j1(self.shortdir[1], shortlist[0], pOn=False) # zero move to fix turnoff
            
        self.m1(self.longdir[1], longlist[llpos], pOn=True) # write rest of first line
        for index,i in enumerate(shortlist[1:]):
            if llpos==1:
                llpos = 0
            else:
                llpos = 1
            if self.killZigs:
                self.turnOff(self.flag0)
                self.j1(self.shortdir[1], i, pOn=False) # zig
                self.turnOn(self.flag0)
                if zeroJog:
                    self.m1(self.longdir[1], mids[llpos], pOn=True) # write next line
                    self.j1(self.shortdir[1], i, pOn=False) # zero move to fix turnoff
            else:
                self.m1(self.shortdir[1], i, pOn=True) # zig  
                if zeroJog and index==len(shortlist[1:])-1:
                    self.m1(self.longdir[1], mids[llpos], pOn=True) # partial line
                    self.j1(self.shortdir[1], i, pOn=False) # zero move to fix turnoff
            self.m1(self.longdir[1], longlist[llpos], pOn=True) # write next line
            
        if len(self.positions)>1:
            self.stepPoints = [self.positions[1]]
            
        self.turnOff(0)
        return self.file

########################################
    
class verts(sbpCreator):
    '''Creates a series of vertical lines. Input flag0 is 0-indexed.'''
    
    def __init__(self, flag0:int=0, **kwargs):
        super(verts, self).__init__(**kwargs)
        self.flag0= flag0
        self.downdisp = 0 # displacement between downstroke and upstroke
        self.reps = 5       # reps is the number of passes

        if 'zigzag' in kwargs:
            try:
                self.matchToZigZag(**kwargs)
            except Exception as e:
                print(e)
                self.initFromScratch()
        elif 'vert' in kwargs:
            try:
                self.matchToVerts(**kwargs)
            except:
                self.initFromScratch()
        else:
            self.initFromScratch()
            
        for key,val in kwargs.items():
            if key in self.__dict__.keys():
                setattr(self, key, val)
            
    def initFromScratch(self):
        '''initialize a list of vertical lines'''
        
        self.longdir = '+x'  # longdir is the direction of the positions we're predicting from spacing
            # for example, if we've already written a zigzag with a long direction of +x,
            # we should make the longdir here +x
        self.shortdir = '+y' # shortdir is the direction of the positions we're lining up with existing lines
            # for example, if we've already written a zigzag with a short direction of +x, 
            # we should make shortdir here +y and steal the shortlist from the zigzag
            # directions can be '-x', '+x', '-y', '+y', '-z', '+z'

        self.spacing = 5   # mm spacing between lines
        self.setZBounds(-12.5, self.spacing)
        self.longreps = 5
        self.shortreps = 1
        self.downdisp = 0
        
    def setZBounds(self, zmed:float, zspacing:float)->None:
        '''Set the top and bottom z points. zmed is the middle point of the line, zspacing is half of the length of the line.'''
        self.zmin = p(zmed, t(-1, zspacing))
        self.zmax = p(zmed, zspacing)

    
    
    def matchToZigZag(self, **kwargs) -> None:
        '''Match the initial point and coordinates to an existing zigzag object. 
        zz is a zigzag object
        start is the index of the first line in the shortlist to match
        end is the index of the last line in the shortlist to match
        disp is the displacement off the existing line to set the vertical lines(e.g. -0.5)'''
        
        if 'zigzag' not in kwargs or 'start' not in kwargs or 'end' not in kwargs or 'disp' not in kwargs:
            raise Exception
        zz = kwargs['zigzag']
        self.longlist0 = zz.longlist
        zz.sbp()
        self.longdir = zz.longdir
        self.shortdir = zz.shortdir
        
        # get short list
        sl = zz.shortlist.copy()
        start = kwargs['start']
        end = kwargs['end']
        if start==end:
            self.shortlist = [p(sl[start], kwargs['disp'])]
        else:
            if start>end:
                start0 = end
                end0 = start
            else:
                start0 = start
                end0 = end
            self.shortlist = [p(sl[i], t(kwargs['disp'], oddNeg(i-1))) for i in range(start0, end0+1)]
            if start>end:
                self.shortlist.reverse()
         
        # get spacings
        self.setSpacing(zz.spacing1) 
        
        # get z positions
        zmid = zz.positions[0][2]
        self.setZBounds(zmid, self.spacing1)
        
    
        
    def setSpacing(self, *args)->None:
        '''Determine the spacing between lines. Input one or two spacings, one if you want uniform spacing, two if you want spacing to go ababab'''
        if len(args)==1:
            self.spacing1 = args[0]
            self.spacing2 = args[0]
        else:
            self.spacing1 = args[0]
            self.spacing2 = args[1]

        sp1 = self.floatSC(self.spacing1)
        sp2 = self.floatSC(self.spacing2)
        
        long1 = self.floatSC(self.longlist0[1])
        long2 = self.floatSC(self.longlist0[0])

        self.longreps = int(np.ceil(2*abs(long1 - long2)/(sp1+sp2)))
        if not self.spacing1==self.spacing2:
            if self.longreps%2==1:
                self.longreps+=1
        plus = self.whichPlus(self.longdir)
        self.longlist = [self.altsp(self.longlist0[0], plus, i) for i in range(self.longreps)]
#         self.longlist = [p(self.longlist0[0], t(i, spacing)) for i in range(self.longreps)]
        
    def upDownRow(self, direc='+x', longlist = [5,20], const=0) -> None:
        '''One row of vertical lines. direction is the direction that the row is in, e.g. +x or -y. Longlist is the list of coordinates to hit. const is the coordinate of x or y that is held constant.'''
        self.longdir = direc
        if self.longdir[1]=='x':
            self.shortdir = '+y' 
            # the sign of the shortdir doesn't actually matter because we're only doing one line
        else:
            self.shortdir = '+x'
            
        self.longlist0 = longlist
        self.shortlist = [const]
    
     
    
    def singleUpDownRow(self, direc='+x', longlist = [5,20], const=0, spacing1=1, **kwargs) -> None:
        '''One row of vertical lines, given a spacing. longlist is the endpoints of the row
        direc is the direction that the row goes in
        const is the constant coordinate of the row'''
        self.upDownRow(direc, longlist, const)

        self.shortreps = 1   
        if 'spacing2' in kwargs:
            self.setSpacing(spacing1, kwargs['spacing2'])
        else:
            self.setSpacing(spacing1)
            
    def upDownRowReps(self, direc:str='+y', p0:float=0, const:float=0, spacing:float=1, reps:int=2) -> None:
        '''given a direction (direct), an initial point p0, a constant dimension for the other direction const, a spacing between lines, and a number of reps, set the lists'''
        longlist = [p(p0, t(spacing, i)) for i in range(reps)] # list of points
        self.upDownRow(direc, longlist, const)
        self.longreps = reps
        self.longlist = longlist
        self.spacing1=spacing
        
        
        
    def matchToVerts(self, **kwargs) -> None:
        '''Match initial conditions and spacings to an existing row of vertical lines. vert should be a verts object. dshort is the distance between the existing row and new row in the short direction. dlong is the distance between the existing row and new row along the long direction, which is the direction of the row.'''
        if 'vert' not in kwargs or 'dshort' not in kwargs or 'dlong' not in kwargs:
            raise Exception
        v = kwargs['vert']
        self.longdir = v.longdir
        self.shortdir = v.shortdir
        self.shortlist = [i+kwargs['dshort'] for i in v.shortlist]
        self.longlist = [i+kwargs['dlong'] for i in v.longlist]
        self.spacing = v.spacing
        self.longreps = v.longreps    
        self.zmin = v.zmin
        self.zmax = v.zmax

    
    def sbp(self, zeroJog:bool=False):
        '''Create the sbp file.
        If zeroJog=True, we add a zero jog just before the end of the line to fix the shopbot timing error. This method has been superceded by the wrapper in sbgui_print.py'''
        
        if self.created:
            return self.file
        
        self.created=True
        
        m1 = float(self.longdir[0]+'1') # sign of the long direction
        if type(self.downdisp) is float:
            self.downdisp = abs(self.downdisp)
            self.downdisp = m1*self.downdisp
        else:
            ddfl = self.floatSC(self.downdisp)
            if not np.sign(ddfl)==np.sign(m1):
                self.downdisp = t(-1, self.downdisp)

        longlist = self.longlist
        shortlist = self.shortlist
        
        self.reset() # reset the file and position lists
        rev = False
        ll = longlist
        llr = longlist.copy()
        llr.reverse()
            
        self.j1('z', self.zmax) # go high

        for spos in shortlist:
            self.j1(self.shortdir[1], spos) # go to short coord
            
            # reverse the printing order on every other
            if rev:
                ll1 = llr
                mult = 1
            else:
                ll1 = ll
                mult = -1
                
            rev = not rev
            
            # for each position in longlist, jog to pos, jog plunge, move draw
            for lpos in ll1:
                if self.downdisp!=0:
                    lpos0 =  p(lpos, t(mult, self.downdisp))
                else:
                    lpos0 = lpos
                self.j1(self.longdir[1], lpos0) 
                    # go to first long coord, less one downdisp
                self.j1('z', self.zmin) # plunge
                
                if self.downdisp!=0:
                    self.j1(self.longdir[1], lpos) 
                    # go to coord if not already there
                self.turnOn(self.flag0)
                if zeroJog:
                    self.m1('z', p(self.zmax,-2), pOn=True) # draw most of z
                    self.j1(self.longdir[1], lpos0) # zero move to turn off flow at right time
                self.m1('z', self.zmax, pOn=True) # draw z
                self.turnOff(self.flag0)
            
        if len(self.positions)>1:
            self.stepPoints = [self.positions[0]]

            
        return self.file
    
class disturb(sbpCreator):
    '''write a line, observe it, disturb it, observe it. 
    writeDir is the direction to write in, writeLength of length of written line and disturbed line
    shiftDir is the direction to displace the observed point towards, and shiftLength is the distance the observed point is displaced from the written line
    distDir is the direction to displace the disturbed line, and distLength is the distance the disturbed line is displaced from the written line
    initPt is the first point in the written line
    shiftFrac is the weighting between the beginning and end of the line when finding the observation point. higher to weight the initial point more
    writeExtend>0 to keep moving after flow stops
    wait1 is the time between reaching the observation point and turning on the camera flag
    wait2 is the time between turning on the camera flag and turning off the camera flag
    wait3 is the time between turning off the camera flag and turning it on again
    '''
    
    def __init__(self, flowFlag:int=0, camFlag:int=2
                 , writeDir:str='+y', writeLength:Union[str,float]=10
                 , shiftDir:str='+z', shiftLength:Union[str,float]=5
                 , distDir:str='+z', distLength:Union[str,float]=1
                 , initPt:list=[0,0,0]
                 , shiftFrac:float=0.5
                 , writeExtend:float=0
                 , wait1:Union[str, float]=0.5, wait2:Union[str, float]=0.5, wait3:Union[str, float]=3
                 , numLines:int=1, turnOnFrac:float=1, turnOnWait:float=0, turnOffWait:float=0
                 , **kwargs):
        super(disturb, self).__init__(**kwargs)
        self.flowFlag = flowFlag
        self.camFlag = camFlag
        self.writeDir = writeDir
        self.writeLength = writeLength
        self.shiftDir = shiftDir
        self.shiftLength = shiftLength
        self.distLength = distLength
        self.distDir = distDir
        self.initPt = initPt
        self.shiftFrac = shiftFrac
        self.writeExtend = writeExtend
        self.wait1 = wait1
        self.wait2 = wait2
        self.wait3 = wait3
        self.numLines = numLines
        self.turnOnFrac = turnOnFrac
        self.turnOnWait = turnOnWait
        self.turnOffWait = turnOffWait
        self.getPoints()
    
    def getPoints(self):
        '''determine the beginning and end of the 1st line (w)rite, observe, 2nd line (d)isturb, and 3rd line (e) lines'''
        self.pts = {}
        for s in ['w0', 'wf', 'wf2', 'o', 'd0', 'df', 'df2', 'e0', 'ef', 'ef2']:
            self.pts[s] = self.initPt.copy()
        
        # calculate write positions
        self.windex = {'x':0, 'y':1, 'z':2}[self.writeDir[-1]]
        if self.writeDir[0]=='-':
            self.writeLength = t(-1, self.writeLength)
            self.writeExtend = t(-1, self.writeExtend)
        x0 = self.initPt[self.windex]
        xf = p(x0, self.writeLength)   
        for s in ['wf', 'df', 'ef']:
            # set value of final written and disturbed points
            self.pts[s][self.windex] = xf
        
        self.pts['o'][self.windex] = f'{self.shiftFrac}*({x0})+{1-self.shiftFrac}*({xf})'  # put observe point in middle of line
        
        # extend the written line
#         self.pts['wf2'] = self.pts['wf'].copy()
        for ss in ['wf2', 'df2', 'ef2']:
            self.pts[ss] = self.pts[ss[:-1]].copy()
            if not self.writeExtend==0:
                self.pts[ss][self.windex] = p(self.pts[ss][self.windex], self.writeExtend) 
        
        # calculate observe positions
        self.oindex = {'x':0, 'y':1, 'z':2}[self.shiftDir[-1]]
        if self.shiftDir[0]=='-':
            self.shiftLength = t(-1, self.shiftLength)
        self.pts['o'][self.oindex] = p(self.initPt[self.oindex], self.shiftLength)   # shift observe point over
        
        # calculate disturb positions
        self.dindex = {'x':0, 'y':1, 'z':2}[self.distDir[-1]]
        if self.distDir[0]=='-':
            self.distLength = t(-1, self.distLength)
        for s in ['d0', 'df', 'df2']:
            self.pts[s][self.dindex] = p(self.initPt[self.dindex], self.distLength)   # shift disturb point over
        for s in ['e0', 'ef', 'ef2']:
            self.pts[s][self.dindex] = p(self.initPt[self.dindex], f'2*{self.distLength}')   # shift disturb point over
            
        # for i,val in self.pts.items():
        #     print(i, [self.floatSC(j) for j in val])
            
    def writeLine(self, p:str='w'):
        '''write the initial line'''
        # write line
        if self.writeDir=='+z':
            # vertical line. come in from the top
            self.mz(self.pts[f'{p}f2'][2])  
            self.m2(self.pts[f'{p}0'][0], self.pts[f'{p}0'][1])
        self.j3(*self.pts[f'{p}0'])  # move to the initial point
        self.turnOn(self.flowFlag)  # turn on flow
        self.m3(*self.pts[f'{p}f'])  # go to final written point
        self.turnOff(self.flowFlag) # turn off flow
        if not self.writeExtend==0:
            self.m3(*self.pts[f'{p}f2'])
            
    def observe(self):
        '''go to the observation position'''
        # observe line
        ofunc = 'm'+self.shiftDir[-1]
        getattr(self, ofunc)(self.pts['o'][self.oindex])  # move just in the observation direction
        self.m3(*self.pts['o']) # then to the observation point
        self.snap(zeroJog=False, wait1=self.wait1, wait2=self.wait2, camFlag=self.camFlag)  # take picture
        self.pause(self.wait3)             # wait
        self.snap(zeroJog=False, wait1=self.wait1, wait2=self.wait2, camFlag=self.camFlag)  # take another picture
        
    def midpoint(self, p1:list, p2:list, frac:float) -> list:
        '''get the midpoint between 2 points, weighted by frac'''
        x0 = p1[0]
        y0 = p1[1]
        z0 = p1[2]
        x1 = p2[0]
        y1 = p2[1]
        z1 = p2[2]
        x = f'{frac}*({x0})+{1-frac}*({x1})' 
        y = f'{frac}*({y0})+{1-frac}*({y1})' 
        z = f'{frac}*({z0})+{1-frac}*({z1})' 
        return [x,y,z]
        
    def makeLine(self, p:str='w', write:bool=False):
        '''disturb the line'''

        if self.writeDir=='+z':
            # vertical line. come in from the top
            self.mz(self.pts[f'{p}f2'][2])  
            self.m2(self.pts[f'{p}f2'][0], self.pts[f'{p}f2'][1])
            if self.turnOnFrac<1 and write:
                self.m3(*self.midpoint(self.pts[f'{p}0'], self.pts[f'{p}f2'], self.turnOnFrac))
                self.turnOn(self.flowFlag)
        else:
            dfunc = 'm'+self.writeDir[-1]
            getattr(self, dfunc)(self.pts[f'{p}0'][self.windex])  # move just in the writing direction
            if not self.shiftDir==self.distDir:
                dfunc = 'm'+self.distDir[-1]
                if self.turnOnFrac<1 and write:
                    val = self.midpoint([self.pts[f'{p}0'][self.dindex]], self.cp[self.dindex], self.turnOnFrac)
                    getattr(self, dfunc)(val)
                    self.turnOn(self.flowFlag)
                getattr(self, dfunc)(self.pts[f'{p}0'][self.dindex])  # move just in the disturb shift direction
            else:
                if self.turnOnFrac<1 and write:
                    self.m3(*self.midpoint(self.pts[f'{p}0'], self.cp, self.turnOnFrac))
                    self.turnOn(self.flowFlag)

        self.m3(*self.pts[f'{p}0'])
        if write and not (self.turnOnFrac<1):
            self.turnOn(self.flowFlag)
        if self.turnOnWait>0 and write:
            self.pause(self.turnOnWait)
        self.m3(*self.pts[f'{p}f'])
        if write:
            self.turnOff(self.flowFlag)
        if not self.writeExtend==0:
            self.m3(*self.pts[f'{p}f2'])
        if self.turnOffWait>0 and write:
            self.pause(self.turnOffWait)
                 
    def sbp(self):
        if self.created:
            return self.file
        
        self.created=True
        self.makeLine(p='w', write=True)
        self.observe()
        self.makeLine(p='d', write=(self.numLines>1))
        self.observe()  
        if self.numLines>1:
            self.makeLine(p='e', write=(self.numLines>2))  # disturb at the 3rd position
            self.observe()
        
        return self.file
         
            
    
    
class pics(sbpCreator):
    '''Take pictures'''
    
    
    def __init__(self, flag0:int=2, wait:float=5, **kwargs):
        super(pics, self).__init__(**kwargs)
        self.flag0 = flag0   # 0-indexed
        self.wait = wait
 
    def sbp(self):
        return self.file
        
    
        
