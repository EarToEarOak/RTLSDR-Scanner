# RTLSDR Scanner #

Copyright 2012 - 2015 Al Brown

al [at] eartoearoak.com


A cross platform Python frequency scanning GUI for the OsmoSDR rtl-sdr [library](http://sdr.osmocom.org/trac/wiki/rtl-sdr).

More details can be found [here](http://eartoearoak.com/software/rtlsdr-scanner).

A basic [user manual](https://github.com/EarToEarOak/RTLSDR-Scanner/blob/master/doc/Manual.pdf?raw=true) is also available.

Tested on:

- Windows 7 (x86 and x64)
- Windows 8.1 (x64)
- Ubuntu 12.04 (x86)
- Ubuntu 12.10 (x64)
- Ubuntu 13.04 (x64)
- Ubuntu 14.04 (x64)
- OS X Snow Leopard
- OS X Mountain Lion

## Installation ##
Installation instructions are found [here](http://eartoearoak.com/software/rtlsdr-scanner/rtlsdr-scanner-installation).

Windows executables for x86 and amd64 platforms are available on [GitHub](https://github.com/EarToEarOak/RTLSDR-Scanner/releases).

## Requirements ##

- [Python 2.7.x](http://www.python.org)
- [wxPython](http://www.wxpython.org/)
- [matplotlib](http://matplotlib.org/)
- [numpy](http://www.numpy.org/)
- [Pillow](https://pypi.python.org/pypi/Pillow)
- [rtlsdr](http://sdr.osmocom.org/trac/wiki/rtl-sdr)
- [pyrtlsdr](https://github.com/roger-/pyrtlsdr)
- [pyserial](https://pypi.python.org/pypi/pyserial)

To test for missing libraries run `rtlsdr_scan_diag.py`

Windows 64 bit modules can be found [here](http://www.lfd.uci.edu/~gohlke/pythonlibs/)

## Usage ##

`python -m rtlsdr_scanner [file]`

    file - optional saved scan file to load

**Main Window**

- **Start** - Scan start frequency
- **Stop** - Scan stop frequency
- **Mode** - Single or continuous scanning
- **Dwell** - Sampling time spent on each step
- **FFT Size** - FFT size, greater values result in higher analysis precision (with higher sizes dwell should be increased)
- **Live update** - Update the display on each step (caution only use with small scans and low dwell times)
- **Grid** - Show a grid on the scan

**File Menu**

- **Open...** - Open a saved scan
- **Save As...** - Save a scan
- **Export...** - Export a scan to a CSV file
- **Properties..** - Scan information

**Edit Menu**

- **Preferences** - Set dongle gain, calibration, Local Oscillator and the sample bands to use

**Scan Menu**

- **Start** - Start a scan
- **Stop** - Stop a scan

**Tools Menu**

- **Compare** - Compare two previously saved scans
- **Auto Calibration** - Perform a crude calibration of the dongle to a known signal (this should be a continuous, steady signal)

## License ##

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 3.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
