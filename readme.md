# RTLSDR Scanner #

Copyright 2012, 2013 Al Brown

al [at] eartoearoak.com


A cross platform Python frequency scanning GUI for the OsmoSDR rtl-sdr [library](http://sdr.osmocom.org/trac/wiki/rtl-sdr).

Full details can be found [here](http://eartoearoak.com/software/rtlsdr-scanner)

Tested on:

- Windows 7 (x86 and x64)
- Windows XP (x86)
- Ubuntu 12.04 (x86)
- Ubuntu 12.10 (x64)
- Ubuntu 13.04 (x64)
- OS X Snow Leopard

## Binaries ##
Test binaries can be found on [SourceForge](http://sourceforge.net/projects/rtlsdrscanner/files/)

## Requirements ##

- [Python 2.6](http://www.python.org) or greater
- [wxPython](http://www.wxpython.org/)
- [matplotlib](http://matplotlib.org/)
- [numpy](http://www.numpy.org/)
- [rtlsdr](http://sdr.osmocom.org/trac/wiki/rtl-sdr)
- [pyrtlsdr](https://github.com/roger-/pyrtlsdr)

To test for missing libraries run `rtlsdr_scan_diag.py`

Windows 64 bit modules can be found [here](http://www.lfd.uci.edu/~gohlke/pythonlibs/)

OS X users report success using [Homebrew](http://mxcl.github.com/homebrew/), if you have problems with imports [this page](http://stackoverflow.com/questions/5121574/wxpython-import-error) may help (thanks @edy555).

## Usage ##

`rtlsdr_scan [file]`

    file - optional saved scan file to load

**Main Window**

- **Start** - Scan start frequency
- **Stop** - Scan stop frequency
- **Dwell** - Sampling time spent on each step
- **FFT Size** - FFT size, greater values result in higher analysis precision (with higher sizes dwell should be increased)
- **Continuous update** - Update the display on each step (caution only use with small scans and low dwell times)
- **Grid** - Show a grid on the scan

**File Menu**

- **Open...** - Open a saved scan
- **Save As...** - Save a scan
- **Export...** - Export a scan to a CSV file

**Scan Menu**

- **Start** - Start a scan
- **Stop** - Stop a scan

**View Menu**

- **Preferences** - Set dongle gain, calibration, Local Oscillator and the sample bands to use

**Tools Menu**

- **Compare** - Compare two previously saved scans
- **Auto Calibration** - Perform a crude calibration of the dongle to a known signal (this should be a continuous, unwavering signal)

## License ##

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
