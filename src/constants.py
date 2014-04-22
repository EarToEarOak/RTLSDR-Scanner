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


class PlotFunc:
    NONE, MIN, MAX, AVG = range(4)


class Markers:
    MIN, MAX, AVG, GMEAN, \
    HP, HFS, HFE, \
    OP, OFS, OFE = range(10)


class File:
    class Exports:
        PLOT, IMAGE = range(2)

    class PlotType:
        CSV, GNUPLOT, FREEMAT = range(3)

    class ImageType:
        BMP, EPS, GIF, JPEG, PDF, PNG, PPM, TIFF = range(8)

    PLOT = [""] * 3
    PLOT[PlotType.CSV] = "CSV table (*.csv)|*.csv"
    PLOT[PlotType.GNUPLOT] = "gnuplot script (*.plt)|*.plt"
    PLOT[PlotType.FREEMAT] = "FreeMat script (*.m)|*.m"

    IMAGE = [""] * 8
    IMAGE[ImageType.BMP] = 'Bitmap image (*.bmp)|*.bmp'
    IMAGE[ImageType.EPS] = 'Encapsulated PostScript (*.eps)|*.eps'
    IMAGE[ImageType.GIF] = 'GIF image (*.gif)|*.gif'
    IMAGE[ImageType.JPEG] = 'JPEG image (*.jpeg)|*.jpeg'
    IMAGE[ImageType.PDF] = 'Portable Document (*.pdf)|*.pdf'
    IMAGE[ImageType.PNG] = 'Portable Network Graphics Image (*.png)|*.png'
    IMAGE[ImageType.PPM] = 'Portable Pixmap image (*.ppm)|*.ppm'
    IMAGE[ImageType.TIFF] = 'Tagged Image File (*.tiff)|*.tiff'

    HEADER = "RTLSDR Scanner"
    VERSION = 8
    RFS = "RTLSDR frequency scan (*.rfs)|*.rfs"

    @staticmethod
    def get_exports(export):
        if export == File.Exports.PLOT:
            exports = File.PLOT
        else:
            exports = File.IMAGE

        return exports

    @staticmethod
    def get_export_ext(index, export=Exports.PLOT):
        exports = File.get_exports(export)
        filter = exports[index]
        delim = filter.index('|*')
        return filter[delim + 2:]

    @staticmethod
    def get_export_filters(export=Exports.PLOT):
        exports = File.get_exports(export)

        filters = ''
        length = len(exports)
        for i in xrange(length):
            filters += exports[i]
            if i < length - 1:
                filters += '|'

        return filters

    @staticmethod
    def get_export_pretty(export=Exports.PLOT):
        exports = File.get_exports(export)

        pretty = ''
        length = len(exports)
        for i in xrange(length):
            pretty += File.get_export_ext(i, export)
            if i < length - 2:
                pretty += ', '
            elif i < length - 1:
                pretty += ' or '

        return pretty

    @staticmethod
    def get_export_type(extension, export=Exports.PLOT):
        exports = File.get_exports(export)
        for i in xrange(len(exports)):
            if extension == File.get_export_ext(i, export):
                return i

        return -1


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
