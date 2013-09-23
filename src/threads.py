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

import heapq
import itertools
import threading

import matplotlib
from matplotlib.artist import ArtistInspector
from matplotlib.lines import Line2D
from matplotlib.text import Annotation
import rtlsdr
import wx

from constants import *
from misc import split_spectrum, setup_plot


EVT_THREAD_STATUS = wx.NewId()


class Status():
    def __init__(self, status, freq, data, thread):
        self.status = status
        self.freq = freq
        self.data = data
        self.thread = thread

    def get_status(self):
        return self.status

    def get_freq(self):
        return self.freq

    def get_data(self):
        return self.data

    def get_thread(self):
        return self.thread


class EventThreadStatus(wx.PyEvent):
    def __init__(self, status, freq=None, data=None, thread=None):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_THREAD_STATUS)
        self.data = Status(status, freq, data, thread)


class ThreadScan(threading.Thread):
    def __init__(self, notify, settings, devices, samples, isCal):
        threading.Thread.__init__(self)
        self.name = 'ThreadScan'
        self.notify = notify
        self.index = settings.index
        self.fstart = settings.start * 1e6
        self.fstop = settings.stop * 1e6
        self.samples = samples
        self.isCal = isCal
        self.gain = devices[self.index].gain
        self.lo = devices[self.index].lo * 1e6
        self.offset = devices[self.index].offset
        self.cancel = False
        wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_STARTING))
        self.start()

    def run(self):
        sdr = self.rtl_setup()
        if sdr is None:
            return

        freq = self.fstart - self.offset
        while freq <= self.fstop + self.offset:
            if self.cancel:
                wx.PostEvent(self.notify,
                             EventThreadStatus(THREAD_STATUS_STOPPED))
                sdr.close()
                return
            try:
                progress = ((freq - self.fstart + self.offset) /
                             (self.fstop - self.fstart + BANDWIDTH)) * 100
                wx.PostEvent(self.notify,
                             EventThreadStatus(THREAD_STATUS_SCAN,
                                               0, progress))
                scan = self.scan(sdr, freq)
                wx.PostEvent(self.notify,
                             EventThreadStatus(THREAD_STATUS_DATA, freq,
                                               scan))
            except (IOError, WindowsError):
                if sdr is not None:
                    sdr.close()
                sdr = self.rtl_setup()
            except (TypeError, AttributeError) as error:
                if self.notify:
                    wx.PostEvent(self.notify,
                             EventThreadStatus(THREAD_STATUS_ERROR,
                                               0, error.message))
                return

            freq += BANDWIDTH / 2

        sdr.close()
        wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_FINISHED,
                                                    0, self.isCal))

    def abort(self):
        self.cancel = True

    def rtl_setup(self):
        sdr = None
        try:
            sdr = rtlsdr.RtlSdr(self.index)
            sdr.set_sample_rate(SAMPLE_RATE)
            sdr.set_gain(self.gain)
        except IOError as error:
            wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_ERROR,
                                                        0, error.message))

        return sdr

    def scan(self, sdr, freq):
        sdr.set_center_freq(freq + self.lo)
        capture = sdr.read_samples(self.samples)

        return capture


class ThreadProcess(threading.Thread):
    def __init__(self, notify, freq, data, settings, devices, nfft):
        threading.Thread.__init__(self)
        self.name = 'ThreadProcess'
        self.notify = notify
        self.freq = freq
        self.data = data
        self.cal = devices[settings.index].calibration
        self.nfft = nfft
        self.window = matplotlib.numpy.hamming(nfft)

        self.start()

    def run(self):
        scan = {}
        powers, freqs = matplotlib.mlab.psd(self.data,
                         NFFT=self.nfft,
                         Fs=SAMPLE_RATE / 1e6,
                         window=self.window)
        for freq, pwr in itertools.izip(freqs, powers):
            xr = freq + (self.freq / 1e6)
            xr = xr + (xr * self.cal / 1e6)
            xr = int((xr * 5e4) + 0.5) / 5e4
            scan[xr] = pwr
        thread = threading.current_thread()
        wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_PROCESSED,
                                                    self.freq, scan, thread))


class ThreadPlot(threading.Thread):
    def __init__(self, notify, graph, spectrum, settings, grid, full):
        threading.Thread.__init__(self)
        self.name = 'ThreadPlot'
        self.notify = notify
        self.graph = graph
        self.spectrum = spectrum
        self.settings = settings
        self.grid = grid
        self.full = full

        self.start()

    def run(self):
        setup_plot(self.graph, self.settings, self.grid)

        axes = self.graph.get_axes()

        children = axes.get_children()
        for child in children:
            if isinstance(child, Annotation):
                child.remove()
            elif child.get_gid() is not None and child.get_gid() == 'peak':
                child.remove()

        self.retain_plot(axes)

        freqs, powers = split_spectrum(self.spectrum)
        axes.plot(freqs, powers, linewidth=0.4, color='b', alpha=1)

        self.annotate(axes)

        self.graph.get_canvas().draw()
        wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_PLOTTED))

    def retain_plot(self, axes):
        lines = axes.get_lines()
        if not self.settings.retainScans:
            if len(lines) > 0:
                axes.lines.pop(0)
        else:
            if not self.full:
                if len(lines) > 0:
                    axes.lines.pop(len(lines) - 1)
            else:
                if len(lines) >= self.settings.maxScans:
                    axes.lines.pop(0)
                if self.settings.fadeScans:
                    for line in lines:
                        line.set_alpha(line.get_alpha() - 1 / self.settings.maxScans)

    def annotate(self, axes):
        if self.settings.annotate:
            try:
                freq = max(self.spectrum.iterkeys(),
                           key=(lambda key: self.spectrum[key]))
                power = self.spectrum[freq]
                textX = ((self.settings.stop - self.settings.start) / 50.0) + freq
                axes.annotate('{0:.3f}MHz\n{1:.2f}dB'.format(freq, power),
                              xy=(freq, power), xytext=(textX, power),
                              ha='left', va='top', size='small')
                axes.plot(freq, power, marker='x', markersize=10, color='r',
                          gid='peak')
            except RuntimeError:
                pass

