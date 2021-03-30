#!/usr/bin/env python
'''Shopbot GUI Shopbot functions'''


from PyQt5 import QtCore, QtWidgets, QtGui, QtMultimedia, QtMultimediaWidgets
import PyQt5.QtWidgets as qtw
import pyqtgraph as pg
import cv2
import sys
import time
import datetime
import numpy as np
from random import randint
import sip
import ctypes
import os
import winreg
import subprocess
from typing import List, Dict, Tuple, Union, Any, TextIO
import logging
from config import cfg

from sbgui_general import *

__author__ = "Leanne Friedrich"
__copyright__ = "This data is publicly available according to the NIST statements of copyright, fair use and licensing; see https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software"
__credits__ = ["Leanne Friedrich"]
__license__ = "MIT"
__version__ = "1.0.4"
__maintainer__ = "Leanne Friedrich"
__email__ = "Leanne.Friedrich@nist.gov"
__status__ = "Development"