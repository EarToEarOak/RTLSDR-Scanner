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
from collections import OrderedDict
import datetime
import json
from operator import itemgetter
import os
import sys
import time
import urllib

from matplotlib import cm
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.dates import date2num
import wx

from constants import SAMPLE_RATE, File, TIMESTAMP_FILE, Display


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
        device = settings.devices[settings.index]
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


class ValidatorCoord(wx.PyValidator):
    def __init__(self, isLat):
        wx.PyValidator.__init__(self)
        self.isLat = isLat

    def Validate(self, _window):
        textCtrl = self.GetWindow()
        text = textCtrl.GetValue()
        if len(text) == 0 or text == '-' or text.lower() == 'unknown':
            textCtrl.SetForegroundColour("black")
            textCtrl.Refresh()
            return True

        value = None
        try:
            value = float(text)
            if self.isLat and (value < -90 or value > 90):
                raise ValueError()
            elif value < -180 or value > 180:
                raise ValueError()
        except ValueError:
            textCtrl.SetForegroundColour("red")
            textCtrl.SetFocus()
            textCtrl.Refresh()
            return False

        textCtrl.SetForegroundColour("black")
        textCtrl.Refresh()
        return True

    def TransferToWindow(self):
        return True

    def TransferFromWindow(self):
        return True

    def Clone(self):
        return ValidatorCoord(self.isLat)


class Extent():
    def __init__(self, spectrum):
        self.clear()
        self.calc_extent(spectrum)

    def clear(self):
        self.fMin = float('inf')
        self.fMax = float('-inf')
        self.lMin = float('inf')
        self.lMax = float('-inf')
        self.tMin = float('inf')
        self.tMax = float('-inf')
        self.fPeak = None
        self.lPeak = None
        self.tPeak = None

    def calc_extent(self, spectrum):
        for timeStamp in spectrum:
            points = spectrum[timeStamp].items()
            if len(points) > 0:
                fMin = min(points, key=itemgetter(0))[0]
                fMax = max(points, key=itemgetter(0))[0]
                lMin = min(points, key=itemgetter(1))[1]
                lMax = max(points, key=itemgetter(1))[1]
                self.fMin = min(self.fMin, fMin)
                self.fMax = max(self.fMax, fMax)
                self.lMin = min(self.lMin, lMin)
                self.lMax = max(self.lMax, lMax)
        self.tMin = min(spectrum)
        self.tMax = max(spectrum)
        self.tPeak = self.tMax
        if len(spectrum[self.tMax]) > 0:
            self.fPeak, self.lPeak = max(spectrum[self.tMax].items(),
                                         key=lambda(_f, l): l)

    def get_f(self):
        if self.fMin == self.fMax:
            return self.fMin, self.fMax - 0.001
        return self.fMin, self.fMax

    def get_l(self):
        if self.lMin == self.lMax:
            return self.lMin, self.lMax - 0.001
        return self.lMin, self.lMax

    def get_t(self):
        return epoch_to_mpl(self.tMax), epoch_to_mpl(self.tMin - 1)

    def get_ft(self):
        tExtent = self.get_t()
        return [self.fMin, self.fMax, tExtent[0], tExtent[1]]

    def get_peak_fl(self):
        return self.fPeak, self.lPeak

    def get_peak_flt(self):
        return self.fPeak, self.lPeak, self.tPeak


class MouseZoom():
    SCALE_STEP = 1.3

    def __init__(self, plot, display, toolbar):
        if display == Display.SURFACE:
            return
        self.axes = plot.get_axes()
        self.toolbar = toolbar
        figure = self.axes.get_figure()
        figure.canvas.mpl_connect('scroll_event', self.zoom)

    def zoom(self, event):
        if event.button == 'up':
            scale = 1 / self.SCALE_STEP
        elif event.button == 'down':
            scale = self.SCALE_STEP
        else:
            return

        if self.toolbar._views.empty():
            self.toolbar.push_current()

        xLim = self.axes.get_xlim()
        yLim = self.axes.get_ylim()
        xPos = event.xdata
        yPos = event.ydata
        xPosRel = (xLim[1] - xPos) / (xLim[1] - xLim[0])
        yPosRel = (yLim[1] - yPos) / (yLim[1] - yLim[0])

        newXLim = (xLim[1] - xLim[0]) * scale
        newYLim = (yLim[1] - yLim[0]) * scale
        xStart = xPos - newXLim * (1 - xPosRel)
        xStop = xPos + newXLim * xPosRel
        yStart = yPos - newYLim * (1 - yPosRel)
        yStop = yPos + newYLim * yPosRel

        self.axes.set_xlim([xStart, xStop])
        self.axes.set_ylim([yStart, yStop])
        self.toolbar.push_current()

        self.axes.figure.canvas.draw()


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

    return scanInfo, spectrum


def save_plot(dirname, filename, scanInfo, spectrum):
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
                          'Spectrum': spectrum}]

    handle = open(os.path.join(dirname, filename), 'wb')
    handle.write(json.dumps(data, indent=4))
    handle.close()


def export_plot(dirname, filename, exportType, spectrum):
    spectrum = sort_spectrum(spectrum)
    handle = open(os.path.join(dirname, filename), 'wb')
    if exportType == File.ExportType.CSV:
        export_csv(handle, spectrum)
    elif exportType == File.ExportType.PLT:
        export_plt(handle, spectrum)
    handle.close()


def export_csv(handle, spectrum):
    handle.write("Time (UTC), Frequency (MHz),Level (dB/Hz)\n")
    for plot in spectrum.iteritems():
        for freq, pwr in plot[1].iteritems():
            handle.write("{0}, {1}, {2}\n".format(plot[0], freq, pwr))


def export_plt(handle, spectrum):
    handle.write('set title "RTLSDR Scan"\n')
    handle.write('set xlabel "Frequency (MHz)"\n')
    handle.write('set ylabel "Time"\n')
    handle.write('set zlabel "Level (dB)"\n')
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


def count_points(spectrum):
    points = 0
    for timeStamp in spectrum:
            points += len(spectrum[timeStamp])

    return points


def reduce_points(spectrum, limit, total):
    if total < limit:
        return spectrum

    newSpectrum = OrderedDict()
    ratio = float(total) / limit
    for timeStamp in spectrum:
        points = spectrum[timeStamp].items()
        reduced = OrderedDict()
        for i in xrange(int(len(points) / ratio)):
            point = points[int(i * ratio):int((i + 1) * ratio)][0]
            reduced[point[0]] = point[1]
        newSpectrum[timeStamp] = reduced

    return newSpectrum


def split_spectrum(spectrum):
    freqs = spectrum.keys()
    powers = map(spectrum.get, freqs)

    return freqs, powers


def sort_spectrum(spectrum):
    newSpectrum = OrderedDict()
    for timeStamp in reversed(sorted(spectrum)):
        newPoints = OrderedDict()
        points = sorted(spectrum[timeStamp].items())
        for point in points:
            newPoints[point[0]] = point[1]
        newSpectrum[timeStamp] = newPoints

    return newSpectrum


def next_2_to_pow(val):
    val -= 1
    val |= val >> 1
    val |= val >> 2
    val |= val >> 4
    val |= val >> 8
    val |= val >> 16
    return val + 1


def calc_samples(dwell):
    samples = dwell * SAMPLE_RATE
    samples = next_2_to_pow(int(samples))
    return samples


def calc_real_dwell(dwell):
    samples = calc_samples(dwell)
    dwellReal = samples / SAMPLE_RATE
    return (int)(dwellReal * 1000.0) / 1000.0


def nearest(value, values):
    offset = [abs(value - v) for v in values]
    return values[offset.index(min(offset))]


def epoch_to_local(epoch):
    local = time.localtime(epoch)
    return time.mktime(local)


def epoch_to_mpl(epoch):
    epoch = epoch_to_local(epoch)
    dt = datetime.datetime.fromtimestamp(epoch)
    return date2num(dt)


def format_time(timeStamp, withDate=False):
    if timeStamp <= 1:
        return 'Unknown'

    if withDate:
        return time.strftime('%c', time.localtime(timeStamp))

    return time.strftime('%H:%M:%S', time.localtime(timeStamp))


def load_bitmap(name):
    scriptDir = os.path.dirname(os.path.realpath(sys.argv[0]))
    if(os.path.isdir(scriptDir + '/res')):
        resDir = os.path.normpath(scriptDir + '/res')
    else:
        resDir = os.path.normpath(scriptDir + '/../res')

    return wx.Bitmap(resDir + '/' + name + '.png', wx.BITMAP_TYPE_PNG)


def add_colours():
    r = {'red':     ((0.0, 1.0, 1.0),
                     (1.0, 1.0, 1.0)),
         'green':   ((0.0, 0.0, 0.0),
                     (1.0, 0.0, 0.0)),
         'blue':   ((0.0, 0.0, 0.0),
                         (1.0, 0.0, 0.0))
        }
    g = {'red':     ((0.0, 0.0, 0.0),
                     (1.0, 0.0, 0.0)),
         'green':   ((0.0, 1.0, 1.0),
                     (1.0, 1.0, 1.0)),
         'blue':    ((0.0, 0.0, 0.0),
                     (1.0, 0.0, 0.0))
        }
    b = {'red':     ((0.0, 0.0, 0.0),
                     (1.0, 0.0, 0.0)),
         'green':   ((0.0, 0.0, 0.0),
                     (1.0, 0.0, 0.0)),
         'blue':    ((0.0, 1.0, 1.0),
                     (1.0, 1.0, 1.0))
        }

    rMap = LinearSegmentedColormap('red_map', r)
    gMap = LinearSegmentedColormap('red_map', g)
    bMap = LinearSegmentedColormap('red_map', b)
    cm.register_cmap(name=' Pure Red', cmap=rMap)
    cm.register_cmap(name=' Pure Green', cmap=gMap)
    cm.register_cmap(name=' Pure Blue', cmap=bMap)


def get_colours():
    colours = [colour for colour in cm.cmap_d]
    colours.sort()

    return colours


def set_version_timestamp():
    scriptDir = os.path.dirname(os.path.realpath(sys.argv[0]))
    timeStamp = str(int(time.time()))
    f = open(scriptDir + '/' + TIMESTAMP_FILE, 'w')
    f.write(timeStamp)
    f.close()


def get_version_timestamp(asSeconds=False):
    scriptDir = os.path.dirname(os.path.realpath(sys.argv[0]))
    f = open(scriptDir + '/' + TIMESTAMP_FILE, 'r')
    timeStamp = int(f.readline())
    f.close()
    if asSeconds:
        return timeStamp
    else:
        return format_time(timeStamp, True)


def get_version_timestamp_repo():
    f = urllib.urlopen('https://raw.github.com/EarToEarOak/RTLSDR-Scanner/master/src/version-timestamp')
    timeStamp = int(f.readline())
    f.close()
    return timeStamp


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
