# ShopbotPyQt
## A GUI for controlling a Shopbot, Basler camera, webcam, and Fluigent mass flow controller.

To view the user guide in browser, visit https://htmlpreview.github.io/?https://github.com/usnistgov/ShopbotPyQt/blob/main/user_guide/index.html


## Authors
- Leanne M. Friedrich
    - National Institute of Standards and Technology, MML
    - Leanne.Friedrich@nist.gov
    - https://github.com/leanfried
    - ORCID: 0000-0002-0382-3980
- B. Leigh Vining
    - Montgomery College
    - National Institute of Standards and Technology, MML
    - /https://github.com/bilevi

## Contact
- Leanne Friedrich
    - Leanne.Friedrich@nist.gov

## Description

Files for controlling custom Shopbot/Fluigent 3D printer. GUI is built using PyQt.

Run this using 
    ` run sbgui.py `
    in the Jupyter command line 
or 
    ` python3 sbgui.py `
    in the anaconda command line

The GUI contains boxes for the following functions: 

1. Select folders and establish a naming convention for files generated during a print.
2. Send a .sbp or .gcode file to SB3 software, which controls a Shopbot (https://www.shopbottools.com/support/control-software)
3. Preview, record, and snap frames from a Basler camera. This build requires pypylon (https://github.com/basler/pypylon)
4. Preview, record, and snap frames for two webcams using OpenCV (https://pypi.org/project/opencv-python/)
5. Control Fluigent pressure controller with a variable number of channels. Includes a running display of the pressures coming out of each channel. Repo includes files for Fluigent SDK (https://github.com/Fluigent/fgt-SDK)

This GUI enables the user to coordinate Fluigent, Shopbot, and camera functions. This build is written specifically for Windows. To run this code on another OS, you will need to make changes to flags.py and general.py, at the very least. Coordinating the Shopbot with the cameras and Fluigent relies on the output flags that you can see in the Sb3 software. These flags are stored as windows registry keys, usually held in 'Software\\VB and VBA Program Settings\\Shopbot\\UserData'. This is designed for a Shopbot with 12 output flags, a Fluigent with two channels, and three cameras. 

For instructions on interacting with the GUI, see the user_guide folder in this repo, or https://htmlpreview.github.io/?https://github.com/usnistgov/ShopbotPyQt/blob/main/user_guide/index.html.


## Data Use Notes

This code is publicly available according to the NIST statements of copyright,
fair use and licensing; see 
https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software

You may cite the use of this code as follows:
> Friedrich, L., & Vining, B.L. (2022), ShopbotPyQt, Version XXX, National Institute of Standards and Technology (Accessed XXXX-XX-XX)


## File Overview


- `README.md`

- `LICENSE`

- `requirements.txt`

- **pythonGUI**
    Python files for the GUI
    
    - **configs**
        - `config.yml`
            Define settings that are saved from session to session, like file locations, camera frame rate, etc. This should be unique to your computer, not updated from the main Github repo. To save time, you may want to copy config_default.yml to config.yml on the first run and update file paths and variables as needed.
            
        - `config_default.yml`
            Default settings. This file is copied to `config.yml` if there is no `config.yml` file.
            
        - `densities.yml`
            List of saved densities for saved fluids. 

    - **Fluigent**
        This is the Fluigent SDK for Python, available at https://github.com/Fluigent/fgt-SDK

    - **icons**
        Images used in the GUI
        
    - **pypylon**
        This is the Pylon SDK for Python, which allows the GUI to talk to Basler cameras.
        
    - **testResults**
        This holds results from performance tests.
        
    - **tests**
        This holds stripped-down versions of the GUI for testing the GUI one piece at a time.
        
    - `\__init\__.py`
        Metadata about this repo
        
    - `calibration.py`
        Window for calibrating ink speeds against ink pressures.
        
    - `cam_bascam.py`
        Communicate with Basler cameras.
        
    - `cam_webcam.py`
        Communicate with webcams.
        
    - `cameras.py`
        Set up GUI elements for cameras.
        
    - `camObj.py`
        Set up general functions for cameras.
        
    - `camThreads.py`
        Set up external threading for camera recording and previewing
        
    - `channelWatch.py`
        Set up external threading for watching changes to pressures during printing.

    - `config.py`
        Import saved settings
        
    -  `convert.py`
        Functions for converting a .gcode file to .sbp format.
        
    - `files.py`
        File handling
        
    - `flags.py`
        Interacting with Shopbot flags and windows registry keys
        
    - `fluigent.py`
        Interacting with the Fluigent pressure controller
        
    - `fluThreads.py`
        Set up external threading for the live pressure graph in the GUI
        
    - `general.py`
        Tools used across the GUI. Shortcuts for creating GUI elements.
        
    - `layout.py`
        Set up the overall layout of the GUI
        
    - `log.py`
        Log messages created by the GUI

    - `sbgui.py`
        The main module for the GUI. Run this to launch the GUI.
        
    - `sbList.py`
        Tools for the .sbp file queue and run buttons
        
    - `sbpConvert.py`
        Tools for converting text values to numerical values in .sbp files
        
    - `sbpRead.py`
        Tools for converting .sbp files to .csv lists of points
        
    - `sbprint.py`
        Loop that runs during a print
        
    - `settings.py`
        Sets up the settings window
        
    - `shopbot.py`
        Sets up the shopbot portion of the GUI.


- **SBP files**
    The Shopbot control software is Sb3, which can take .gcode or .sbp files as inputs. We have chosen to use a custom format for .sbp files for their ease of use and compatibility with Shopbot accessories. More info about .sbp files can be found here: https://www.shopbottools.com/ShopBotDocs/files/ComRef.pdf and here: https://www.shopbottools.com/ShopBotDocs/files/SBG00314150707ProgHandWin.pdf
        
    - *sbpcreator_programmatic.ipynb*
        (Under development) Jupyter notebook for generating sbp files composed of loops
        
    - *sbpcreator_programmatic.py*
        (Under development) Functions for generating sbp files composed of loops

    - *sbpcreator.ipynb*
        Jupyter notebook for generating sbp files

    - *sbpcreator.py*
        Functions for generating sbp files containing simple shapes: zigzags, vertical lines, etc. It also programs in output flag handling, which lets the Shopbot tell the GUI when to change the Fluigent pressure, start/stop videos, and capture images. 
        
    - **Folders**
    
        - *XXXX.LOG*
            A log file that describes what happened the last time you ran XXXX.sbp

        - *XXXX.sbp* 
            A Shopbot input file.

        - *XXXX.csv* 
            A table of points and pressure indicators that ShopbotPyQt uses to time changes in state.
            
        - *XXXXList.txt*
            A list of files in this folder and breakpoints that lets us load many files into the GUI all at once.
            
            
            
- **user_guide**
    Guide to use and assembly of the NIST Shopbot hardware and this software. Open `index.html` in browser to go to the homepage, or visit https://htmlpreview.github.io/?https://github.com/usnistgov/ShopbotPyQt/blob/main/user_guide/index.html to see the current version on GitHub.
    




