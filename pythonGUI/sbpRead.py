#!/usr/bin/env python
'''Functions for reading shopbot files'''

# external packages
import os
import sys
import re
from typing import List, Dict, Tuple, Union, Any, TextIO
import pandas as pd
import logging
import numpy as np

# local files
from sbpConvert import *

#-----------------------------------------------------

class SBPHeader:
    '''read header data from the current shopbot file and return an object'''
    
    def __init__(self, sbpName:str):
        if not os.path.exists(sbpName):
            return
        self.SBPfile=os.path.basename(sbpName)
        self.hrows = 0  # number of rows in the header
        self.vardefs = {}
        
        # read the header into the dictionary
        with open(sbpName, mode='r') as f:
            cont = True
            while cont:
                l = f.readline()
                self.hrows+=1
                cont = self.readLine(l)
            # self.hrows-=1
                
    def readToDict(self, spl:List[str], idict:dict) -> dict:
        '''given a dictionary of indices and names, read values into the dictionary'''
        for key,name in idict.items():
            if len(spl)>key:
                val = spl[key]
                if type(val) is float or len(val)>0:
                    setattr(self, name, val)

    def checkSpl(self, command:str, l:str) -> Tuple[List, int]:
        '''check if the line contains the command. return empty dictionary, list of entries, and number of entries'''
        if not l.startswith(command):
            raise ValueError(f'{l} is not a {command} command')
        else:
            spl = splitStrip(l)
            return spl, len(spl)

    #----------------------------------------

    def readMS(self, l:str) -> None:
        '''read a MS command 
        {XY Move Speed, Z Move Speed, A Move Speed, B Move Speed}'''
        spl, entries = self.checkSpl('MS', l) 
        d = dict([[i+1,'speed_move_'+['xy', 'z', 'a', 'b'][i]] for i in range(4)])
        self.readToDict(spl, d)

    def readJS(self, l:str) -> None:
        '''read a JS command 
        {XY Jog Speed, Z Jog Speed, A Jog Speed, B Jog Speed}'''
        spl, entries = self.checkSpl('JS', l) 
        d = dict([[i+1,'speed_jog_'+['xy', 'z', 'a', 'b'][i]] for i in range(4)])
        self.readToDict(spl, d)

    def readVD(self, l:str) -> None:
        '''read a VD command. l is the whole line. 
        {-obsolete-, number of axes, linear units, units type A, units type B, -
    obsolete-, display file comments, keypad fixed distance, keypad remote, write
    part file log, write system log, message screen loc X, message screen loc Y,
    message screen size X, message screen size Y, show file progress}, keypad
    switches auto-off, show file progress, main display type'''
        spl, entries = self.checkSpl('VD', l)        
        self.readToDict(spl, {1:'axes'})

        for row in [[2,'XYZ'], [3, 'A'], [4, 'B']]:
            # units for xyz, a, and b axes
            if entries>row[0]:
                if int(spl[row[0]])==1:
                    setattr(self, f'{row[1]}_units', 'mm')
                elif int(spl[row[0]])==0:
                    setattr(self, f'{row[1]}_units', 'in')
                    
    def readVL(self,l:str) -> None:
        '''read a VL command. l is hte whole line.
            {low-X , high-X, low-Y , high-Y, low-Z , high-Z, low-Acc , high-Acc, [1-file 
            limit checking ON or 0-limit checking OFF], low-B, high-B}'''
        spl, entries = self.checkSpl('VL', l)
        
        d = {1: 'low_x', 2: 'high_x', 3: 'low_y', 4: 'high_y', 5: 'low_z', 6: 'high_z', 7: 'low_acc', 8: 'high_acc',
            9: 'limit_checking', 10: 'low_b', 11: 'high_b'}
        self.readToDict(spl, d)
        

    def readVO(self,l:str) -> None:
        '''read a VO command. l is the whole line. 
        {Activate Offset, Offset-X, Offset-Y, Offset-Z, Offset-A, Offset-B, Offset-C}'''
        spl, entries = self.checkSpl('VO', l)        
        self.readToDict(spl, {1:'activate_offset'})
        d = dict([[i+2,'offset_'+['x', 'y', 'z', 'a', 'b', 'c'][i]] for i in range(6)])
        self.readToDict(spl,  d)


    def readVR(self, l:str) -> None:
        '''read a VR command 
        {XY-Move Ramp Speed, Z-Move Ramp Speed, A-Move Ramp Speed, B-Move Ramp Speed,
    XY-Jog Ramp Speed, Z-Jog Ramp Speed, A-Jog Ramp Speed, B-Jog Ramp Speed, Move
    Ramp Rate, Jog Ramp Rate, 3D Ramp Threshold, Minimum distance, Slow Corner
    Speed, -obsolete-, -obsolete, KeyPad Ramp Rate}'''
        spl, entries = self.checkSpl('VR', l) 

        d = dict([[i+4*j+1,'ramp_speed_'+['move', 'jog'][j]+'_'+['xy', 'z', 'a', 'b'][i]] for j in range(2) for i in range(4)])
        self.readToDict(spl, d)
        d = {9:'move_ramp_rate', 10:'jog_ramp_rate', 11:'3D_ramp_thresh', 12:'min_distance', 13:'slow_corner_speed', 16:'keypad_ramp_rate'}     
        self.readToDict(spl, d)


    def readVS(self, l:str) -> None:
        '''read a VS command 
        {XY Move Speed, Z Move Speed, A Move Speed, B Move Speed, XY Jog Speed, Z Jog
    Speed, A Jog Speed, B Jog Speed}'''
        spl, entries = self.checkSpl('VS', l) 
        d = dict([[i+4*j+1,'speed_'+['move', 'jog'][j]+'_'+['xy', 'z', 'a', 'b'][i]] for j in range(2) for i in range(4)])
        self.readToDict(spl, d)

    def readVU(self, l:str) -> None:
        '''read a VU command 
        {x-axis Unit, y-axis Unit, z-axis Unit, a-axis Unit, circle segment
    resolution, (obs), (obs), (obs), b-axis Unit, resM-x, resM-y, resM-Z, resM-A,
    resM-B, StepInt divider, Disable Res shifting}'''
        spl, entries = self.checkSpl('VU', l) 
        d = dict([[i+1,['x', 'y', 'z', 'a'][i]+'_steps_per_unit'] for i in range(4)])
        self.readToDict(spl, d)
        d = {5:'circle_segment_resolution', 9:'b_steps_per_unit', 15:'step_interval_divider', 16:'disable_res_shifting'}
        self.readToDict(spl, d)
        d = dict([[i+10,'resM_'+['x', 'y', 'z', 'a', 'b'][i]] for i in range(5)])
        self.readToDict(spl, d)

    def readVarDef(self, l:str) -> dict:
        '''read a variable definition'''
        if not l[0]=='&':
            raise ValueError(f'{l} is not a variable definition')
        spl = splitStrip(l, delimiter='=')
        key = spl[0]
        va = spl[1]
        setattr(self, key, va)
        self.vardefs[key[1:]] = va   # remove & from key for vardefs dictionary


    def readLine(self, l:str) -> bool:
        '''read the line and add it to the dictionary. return True if the line is a header line'''
        if len(l)==0:
            return False

        if l.startswith('&'):
            self.readVarDef(l)
        elif l.startswith('MS'):
            self.readMS(l)
        elif l.startswith('JS'):
            self.readJS(l)
        elif l.startswith('VD'):
            self.readVD(l)
        elif l.startswith('VO'):
            self.readVO(l)
        elif l.startswith('VR'):
            self.readVR(l)
        elif l.startswith('VS'):
            self.readVS(l)
        elif l.startswith('VU'):
            self.readVU(l)
        elif l.startswith('VL'):
            self.readVL(l)
        elif l.startswith('SA') or l.startswith('MH'):
            return True
        elif l.startswith('\''):
            return True
        
        else:
            # line is not an expected header line
            if not hasattr(self, 'speed_move_xy'):
                # keep reading if we haven't defined a move speed
                return True
            else:
                # stop reading
                return False

        # keep reading
        return True
    
    #------
    
    def print(self) -> None:
        for key in self.__dict__:
            if not key in ['vardefs']:
                print(f'{key}: {getattr(self, key)}')


    def table(self) -> None:
        '''create a table of values with units'''
        tab = []
        units = {}
        
        for s in ['XYZ', 'A', 'B']:
            if hasattr(self, f'{s}_units'):
                units[s.lower()] = getattr(self, f'{s}_units')
            else:
                units[s.lower()] = ''

        for key in self.__dict__:
            if not key in ['vardefs', 'hrows']:
                u = ''
                if key.startswith('&') or key in ['circle']:
                    u = units['xyz']
                elif key.endswith('steps_per_unit'):
                    if key[0] in ['x', 'y', 'z']:
                        u = 'steps/'+units['xyz']
                    elif key[0]=='a':
                        u = 'steps/'+units['a']
                    elif key[0]=='b':
                        u = 'steps/'+units['b']
                elif key.startswith('speed_') or key.startswith('ramp'):
                    if key[-1]=='y' or key[-1]=='z':
                        u = units['xyz']+'/s'
                    elif key[-1]=='a':
                        u = units['a']+'/s'
                    elif key[-1]=='b':
                        u = units['b']+'/s'
                elif key.endswith('ramp_rate'):
                    uu =  units['xyz']
                    u = f'{uu}/(2{uu}/s)'
                elif key in ['3D_ramp_thresh', 'slow_corner_speed']:
                    u = '%'
                elif key=='min_distance':
                    u = units['xyz']
                tab.append([key, u, str(getattr(self, key))])
            
        return tab
    
    def floatSC(self, vi:str) -> float:
        '''Evaluate the expression vi with the values of all variables'''
        return floatSC(vi, self.vardefs)
    
    
    
class SBPPoints:
    '''this class holds methods and structures to track where the stage should be, and what state the pressure controller should be in'''
    
    def __init__(self, file:str):
        if not file.endswith('.sbp'):
            raise ValueError('Input to SBPPoints must be an SBP file')
        self.header = SBPHeader(file)  # scrape variables
        self.line = 0 
        if hasattr(self.header, 'speed_move_xy'):
            self.ms = self.header.speed_move_xy 
        else:
            raise ValueError(f'Missing move speed definition in {file}')
        if hasattr(self.header, 'speed_jog_xy'):
            self.js = self.header.speed_jog_xy
        else:
            self.js = np.nan
        self.file = file
        self.channels = channelsTriggered(file)
        self.cp = ['','','']
        self.points = [{'x':'', 'y':'', 'z':'', 'line':self.header.hrows}]   # list of dictionary points
        self.pressures = dict([[i,0] for i in self.channels])   
        for channel in self.channels:
            self.points[0][f'p{channel}_before'] = 0
            self.points[0][f'p{channel}_after'] = 0
        self.points[0]['speed'] = 0
        self.scrapeFile()
        
        
    def scrapeFile(self) -> None:
        '''scrape lines from the file into the list of points'''
        # read the header into the dictionary
        with open(self.file, mode='r') as f:
            for i in range(self.header.hrows):
                self.line+=1
                l = f.readline()
            while len(l)>0:
                self.readLine(l)    # interpret the line
                self.lastLine = l   # store the line
                self.line+=1
                l = f.readline()    # get a new line
                
                
                
    def floatSC(self, vi:Union[str, float]) -> float:
        '''evaluate the expression vi with the variable dictionary'''
        return floatSC(vi, self.header.vardefs)
    
    def addPoint(self, command:str) -> None:
        '''add the current point to the list'''
        p1 = {'line':self.line, 'x':self.cp[0], 'y':self.cp[1], 'z':self.cp[2]}
        # print(self.pressures)
        for c in self.channels:
            for s in ['before', 'after']:
                p1[f'p{c}_{s}'] = self.pressures[c]
        if command.startswith('M'):
            p1['speed'] = self.ms
        elif command.startswith('J'):
            p1['speed'] = self.js
        elif command.startswith('PAUSE'):
            p1['speed'] = 0
        else:
            p1['speed'] = 0
        # if p1['speed']==0 and len(self.points)>1:
        #     # only add this point if we're changing channels
        #     add = False
        #     for c in self.channels:
        #         if not p1[f'p{c}_before'] == p1[f'p{c}_after']:
        #             add = True
        #     if add:
        #         self.points.append(p1)
        #     else:
        #         print(self.points)
        # else:
        #     self.points.append(p1)
        self.points.append(p1)
        
    def changeInkSpeed(self, command:str) -> None:
        '''add a change of ink speed to the list'''
        spl = re.split('=', command)
        channel = spl[0][-1]
        val = float(spl[1])
        self.points.append({'line':self.line, f'p{channel}_before':-1000, f'p{channel}_after':val})  # -1000 is code for "change speed"    
        
    def readLineSO(self, spl:list) -> None:
        '''read an SO line'''
        if hasattr(self, 'lastLine'):
            if self.lastLine.startswith('SO'):
                # turned off/on
                self.addPoint('')
                
        # get the flag
        li = spl[1]
        if type(li) is str:
            if li[1:] in self.header.vardefs:
                channel = self.header.vardefs[li[1:]]-1
            else:
                print(self.header.vardefs)
                raise ValueError(f'Missing pressure channel in header: {li}')
        else:
            channel = int(spl[1])-1 # shopbot flags are 1-indexed, but we store 0-indexed
            
        # get the value we're setting the flag to
        self.pressures[channel] = spl[2]

        # note that the previous point ends in a flag change
        i = -1
        plast = self.points[i]
        while (not f'p{int(channel)}_after' in plast or plast[f'p{int(channel)}_before']<0) and i>-len(self.points):
            i = i-1
            plast = self.points[i]
        if f'p{int(channel)}_after' in plast and plast[f'p{int(channel)}_after'] in [0,1]:
            self.points[i][f'p{int(channel)}_after'] = self.pressures[channel]   # 0-indexed
            
    def readLineMove(self, spl:list) -> None:
        '''read a move'''
        if spl[0][1] in ['X', 'Y', 'Z']:
            # MX, MY, MZ, JX, JY, JZ
            self.cp[{'X':0, 'Y':1, 'Z':2}[spl[0][1]]]=self.floatSC(spl[1])
        elif spl[0][1] in ['2', '3']:
            # M2, M3, J2, J3
            for i in range(int(spl[0][1])):
                self.cp[i] = self.floatSC(spl[i+1])
        elif spl[0][1] =='S':
            # change translation speed
            if spl[0][0]=='M':
                self.ms = spl[1]
            elif spl[0][0]=='J':
                self.js = spl[1]
        self.addPoint(spl[0])
            
    def readLine(self, l:str) -> None:
        '''read a line into the list of points'''
        spl = splitStrip(l)
        if spl[0]=='SO':
            self.readLineSO(spl)
        elif spl[0][0] in ['M', 'J']:
            self.readLineMove(spl)
        elif spl[0].startswith('PAUSE'):
            self.addPoint('PAUSE')
        elif spl[0].startswith('\'ink_speed'):
            self.changeInkSpeed(spl[0])
            
            
    def export(self) -> None:
        '''export the points table to file'''
        df = pd.DataFrame(self.points)
        fn = self.file.replace('.sbp', '.csv')
        df.to_csv(fn)
        print(f'Exported points to {fn}')
            
      

    

