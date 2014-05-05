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
    NONE, AVG, MIN, MAX, VAR = range(5)


class Markers:
    MIN, MAX, AVG, GMEAN, \
    HP, HFS, HFE, \
    OP, OFS, OFE = range(10)


class File:
    class Types:
        SAVE, PLOT, IMAGE, GEO = range(4)

    class SaveType:
        RFS = 0

    class PlotType:
        CSV, GNUPLOT, FREEMAT = range(3)

    class ImageType:
        BMP, EPS, GIF, JPEG, PDF, PNG, PPM, TIFF = range(8)

    class GeoType:
        KMZ, CSV = range(2)

    SAVE = [''] * 1
    SAVE[SaveType.RFS] = 'RTLSDR frequency scan (*.rfs)|*.rfs'

    PLOT = [''] * 3
    PLOT[PlotType.CSV] = "CSV table (*.csv)|*.csv"
    PLOT[PlotType.GNUPLOT] = "gnuplot script (*.plt)|*.plt"
    PLOT[PlotType.FREEMAT] = "FreeMat script (*.m)|*.m"

    IMAGE = [''] * 8
    IMAGE[ImageType.BMP] = 'Bitmap image (*.bmp)|*.bmp'
    IMAGE[ImageType.EPS] = 'Encapsulated PostScript (*.eps)|*.eps'
    IMAGE[ImageType.GIF] = 'GIF image (*.gif)|*.gif'
    IMAGE[ImageType.JPEG] = 'JPEG image (*.jpeg)|*.jpeg'
    IMAGE[ImageType.PDF] = 'Portable Document (*.pdf)|*.pdf'
    IMAGE[ImageType.PNG] = 'Portable Network Graphics Image (*.png)|*.png'
    IMAGE[ImageType.PPM] = 'Portable Pixmap image (*.ppm)|*.ppm'
    IMAGE[ImageType.TIFF] = 'Tagged Image File (*.tiff)|*.tiff'

    GEO = [''] * 2
    GEO[GeoType.KMZ] = 'Google Earth (*.kmz)|*.kmz'
    GEO[GeoType.CSV] = 'CSV Table (*.csv)|*.csv'

    HEADER = "RTLSDR Scanner"
    VERSION = 9

    @staticmethod
    def __get_types(type):
        return [File.SAVE, File.PLOT, File.IMAGE, File.GEO][type]

    @staticmethod
    def get_type_ext(index, type=Types.PLOT):
        types = File.__get_types(type)
        filter = types[index]
        delim = filter.index('|*')
        return filter[delim + 2:]

    @staticmethod
    def get_type_filters(type=Types.PLOT):
        types = File.__get_types(type)

        filters = ''
        length = len(types)
        for i in xrange(length):
            filters += types[i]
            if i < length - 1:
                filters += '|'

        return filters

    @staticmethod
    def get_type_pretty(type=Types.PLOT):
        types = File.__get_types(type)

        pretty = ''
        length = len(types)
        for i in xrange(length):
            pretty += File.get_type_ext(i, type)
            if i < length - 2:
                pretty += ', '
            elif i < length - 1:
                pretty += ' or '

        return pretty

    @staticmethod
    def get_type_index(extension, type=Types.PLOT):
        exports = File.__get_types(type)
        for i in xrange(len(exports)):
            if extension == File.get_type_ext(i, type):
                return i

        return -1


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
