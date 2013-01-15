# RTLSDR Scanner #

Copyright 2012, 2013 Al Brown


A cross platform Python frequency scanning GUI for the OsmoSDR rtl-sdr [library](http://sdr.osmocom.org/trac/wiki/rtl-sdr).

Full details can be found [here](http://eartoearoak.com/software/rtlsdr-scanner)

Tested on:

- Windows 7 (x86 and x64)
- Ubuntu 12.04 (x86)
- Ubuntu 12.10 (x64)

## Requirements ##

- [Python 2.6](http://www.python.org) or greater
- [wxPython](http://www.wxpython.org/)
- [matplotlib](http://matplotlib.org/)
- [numpy](http://www.numpy.org/)
- [rtlsdr](http://sdr.osmocom.org/trac/wiki/rtl-sdr)
- [pyrtlsdr](https://github.com/roger-/pyrtlsdr)

Windows 64 bit modules can be found [here](http://www.lfd.uci.edu/~gohlke/pythonlibs/)

## Usage ##

`rtlsdr_scan [file]`

    file - optional saved scan file to load

**Main Window**

- **Start** - Scan start frequency
- **Stop** - Scan stop frequency
- **Dwell** - Sampling time spent on each step
- **Continous update** - Update the display on each step (caution only use with small scans and low dwell times)
- **Grid** - Show a grid on the scan

**File Menu**

- **Open...** - Open a saved scan
- **Save As...** - Save a scan
- **Export...** - Export a scan to a CSV file

**Scan Menu**

- **Start** - Start a scan
- **Stop** - Stop a scan

**View Menu**

- **Preferences** - Set dongle calibration and Local Oscillator offset

**Tools Menu**

- **Auto Calibration** - Perform a crude calibration of the dongle to a known signal (this should be a continous, unwavering signal)

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