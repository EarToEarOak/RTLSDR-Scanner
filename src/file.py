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

from PIL import Image
import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg
import wx

from constants import File
from spectrum import sort_spectrum, create_mesh


class ScanInfo():
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

    def setFromSettings(self, settings):
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

    def setToSettings(self, settings):
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
        return 0, 0, 0, 0, []
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
                location = data[1]['Location']

        except ValueError:
            error = True
        except KeyError:
            error = True

    handle.close()

    if error or header != File.HEADER:
        wx.MessageBox('Invalid or corrupted file', 'Warning',
                  wx.OK | wx.ICON_WARNING)
        return 0, 0, 0, 0, []

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


def save_plot(dirname, filename, scanInfo, spectrum, location):
    data = [File.HEADER, {'Version': File.VERSION,
                          'Start':scanInfo.start,
                          'Stop':scanInfo.stop,
                          'Dwell':scanInfo.dwell,
                          'Nfft':scanInfo.nfft,
                          'Device':scanInfo.name,
                          'Gain':scanInfo.gain,
                          'LO':scanInfo.lo,
                          'Calibration':scanInfo.calibration,
                          'Tuner':scanInfo.tuner,
                          'Time':scanInfo.time,
                          'Latitude':scanInfo.lat,
                          'Longitude':scanInfo.lon,
                          'Description':scanInfo.desc,
                          'Spectrum': spectrum,
                          'Location': location}]

    handle = open(os.path.join(dirname, filename), 'wb')
    handle.write(json.dumps(data, indent=4))
    handle.close()


def export_plot(dirname, filename, exportType, spectrum):
    spectrum = sort_spectrum(spectrum)
    handle = open(os.path.join(dirname, filename), 'wb')
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
    ext = File.get_export_ext(format, File.Exports.IMAGE)
    image.save(filename, format=ext[1::], dpi=(dpi, dpi))

    figure.set_size_inches(oldSize)
    figure.set_dpi(oldDpi)


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


def write_numpy(handle, array, name):
    handle.write('{0}=[\n'.format(name))
    for i in array:
        for j in i:
            handle.write('{0} '.format(j))
        handle.write(';\n')
    handle.write(']\n')


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
