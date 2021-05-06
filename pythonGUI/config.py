#!/usr/bin/env python
'''Tools for loading settings'''

# external packages
import yaml
from box import Box
import sys
import os

# info
__author__ = "Leanne Friedrich"
__copyright__ = "This data is publicly available according to the NIST statements of copyright, fair use and licensing; see https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software"
__credits__ = ["Leanne Friedrich"]
__license__ = "MIT"
__version__ = "1.0.4"
__maintainer__ = "Leanne Friedrich"
__email__ = "Leanne.Friedrich@nist.gov"
__status__ = "Development"

#----------------------------------------------------

def getConfigDir() -> str:
    currentdir = os.path.dirname(os.path.realpath(__file__))
    parentdir = os.path.dirname(currentdir)
    configdir = os.path.join(currentdir, 'configs')
    if not os.path.exists(configdir):
        configdir = os.path.join(parentdir, 'configs')
        if not os.path.exists(configdir):
            raise FileNotFoundError(f"No configs directory found")
    return configdir

def dumpConfigs(cfg:Box, path:str) -> None:
    '''Saves config file'''
    with open(path, "w") as ymlout:
        yaml.dump(cfg.to_dict(), ymlout)
        
def loadConfigFile(path:str) -> Box:
    with open(path, "r") as ymlfile:
        cfg = Box(yaml.safe_load(ymlfile))
        return cfg
        
        
#----------------------------------------------------
configdir = getConfigDir()
path = os.path.join(configdir,"config.yml")
if not os.path.exists(path):
    path = os.path.join(configdir, 'config_default.yml')
llist = os.listdir(configdir)
while not os.path.exists(path):
    l = llist.pop(0)
    if l.endswith('yml') or l.endswidth('yaml'):
        path = os.path.join(configdir, l)
            
cfg = loadConfigFile(path)
    
    
