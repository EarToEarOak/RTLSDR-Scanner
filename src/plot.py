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
import threading

from matplotlib.ticker import ScalarFormatter, AutoMinorLocator
import wx

from constants import File, Plot
from events import EventThreadStatus, Event
from misc import split_spectrum


class ThreadPlot(threading.Thread):
    def __init__(self, notify, lock, graph, spectrum, settings, grid, full, fade):
        threading.Thread.__init__(self)
        self.name = 'ThreadPlot'
        self.notify = notify
        self.lock = lock
        self.graph = graph
        self.spectrum = spectrum
        self.settings = settings
        self.grid = grid
        self.full = full
        self.fade = fade

        self.start()

    def run(self):
        setup_plot(self.graph, self.settings, self.grid)

        axes = self.graph.get_axes()
        if not self.settings.retainScans:
            remove_plot(axes, Plot.STR_FULL)
        remove_plot(axes, Plot.STR_PARTIAL)

        if self.full:
            name = Plot.STR_FULL
        else:
            name = Plot.STR_PARTIAL
        self.graph.get_canvas().Name = name

        freqs, powers = split_spectrum(self.spectrum)
        axes.plot(freqs, powers, linewidth=0.4, color='b', alpha=1, gid=name)
        self.retain_plot(axes)

        if self.full:
            self.annotate(axes)

        self.graph.get_figure().tight_layout()

        wx.PostEvent(self.notify, EventThreadStatus(Event.DRAW))

    def retain_plot(self, axes):
        if self.full:
            if self.count_plots(axes) >= self.settings.maxScans:
                self.remove_first(axes)
            if self.settings.fadeScans:
                self.fade_plots(axes)

    def remove_first(self, axes):
        children = axes.get_children()
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() == Plot.STR_FULL or \
                child.get_gid() == Plot.STR_PARTIAL:
                    child.remove()
                break

    def remove_last(self, axes):
        children = axes.get_children()
        for child in reversed(children):
            if child.get_gid() is not None:
                if child.get_gid() == Plot.STR_FULL or \
                child.get_gid() == Plot.STR_PARTIAL:
                    child.remove()
                break

    def count_plots(self, axes):
        children = axes.get_children()
        count = 0
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() == Plot.STR_FULL or \
                child.get_gid() == Plot.STR_PARTIAL:
                    count += 1
        return count

    def fade_plots(self, axes):
        if self.fade:
            children = axes.get_children()
            for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == Plot.STR_FULL or\
                    child.get_gid() == Plot.STR_PARTIAL:
                        child.set_alpha(child.get_alpha() - 1.0 / self.settings.maxScans)

    def annotate(self, axes):
        children = axes.get_children()
        if self.settings.annotate and len(self.spectrum) > 0:
            for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == 'peak':
                        child.remove()
            try:
                freq = max(self.spectrum.iterkeys(),
                           key=(lambda key: self.spectrum[key]))
                power = self.spectrum[freq]
                start, stop = axes.get_xlim()
                textX = ((stop - start) / 50.0) + freq
                axes.annotate('{0:.3f}MHz\n{1:.2f}dB'.format(freq, power),
                              xy=(freq, power), xytext=(textX, power),
                              ha='left', va='top', size='small', gid='peak')
                axes.plot(freq, power, marker='x', markersize=10, color='r',
                          gid='peak')
            except RuntimeError:
                pass
            except KeyError:
                pass


def setup_plot(graph, settings, grid):
    axes = graph.get_axes()
    if len(settings.devices) > 0:
        gain = settings.devices[settings.index].gain
    else:
        gain = 0
    formatter = ScalarFormatter(useOffset=False)

    axes.set_title("Frequency Scan\n{0} - {1} MHz,"
                   " gain = {2}dB".format(settings.start,
                                        settings.stop, gain))
    axes.set_xlabel("Frequency (MHz)")
    axes.set_ylabel('Level (dB)')
    axes.xaxis.set_major_formatter(formatter)
    axes.yaxis.set_major_formatter(formatter)
    axes.xaxis.set_minor_locator(AutoMinorLocator(10))
    axes.yaxis.set_minor_locator(AutoMinorLocator(10))
    axes.grid(grid)


def scale_plot(graph, settings, updateScale=False):
    axes = graph.get_axes()
    if settings.autoScale:
        axes.set_ylim(auto=True)
        axes.set_xlim(auto=True)
        settings.yMin, settings.yMax = axes.get_ylim()
    else:
        axes.set_ylim(auto=False)
        axes.set_xlim(auto=False)
        if updateScale:
            if settings.yMin == settings.yMax:
                settings.yMax += 1
            axes.set_ylim(settings.yMin, settings.yMax)


def remove_plot(axes, plot):
    children = axes.get_children()
    for child in children:
        if child.get_gid() is not None:
            if child.get_gid() == plot:
                child.remove()


def open_plot(dirname, filename):
    pickle = True
    error = False
    dwell = 0.131
    nfft = 1024
    spectrum = {}

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
        except ValueError:
            error = True
        except KeyError:
            error = True

    handle.close()

    if error or header != File.HEADER:
        wx.MessageBox('Invalid or corrupted file', 'Warning',
                  wx.OK | wx.ICON_WARNING)
        return 0, 0, 0, 0, []

    return start, stop, dwell, nfft, spectrum


def save_plot(dirname, filename, settings, spectrum):
    data = [File.HEADER, {'Version': File.VERSION,
                          'Start':settings.start,
                          'Stop':settings.stop,
                          'Dwell':settings.dwell,
                          'Nfft':settings.nfft,
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
