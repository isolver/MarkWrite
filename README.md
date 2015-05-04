# MarkWrite
A tool for the inspection and segmentation of digitized writing data 
from pen tablet type devices.

![MarkWrite screenshot](https://github.com/isolver/MarkWrite/blob/master/MarkWriteApp_sm.png)

# Status
MarkWrite 0.1 was released on May 2nd, 2015. Although there is a large 
'wish list' of unimplemented functionality, the application should be of use
to people wanting to segment digitized pen data into sentences, words, letters,
... 

[Documentation](https://github.com/isolver/MarkWrite/blob/master/docs/MarkWrite 0.1 User Guide.pdf) is currently available in PDF format.

# Installation / Running
Currently only Windows 7 / 8 have been tested with the app; 
other environments may work but who knows.

## Windows 7 / 8 Executable

Standalone versions of MarkWrite for Windows 7/8 32bit and [64bit](https://github.com/isolver/MarkWrite/releases/download/v0.1.0/MarkWrite.0.1.64bit.zip)
are available. In this case Python does not need to be installed
on the computer being used; it is included in the MarkWrite program folder. 
To use the exe, download one of the .zip archived MarkWrite program folders, 
uncompress it, and then launch MarkWrite.exe in the folder.

## Running from Source
The source code can be downloaded and MarkWrite can be run from a 
Python 2.7 32 or 64 bit environment. 

The following Python packages must be installed for MarkWrite to run:

1. numpy 1.9
2. pyqtgraph 0.9.10
3. PyQt 4.9

There is no need to install a 'markwrite' package, simply start the runapp.py 
script.

Note: Ensure the directory runapp.py is in is included in your 
python path. If the runapp.py script is run from it's folder, then most python 
env's will include the './' folder in the path by default.

# Credits

Initial development was funded by School of Social Sciences, Nottingham Trent University, UK.

# License

GNU General Public License (GPL) Version 3

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
