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

import os
from threading import Thread

from matplotlib import cm
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator
import numpy
from numpy.ma.bench import xs
import wx

from events import EventThreadStatus, Event
from misc import split_spectrum
from plot import thread_plot


class Spectrogram:
    def __init__(self, notify, graph, settings, grid, lock):
        self.notify = notify
        self.settings = settings
        self.graph = graph
        self.data = [[], [], []]
        self.index = 0
        self.axes = None
        self.lock = lock
        self.plot = None
        self.setup_plot()
        self.set_grid(grid)
        self.redraw()

    def setup_plot(self):
        gs = GridSpec(1, 2, width_ratios=[9.5, 0.5])
        figure = self.graph.get_figure()
        self.axes = figure.add_subplot(gs[0])
        self.create_plot()

        if len(self.settings.devices) > 0:
            gain = self.settings.devices[self.settings.index].gain
        else:
            gain = 0
        self.axes.set_title("Frequency Scan\n{0} - {1} MHz,"
                            " gain = {2}dB".format(self.settings.start,
                                                   self.settings.stop, gain))
        self.axes.set_xlabel("Frequency (MHz)")
        self.axes.set_ylabel('Time')
        formatter = ScalarFormatter(useOffset=False)
        self.axes.xaxis.set_major_formatter(formatter)
        self.axes.yaxis.set_major_formatter(formatter)
        self.axes.xaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.yaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.set_xlim(self.settings.start, self.settings.stop)
        self.axes.set_ylim(-50, 0)

        self.bar = figure.add_subplot(gs[1])
        figure.colorbar(self.plot, cax=self.bar)
        self.bar.set_ylabel('Level (dB)')

    def scale_plot(self):
        pass

    def create_plot(self):
        with self.lock:
            self.plot = self.axes.pcolormesh(numpy.array(self.data), vmin=-50, vmax=0)

    def redraw(self):
        if os.name == "nt":
            thread = Thread(target=thread_plot, args=(self.graph, self.lock,))
            thread.start()
        else:
            wx.PostEvent(self.notify, EventThreadStatus(Event.DRAW))

    def set_plot(self, plot):
        # TODO:
        pass

    def new_plot(self):
        self.index += 1

    def annotate_plot(self):
        pass

    def clear_plots(self):
        with self.lock:
            self.data = [[], [], []]
            self.index = 0
            children = self.axes.get_children()
            for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == "spec" :
                        child.remove()

        self.create_plot()

    def set_grid(self, on):
        self.axes.grid(on)
        self.redraw()


def thread_plot(graph, lock):
    with lock:
        graph.get_canvas().draw()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
