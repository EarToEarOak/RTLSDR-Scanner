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
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator
import numpy

from constants import Markers
from events import EventThreadStatus, Event, post_event
from spectrum import Measure


class Plotter():
    def __init__(self, notify, figure, settings):
        self.notify = notify
        self.figure = figure
        self.settings = settings
        self.average = settings.average
        self.axes = None
        self.bar = None
        self.threadPlot = None
        self.extent = None
        self.lines = {}
        self.labels = {}
        self.overflowLabels = {}
        self.overflow = {'left': [],
                         'right': [],
                         'top': [],
                         'bottom': []}

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

        self.setup_measure()
        self.setup_overflow()
        self.hide_measure()

    def setup_measure(self):
        dashesAvg = [4, 5, 1, 5, 1, 5]
        dashesGM = [5, 5, 5, 5, 1, 5, 1, 5]
        dashesHalf = [1, 5, 5, 5, 5, 5]
        self.lines[Markers.MIN] = Line2D([0, 0], [0, 0], linestyle='--',
                                         color='black')
        self.lines[Markers.MAX] = Line2D([0, 0], [0, 0], linestyle='-.',
                                         color='black')
        self.lines[Markers.AVG] = Line2D([0, 0], [0, 0], dashes=dashesAvg,
                                         color='magenta')
        self.lines[Markers.GMEAN] = Line2D([0, 0], [0, 0], dashes=dashesGM,
                                           color='green')
        self.lines[Markers.HP] = Line2D([0, 0], [0, 0], dashes=dashesHalf,
                                        color='purple')
        self.lines[Markers.HFS] = Line2D([0, 0], [0, 0], dashes=dashesHalf,
                                         color='purple')
        self.lines[Markers.HFE] = Line2D([0, 0], [0, 0], dashes=dashesHalf,
                                         color='purple')
        self.lines[Markers.OP] = Line2D([0, 0], [0, 0], dashes=dashesHalf,
                                        color='#996600')
        self.lines[Markers.OFS] = Line2D([0, 0], [0, 0], dashes=dashesHalf,
                                         color='#996600')
        self.lines[Markers.OFE] = Line2D([0, 0], [0, 0], dashes=dashesHalf,
                                         color='#996600')
        if matplotlib.__version__ >= '1.3':
            effect = patheffects.withStroke(linewidth=3, foreground="w",
                                            alpha=0.75)
            self.lines[Markers.MIN].set_path_effects([effect])
            self.lines[Markers.MAX].set_path_effects([effect])
            self.lines[Markers.AVG].set_path_effects([effect])
            self.lines[Markers.GMEAN].set_path_effects([effect])
            self.lines[Markers.HP].set_path_effects([effect])
            self.lines[Markers.HFS].set_path_effects([effect])
            self.lines[Markers.HFE].set_path_effects([effect])
            self.lines[Markers.OP].set_path_effects([effect])
            self.lines[Markers.OFS].set_path_effects([effect])
            self.lines[Markers.OFE].set_path_effects([effect])

        for line in self.lines.itervalues():
            self.axes.add_line(line)

        bbox = self.axes.bbox
        box = dict(boxstyle='round', fc='white', ec='black', clip_box=bbox)
        self.labels[Markers.MIN] = Text(0, 0, 'Min', fontsize='xx-small',
                                        ha="right", va="bottom", bbox=box,
                                        color='black')
        self.labels[Markers.MAX] = Text(0, 0, 'Max', fontsize='xx-small',
                                        ha="right", va="top", bbox=box,
                                        color='black')
        box['ec'] = 'magenta'
        self.labels[Markers.AVG] = Text(0, 0, 'Mean', fontsize='xx-small',
                                        ha="right", va="center", bbox=box,
                                        color='magenta')
        box['ec'] = 'green'
        self.labels[Markers.GMEAN] = Text(0, 0, 'GMean', fontsize='xx-small',
                                          ha="right", va="center", bbox=box,
                                          color='green')
        box['ec'] = 'purple'
        self.labels[Markers.HP] = Text(0, 0, '-3dB', fontsize='xx-small',
                                       ha="right", va="center", bbox=box,
                                       color='purple')
        self.labels[Markers.HFS] = Text(0, 0, '-3dB Start', fontsize='xx-small',
                                        ha="center", va="top", bbox=box,
                                        color='purple')
        self.labels[Markers.HFE] = Text(0, 0, '-3dB End', fontsize='xx-small',
                                        ha="center", va="top", bbox=box,
                                        color='purple')
        box['ec'] = '#996600'
        self.labels[Markers.OP] = Text(0, 0, 'OBW', fontsize='xx-small',
                                       ha="right", va="center", bbox=box,
                                       color='#996600')
        self.labels[Markers.OFS] = Text(0, 0, 'OBW Start', fontsize='xx-small',
                                        ha="center", va="top", bbox=box,
                                        color='#996600')
        self.labels[Markers.OFE] = Text(0, 0, 'OBW End', fontsize='xx-small',
                                        ha="center", va="top", bbox=box,
                                        color='#996600')

        for label in self.labels.itervalues():
            self.axes.add_artist(label)

    def setup_overflow(self):
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
        self.overflowLabels['top'] = Text(0.9, 1, '', fontsize='xx-small',
                                          ha="right", va="top", bbox=box,
                                          transform=self.axes.transAxes,
                                          alpha=0.5)
        self.overflowLabels['bottom'] = Text(0.9, 0, '', fontsize='xx-small',
                                             ha="right", va="bottom", bbox=box,
                                             transform=self.axes.transAxes,
                                             alpha=0.5)

        for label in self.overflowLabels.itervalues():
            self.axes.add_artist(label)

    def clear_overflow(self):
        for label in self.overflowLabels:
            self.overflow[label] = []

    def draw_hline(self, marker, y):
        line = self.lines[marker]
        label = self.labels[marker]
        xLim = self.axes.get_xlim()
        yLim = self.axes.get_ylim()
        if yLim[0] <= y <= yLim[1]:
            line.set_visible(True)
            line.set_xdata([xLim[0], xLim[1]])
            line.set_ydata([y, y])
            self.axes.draw_artist(line)
            label.set_visible(True)
            label.set_position((xLim[1], y))
            self.axes.draw_artist(label)
        elif y is not None and y < yLim[0]:
            self.overflow['bottom'].append(marker)
        elif y is not None and y > yLim[1]:
            self.overflow['top'].append(marker)

    def draw_vline(self, marker, x):
        line = self.lines[marker]
        label = self.labels[marker]
        yLim = self.axes.get_ylim()
        xLim = self.axes.get_xlim()
        if xLim[0] <= x <= xLim[1]:
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

    def draw_overflow(self):
        for pos, overflow in self.overflow.iteritems():
            if len(overflow) > 0:
                text = ''
                for measure in overflow:
                    if len(text) > 0:
                        text += '\n'
                    text += self.labels[measure].get_text()

                label = self.overflowLabels[pos]
                if pos == 'top':
                    textMath = '$\\blacktriangle$\n' + text
                elif pos == 'bottom':
                    textMath = '$\\blacktriangledown$\n' + text
                elif pos == 'left':
                    textMath = '$\\blacktriangleleft$\n' + text
                elif pos == 'right':
                    textMath = '$\\blacktriangleright$\n' + text

                label.set_text(textMath)
                label.set_visible(True)
                self.axes.draw_artist(label)

    def draw_measure(self, measure, show):
        if self.axes._cachedRenderer is None:
            return

        self.hide_measure()
        self.clear_overflow()

        if show[Measure.MIN]:
            y = measure.get_min_p()[1]
            self.draw_hline(Markers.MIN, y)

        if show[Measure.MAX]:
            y = measure.get_max_p()[1]
            self.draw_hline(Markers.MAX, y)

        if show[Measure.AVG]:
            y = measure.get_avg_p()
            self.draw_hline(Markers.AVG, y)

        if show[Measure.GMEAN]:
            y = measure.get_gmean_p()
            self.draw_hline(Markers.GMEAN, y)

        if show[Measure.HBW]:
            xStart, xEnd, y = measure.get_hpw()
            self.draw_hline(Markers.HP, y)
            self.draw_vline(Markers.HFS, xStart)
            self.draw_vline(Markers.HFE, xEnd)

        if show[Measure.OBW]:
            xStart, xEnd, y = measure.get_obw()
            self.draw_hline(Markers.OP, y)
            self.draw_vline(Markers.OFE, xStart)
            self.draw_vline(Markers.OFE, xEnd)

        self.draw_overflow()

    def hide_measure(self):
        for line in self.lines.itervalues():
            line.set_visible(False)
        for label in self.labels.itervalues():
            label.set_visible(False)
        for label in self.overflowLabels.itervalues():
            label.set_visible(False)

    def scale_plot(self, force=False):
        if self.extent is not None:
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

    def get_axes_bar(self):
        return self.barBase.ax

    def get_plot_thread(self):
        return self.threadPlot

    def set_title(self, title):
        self.axes.set_title(title)

    def set_plot(self, spectrum, extent, annotate=False):
        self.extent = extent
        self.threadPlot = ThreadPlot(self, self.axes, spectrum,
                                     self.extent,
                                     self.settings.colourMap,
                                     self.settings.autoL,
                                     self.settings.lineWidth,
                                     self.barBase,
                                     self.settings.fadeScans,
                                     annotate, self.settings.average)
        self.threadPlot.start()

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
    def __init__(self, parent, axes, data, extent,
                 colourMap, autoL, lineWidth,
                 barBase, fade, annotate, average):
        threading.Thread.__init__(self)
        self.name = "Plot"
        self.parent = parent
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

    def run(self):
        if self.data is None:
            self.parent.threadPlot = None
            return

        peakF = None
        peakL = None
        total = len(self.data)
        if total > 0:
            self.parent.clear_plots()
            lc = None
            if self.average:
                avg = OrderedDict()
                count = len(self.data)

                for timeStamp in self.data:

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

                    if len(self.data[timeStamp]) < 2:
                        self.parent.threadPlot = None
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

        self.parent.threadPlot = None

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
                               ha='left', va='top', size='x-small',
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
                               ha='left', va='top', size='x-small',
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


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
