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

from matplotlib.ticker import ScalarFormatter, AutoMinorLocator
import wx

from events import EventThreadStatus, Event
from misc import split_spectrum


class Plotter():
    def __init__(self, notify, graph, settings, grid, lock):
        self.notify = notify
        self.settings = settings
        self.graph = graph
        self.lock = lock
        self.axes = None
        self.currentPlot = None
        self.lastPlot = None
        self.setup_plot()
        self.set_grid(grid)
        self.redraw()

    def setup_plot(self):
        self.axes = self.graph.get_figure().add_subplot(111)
        self.create_plot()

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

    def create_plot(self):
        with self.lock:
            self.lastPlot = self.currentPlot
            self.currentPlot, = self.axes.plot([], [], linewidth=0.4,
                                               color='b', alpha=1, gid="plot")

    def redraw(self):
        self.graph.get_figure().tight_layout()
        if os.name == "nt":
            thread = Thread(target=thread_plot, args=(self.graph, self.lock,))
            thread.start()
        else:
            wx.PostEvent(self.notify, EventThreadStatus(Event.DRAW))

    def set_plot(self, plot):
        if len(plot) > 0:
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

        self.create_plot()

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
        self.redraw()

    def clear_plots(self):
        with self.lock:
            children = self.axes.get_children()
            for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == "plot" or child.get_gid() == "peak":
                        child.remove()

        self.create_plot()
        self.lastPlot = None

    def set_grid(self, on):
        self.axes.grid(on)
        self.redraw()


def thread_plot(graph, lock):
    with lock:
        graph.get_canvas().draw()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
