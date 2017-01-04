#
# rtlsdr_scan
#
# http://eartoearoak.com/software/rtlsdr-scanner
#
# Copyright 2012 - 2015 Al Brown
#
# A frequency scanning GUI for the OsmoSDR rtl-sdr library at
# http://sdr.osmocom.org/trac/wiki/rtl-sdr
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import numpy


APP_NAME = 'RTLSDR Scanner'

F_MIN = 0
F_MAX = 9999
GAIN = 0
SAMPLE_RATE = 2e6
BANDWIDTH = 500e3

LOCATION_PORT = 7786

MODE = ["Single", 0,
        "Continuous", 1,
        "Maximum", 2]

NFFT = [16,
        32,
        64,
        128,
        256,
        512,
        1024,
        2048,
        4096,
        8192,
        16384,
        32768]

DISPLAY = ["Plot", 0,
           "Spectrogram", 1,
           "3D Spectrogram", 2,
           "Status", 3,
           "Time Line", 4,
           "Preview", 5]

TUNER = ["Unknown",
         "Elonics E4000",
         "Fitipower FC0012",
         "Fitipower FC0013",
         "FCI FC2580",
         "Rafael Micro R820T",
         "Rafael Micro R828D"]

WINFUNC = ["Bartlett", numpy.bartlett,
           "Blackman", numpy.blackman,
           "Hamming", numpy.hamming,
           "Hanning", numpy.hanning]


class Warn(object):
    SCAN, OPEN, EXIT, NEW, MERGE = range(5)


class Cal(object):
    START, DONE, OK, CANCEL = range(4)


class Display(object):
    PLOT, SPECT, SURFACE, STATUS, TIMELINE, PREVIEW = range(6)


class Mode(object):
    SINGLE, CONTIN, MAX = range(3)


class Plot(object):
    STR_FULL = 'Full'
    STR_PARTIAL = 'Partial'


class PlotFunc(object):
    NONE, AVG, MIN, MAX, VAR, SMOOTH, DIFF, DELTA = range(8)


class Markers(object):
    MIN, MAX, AVG, GMEAN, \
        HP, HFS, HFE, \
        OP, OFS, OFE = range(10)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
