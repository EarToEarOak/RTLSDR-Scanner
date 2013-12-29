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
import numpy
import wx

from events import EventThreadStatus, Event
from misc import split_spectrum


class Plotter():
    def __init__(self, notify, graph, settings, grid, lock):
        self.notify = notify
        self.settings = settings
        self.graph = graph
        self.lock = lock
        self.figure = self.graph.get_figure()
        self.axes = None
        self.currentPlot = None
        self.setup_plot()
        self.set_grid(grid)
        self.redraw_plot()

    def setup_plot(self):
        self.axes = self.figure.add_subplot(111)

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

    def scale_plot(self, force=False):
        with self.lock:
            if self.settings.autoScale or force:
                self.axes.set_ylim(auto=True)
                self.axes.set_xlim(auto=True)
                self.axes.relim()
                self.axes.autoscale_view()
                self.settings.yMin, self.settings.yMax = self.axes.get_ylim()
            else:
                self.axes.set_ylim(auto=False)
                self.axes.set_xlim(auto=False)
                self.axes.set_ylim(self.settings.yMin, self.settings.yMax)

    def redraw_plot(self):
        self.graph.get_figure().tight_layout()
        if os.name == "nt":
            thread = Thread(target=thread_plot, args=(self.graph, self.lock,))
            thread.start()
        else:
            wx.PostEvent(self.notify, EventThreadStatus(Event.DRAW))

    def set_plot(self, plot, annotate=False):
        total = len(plot)
        if total > 0:
            self.clear_plots()
            count = 1.0
            with self.lock:
                for timeStamp in sorted(plot):
                    xs, ys = split_spectrum(plot[timeStamp])
                    alpha = count / total
                    self.axes.plot(xs, ys, linewidth=0.4, gid="plot",
                                   color='b', alpha=alpha)
                    count += 1

                self.axes.relim()
                self.axes.autoscale_view()
            self.scale_plot()
            if annotate:
                self.annotate_plot()
            self.redraw_plot()

    def get_plots(self):
        plots = []
        with self.lock:
            children = self.axes.get_children()
            for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == "plot":
                        plots.append(child)

        return plots

    def annotate_plot(self):
        self.clear_markers()

        plots = self.get_plots()
        with self.lock:
            if len(plots) == 1:
                plot = plots[0]
            else:
                plot = plots[len(plots) - 2]
            xData, yData = plot.get_data()
            pos = numpy.argmax(yData)
            x = xData[pos]
            y = yData[pos]

        start, stop = self.axes.get_xlim()
        textX = ((stop - start) / 50.0) + x
        self.axes.annotate('{0:.3f}MHz\n{1:.2f}dB'.format(x, y),
                           xy=(x, y), xytext=(textX, y),
                           ha='left', va='top', size='small', gid='peak')
        self.axes.plot(x, y, marker='x', markersize=10, color='r',
                       gid='peak')
        self.redraw_plot()
        pass

    def clear_plots(self):
        with self.lock:
            children = self.axes.get_children()
            for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == "plot" or child.get_gid() == "peak":
                        child.remove()

    def clear_markers(self):
        with self.lock:
            children = self.axes.get_children()
            for child in children:
                    if child.get_gid() is not None:
                        if child.get_gid() == 'peak':
                            child.remove()

    def set_grid(self, on):
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
