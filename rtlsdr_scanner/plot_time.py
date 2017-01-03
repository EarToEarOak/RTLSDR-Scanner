#
# rtlsdr_scan
#
# http://eartoearoak.com/software/rtlsdr-scanner
#
# Copyright 2012 - 2015 Al Brown
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
import time

from matplotlib.ticker import ScalarFormatter, AutoMinorLocator

from rtlsdr_scanner.events import post_event, EventThread, Event
from rtlsdr_scanner.utils_mpl import utc_to_mpl, set_date_ticks


class PlotterTime(object):
    def __init__(self, notify, figure, settings):
        self.notify = notify
        self.figure = figure
        self.settings = settings
        self.plot = None
        self.axes = None
        self.threadPlot = None

        self.__setup_plot()
        self.set_grid(self.settings.grid)

    def __setup_plot(self):
        self.axes = self.figure.add_subplot(111)

        self.axes.set_xlabel("Time")
        self.axes.set_ylabel('Points')

        numFormatter = ScalarFormatter(useOffset=False)
        set_date_ticks(self.axes.xaxis, False)
        self.axes.yaxis.set_major_formatter(numFormatter)
        self.axes.yaxis.set_minor_locator(AutoMinorLocator(10))

        now = time.time()
        self.axes.set_xlim(utc_to_mpl(now), utc_to_mpl(now - 10))

    def draw_measure(self, _measure, _show):
        pass

    def hide_measure(self):
        pass

    def scale_plot(self, force=False):
        if self.figure is not None and self.plot is not None:
            if self.settings.autoT or force:
                times = self.plot[0].get_data()[0]
                tMin = min(times)
                tMax = max(times)
                if tMin == tMax:
                    tMax += utc_to_mpl(10)
                self.axes.set_xlim(tMin, tMax)
            if self.settings.autoL or force:
                self.axes.autoscale(True, 'y', True)

    def get_axes(self):
        return self.axes

    def get_axes_bar(self):
        return None

    def get_bar(self):
        return self.barBase

    def get_plot_thread(self):
        return self.threadPlot

    def set_title(self, title):
        self.axes.set_title(title, fontsize='medium')

    def set_plot(self, spectrum, extent, _annotate=False):
        self.threadPlot = ThreadPlot(self, self.settings, self.axes,
                                     spectrum, extent)
        self.threadPlot.start()

        return self.threadPlot

    def redraw_plot(self):
        if self.figure is not None:
            post_event(self.notify, EventThread(Event.DRAW))

    def clear_plots(self):
        set_date_ticks(self.axes.xaxis, False)
        children = self.axes.get_children()
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() == 'plot':
                    child.remove()

    def set_grid(self, on):
        self.axes.grid(on)
        self.redraw_plot()

    def set_axes(self, on):
        if on:
            self.axes.set_axis_on()
        else:
            self.axes.set_axis_off()

    def close(self):
        self.figure.clear()
        self.figure = None


class ThreadPlot(threading.Thread):
    def __init__(self, parent, settings, axes, data, extent):
        threading.Thread.__init__(self)
        self.name = "Plot"
        self.parent = parent
        self.settings = settings
        self.axes = axes
        self.data = data
        self.extent = extent

    def run(self):
        if self.data is None:
            self.parent.threadPlot = None
            return

        total = len(self.data)
        if total > 0:
            self.parent.clear_plots()

            xs = [utc_to_mpl(x) for x in self.data.keys()]
            ys = [len(sweep) for sweep in self.data.values()]

            self.parent.plot = self.axes.plot(xs, ys, 'bo', gid='plot')

            set_date_ticks(self.axes.xaxis)
            self.parent.scale_plot()
            self.parent.redraw_plot()

        self.parent.threadPlot = None


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
