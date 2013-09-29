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

import threading

import rtlsdr

from constants import *
from events import *
from misc import split_spectrum
from plot import setup_plot


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
        wx.PostEvent(self.notify, EventThreadStatus(EVENT_STARTING))
        self.start()

    def run(self):
        sdr = self.rtl_setup()
        if sdr is None:
            return

        freq = self.fstart - self.offset - BANDWIDTH
        while freq <= self.fstop + self.offset:
            if self.cancel:
                wx.PostEvent(self.notify,
                             EventThreadStatus(EVENT_STOPPED))
                sdr.close()
                return
            try:
                progress = ((freq - self.fstart + self.offset) /
                             (self.fstop - self.fstart + BANDWIDTH)) * 100
                wx.PostEvent(self.notify,
                             EventThreadStatus(EVENT_SCAN,
                                               0, progress))
                scan = self.scan(sdr, freq)
                wx.PostEvent(self.notify,
                             EventThreadStatus(EVENT_DATA, freq,
                                               scan))
            except (IOError, WindowsError):
                if sdr is not None:
                    sdr.close()
                sdr = self.rtl_setup()
            except (TypeError, AttributeError) as error:
                if self.notify:
                    wx.PostEvent(self.notify,
                             EventThreadStatus(EVENT_ERROR,
                                               0, error.message))
                return

            freq += BANDWIDTH / 2

        sdr.close()
        wx.PostEvent(self.notify, EventThreadStatus(EVENT_FINISHED,
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
            wx.PostEvent(self.notify, EventThreadStatus(EVENT_ERROR,
                                                        0, error.message))

        return sdr

    def scan(self, sdr, freq):
        sdr.set_center_freq(freq + self.lo)
        capture = sdr.read_samples(self.samples)

        return capture


class ThreadPlot(threading.Thread):
    def __init__(self, graph, spectrum, settings, grid, full, fade):
        threading.Thread.__init__(self)
        self.name = 'ThreadPlot'
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
        self.remove_partial(axes)
        if self.full:
            name = PLOT_STR_FULL
        else:
            name = PLOT_STR_PARTIAL
        self.graph.get_canvas().Name = name

        freqs, powers = split_spectrum(self.spectrum)
        axes.plot(freqs, powers, linewidth=0.4, color='b', alpha=1, gid=name)
        self.retain_plot(axes)

        if self.full:
            self.annotate(axes)

        self.graph.get_canvas().draw()

    def retain_plot(self, axes):
        if not self.settings.retainScans:
            self.remove_first(axes)
        else:
            if self.full:
                if self.count_plots(axes) >= self.settings.maxScans:
                    self.remove_first(axes)
                if self.settings.fadeScans:
                    self.fade_plots(axes)

    def remove_partial(self, axes):
        children = axes.get_children()
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() == PLOT_STR_PARTIAL:
                    child.remove()

    def remove_first(self, axes):
        children = axes.get_children()
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() == PLOT_STR_FULL or \
                child.get_gid() == PLOT_STR_PARTIAL:
                    child.remove()
                break

    def remove_last(self, axes):
        children = axes.get_children()
        for child in reversed(children):
            if child.get_gid() is not None:
                if child.get_gid() == PLOT_STR_FULL or \
                child.get_gid() == PLOT_STR_PARTIAL:
                    child.remove()
                break

    def count_plots(self, axes):
        children = axes.get_children()
        count = 0
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() == PLOT_STR_FULL or \
                child.get_gid() == PLOT_STR_PARTIAL:
                    count += 1
        return count

    def fade_plots(self, axes):
        if self.fade:
            children = axes.get_children()
            for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == PLOT_STR_FULL or\
                    child.get_gid() == PLOT_STR_PARTIAL:
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


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
