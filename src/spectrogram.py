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
import time

from matplotlib import cm, patheffects
import matplotlib
from matplotlib.colorbar import ColorbarBase
from matplotlib.colors import Normalize
from matplotlib.dates import DateFormatter
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator

from events import EventThreadStatus, Event, post_event
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
        self.lock = lock
        self.axes = None
        self.plot = None
        self.threadPlot = None
        self.setup_plot()
        self.set_grid(grid)

    def setup_plot(self):
        gs = GridSpec(1, 2, width_ratios=[9.5, 0.5])
        self.axes = self.figure.add_subplot(gs[0])
        self.axes.set_axis_bgcolor('Gainsboro')

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

    def scale_plot(self, force=False):
        if self.figure is not None and self.plot is not None:
            with self.lock:
                if self.settings.autoScale or force:
                    extent = self.plot.get_extent()
                    self.axes.set_xlim(extent[0], extent[1])
                    self.axes.set_ylim(extent[2], extent[3])
                    self.settings.yMin, self.settings.yMax = self.plot.get_clim()
                else:
                    self.plot.norm.vmin = self.settings.yMin
                    self.plot.norm.vmax = self.settings.yMax

                vmin, vmax = self.plot.get_clim()
                self.barBase.set_clim(vmin, vmax)
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

        self.threadPlot = ThreadPlot(self, self.lock, self.axes,
                                     data, self.settings.retainMax,
                                     self.settings.colourMap,
                                     self.settings.autoScale,
                                     self.settings.yMin,
                                     self.settings.yMax,
                                     annotate).start()

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

    def thread_draw(self):
        with self.lock:
            if self.figure is not None:
                try:
                    self.graph.get_figure().tight_layout()
                    self.graph.get_canvas().draw()
                except:
                    pass


class ThreadPlot(threading.Thread):
    def __init__(self, parent, lock, axes, data, retainMax, colourMap,
                 autoScale, minZ, maxZ, annotate):
        threading.Thread.__init__(self)
        self.name = "Plot"
        self.parent = parent
        self.lock = lock
        self.axes = axes
        self.data = data
        self.retainMax = retainMax
        self.colourMap = colourMap
        self.autoScale = autoScale
        self.min = minZ
        self.max = maxZ
        self.annotate = annotate
        self.abort = False

    def run(self):
        with self.lock:
            if self.abort:
                return
            total = len(self.data)
            if total > 0:
                timeMin = min(self.data)
                timeMax = max(self.data)
                plotFirst = self.data[timeMin]
                if len(plotFirst) == 0:
                    return
                xMin = min(plotFirst)
                xMax = max(plotFirst)
                width = len(plotFirst)
                if total == 1:
                    timeMax += 1
                extent = [xMin, xMax,
                          epoch_to_mpl(timeMax), epoch_to_mpl(timeMin)]

                c = np.ma.masked_all((self.retainMax, width))
                self.parent.clear_plots()
                j = self.retainMax
                for ys in reversed(sorted(self.data)):
                    j -= 1
                    _xs, zs = split_spectrum(self.data[ys])
                    for i in range(len(zs)):
                        if self.abort:
                            return
                        c[j, i] = zs[i]

                norm = None
                if not self.autoScale:
                    norm = Normalize(vmin=self.min, vmax=self.max)

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

    def annotate_plot(self):
        times = self.data.keys()
        if len(times) > 1:
            times.sort()
            timeStamp = times[-2]
            plot = self.data[timeStamp]
        else:
            timeStamp = times[0]
            plot = self.data[timeStamp]

        self.clear_markers()
        xMax = max(plot, key=plot.get)
        yMax = plot[xMax]

        start, stop = self.axes.get_xlim()
        y = epoch_to_mpl(timeStamp)
        textX = ((stop - start) / 50.0) + xMax
        when = time.strftime('%H:%M:%S', time.localtime(timeStamp))

        if(matplotlib.__version__ < '1.3'):
            self.axes.annotate('{0:.6f}MHz\n{1:.2f}dB\n{2}'.format(xMax,
                                                                   yMax,
                                                                   when),
                               xy=(xMax, y), xytext=(textX, y),
                               ha='left', va='bottom', size='small',
                               color='w', gid='peak')
            self.axes.plot(xMax, y, marker='x', markersize=10, color='w',
                           mew=3, gid='peak')
            self.axes.plot(xMax, y, marker='x', markersize=10, color='r',
                           gid='peak')
        else:
            effect = patheffects.withStroke(linewidth=3, foreground="w",
                                            alpha=0.75)
            self.axes.annotate('{0:.6f}MHz\n{1:.2f}dB\n{2}'.format(xMax,
                                                                   yMax,
                                                                   when),
                               xy=(xMax, y), xytext=(textX, y),
                               ha='left', va='bottom', size='small',
                               path_effects=[effect], gid='peak')
            self.axes.plot(xMax, y, marker='x', markersize=10, color='r',
                           path_effects=[effect], gid='peak')

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
