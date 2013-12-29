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
import time

from matplotlib import cm
from matplotlib.colorbar import ColorbarBase
from matplotlib.colors import Normalize
from matplotlib.dates import DateFormatter
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator
import wx

from events import EventThreadStatus, Event
from misc import split_spectrum, epoch_to_mpl
import numpy as np


class Spectrogram:
    def __init__(self, notify, graph, settings, grid, lock):
        self.notify = notify
        self.settings = settings
        self.graph = graph
        self.data = [[], [], []]
        self.index = 0
        self.figure = self.graph.get_figure()
        self.grid = grid
        self.lock = lock
        self.axes = None
        self.plot = None
        self.setup_plot()
        self.set_grid(grid)
        self.redraw_plot()

    def setup_plot(self):
        gs = GridSpec(1, 2, width_ratios=[9.5, 0.5])
        self.axes = self.figure.add_subplot(gs[0])

        if len(self.settings.devices) > 0:
            gain = self.settings.devices[self.settings.index].gain
        else:
            gain = 0
        self.axes.set_title("Frequency Spectrogram\n{0} - {1} MHz,"
                            " gain = {2}dB".format(self.settings.start,
                                                   self.settings.stop, gain))
        self.axes.set_xlabel("Frequency (MHz)")
        self.axes.set_ylabel('Time')
        numFormatter = ScalarFormatter(useOffset=False)
        timeFormatter = DateFormatter("%H:%M:%S")

        self.axes.xaxis.set_major_formatter(numFormatter)
        self.axes.yaxis.set_major_formatter(timeFormatter)
        self.axes.xaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.yaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.set_xlim(self.settings.start, self.settings.stop)
        now = time.time()
        self.axes.set_ylim(epoch_to_mpl(now), epoch_to_mpl(now - 10))

        self.bar = self.figure.add_subplot(gs[1])
        norm = Normalize(vmin=-50, vmax=0)
        self.barBase = ColorbarBase(self.bar, norm=norm,
                                    cmap=cm.get_cmap('jet'))
        self.barBase.set_label('Level (dB)')

    def scale_plot(self):
        with self.lock:
            if self.settings.autoScale:
                self.axes.set_ylim(auto=True)
                self.axes.set_xlim(auto=True)
                self.settings.yMin, self.settings.yMax = self.plot.get_clim()
            else:
                self.axes.set_ylim(auto=False)
                self.axes.set_xlim(auto=False)
                self.plot.set_clim(self.settings.yMin, self.settings.yMax)

        vmin, vmax = self.plot.get_clim()
        self.barBase.set_clim(vmin, vmax)
        self.barBase.draw_all()

    def redraw_plot(self):
        self.graph.get_figure().tight_layout()
        if os.name == "nt":
            thread = Thread(target=thread_plot, args=(self.graph, self.lock,))
            thread.start()
        else:
            wx.PostEvent(self.notify, EventThreadStatus(Event.DRAW))

    def set_plot(self, plot, _annotate):
        total = len(plot)

        if total > 0:
            firstPlot = plot.items()[0]
            timeMin = firstPlot[0]
            timeMax = plot.items()[len(plot) - 1][0]
            xMin = min(firstPlot[1])
            xMax = max(firstPlot[1])
            if total == 1:
                timeMax += 1
            extent = [xMin, xMax,
                      epoch_to_mpl(timeMax), epoch_to_mpl(timeMin)]
            width = len(firstPlot[1])

            c = np.ma.masked_all((self.settings.retainMax, width))
            self.clear_plots()
            with self.lock:
                j = self.settings.retainMax
                for ys in reversed(plot):
                    j -= 1
                    _xs, zs = split_spectrum(plot[ys])
                    for i in range(len(zs)):
                        c[j, i] = zs[i]

                self.plot = self.axes.imshow(c, aspect='auto',
                                             extent=extent,
                                             cmap=cm.get_cmap('jet'),
                                             gid="plot")
                self.axes.grid(self.grid)

            self.scale_plot()
            self.redraw_plot()

    def annotate_plot(self):
        pass

    def clear_plots(self):
        with self.lock:
            children = self.axes.get_children()
            for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == "plot":
                        child.remove()

    def set_grid(self, on):
        self.grid = on
        self.axes.grid(on)
        self.redraw_plot()

    def close(self):
        self.figure.clear()


def thread_plot(graph, lock):
    with lock:
        graph.get_canvas().draw()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
