#
# rtlsdr_scan
#
# http://eartoearoak.com/software/rtlsdr-scanner
#
# Copyright 2012, 2013 Al Brown
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

from matplotlib.ticker import ScalarFormatter, AutoMinorLocator
import wx

from constants import File
from events import EventThreadStatus, Event
from misc import split_spectrum


class Plotter():
    def __init__(self, notify, graph, settings, grid, lock):
        self.notify = notify
        self.graph = graph
        self.settings = settings
        self.graph = graph
        self.grid = grid
        self.lock = lock
        self.axes = None
        self.currentPlot = None
        self.lastPlot = None
        self.setup_plot()
        self.clear_plots()

    def setup_plot(self):
        self.axes = self.graph.get_axes()
        if len(self.settings.devices) > 0:
            gain = self.settings.devices[self.settings.index].gain
        else:
            gain = 0
        formatter = ScalarFormatter(useOffset=False)

        self.axes.set_title("Frequency Scan\n{0} - {1} MHz,"
                            " gain = {2}dB".format(self.settings.start,
                                                   self.settings.stop, gain))
        self.axes.set_xlabel("Frequency (MHz)")
        self.axes.set_ylabel('Level (dB)')
        self.axes.xaxis.set_major_formatter(formatter)
        self.axes.yaxis.set_major_formatter(formatter)
        self.axes.xaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.yaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.grid(self.grid)
        self.axes.set_xlim(self.settings.start, self.settings.stop)
        self.axes.set_ylim(-50, 0)

    def scale_plot(self):
        with self.lock:
            if self.settings.autoScale:
                self.axes.set_ylim(auto=True)
                self.axes.set_xlim(auto=True)
                self.axes.relim()
                self.axes.autoscale_view()
                self.settings.yMin, self.settings.yMax = self.axes.get_ylim()
            else:
                self.axes.set_ylim(auto=False)
                self.axes.set_xlim(auto=False)
                self.axes.set_ylim(self.settings.yMin, self.settings.yMax)

    def retain_plot(self):
        if self.count_plots() >= self.settings.maxScans:
            self.remove_first()

    def remove_first(self):
        with self.lock:
            children = self.axes.get_children()
            for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == "plot":
                        child.remove()
                    break

    def remove_last(self):
        with self.lock:
            children = self.axes.get_children()
            for child in reversed(children):
                if child.get_gid() is not None:
                    if child.get_gid() == "plot":
                        child.remove()
                    break

    def count_plots(self):
        with self.lock:
            children = self.axes.get_children()
            count = 0
            for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == "plot":
                        count += 1
            return count

    def fade_plots(self):
        with self.lock:
            children = self.axes.get_children()
            for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == "plot":
                        child.set_alpha(child.get_alpha() - 1.0 \
                                        / self.settings.maxScans)

    def redraw(self):
        self.graph.get_figure().tight_layout()
        wx.PostEvent(self.notify, EventThreadStatus(Event.DRAW))

    def set_plot(self, plot):
        xs, ys = split_spectrum(plot)
        with self.lock:
            self.currentPlot.set_data(xs, ys)
            self.axes.relim()
            self.axes.autoscale_view()
        self.scale_plot()
        self.redraw()

    def new_plot(self):
        if self.settings.retainScans:
            self.retain_plot()
        else:
            self.remove_first()
        if self.settings.retainScans and self.settings.fadeScans:
            self.fade_plots()

        with self.lock:
            self.lastPlot = self.currentPlot
            self.currentPlot, = self.axes.plot([], [], linewidth=0.4, color='b',
                                               alpha=1, gid="plot")
        self.redraw()

    def annotate_plot(self):
        with self.lock:
            if not self.settings.annotate:
                return
            children = self.axes.get_children()
            for child in children:
                    if child.get_gid() is not None:
                        if child.get_gid() == 'peak':
                            child.remove()

            if self.lastPlot is not None:
                line = self.lastPlot
            else:
                line = self.currentPlot

            data = line.get_data()
            y = max(data[1])
            pos = data[1].index(y)
            x = data[0][pos]
            start, stop = self.axes.get_xlim()
            textX = ((stop - start) / 50.0) + x
            self.axes.annotate('{0:.3f}MHz\n{1:.2f}dB'.format(x, y),
                               xy=(x, y), xytext=(textX, y),
                               ha='left', va='top', size='small', gid='peak')
            self.axes.plot(x, y, marker='x', markersize=10, color='r',
                           gid='peak')

    def clear_plots(self):
        with self.lock:
            children = self.axes.get_children()
            for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == "plot" or child.get_gid() == "peak":
                        child.remove()

        self.new_plot()
        self.lastPlot = None


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
    lat = None
    lon = None

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

    path = os.path.join(dirname, filename)
    if not os.path.exists(path):
        return 0, 0, 0, 0, []
    handle = open(path, 'rb')
    try:
        header = cPickle.load(handle)
    except cPickle.UnpicklingError:
        pickle = False

    if pickle:
        try:
            _version = cPickle.load(handle)
            start = cPickle.load(handle)
            stop = cPickle.load(handle)
            spectrum = cPickle.load(handle)
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
            for key, value in data[1]['Spectrum'].iteritems():
                spectrum[float(key)] = value
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
                          'Spectrum': spectrum}]

    handle = open(os.path.join(dirname, filename), 'wb')
    handle.write(json.dumps(data, indent=4))
    handle.close()


def export_plot(dirname, filename, spectrum):
    handle = open(os.path.join(dirname, filename), 'wb')
    handle.write("Frequency (MHz),Level (dB)\n")
    for freq, pwr in spectrum.iteritems():
        handle.write("{0},{1}\n".format(freq, pwr))
    handle.close()

if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)

