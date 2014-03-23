#
# rtlsdr_scan
#
# http://eartoearoak.com/software/rtlsdr-scanner
#
# Copyright 2012 - 2014 Al Brown
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


F_MIN = 0
F_MAX = 9999
GAIN = 0
SAMPLE_RATE = 2e6
BANDWIDTH = 500e3
TIMESTAMP_FILE = 'version-timestamp'

MODE = ["Single", 0,
        "Continuous", 1]

NFFT = [16,
        32,
        64,
        128,
        512,
        1024,
        2048,
        4096,
        8192,
        16384,
        32768]

DWELL = ["16 ms", 0.016,
         "32 ms", 0.032,
         "65 ms", 0.065,
         "131 ms", 0.131,
         "262 ms", 0.262,
         "524 ms", 0.524,
         "1 s", 1.048,
         "2 s", 2.097,
         "8 s", 8.388]

DISPLAY = ["Plot", 0,
           "Spectrogram", 1,
           "3D Spectrogram", 2]

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


class Warn:
    SCAN, OPEN, EXIT = range(3)


class Cal:
    START, DONE, OK, CANCEL = range(4)


class Display:
    PLOT, SPECT, SURFACE = range(3)


class Mode:
    SINGLE, CONTIN = range(2)


class Plot:
    STR_FULL = 'Full'
    STR_PARTIAL = 'Partial'


class File:
    class ExportType:
        CSV, GNUPLOT, FREEMAT = range(3)

    FILTERS = [""] * 3
    FILTERS[ExportType.CSV] = "CSV table (*.csv)|*.csv"
    FILTERS[ExportType.GNUPLOT] = "gnuplot script (*.plt)|*.plt"
    FILTERS[ExportType.FREEMAT] = "FreeMat script (*.m)|*.m"

    HEADER = "RTLSDR Scanner"
    VERSION = 8
    RFS = "RTLSDR frequency scan (*.rfs)|*.rfs"

    @staticmethod
    def get_export_filters():
        filters = ""
        length = len(File.FILTERS)
        for i in xrange(length):
            filters += File.FILTERS[i]
            if i < length - 1:
                filters += '|'

        return filters

    @staticmethod
    def get_export_type(ext):
        try:
            return next(x for x, i in enumerate(File.FILTERS) if i[-4:] == ext)
        except StopIteration:
            return -1


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
