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
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator
import numpy

from constants import Markers
from events import EventThread, Event, post_event
from misc import format_time, format_precision
from spectrum import split_spectrum, Measure
from utils_mpl import utc_to_mpl


class Spectrogram(object):
    def __init__(self, notify, figure, settings):
        self.notify = notify
        self.figure = figure
        self.settings = settings
        self.data = [[], [], []]
        self.axes = None
        self.plot = None
        self.extent = None
        self.bar = None
        self.barBase = None
        self.lines = {}
        self.labels = {}
        self.overflowLabels = {}
        self.overflow = {'left': [],
                         'right': []}

        self.threadPlot = None
        self.__setup_plot()
        self.set_grid(self.settings.grid)

    def __setup_plot(self):
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
        self.axes.set_ylim(utc_to_mpl(now), utc_to_mpl(now - 10))

        self.bar = self.figure.add_subplot(gs[1])
        norm = Normalize(vmin=-50, vmax=0)
        self.barBase = ColorbarBase(self.bar, norm=norm,
                                    cmap=cm.get_cmap(self.settings.colourMap))

        self.__setup_measure()
        self.__setup_overflow()
        self.hide_measure()

    def __setup_measure(self):
        dashesHalf = [1, 5, 5, 5, 5, 5]
        self.lines[Markers.HFS] = Line2D([0, 0], [0, 0], dashes=dashesHalf,
                                         color='purple')
        self.lines[Markers.HFE] = Line2D([0, 0], [0, 0], dashes=dashesHalf,
                                         color='purple')
        self.lines[Markers.OFS] = Line2D([0, 0], [0, 0], dashes=dashesHalf,
                                         color='#996600')
        self.lines[Markers.OFE] = Line2D([0, 0], [0, 0], dashes=dashesHalf,
                                         color='#996600')
        if matplotlib.__version__ >= '1.3':
            effect = patheffects.withStroke(linewidth=3, foreground="w",
                                            alpha=0.75)
            self.lines[Markers.HFS].set_path_effects([effect])
            self.lines[Markers.HFE].set_path_effects([effect])
            self.lines[Markers.OFS].set_path_effects([effect])
            self.lines[Markers.OFE].set_path_effects([effect])

        for line in self.lines.itervalues():
            self.axes.add_line(line)

        bbox = self.axes.bbox
        box = dict(boxstyle='round', fc='white', ec='purple', clip_box=bbox)
        self.labels[Markers.HFS] = Text(0, 0, '-3dB', fontsize='xx-small',
                                        ha="center", va="top", bbox=box,
                                        color='purple')
        self.labels[Markers.HFE] = Text(0, 0, '-3dB', fontsize='xx-small',
                                        ha="center", va="top", bbox=box,
                                        color='purple')
        box['ec'] = '#996600'
        self.labels[Markers.OFS] = Text(0, 0, 'OBW', fontsize='xx-small',
                                        ha="center", va="top", bbox=box,
                                        color='#996600')
        self.labels[Markers.OFE] = Text(0, 0, 'OBW', fontsize='xx-small',
                                        ha="center", va="top", bbox=box,
                                        color='#996600')

        for label in self.labels.itervalues():
            self.axes.add_artist(label)

    def __setup_overflow(self):
        bbox = self.axes.bbox
        box = dict(boxstyle='round', fc='white', ec='black', alpha=0.5,
                   clip_box=bbox)
        self.overflowLabels['left'] = Text(0, 0.9, '', fontsize='xx-small',
                                           ha="left", va="top", bbox=box,
                                           transform=self.axes.transAxes,
                                           alpha=0.5)
        self.overflowLabels['right'] = Text(1, 0.9, '', fontsize='xx-small',
                                            ha="right", va="top", bbox=box,
                                            transform=self.axes.transAxes,
                                            alpha=0.5)

        for label in self.overflowLabels.itervalues():
            self.axes.add_artist(label)

    def __clear_overflow(self):
        for label in self.overflowLabels:
            self.overflow[label] = []

    def __draw_vline(self, marker, x):
        line = self.lines[marker]
        label = self.labels[marker]
        yLim = self.axes.get_ylim()
        xLim = self.axes.get_xlim()
        if xLim[0] < x < xLim[1]:
            line.set_visible(True)
            line.set_xdata([x, x])
            line.set_ydata([yLim[0], yLim[1]])
            self.axes.draw_artist(line)
            label.set_visible(True)
            label.set_position((x, yLim[1]))
            self.axes.draw_artist(label)
        elif x is not None and x < xLim[0]:
            self.overflow['left'].append(marker)
        elif x is not None and x > xLim[1]:
            self.overflow['right'].append(marker)

    def __draw_overflow(self):
        for pos, overflow in self.overflow.iteritems():
            if len(overflow) > 0:
                text = ''
                for measure in overflow:
                    if len(text) > 0:
                        text += '\n'
                    text += self.labels[measure].get_text()

                label = self.overflowLabels[pos]
                if pos == 'left':
                    textMath = '$\\blacktriangleleft$\n' + text
                elif pos == 'right':
                    textMath = '$\\blacktriangleright$\n' + text

                label.set_text(textMath)
                label.set_visible(True)
                self.axes.draw_artist(label)

    def draw_measure(self, measure, show):
        if self.axes.get_renderer_cache() is None:
            return

        self.hide_measure()
        self.__clear_overflow()

        if show[Measure.HBW]:
            xStart, xEnd, _y = measure.get_hpw()
            self.__draw_vline(Markers.HFS, xStart)
            self.__draw_vline(Markers.HFE, xEnd)

        if show[Measure.OBW]:
            xStart, xEnd, _y = measure.get_obw()
            self.__draw_vline(Markers.OFS, xStart)
            self.__draw_vline(Markers.OFE, xEnd)

        self.__draw_overflow()

    def hide_measure(self):
        for line in self.lines.itervalues():
            line.set_visible(False)
        for label in self.labels.itervalues():
            label.set_visible(False)
        for label in self.overflowLabels.itervalues():
            label.set_visible(False)

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
            post_event(self.notify, EventThread(Event.DRAW))

    def get_axes(self):
        return self.axes

    def get_axes_bar(self):
        return self.barBase.ax

    def get_plot_thread(self):
        return self.threadPlot

    def set_title(self, title):
        self.axes.set_title(title, fontsize='medium')

    def set_plot(self, spectrum, extent, annotate=False):
        self.extent = extent
        self.threadPlot = ThreadPlot(self, self.settings,
                                     self.axes,
                                     spectrum,
                                     self.extent,
                                     self.barBase,
                                     annotate)
        self.threadPlot.start()

    def clear_plots(self):
        children = self.axes.get_children()
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() == "plot_line" or child.get_gid() == "peak":
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
    def __init__(self, parent, settings, axes, data, extent,
                 barBase, annotate):
        threading.Thread.__init__(self)
        self.name = "Plot"
        self.parent = parent
        self.settings = settings
        self.axes = axes
        self.data = data
        self.extent = extent
        self.barBase = barBase
        self.annotate = annotate

    def run(self):
        if self.data is None:
            self.parent.threadPlot = None
            return

        total = len(self.data)
        if total > 0:
            width = len(self.data[min(self.data)])
            height = len(self.data)
            c = numpy.ma.masked_all((height, width))
            self.parent.clear_plots()
            j = height
            for ys in self.data:
                j -= 1
                _xs, zs = split_spectrum(self.data[ys])
                for i in range(len(zs)):
                    try:
                        c[j, i] = zs[i]
                    except IndexError:
                        continue

            norm = None
            if not self.settings.autoL:
                minY, maxY = self.barBase.get_clim()
                norm = Normalize(vmin=minY, vmax=maxY)

            extent = self.extent.get_ft()
            self.parent.plot = self.axes.imshow(c, aspect='auto',
                                                extent=extent,
                                                norm=norm,
                                                cmap=cm.get_cmap(self.settings.colourMap),
                                                interpolation='spline16',
                                                gid="plot_line")

            if self.annotate:
                self.__annotate_plot()

            self.parent.scale_plot()
            self.parent.redraw_plot()

        self.parent.threadPlot = None

    def __annotate_plot(self):
        self.__clear_markers()
        fMax, lMax, tMax = self.extent.get_peak_flt()
        y = utc_to_mpl(tMax)

        start, stop = self.axes.get_xlim()
        textX = ((stop - start) / 50.0) + fMax
        when = format_time(tMax)

        text = '{}\n{}\n{when}'.format(*format_precision(self.settings, fMax, lMax,
                                                         fancyUnits=True),
                                       when=when)
        if matplotlib.__version__ < '1.3':
            self.axes.annotate(text,
                               xy=(fMax, y), xytext=(textX, y),
                               ha='left', va='bottom', size='x-small',
                               color='w', gid='peak')
            self.axes.plot(fMax, y, marker='x', markersize=10, color='w',
                           mew=3, gid='peak')
            self.axes.plot(fMax, y, marker='x', markersize=10, color='r',
                           gid='peak')
        else:
            effect = patheffects.withStroke(linewidth=2, foreground="w",
                                            alpha=0.75)
            self.axes.annotate(text,
                               xy=(fMax, y), xytext=(textX, y),
                               ha='left', va='bottom', size='x-small',
                               path_effects=[effect], gid='peak')
            self.axes.plot(fMax, y, marker='x', markersize=10, color='r',
                           path_effects=[effect], gid='peak')

    def __clear_markers(self):
        children = self.axes.get_children()
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() == 'peak':
                    child.remove()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
