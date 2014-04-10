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
import time

from matplotlib import cm, patheffects
import matplotlib
from matplotlib.colorbar import ColorbarBase
from matplotlib.colors import Normalize
from matplotlib.dates import DateFormatter
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator
import numpy

from events import EventThreadStatus, Event, post_event
from misc import format_time
from spectrum import epoch_to_mpl, split_spectrum


class Spectrogram:
    def __init__(self, notify, figure, settings):
        self.notify = notify
        self.figure = figure
        self.settings = settings
        self.data = [[], [], []]
        self.index = 0
        self.axes = None
        self.plot = None
        self.extent = None
        self.threadPlot = None
        self.setup_plot()
        self.set_grid(self.settings.grid)

    def setup_plot(self):
        gs = GridSpec(1, 2, width_ratios=[9.5, 0.5])
        self.axes = self.figure.add_subplot(gs[0],
                                            axisbg=self.settings.background)

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
                                    cmap=cm.get_cmap(self.settings.colourMap))
        self.barBase.set_label('Level (dB)')

    def draw_measure(self, *args):
        pass

    def hide_measure(self):
        pass

    def scale_plot(self, force=False):
        if self.figure is not None and self.plot is not None:
            extent = self.plot.get_extent()
            if self.settings.autoF or force:
                if extent[0] == extent[1]:
                    extent[1] += 1
                self.axes.set_xlim(extent[0], extent[1])
            if self.settings.autoL or force:
                vmin, vmax = self.plot.get_clim()
                self.barBase.set_clim(vmin, vmax)
                try:
                    self.barBase.draw_all()
                except:
                    pass
            if self.settings.autoT or force:
                self.axes.set_ylim(extent[2], extent[3])

    def redraw_plot(self):
        if self.figure is not None:
            post_event(self.notify, EventThreadStatus(Event.DRAW))

    def get_axes(self):
        return self.axes

    def get_plot_thread(self):
        return self.threadPlot

    def set_title(self, title):
        self.axes.set_title(title)

    def set_plot(self, data, extent, annotate=False):
        self.extent = extent
        self.threadPlot = ThreadPlot(self, self.axes,
                                     data, self.extent,
                                     self.settings.retainMax,
                                     self.settings.colourMap,
                                     self.settings.autoL,
                                     self.barBase,
                                     annotate)
        self.threadPlot.start()

    def clear_plots(self):
        children = self.axes.get_children()
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() == "plot" or child.get_gid() == "peak":
                    child.remove()

    def set_grid(self, on):
        if on:
            self.axes.grid(True, color='w')
        else:
            self.axes.grid(False)
        self.redraw_plot()

    def set_colourmap(self, colourMap):
        if self.plot is not None:
            self.plot.set_cmap(colourMap)
        self.barBase.set_cmap(colourMap)
        try:
            self.barBase.draw_all()
        except:
            pass

    def close(self):
        self.figure.clear()
        self.figure = None


class ThreadPlot(threading.Thread):
    def __init__(self, parent, axes, data, extent, retainMax, colourMap,
                 autoL, barBase, annotate):
        threading.Thread.__init__(self)
        self.name = "Plot"
        self.parent = parent
        self.axes = axes
        self.data = data
        self.extent = extent
        self.retainMax = retainMax
        self.colourMap = colourMap
        self.autoL = autoL
        self.barBase = barBase
        self.annotate = annotate

    def run(self):
        if self.data is None:
            self.parent.threadPlot = None
            return

        total = len(self.data)
        if total > 0:
            width = len(self.data[min(self.data)])
            c = numpy.ma.masked_all((self.retainMax, width))
            self.parent.clear_plots()
            j = self.retainMax
            for ys in self.data:
                j -= 1
                _xs, zs = split_spectrum(self.data[ys])
                for i in range(len(zs)):
                    c[j, i] = zs[i]

            norm = None
            if not self.autoL:
                minY, maxY = self.barBase.get_clim()
                norm = Normalize(vmin=minY, vmax=maxY)

            extent = self.extent.get_ft()
            self.parent.plot = self.axes.imshow(c, aspect='auto',
                                                extent=extent,
                                                norm=norm,
                                                cmap=cm.get_cmap(self.colourMap),
                                                interpolation='spline16',
                                                gid="plot")

            if self.annotate:
                self.annotate_plot()

        if total > 0:
            self.parent.scale_plot()
            self.parent.redraw_plot()

        self.parent.threadPlot = None

    def annotate_plot(self):

        self.clear_markers()
        fMax, lMax, tMax = self.extent.get_peak_flt()
        y = epoch_to_mpl(tMax)

        start, stop = self.axes.get_xlim()
        textX = ((stop - start) / 50.0) + fMax
        when = format_time(fMax)

        if(matplotlib.__version__ < '1.3'):
            self.axes.annotate('{0:.6f}MHz\n{1:.2f}dB\n{2}'.format(fMax,
                                                                   lMax,
                                                                   when),
                               xy=(fMax, y), xytext=(textX, y),
                               ha='left', va='bottom', size='small',
                               color='w', gid='peak')
            self.axes.plot(fMax, y, marker='x', markersize=10, color='w',
                           mew=3, gid='peak')
            self.axes.plot(fMax, y, marker='x', markersize=10, color='r',
                           gid='peak')
        else:
            effect = patheffects.withStroke(linewidth=3, foreground="w",
                                            alpha=0.75)
            self.axes.annotate('{0:.6f}MHz\n{1:.2f}dB\n{2}'.format(fMax,
                                                                   lMax,
                                                                   when),
                               xy=(fMax, y), xytext=(textX, y),
                               ha='left', va='bottom', size='small',
                               path_effects=[effect], gid='peak')
            self.axes.plot(fMax, y, marker='x', markersize=10, color='r',
                           path_effects=[effect], gid='peak')

    def clear_markers(self):
        children = self.axes.get_children()
        for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == 'peak':
                        child.remove()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
