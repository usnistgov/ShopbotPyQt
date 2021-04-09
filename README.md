### NIST Repository:
ShopbotPyQt: A GUI for controlling a Shopbot, Basler camera, webcam, and Fluigent mass flow controller

Version 1.0.4

### Authors:
- Leanne Friedrich
    - National Institute of Standards and Technology, MML
    - Leanne.Friedrich@nist.gov
- Jonathan E. Seppala
    - National Institute of Standards and Technology, MML
    - Jonathan.Seppala@nist.gov

### Contact:
- Leanne Friedrich
    - Leanne.Friedrich@nist.gov

### Description:

Files for controlling custom Shopbot/Fluigent 3D printer. GUI is built using PyQt.

The GUI contains boxes for the following functions: 

1. Select folders and establish a naming convention for files generated during a print.
2. Send a .sbp or .gcode file to SB3 software, which controls a Shopbot (https://www.shopbottools.com/support/control-software)
3. Preview, record, and snap frames from a Basler camera. This build requires pypylon (https://github.com/basler/pypylon)
4. Preview, record, and snap frames for two webcams using OpenCV (https://pypi.org/project/opencv-python/)
5. Control Fluigent pressure controller with a variable number of channels. Includes a running display of the pressures coming out of each channel. Repo includes files for Fluigent SDK (https://github.com/Fluigent/fgt-SDK)

This GUI enables the user to coordinate Fluigent, Shopbot, and camera functions. For example, if you want to turn on the first Fluigent channel at some point in the print, insert a line into the .sbp file: 'SO, 1, 1'. To turn off the channel, insert 'SO, 1, 0'. To turn on channel 2, insert 'SO, 2, 1'. The GUI will watch for those signals and automatically turn the pressure on and off during printing. 

If you want to record videos during a print, use the appropriate checkboxes in the camera sections. Cameras will automatically start recording when the first pressure channel is turned on and stop recording when the last pressure channel is turned off. Alternatively, if you don't use the pressure channels at all, the cameras will start and end when the Shopbot starts and stops running the file. 

This build is written specifically for Windows. To switch to a different OS, you will at the very least need to modify the functions sbBox.connectKeys() and sbBox.getSBFlag(), where python querying a specific windows registry key that allows the GUI to talk to the Shopbot software.


--- 

# General Information

Version 1.0.4 was generated: August 2020 - April 2021.

---

# Data Use Notes


This code is publicly available according to the NIST statements of copyright,
fair use and licensing; see 
https://www.nist.gov/director/copyright-fair-use-and-licensing-statements-srd-data-and-software

You may cite the use of this code as follows:
Friedrich, L., & Seppala, J.E. (2021), ShopbotPyQt, Version 1.0.4, National Institute of Standards and Technology (Accessed XXXX-XX-XX)


---

# References


---

# Data Overview


This data follows the basic storage structure established by OpenFOAM.

The files included in this publication use the following hierarchy:

- *README.md*

- *LICENSE*

- **pythonGUI**
	- Python files for the GUI

	- **Fluigent**
		- This is the Fluigent SDK for Python, available at https://github.com/Fluigent/fgt-SDK

	- **icons**
		- Images used in the GUI

	- *config.py*
		- Import environmental variables

	- *config.yaml*
		- Define environmental variables including sbp (path to sbp files) and vid (path to video folder)

	- *sbgui.py*
		- The main module for the GUI. Run this to launch the GUI.

	- *sbgui_cameras.py*
		- Functions for controlling the cameras

	- *sbgui_files.py*
		- Functions for file handling

	- *sbgui_fluigent.py*
		- Functions for controlling the Fluigent

	- *sbgui_general.py*
		- Functions for setting up common layout elements

	- *sbgui_layout.py*
		- Functions for establishing the overall layout of the GUI

	- *sbgui_shopbot.py*
		- Functions for controlling the shopbot.


- **SBP files**
	- The Shopbot control software is Sb3, which can take .gcode or .sbp files as inputs. We have chosen to use .sbp files for their ease of use and compatibility with Shopbot accessories. More info about .sbp files can be found here: https://www.shopbottools.com/ShopBotDocs/files/ComRef.pdf and here: https://www.shopbottools.com/ShopBotDocs/files/SBG00314150707ProgHandWin.pdf

	- *XXXX.LOG*
		- A log file that describes what happened the last time you ran XXXX.sbp

	- *XXXX.sbp* 
		- A shopbot input file.

	- *sbpcreator.ipynb*
		- Jupyter notebook for generating sbp files

	- *sbpcreator.py*
		- Functions for generating sbp files containing simple shapes: zigzags, vertical lines, etc. It also programs in output flag handling, which lets the Shopbot tell the GUI when to change the Fluigent pressure, start/stop videos, and capture images. 

--- 

# Version History


4/09/2021: v1.0.4

---

# METHODOLOGICAL INFORMATION


Run this using 
	` run sbgui.py `
	in the Jupyter command line 
or 
	` python3 sbgui.py `
	in the anaconda command line




Coordinating the shopbot with the cameras and Fluigent relies on the output flags that you can see in the Sb3 software. These flags are stored as windows registry keys, usually held in 'Software\\VB and VBA Program Settings\\Shopbot\\UserData'. This is designed for a shopbot with four output flags, a Fluigent with two channels, and three cameras. 

When the shopbot runs a program that sets the output flags, it first turns on output flag 4 (1-indexed). Then, it asks the user to let it turn on the spindle. (You should say yes.) This python GUI will watch those output flags for commands. If flag 3 (1-indexed) is turned on, the checked cameras will take a picture. If flag 1 is turned on, Fluigent channel 1 (1-indexed) will turn on to whatever is inserted into "Run Pressure". If there is a second channel, flag 2 will turn on Fluigent channel 2. When the shopbot is done with the whole file, it will turn off all output flags, and the python GUI will take that as a sign that it is time to stop recording.

