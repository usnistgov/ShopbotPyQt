import math
import numpy as np
import os
import sys
import re
from typing import List, Dict, Tuple, Union, Any, TextIO
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import sympy as sy

        
def oddNeg(n:int)->int:
    return 2*((n%2)-1/2)

def fs(i) -> str:
    if type(i) is str:
        return i
    else:
        return '%3.2f' % i
    
# generic plus float function
def pf(a:float, b:float)->float:
    return a+b

# generic multiply float function
def mf(a:float, b:float)->float:
    return a*b 
    
# plus or times for combos of strings and floats
def pt(*dims, **kwargs) -> Union[str, float]:
    s = ''
    if kwargs['mode']=='add':
        toti = 0
        op = ' + '
        opf = pf

    elif kwargs['mode']=='mult':
        toti = 1
        op = ' * '
        opf = mf
    else:
        raise ValueError('mode must be add or mult')
      
    tot = toti
    for d in dims:
        try:
            d1 = float(d)
        except:
            if not d[0]=='(' and ('-' in d or '+' in d):
                dparen = '('+d+')'
            else:
                dparen = d
            s = s + dparen + op
        else:
            tot = opf(tot, d1)
    if len(s)==0:
        return tot
    elif tot==toti:
        return s[:-3]
    else:
        return s + fs(tot)

# add combos of strings and floats
def p(*dims) -> Union[str, float]:
    return pt(*dims, mode='add')

# multiply combos of strings and floats
def t(*dims) -> Union[str, float]:
    return pt(*dims, mode='mult')

#############-----------------------------------

class sbpCreator:
    def __init__(self, **kwargs):
        self.channel = 0    # channel is the pressure channel to turn on
        self.file = ''
        self.cp = [0,0,0] # current point
        self.positions = []
        self.stepPoints = []
        self.vardefs = {}
        if 'lastPt' in kwargs:
            self.takeLastPt(kwargs['lastPt'])
    
    # function for adding two sbpcreators togethers
    def __add__(self, other):
        scout = sbpCreator()
        self.sbp()
        other.sbp()
        scout.file = self.file + other.file
        scout.cp = other.cp
        scout.positions = self.positions + other.positions
        scout.stepPoints = self.stepPoints + other.stepPoints
        scout.vardefs = {**self.vardefs, **other.vardefs}
        return scout
    
    # return 1 if the last point is not valid
    def takeLastPt(self, other) -> int:
        self.vardefs = {**self.vardefs, **other.vardefs}
        if len(other.positions)>0:
            lp = other.positions[-1]
            self.cp = lp.copy()
        else:
            return 1
        return 0
    
    def whichPlus(self, longdir:str) -> int:
        if longdir[0]=='-':
            return -1
        else:
            return 1  
    
    def which0(self, longdir:str) -> Tuple[float, int]:
        # determine the endpoints of the long lines
        if longdir[1]=='x':
            long0 = self.x0
        elif longdir[1]=='y':
            long0 = self.y0
        else:
            long0 = self.z0
        plus = self.whichPlus(longdir) 
        return long0, plus
    
    def altsp(self, p0, plus, i):
        p1 = t(plus, self.spacing1, np.floor(i/2))
        p2 = t(plus, self.spacing2, np.ceil(i/2))
        return p(p0, p1, p2)
    
     # NOTE: the number of reps in the zigzag is fixed and cannot change if you go back and change the header variables (e.g. '&spacing'), so you can either set it using this function or set it manually, but if you want the number of reps to be responsive to '&spacing', etc., you need to rebuild the whole file
    def updateReps(self, slideH:float, margin:float, divisible:int) -> None:
        s1 = self.floatSC(self.spacing1)
        s2 = self.floatSC(self.spacing2)
        r = np.floor((slideH - 2*margin) / (s1 + s2) * 2)
        r = np.floor(r/divisible)*divisible
        self.reps = int(r)
    
    def reset(self):
        self.file = ''
        self.positions = []
    
    # update the list of positions and file
    # this should be redefined for each specific case
    def sbp(self):
        return self.file
    
    def floatSC(self, vi) -> float:
        try:
            vout = float(vi)
        except:
            if type(vi) is str:
                for key, val in self.vardefs.items():
                    vi = vi.replace('&'+key, str(val))
                try:
                    vout = eval(vi)
                except:
                    print(vi)
                    raise TypeError('Cannot convert to float')
                else:
                    return vout
            else:
                raise TypeError('Cannot convert to float')
        else:
            return vout
        
    def strSimplify(self, vi, *args) -> str:
        if not type(vi) is str:
            return vi
        if len(args)==0:
            defdict = self.vardefs
        else:
            defdict = {key: value for key, value in self.vardefs.items() if key in args[0]} 
        for key, val in defdict.items():
            vi = vi.replace('&'+key, fs(val))
        
        vin = vi.replace('&', 'UND')

        try:
            vout = sy.simplify(vin)
        except:
            vout = vi
        else:
            try:
                vout = fs(vout)
            except:
                vout = str(vout)
            vout = vout.replace('UND', '&')
        vout = vout.replace(' 1.0*', '')
        vout = vout.replace('-1.0*', '-')
        vout = vout.replace('+1.0*', '+')
        vout = vout.replace('*1.0*', '*')
        vout = vout.replace(' + 0.0', '')
        vout = vout.replace('.00000000000001', '.0')
        return vout
    
    # this if for simplifying and formatting as string without any variable replacements
    def fsss(self, vi) -> str:
        if type(vi) is str:
            return self.strSimplify(vi, [0])
        else:
            return fs(vi)
        
    
    #------------
    
    # search the dictionary for the string (e.g. 'x', 'y', 'z'). 
    # If it's not there, return the coord from the point cp
    def updatePtsXYZ(self, dic:Dict, st:str):  
        if st in dic:
            val = dic[st]
        else:
            idx = ['x','y','z'].index(st)
            val = self.cp[idx]
        return val
        
    def updatePts(self, **kwargs):
        x = self.updatePtsXYZ(kwargs, 'x')
        y = self.updatePtsXYZ(kwargs, 'y')
        z = self.updatePtsXYZ(kwargs, 'z')
        self.cp = [x,y,z]
        self.positions.append([x,y,z])
        
    
                
    #------------
    # move commands
    #------------
    # direc is a direction (e.g. '+x')
    # position is a coordinate (e.g. 5.0)
    # ms is move string ('M' or 'J')
    
    #-----
    def mj3(self, x:Union[float, str], y:Union[float, str], z:Union[float, str], ms:str) -> str:
        s = ms.upper() + '3, ' + self.fsss(x) + ', ' + self.fsss(y) + ', ' + self.fsss(z) + '\n'
        self.updatePts(x=x, y=y, z=z)
        self.file+=s
        return s
    
    def m3(self, x:Union[float, str], y:Union[float, str], z:Union[float, str]) -> str:
        return self.mj3(x,y,z,'M')
    
    def j3(self, x:Union[float, str], y:Union[float, str], z:Union[float, str]) -> str:
        return self.mj3(x,y,z,'J')
    
    #-----
    def mj2(self, x:Union[float, str], y:Union[float, str], ms:str) -> str:
        s = ms.upper() + '2, ' + self.fsss(x) + ', ' + self.fsss(y) + '\n'
        self.updatePts(x=x, y=y)
        self.file+=s
        return s

    def m2(self, x:Union[float, str], y:Union[float, str]) -> str:
        return self.mj2(x, y, 'M')
    
    def j2(self, x:Union[float, str], y:Union[float, str]) -> str:
        return self.mj2(x, y, 'J')
    
    #-----
    def mj1(self, direc:str, position:Union[float, str], ms:str) -> str:
        if len(direc)>1:
            dire = direc[-1]
        else:
            dire = direc
        s = ms.upper() + dire.upper() + ', ' + self.fsss(position) + '\n'
        if dire=='x':
            self.updatePts(x=position)
        elif dire=='y':
            self.updatePts(y=position)
        else:
            self.updatePts(z=position)
        self.file+=s
        return s
    
    def m1(self, direc:str, position:Union[float, str]) -> str:
        return self.mj1(direc, position, 'M')
    
    def j1(self, direc:str, position:Union[float, str]) -> str:
        return self.mj1(direc, position, 'J')

    def jz(self, z:Union[float, str]) -> str:
        return self.mj1('Z', z, 'J')
    
    def withdraw(self) -> None:
        self.mj1('Z', 10, 'J')
        self.mj1('Y', 150, 'J')
        self.mj1('X', 80, 'J')
        return 

    #------------
    
    def turnOnSpindle(self) -> str:
        s = 'SetSpindleStatus,1\n'
        self.file+=s
        return s
    
    def turnOn(self, channel:int) -> str:
        s = 'SO, ' + str(channel+1) + ', 1\n'
        self.file+=s
        return s
    
    def turnOff(self, channel:int) -> str:
        s = 'SO, ' + str(channel+1) + ', 0\n'
        self.file+=s
        return s
    
    #------------
    
    def convertFile(self, keys) -> str:
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
    
    # convert positions list to a list of float coordinates
    def convertPts(self, pts) -> np.ndarray:
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
    
    # plot the toolpath
    def plot(self, ele:float = 70, azi:float=35) -> None:
        self.sbp()
        if len(self.positions)==0:
            raise Exception('No points to plot')
        try:
            pts = self.convertPts(self.positions)
            sp = self.convertPts(self.stepPoints)
        except Exception as e:
            raise e

        fig = plt.figure(figsize=(15,15))
        ax = fig.add_subplot(111, projection='3d')
        ax.view_init(elev=ele, azim=azi)
        
        xdim = 25
        ydim = 75
        zdim = 25
        mindim = min([xdim, ydim, zdim])
        x_scale=xdim/mindim
        y_scale=ydim/mindim
        z_scale=zdim/mindim

        scale=np.diag([x_scale, y_scale, z_scale, 1.0])
        scale=scale*(1.0/scale.max())
        scale[3,3]=1.0

        def short_proj():
            return np.dot(Axes3D.get_proj(ax), scale)

        ax.get_proj=short_proj

        mx = min(pts[:,0])
        my = min(pts[:,1])
        mz = min(pts[:,2])
        maxdim = max([max(pts[:,0]) - mx, max(pts[:,1]) - my, max(pts[:,2]) - mz])
        ax.set_xlim3d(0, xdim)
        ax.set_ylim3d(0, ydim)
        ax.set_zlim3d(-zdim, 0)
        ax.plot(pts[:,0], pts[:,1], zs=pts[:,2])
             
        ax.scatter([sp[:,0]], [sp[:,1]], [sp[:,2]], c='red')
        ax.set_xlabel('$X$')
        ax.set_ylabel('$Y$')
        ax.set_zlabel('$Z$')
        #fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        
        return ax
    
    def export(self, filename:str, *args) -> None:
        fout = self.convertFile(*args)
        File_object = open(filename,"w")
        File_object.write(fout)
        File_object.close()
        print("Exported file %s" % filename)
    
    
############---------------------------------
    
class defVars(sbpCreator):
    def __init__(self, **kwargs):
        super(defVars, self).__init__()
        for key, val in kwargs.items():
            self.file+='&' + key + ' = ' + fs(val) + '\n'
        self.vardefs = {**self.vardefs, **kwargs}
    
    def setSpeeds(self, **kwargs):
        for i in kwargs:
            self.file+= i.upper() + 'S, ' + str(kwargs[i]) + '\n'
            
    def setUnits(self, **kwargs):
        self.file+='VD , , 1\nVU, 157.480315, 157.480315, -157.480315\n'

############---------------------------------

class startingPoint(sbpCreator):
    def __init__(self, x, y, z):
        super(startingPoint, self).__init__()
        self.cp = [x,y,z]
        self.positions = [[x,y,z]]
        self.stepPoints = [[x,y,z]]
        
    def sbp(self) -> str:
        return self.file

############---------------------------------
    
class zigzag(sbpCreator):
    def __init__(self, **kwargs):
        super(zigzag, self).__init__(**kwargs)
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
            
    def takeLastPt(self, other) -> None:
        out = super(zigzag, self).takeLastPt(other)
        if out==0:
            self.x0 = self.cp[0]
            self.y0 = self.cp[1]
            self.z0 = self.cp[2]          
    
    
    def getLongList(self) -> List[float]:
        long0, plus = self.which0(self.longdir)  
        longlist = [long0, p(long0, t(plus, self.width))]
        self.longlist = longlist
        return longlist
    
    def getShortList(self) -> List[float]:
        short0, plus = self.which0(self.shortdir)
        shortlist = [p(short0, t(plus, self.spacing1, np.floor(i/2)), t(plus, self.spacing2, np.ceil(i/2))) for i in range(self.reps)]
        self.shortlist = shortlist
        return shortlist
        
    def sbp(self) -> str:
        longlist = self.getLongList()
        shortlist = self.getShortList()
        
        self.reset()  # reset the file and position lists
        self.m2(self.x0, self.y0) # go to first xy position
        self.jz(self.z0) # go to first z position
        self.turnOn(0)
        llpos = 1
        self.m1(self.longdir[1], longlist[llpos]) # write first line
        for i in shortlist[1:]:
            if llpos==1:
                llpos = 0
            else:
                llpos = 1
            self.m1(self.shortdir[1], i) # zig
            self.m1(self.longdir[1], longlist[llpos]) # write next line
            
        if len(self.positions)>1:
            self.stepPoints = [self.positions[1]]
            
        self.turnOff(0)
        return self.file

########################################
    
class verts(sbpCreator):
    def __init__(self, **kwargs):
        super(verts, self).__init__(**kwargs)

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
        self.zmin = p(zmed, t(-1, zspacing))
        self.zmax = p(zmed, zspacing)

    
    # zz is a zigzag object
    # start is the index of the first line in the shortlist to match
    # end is the index of the last line in the shortlist to match
    # disp is the displacement off the existing line to set the vertical lines(e.g. -0.5)
    def matchToZigZag(self, **kwargs) -> None:
        
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

        self.longreps = int(np.floor(2*abs(long1 - long2)/(sp1+sp2)))
        if not self.spacing1==self.spacing2:
            if self.longreps%2==1:
                self.longreps+=1
        plus = self.whichPlus(self.longdir)
        self.longlist = [self.altsp(self.longlist0[0], plus, i) for i in range(self.longreps)]
#         self.longlist = [p(self.longlist0[0], t(i, spacing)) for i in range(self.longreps)]
        
    def upDownRow(self, direc='+x', longlist = [5,20], const=0) -> None:
        self.longdir = direc
        if self.longdir[1]=='x':
            self.shortdir = '+y' 
            # the sign of the shortdir doesn't actually matter because we're only doing one line
        else:
            self.shortdir = '+x'
            
        self.longlist0 = longlist
        self.shortlist = [const]
    
     
    # longlist is the endpoints of the row
    # direc is the direction that the row goes in
    # const is the constant coordinate of the row
    def singleUpDownRow(self, direc='+x', longlist = [5,20], const=0, spacing1=1, **kwargs) -> None:
        self.upDownRow(direc, longlist, const)

        self.shortreps = 1   
        if 'spacing2' in kwargs:
            self.setSpacing(spacing1, kwargs['spacing2'])
        else:
            self.setSpacing(spacing1)
        
        
    def matchToVerts(self, **kwargs) -> None:
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

    
    def sbp(self):
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
        
#         self.turnOn()
        
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
                self.turnOn(0)
                self.m1('z', self.zmax) # draw z
                self.turnOff(0)
            
        if len(self.positions)>1:
            self.stepPoints = [self.positions[0]]
            
#         self.turnOff()
            
        return self.file
        
