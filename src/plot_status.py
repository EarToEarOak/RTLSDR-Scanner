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
import threading

from matplotlib.table import Table

from events import post_event, EventThread, Event
from misc import format_time, format_precision
from utils_mpl import find_artists, set_table_colour


class PlotterStatus(object):
    def __init__(self, notify, figure, settings):
        self.notify = notify
        self.figure = figure
        self.settings = settings
        self.axes = None
        self.threadPlot = None

        self.__setup_plot()
        self.set_grid(self.settings.grid)

    def __setup_plot(self):
        self.axes = self.figure.add_subplot(111)
        self.axes.set_axis_off()
        self.axes.annotate('No data', (0.5, 0.5),
                           textcoords='figure fraction',
                           fontsize='large',
                           ha='center', va='center',
                           gid='noData')

    def draw_measure(self, _measure, _show):
        pass

    def hide_measure(self):
        pass

    def scale_plot(self, _force=False):
        pass

    def redraw_plot(self):
        if self.figure is not None:
            post_event(self.notify, EventThread(Event.DRAW))

    def get_axes(self):
        return None

    def get_axes_bar(self):
        return None

    def get_plot_thread(self):
        return self.threadPlot

    def set_title(self, title):
        self.axes.set_title(title, fontsize='medium')

    def set_plot(self, spectrum, extent, _annotate=False):
        self.threadPlot = ThreadPlot(self, self.settings, self.axes,
                                     spectrum, extent)
        self.threadPlot.start()

        return self.threadPlot

    def clear_plots(self):
        table = find_artists(self.figure, 'table')
        if table:
            table[0].remove()
        noData = find_artists(self.figure, 'noData')
        noData[0].set_alpha(1)

    def set_grid(self, on):
        table = find_artists(self.axes, 'table')
        if len(table):
            if on:
                colour = 'LightGray'
            else:
                colour = 'w'
            set_table_colour(table[0], colour)
            self.redraw_plot()

    def set_bar(self, _on):
        pass

    def set_axes(self, _on):
        pass

    def set_colourmap_use(self, _on):
        pass

    def set_colourmap(self, _colourMap):
        pass

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
        self.parent.clear_plots()
        if self.data is None:
            self.parent.threadPlot = None
            return

        tMin = format_time(self.extent.tMin, True)
        tMax = format_time(self.extent.tMax, True)
        fMin = format_precision(self.settings, freq=self.extent.fMin,
                                fancyUnits=True)
        fMax = format_precision(self.settings, freq=self.extent.fMax,
                                fancyUnits=True)
        lMin = format_precision(self.settings, level=self.extent.lMin,
                                fancyUnits=True)
        lMax = format_precision(self.settings, level=self.extent.lMax,
                                fancyUnits=True)
        peak = self.extent.get_peak_flt()
        peakF = format_precision(self.settings, freq=peak[0],
                                 fancyUnits=True)
        peakL = format_precision(self.settings, level=peak[1],
                                 fancyUnits=True)
        peakT = format_time(peak[2], True)

        text = [['Sweeps', '', len(self.data)],
                ['Extents', '', ''],
                ['', 'Start', tMin],
                ['', 'End', tMax],
                ['', 'Min frequency', fMin],
                ['', 'Max frequency', fMax],
                ['', 'Min level', lMin],
                ['', 'Max level', lMax],
                ['Peak', '', ''],
                ['', 'Level', peakL],
                ['', 'Frequency', peakF],
                ['', 'Time', peakT],
                ]

        table = Table(self.axes, loc='center', gid='table')

        rows = len(text)
        cols = len(text[0])
        for row in xrange(rows):
            for col in xrange(cols):
                table.add_cell(row, col,
                               text=text[row][col],
                               width=1.0 / cols, height=1.0 / rows)

        if self.settings.grid:
            colour = 'LightGray'
        else:
            colour = 'w'
        set_table_colour(table, colour)

        for i in range(3):
            table.auto_set_column_width(i)

        self.axes.add_table(table)
        noData = find_artists(self.axes, 'noData')
        noData[0].set_alpha(0)
        self.parent.redraw_plot()

        self.parent.threadPlot = None


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
