# ShopbotGUI

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
