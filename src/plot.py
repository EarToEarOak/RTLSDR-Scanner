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

from collections import OrderedDict
import threading

from matplotlib import patheffects, cm
import matplotlib
from matplotlib.collections import LineCollection
from matplotlib.colorbar import ColorbarBase
from matplotlib.colors import Normalize
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator
import numpy

from events import EventThreadStatus, Event, post_event


class Plotter():
    def __init__(self, notify, figure, settings, lock):
        self.notify = notify
        self.figure = figure
        self.settings = settings
        self.average = settings.average
        self.lock = lock
        self.axes = None
        self.bar = None
        self.threadPlot = None
        self.extent = None
        self.setup_plot()
        self.set_grid(self.settings.grid)

    def setup_plot(self):
        formatter = ScalarFormatter(useOffset=False)

        gs = GridSpec(1, 2, width_ratios=[9.5, 0.5])

        self.axes = self.figure.add_subplot(gs[0],
                                            axisbg=self.settings.background)
        self.axes.set_xlabel("Frequency (MHz)")
        self.axes.set_ylabel('Level (dB)')
        self.axes.xaxis.set_major_formatter(formatter)
        self.axes.yaxis.set_major_formatter(formatter)
        self.axes.xaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.yaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.set_xlim(self.settings.start, self.settings.stop)
        self.axes.set_ylim(-50, 0)

        self.bar = self.figure.add_subplot(gs[1])
        norm = Normalize(vmin=-50, vmax=0)
        self.barBase = ColorbarBase(self.bar, norm=norm,
                                    cmap=cm.get_cmap(self.settings.colourMap))
        self.barBase.set_label('Level (dB)')

    def scale_plot(self, force=False):
        if self.extent is not None:
            with self.lock:
                if self.settings.autoF or force:
                    self.axes.set_xlim(self.extent.get_f())
                if self.settings.autoL or force:
                    self.axes.set_ylim(self.extent.get_l())
                    self.barBase.set_clim(self.extent.get_l())
                    norm = Normalize(vmin=self.extent.get_l()[0],
                                     vmax=self.extent.get_l()[1])
                    for collection in self.axes.collections:
                        collection.set_norm(norm)
                    try:
                        self.barBase.draw_all()
                    except:
                        pass

    def redraw_plot(self):
        if self.figure is not None:
            post_event(self.notify, EventThreadStatus(Event.DRAW))

    def get_axes(self):
        return self.axes

    def set_title(self, title):
        self.axes.set_title(title)

    def set_plot(self, spectrum, extent, annotate=False):
        if self.threadPlot is not None and self.threadPlot.isAlive():
            self.threadPlot.cancel()
            self.threadPlot.join()

        self.extent = extent
        self.threadPlot = ThreadPlot(self, self.lock, self.axes, spectrum,
                                     self.extent,
                                     self.settings.colourMap,
                                     self.settings.autoL,
                                     self.settings.lineWidth,
                                     self.barBase,
                                     self.settings.fadeScans,
                                     annotate, self.settings.average).start()

    def clear_plots(self):
        children = self.axes.get_children()
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() == "plot" or child.get_gid() == "peak":
                    child.remove()

    def set_grid(self, on):
        self.axes.grid(on)
        self.redraw_plot()

    def set_colourmap(self, colourMap):
        for collection in self.axes.collections:
            collection.set_cmap(colourMap)
        self.barBase.set_cmap(colourMap)
        try:
            self.barBase.draw_all()
        except:
            pass

    def close(self):
        self.figure.clear()
        self.figure = None


class ThreadPlot(threading.Thread):
    def __init__(self, parent, lock, axes, data, extent,
                 colourMap, autoL, lineWidth,
                 barBase, fade, annotate, average):
        threading.Thread.__init__(self)
        self.name = "Plot"
        self.parent = parent
        self.lock = lock
        self.axes = axes
        self.data = data
        self.extent = extent
        self.colourMap = colourMap
        self.autoL = autoL
        self.lineWidth = lineWidth
        self.barBase = barBase
        self.annotate = annotate
        self.fade = fade
        self.average = average
        self.abort = False

    def run(self):
        peakF = None
        peakL = None

        with self.lock:
            if self.abort:
                return
            total = len(self.data)
            if total > 0:
                self.parent.clear_plots()
                lc = None
                if self.average:
                    avg = OrderedDict()
                    count = len(self.data)

                    for timeStamp in self.data:
                        if self.abort:
                            return

                        if len(self.data[timeStamp]) < 2:
                            return

                        for x, y in self.data[timeStamp].items():
                            if x in avg:
                                avg[x] = (avg[x] + y) / 2
                            else:
                                avg[x] = y

                    data = avg.items()
                    peakF, peakL = max(data, key=lambda item: item[1])

                    segments, levels = self.create_segments(data)
                    lc = LineCollection(segments)
                    lc.set_array(numpy.array(levels))
                    lc.set_norm(self.get_norm(self.autoL, self.extent))
                    lc.set_cmap(self.colourMap)
                    lc.set_linewidth(self.lineWidth)
                    lc.set_gid('plot')
                    self.axes.add_collection(lc)
                    self.parent.lc = lc
                else:
                    count = 0.0
                    for timeStamp in self.data:
                        if self.abort:
                            return

                        if len(self.data[timeStamp]) < 2:
                            return

                        if self.fade:
                            alpha = (total - count) / total
                        else:
                            alpha = 1

                        data = self.data[timeStamp].items()
                        peakF, peakL = self.extent.get_peak_fl()

                        segments, levels = self.create_segments(data)
                        lc = LineCollection(segments)
                        lc.set_array(numpy.array(levels))
                        lc.set_norm(self.get_norm(self.autoL, self.extent))
                        lc.set_cmap(self.colourMap)
                        lc.set_linewidth(self.lineWidth)
                        lc.set_gid('plot')
                        lc.set_alpha(alpha)
                        self.axes.add_collection(lc)
                        count += 1

                if self.annotate:
                    self.annotate_plot(peakF, peakL)

        if total > 0:
            self.parent.scale_plot()
            self.parent.redraw_plot()

    def create_segments(self, points):
        segments = []
        levels = []

        prev = points[0]
        for point in points:
            segment = [prev, point]
            segments.append(segment)
            levels.append((point[1] + prev[1]) / 2.0)
            prev = point

        return segments, levels

    def get_norm(self, autoL, extent):
        if autoL:
            vmin, vmax = self.barBase.get_clim()
        else:
            yExtent = extent.get_l()
            vmin = yExtent[0]
            vmax = yExtent[1]

        return Normalize(vmin=vmin, vmax=vmax)

    def annotate_plot(self, x, y):
        self.clear_markers()

        start, stop = self.axes.get_xlim()
        textX = ((stop - start) / 50.0) + x

        if(matplotlib.__version__ < '1.3'):
            self.axes.annotate('{0:.6f} MHz\n{1:.2f} dB'.format(x, y),
                               xy=(x, y), xytext=(textX, y),
                               ha='left', va='top', size='small',
                               gid='peak')
            self.axes.plot(x, y, marker='x', markersize=10, color='w',
                           mew=3, gid='peak')
            self.axes.plot(x, y, marker='x', markersize=10, color='r',
                           gid='peak')
        else:
            effect = patheffects.withStroke(linewidth=3, foreground="w",
                                            alpha=0.75)
            self.axes.annotate('{0:.6f} MHz\n{1:.2f} dB'.format(x, y),
                               xy=(x, y), xytext=(textX, y),
                               ha='left', va='top', size='small',
                               path_effects=[effect], gid='peak')
            self.axes.plot(x, y, marker='x', markersize=10, color='r',
                           path_effects=[effect], gid='peak')

    def get_plots(self):
        plots = []
        children = self.axes.get_children()
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() == "plot":
                    plots.append(child)

        return plots

    def clear_markers(self):
        children = self.axes.get_children()
        for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == 'peak':
                        child.remove()

    def cancel(self):
        self.abort = True


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
