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

import os
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
from misc import Extent


class Plotter():
    def __init__(self, notify, graph, settings, grid, lock):
        self.notify = notify
        self.settings = settings
        self.graph = graph
        self.average = settings.average
        self.lock = lock
        self.figure = self.graph.get_figure()
        self.axes = None
        self.bar = None
        self.threadPlot = None
        self.extent = None
        self.setup_plot()
        self.set_grid(grid)

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
                    self.axes.set_xlim(self.extent.get_x())
                if self.settings.autoL or force:
                    self.axes.set_ylim(self.extent.get_z())
                    self.barBase.set_clim(self.extent.get_z())
                    norm = Normalize(vmin=self.extent.get_z()[0],
                                     vmax=self.extent.get_z()[1])
                    for collection in self.axes.collections:
                        collection.set_norm(norm)
                    try:
                        self.barBase.draw_all()
                    except:
                        pass

    def redraw_plot(self):
        if self.figure is not None:
            if os.name == "nt":
                threading.Thread(target=self.thread_draw, name='Draw').start()
            else:
                post_event(self.notify, EventThreadStatus(Event.DRAW))

    def set_title(self, title):
        self.axes.set_title(title)

    def set_plot(self, data, annotate=False):
        if self.threadPlot is not None and self.threadPlot.isAlive():
            self.threadPlot.cancel()
            self.threadPlot.join()

        self.threadPlot = ThreadPlot(self, self.lock, self.axes, data,
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

    def thread_draw(self):
        with self.lock:
            if self.figure is not None:
                try:
                    self.graph.get_figure().tight_layout()
                    self.graph.get_canvas().draw()
                except:
                    pass


class ThreadPlot(threading.Thread):
    def __init__(self, parent, lock, axes, data, colourMap, autoL, lineWidth,
                 barBase, fade, annotate, average):
        threading.Thread.__init__(self)
        self.name = "Plot"
        self.parent = parent
        self.lock = lock
        self.axes = axes
        self.data = data
        self.colourMap = colourMap
        self.autoL = autoL
        self.lineWidth = lineWidth
        self.barBase = barBase
        self.annotate = annotate
        self.fade = fade
        self.average = average
        self.abort = False

    def run(self):
        peakX = None
        peakY = None

        with self.lock:
            if self.abort:
                return
            total = len(self.data)
            if total > 0:
                self.parent.clear_plots()
                extent = Extent()
                lc = None
                if self.average:
                    avg = {}
                    count = len(self.data)

                    for timeStamp in sorted(self.data):
                        if self.abort:
                            return

                        if len(self.data[timeStamp]) < 2:
                            return

                        for x, y in self.data[timeStamp].items():
                            if x in avg:
                                avg[x] = (avg[x] + y) / 2
                            else:
                                avg[x] = y

                    extent.update_from_2d(avg)
                    self.parent.extent = extent

                    data = sorted(avg.items())
                    peakX, peakY = max(data, key=lambda item: item[1])

                    segments = self.create_segments(data)
                    lc = LineCollection(segments)
                    lc.set_array(numpy.array([x[1] for x in data]))
                    lc.set_norm(self.get_norm(self.autoL, extent))
                    lc.set_cmap(self.colourMap)
                    lc.set_linewidth(self.lineWidth)
                    lc.set_gid('plot')
                    self.axes.add_collection(lc)
                    self.parent.lc = lc
                else:
                    count = 1.0
                    for timeStamp in sorted(self.data):
                        if self.abort:
                            return

                        if len(self.data[timeStamp]) < 2:
                            return

                        if self.fade:
                            alpha = count / total
                        else:
                            alpha = 1

                        extent.update_from_2d(self.data[timeStamp])
                        self.parent.extent = extent

                        data = sorted(self.data[timeStamp].items())
                        peakX, peakY = max(data, key=lambda item: item[1])

                        segments = self.create_segments(data)
                        lc = LineCollection(segments)
                        lc.set_array(numpy.array([x[1] for x in data]))
                        lc.set_norm(self.get_norm(self.autoL, extent))
                        lc.set_cmap(self.colourMap)
                        lc.set_linewidth(self.lineWidth)
                        lc.set_gid('plot')
                        lc.set_alpha(alpha)
                        self.axes.add_collection(lc)
                        count += 1

                if self.annotate:
                    self.annotate_plot(peakX, peakY)

        if total > 0:
            self.parent.scale_plot()
            self.parent.redraw_plot()

    def create_segments(self, points):
        segments = []

        prev = points[0]
        for point in points:
            segment = [prev, point]
            segments.append(segment)
            prev = point

        return segments

    def get_norm(self, autoL, extent):
        if autoL:
            vmin, vmax = self.barBase.get_clim()
        else:
            zExtent = extent.get_z()
            vmin = zExtent[0]
            vmax = zExtent[1]

        return Normalize(vmin=vmin, vmax=vmax)

    def annotate_plot(self, x, y):
        self.clear_markers()

        start, stop = self.axes.get_xlim()
        textX = ((stop - start) / 50.0) + x

        if(matplotlib.__version__ < '1.3'):
            self.axes.annotate('{0:.6f}MHz\n{1:.2f}dB'.format(x, y),
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
            self.axes.annotate('{0:.6f}MHz\n{1:.2f}dB'.format(x, y),
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
