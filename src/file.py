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

import cPickle
import json
import os
import tempfile
import zipfile

from PIL import Image
import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg
import wx

from spectrum import sort_spectrum, create_mesh


class File(object):
    class Types(object):
        SAVE, PLOT, IMAGE, GEO = range(4)

    class SaveType(object):
        RFS = 0

    class PlotType(object):
        CSV, GNUPLOT, FREEMAT = range(3)

    class ImageType(object):
        BMP, EPS, GIF, JPEG, PDF, PNG, PPM, TIFF = range(8)

    class GeoType(object):
        KMZ, CSV, BMP, EPS, GIF, JPEG, PDF, PNG, PPM, TIFF = range(10)

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

    GEO = [''] * 10

    GEO[GeoType.BMP] = 'Bitmap image (*.bmp)|*.bmp'
    GEO[GeoType.CSV] = 'CSV Table (*.csv)|*.csv'
    GEO[GeoType.EPS] = 'Encapsulated PostScript (*.eps)|*.eps'
    GEO[GeoType.GIF] = 'GIF image (*.gif)|*.gif'
    GEO[GeoType.JPEG] = 'JPEG image (*.jpeg)|*.jpeg'
    GEO[GeoType.KMZ] = 'Google Earth (*.kmz)|*.kmz'
    GEO[GeoType.PDF] = 'Portable Document (*.pdf)|*.pdf'
    GEO[GeoType.PNG] = 'Portable Network Graphics Image (*.png)|*.png'
    GEO[GeoType.PPM] = 'Portable Pixmap image (*.ppm)|*.ppm'
    GEO[GeoType.TIFF] = 'Tagged Image File (*.tiff)|*.tiff'

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
    def get_type_pretty(type):
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


class ScanInfo(object):
    start = None
    stop = None
    dwell = None
    nfft = None
    name = None
    gain = None
    lo = None
    calibration = None
    tuner = 0
    time = None
    timeFirst = None
    timeLast = None
    lat = None
    lon = None
    desc = ''

    def set_from_settings(self, settings):
        self.start = settings.start
        self.stop = settings.stop
        self.dwell = settings.dwell
        self.nfft = settings.nfft
        device = settings.devicesRtl[settings.indexRtl]
        if device.isDevice:
            self.name = device.name
        else:
            self.name = device.server + ":" + str(device.port)
        self.gain = device.gain
        self.lo = device.lo
        self.calibration = device.calibration
        self.tuner = device.tuner

    def set_to_settings(self, settings):
        settings.start = self.start
        settings.stop = self.stop
        settings.dwell = self.dwell
        settings.nfft = self.nfft


def open_plot(dirname, filename):
    pickle = True
    error = False
    dwell = 0.131
    nfft = 1024
    name = None
    gain = None
    lo = None
    calibration = None
    tuner = 0
    spectrum = {}
    time = None
    lat = None
    lon = None
    desc = ''
    location = {}

    path = os.path.join(dirname, filename)
    if not os.path.exists(path):
        return None, None, None
    handle = open(path, 'rb')
    try:
        header = cPickle.load(handle)
    except cPickle.UnpicklingError:
        pickle = False
    except EOFError:
        pickle = False

    if pickle:
        try:
            _version = cPickle.load(handle)
            start = cPickle.load(handle)
            stop = cPickle.load(handle)
            spectrum[1] = {}
            spectrum[1] = cPickle.load(handle)
        except pickle.PickleError:
            error = True
    else:
        try:
            handle.seek(0)
            data = json.loads(handle.read())
            header = data[0]
            version = data[1]['Version']
            start = data[1]['Start']
            stop = data[1]['Stop']
            if version > 1:
                dwell = data[1]['Dwell']
                nfft = data[1]['Nfft']
            if version > 2:
                name = data[1]['Device']
                gain = data[1]['Gain']
                lo = data[1]['LO']
                calibration = data[1]['Calibration']
            if version > 4:
                tuner = data[1]['Tuner']
            if version > 5:
                time = data[1]['Time']
                lat = data[1]['Latitude']
                lon = data[1]['Longitude']
            if version < 7:
                spectrum[1] = {}
                for f, p in data[1]['Spectrum'].iteritems():
                    spectrum[1][float(f)] = p
            else:
                for t, s in data[1]['Spectrum'].iteritems():
                    spectrum[float(t)] = {}
                    for f, p in s.iteritems():
                        spectrum[float(t)][float(f)] = p
            if version > 7:
                desc = data[1]['Description']
            if version > 8:
                location = {}
                for t, l in data[1]['Location'].iteritems():
                    location[float(t)] = l

        except ValueError:
            error = True
        except KeyError:
            error = True

    handle.close()

    if error or header != File.HEADER:
        wx.MessageBox('Invalid or corrupted file', 'Warning',
                      wx.OK | wx.ICON_WARNING)
        return None, None, None

    scanInfo = ScanInfo()
    scanInfo.start = start
    scanInfo.stop = stop
    scanInfo.dwell = dwell
    scanInfo.nfft = nfft
    scanInfo.name = name
    scanInfo.gain = gain
    scanInfo.lo = lo
    scanInfo.calibration = calibration
    scanInfo.tuner = tuner
    scanInfo.time = time
    scanInfo.lat = lat
    scanInfo.lon = lon
    scanInfo.desc = desc

    return scanInfo, spectrum, location


def save_plot(filename, scanInfo, spectrum, location):
    data = [File.HEADER, {'Version': File.VERSION,
                          'Start': scanInfo.start,
                          'Stop': scanInfo.stop,
                          'Dwell': scanInfo.dwell,
                          'Nfft': scanInfo.nfft,
                          'Device': scanInfo.name,
                          'Gain': scanInfo.gain,
                          'LO': scanInfo.lo,
                          'Calibration': scanInfo.calibration,
                          'Tuner': scanInfo.tuner,
                          'Time': scanInfo.time,
                          'Latitude': scanInfo.lat,
                          'Longitude': scanInfo.lon,
                          'Description': scanInfo.desc,
                          'Spectrum': spectrum,
                          'Location': location}]

    handle = open(os.path.join(filename), 'wb')
    handle.write(json.dumps(data, indent=4))
    handle.close()


def export_plot(filename, exportType, spectrum):
    spectrum = sort_spectrum(spectrum)
    handle = open(filename, 'wb')
    if exportType == File.PlotType.CSV:
        export_csv(handle, spectrum)
    elif exportType == File.PlotType.GNUPLOT:
        export_plt(handle, spectrum)
    elif exportType == File.PlotType.FREEMAT:
        export_freemat(handle, spectrum)
    handle.close()


def export_image(filename, format, figure, dpi):
    oldSize = figure.get_size_inches()
    oldDpi = figure.get_dpi()
    figure.set_size_inches((8, 4.5))
    figure.set_dpi(dpi)

    canvas = FigureCanvasAgg(figure)
    canvas.draw()
    renderer = canvas.get_renderer()
    if matplotlib.__version__ >= '1.2':
        buf = renderer.buffer_rgba()
    else:
        buf = renderer.buffer_rgba(0, 0)
    size = canvas.get_width_height()
    image = Image.frombuffer('RGBA', size, buf, 'raw', 'RGBA', 0, 1)
    image = image.convert('RGB')
    ext = File.get_type_ext(format, File.Types.IMAGE)
    image.save(filename, format=ext[1::], dpi=(dpi, dpi))

    figure.set_size_inches(oldSize)
    figure.set_dpi(oldDpi)


def export_map(filename, exportType, bounds, image, xyz):
    if exportType == File.GeoType.KMZ:
        export_kmz(filename, bounds, image)
    elif exportType == File.GeoType.CSV:
        export_xyz(filename, xyz)
    else:
        export_map_image(filename, exportType, image)


def export_csv(handle, spectrum):
    handle.write(u"Time (UTC), Frequency (MHz),Level (dB/Hz)\n")
    for plot in spectrum.iteritems():
        for freq, pwr in plot[1].iteritems():
            handle.write("{0}, {1}, {2}\n".format(plot[0], freq, pwr))


def export_plt(handle, spectrum):
    handle.write('set title "RTLSDR Scan"\n')
    handle.write('set xlabel "Frequency (MHz)"\n')
    handle.write('set ylabel "Time"\n')
    handle.write('set zlabel "Level (dB/Hz)"\n')
    handle.write('set ydata time\n')
    handle.write('set timefmt "%s"\n')
    handle.write('set format y "%H:%M:%S"\n')
    handle.write('set pm3d\n')
    handle.write('set hidden3d\n')
    handle.write('set palette rgb 33,13,10\n')
    handle.write('splot "-" using 1:2:3 notitle with lines \n')
    for plot in spectrum.iteritems():
        handle.write('\n')
        for freq, pwr in plot[1].iteritems():
            handle.write("{0} {1} {2}\n".format(freq, plot[0], pwr))


def export_freemat(handle, spectrum):
    x, y, z = create_mesh(spectrum, False)
    write_numpy(handle, x, 'x')
    write_numpy(handle, y, 'y')
    write_numpy(handle, z, 'z')
    handle.write('\n')
    handle.write('surf(x,y,z)\n')
    handle.write('view(3)\n')
    handle.write("set(gca, 'plotboxaspectratio', [3, 2, 1])\n")
    handle.write("title('RTLSDR Scan')\n")
    handle.write("xlabel('Frequency (MHz)')\n")
    handle.write("ylabel('Time')\n")
    handle.write("zlabel('Level (dB/Hz)')\n")
    handle.write("grid('on')\n")


def export_kmz(filename, bounds, image):
    tempPath = tempfile.mkdtemp()

    name = os.path.splitext(os.path.basename(filename))[0]
    filePng = name + '.png'
    fileKml = name + '.kml'

    image.save('{0}/{1}'.format(tempPath, filePng))

    handle = open('{0}/{1}'.format(tempPath, fileKml), 'wb')
    handle.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    handle.write('<kml xmlns="http://www.opengis.net/kml/2.2" '
                 'xmlns:gx="http://www.google.com/kml/ext/2.2" '
                 'xmlns:kml="http://www.opengis.net/kml/2.2" '
                 'xmlns:atom="http://www.w3.org/2005/Atom">\n')
    handle.write('<GroundOverlay>\n')
    handle.write('\t<name>RTLSDR Scanner - {0}</name>\n'.format(name))
    handle.write('\t<Icon>\n')
    handle.write('\t\t<href>files/{0}</href>\n'.format(filePng))
    handle.write('\t\t<viewBoundScale>0.75</viewBoundScale>\n')
    handle.write('\t</Icon>\n')
    handle.write('\t<LatLonBox>\n')
    handle.write('\t\t<north>{0}</north>\n'.format(bounds[3]))
    handle.write('\t\t<south>{0}</south>\n'.format(bounds[2]))
    handle.write('\t\t<east>{0}</east>\n'.format(bounds[1]))
    handle.write('\t\t<west>{0}</west>\n'.format(bounds[0]))
    handle.write('\t</LatLonBox>\n')
    handle.write('</GroundOverlay>\n')
    handle.write('</kml>\n')
    handle.close()

    kmz = zipfile.ZipFile(filename, 'w')
    kmz.write('{0}/{1}'.format(tempPath, fileKml),
              '/{0}'.format(fileKml))
    kmz.write('{0}/{1}'.format(tempPath, filePng),
              '/files/{0}'.format(filePng))
    kmz.close()

    os.remove('{0}/{1}'.format(tempPath, filePng))
    os.remove('{0}/{1}'.format(tempPath, fileKml))
    os.rmdir(tempPath)


def export_xyz(filename, xyz):
    handle = open(filename, 'wb')
    handle.write('x, y, Level (dB/Hz)\n')
    for i in range(len(xyz[0])):
        handle.write('{0}, {1}, {2}\n'.format(xyz[0][i], xyz[1][i], xyz[2][i]))
    handle.close()


def export_map_image(filename, exportType, image):
    ext = File.get_type_ext(exportType, File.Types.IMAGE)
    image.save(filename, format=ext[1::])


def write_numpy(handle, array, name):
    handle.write('{0}=[\n'.format(name))
    for i in array:
        for j in i:
            handle.write('{0} '.format(j))
        handle.write(';\n')
    handle.write(']\n')


def extension_add(fileName, index, fileType):
    _name, extCurrent = os.path.splitext(fileName)
    ext = File.get_type_ext(index, fileType)
    if extCurrent != ext:
        return fileName + ext

    return fileName


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
