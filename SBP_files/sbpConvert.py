#!/usr/bin/env python
'''Functions for creating shopbot files'''

# external packages
import os
import sys
import re
from typing import List, Dict, Tuple, Union, Any, TextIO
import sympy as sy



#------------------------------------------

def oddNeg(n:int)->int:
    '''Returns negative 1 if the input is odd'''
    return 2*((n%2)-1/2)

def fs(i) -> str:
    '''Converts a float into a string w/ 3 decimal places'''
    if type(i) is str:
        return i
    else:
        return '%3.3f'%i
    
def pf(a:float, b:float)->float:
    '''literally just adds two numbers'''
    return a+b


def mf(a:float, b:float)->float:
    '''literally just multiplies two numbers'''
    return a*b 
    
# plus or times for combos of strings and floats
def pt(*dims, **kwargs) -> Union[str, float]:
    '''Takes in a list of strings and floats and adds or multiplies them. dims is a list of elements to operate on, and mode should be defined as a keyword, e.g. mode='add' or mode='mult' '''
    
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
                dparen = f'({d})'
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


def p(*dims) -> Union[str, float]:
    '''add combos of strings and floats'''
    return pt(*dims, mode='add')


def t(*dims) -> Union[str, float]:
    '''(times) multiply combos of strings and floats'''
    return pt(*dims, mode='mult')

def mean(*dims) -> Union[str, float]:
    return t(fs(1/len(dims)), f'({p(*dims)})')


#--------------------------


def floatSC(vi:Union[str, float], vardefs:dict) -> float:
    '''Evaluate the expression vi with the values of any variables'''
    try:
        vout = float(vi)
    except:
        if type(vi) is str:
            for key, val in vardefs.items():
                vi = vi.replace(f'&{key}', str(val))
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
        

        
def strSimplify(vi:Union[str, float], defdict:dict) -> str:
    '''Simplify the expression, and evaluate it with any variables requested in the def dict. If you don't want to evaluate any variables, defdict = {}'''
    if not type(vi) is str:
        return vi
    
    for key, val in defdict.items():
        vi = vi.replace(f'&{key}', fs(val))

    vin = vi.replace('&', 'UND')   # replace & character because sy.simplify will try to translate it if you left any variable names in there

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
    
    
def fsss(vi:Union[str, float]) -> str:
    '''this is for simplifying and formatting as string without any variable replacements'''
    if type(vi) is str:
        return strSimplify(vi, {})
    else:
        return fs(vi)



def splitStrip(l:str, delimiter:str=',') -> list:
    '''get a list of values'''
    spl = re.split(delimiter, l)
    out = []
    for s in spl:
        s1 = s.strip()
        try:
            s2 = float(s1)
        except:
            s2 = s1
        out.append(s2)
    return out
    
def channelsTriggered(sbpName:str) -> int:
    '''Identify which channels are triggered during the run. critFlag is a shopbot flag value that indicates that the run is done. We always set this to 0. If you want the video to shut off after the first flow is done, set this to 8. We run this function at the beginning of the run to determine what flag will trigger the start of videos, etc. Results are 0-indexed'''
    channelsTriggered = []
    defs = {}
    with open(sbpName, 'r') as f:
        for line in f:
            if line.startswith('&'):
                spl = splitStrip(line, delimiter='=')
                key = spl[0]
                va = spl[1]
                defs[key[1:]] = int(va)
            if line.startswith('SO') and (line.endswith('1') or line.endswith('1\n')):
                '''the shopbot flags are 1-indexed, while our channels list is 0-indexed, 
                so when it says to change flag 1, we want to change channels[0]'''
                lii = line.split(',')[1]
                try:
                    li = int(lii)-1
                except:
                    li = lii.strip()[1:]
                    if li in defs:
                        li = defs[li]-1
                    else:
                        print(f'{li} not found in defs')
                if li not in channelsTriggered:
                    channelsTriggered.append(li) 
    return channelsTriggered