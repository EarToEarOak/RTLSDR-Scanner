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

from collections import OrderedDict
import threading

from matplotlib import patheffects
import matplotlib
from matplotlib.cm import ScalarMappable
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.colorbar import ColorbarBase
from matplotlib.colors import Normalize
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator
import numpy

from rtlsdr_scanner.constants import Markers, PlotFunc
from rtlsdr_scanner.events import EventThread, Event, post_event
from rtlsdr_scanner.misc import format_precision
from rtlsdr_scanner.spectrum import Measure, Extent, smooth_spectrum, \
    diff_spectrum, delta_spectrum, get_peaks
from rtlsdr_scanner.utils_mpl import get_colours


class Plotter(object):
    def __init__(self, notify, figure, settings):
        self.notify = notify
        self.figure = figure
        self.settings = settings
        self.axes = None
        self.bar = None
        self.barBase = None
        self.threadPlot = None
        self.extent = None
        self.lines = {}
        self.labels = {}
        self.overflowLabels = {}
        self.overflow = {'left': [],
                         'right': [],
                         'top': [],
                         'bottom': []}

        self.__setup_plot()
        self.set_grid(self.settings.grid)

    def __setup_plot(self):
        formatter = ScalarFormatter(useOffset=False)

        gs = GridSpec(1, 2, width_ratios=[9.5, 0.5])

        self.axes = self.figure.add_subplot(gs[0],
                                            facecolor=self.settings.background)
        self.axes.set_xlabel("Frequency (MHz)")
        self.axes.set_ylabel('Level (dB/Hz)')
        self.axes.xaxis.set_major_formatter(formatter)
        self.axes.yaxis.set_major_formatter(formatter)
        self.axes.xaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.yaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.set_xlim(self.settings.start, self.settings.stop)
        self.axes.set_ylim(-50, 0)

        self.bar = self.figure.add_subplot(gs[1])
        norm = Normalize(vmin=-50, vmax=0)
        self.barBase = ColorbarBase(self.bar, norm=norm)
        self.set_colourmap_use(self.settings.colourMapUse)

        self.__setup_measure()
        self.__setup_overflow()
        self.hide_measure()

    def __setup_measure(self):
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

    def __clear_overflow(self):
        for label in self.overflowLabels:
            self.overflow[label] = []

    def __draw_hline(self, marker, y):
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

    def __draw_vline(self, marker, x):
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

    def __draw_overflow(self):
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
        if self.axes.get_renderer_cache() is None:
            return

        self.hide_measure()
        self.__clear_overflow()

        if show[Measure.MIN]:
            y = measure.get_min_p()[1]
            self.__draw_hline(Markers.MIN, y)

        if show[Measure.MAX]:
            y = measure.get_max_p()[1]
            self.__draw_hline(Markers.MAX, y)

        if show[Measure.AVG]:
            y = measure.get_avg_p()
            self.__draw_hline(Markers.AVG, y)

        if show[Measure.GMEAN]:
            y = measure.get_gmean_p()
            self.__draw_hline(Markers.GMEAN, y)

        if show[Measure.HBW]:
            xStart, xEnd, y = measure.get_hpw()
            self.__draw_hline(Markers.HP, y)
            self.__draw_vline(Markers.HFS, xStart)
            self.__draw_vline(Markers.HFE, xEnd)

        if show[Measure.OBW]:
            xStart, xEnd, y = measure.get_obw()
            self.__draw_hline(Markers.OP, y)
            self.__draw_vline(Markers.OFE, xStart)
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
        if self.extent is not None:
            if self.settings.autoF or force:
                self.axes.set_xlim(self.extent.get_f())
            if self.settings.autoL or force:
                self.axes.set_ylim(self.extent.get_l())
                if self.settings.plotFunc == PlotFunc.VAR and len(self.axes.collections) > 0:
                    norm = self.axes.collections[0].norm
                    self.barBase.set_clim((norm.vmin, norm.vmax))
                else:
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
            post_event(self.notify, EventThread(Event.DRAW))

    def get_axes(self):
        return self.axes

    def get_axes_bar(self):
        return self.barBase.ax

    def get_bar(self):
        return self.barBase

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

        return self.threadPlot

    def clear_plots(self):
        children = self.axes.get_children()
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() in ['plot', 'peak', 'peakText',
                                       'peakShadow', 'peakThres']:
                    child.remove()

    def set_grid(self, on):
        self.axes.grid(on)
        self.redraw_plot()

    def set_bar(self, on):
        self.barBase.ax.set_visible(on)
        if on:
            self.axes.change_geometry(1, 2, 1)
            self.axes.get_subplotspec().get_gridspec().set_width_ratios([9.5, 0.5])
        else:
            self.axes.change_geometry(1, 1, 1)

        self.figure.subplots_adjust()

    def set_axes(self, on):
        if on:
            self.axes.set_axis_on()
            self.bar.set_axis_on()
        else:
            self.axes.set_axis_off()
            self.bar.set_axis_off()

    def set_colourmap_use(self, on):
        self.set_bar(on)
        if on:
            colourMap = self.settings.colourMap
        else:
            colourMap = get_colours()[0]

        self.set_colourmap(colourMap)

    def set_colourmap(self, colourMap):
        self.settings.colourMap = colourMap
        for collection in self.axes.collections:
            collection.set_cmap(colourMap)

        if get_colours().index(colourMap) < 4:
            self.set_bar(False)
        else:
            self.set_bar(True)
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
        if self.settings.colourMapUse:
            self.colourMap = settings.colourMap
        else:
            self.colourMap = get_colours()[0]
        self.lineWidth = settings.lineWidth
        self.barBase = barBase
        self.annotate = annotate

    def run(self):
        if self.data is None:
            self.parent.threadPlot = None
            return

        total = len(self.data)
        if total > 0:
            self.parent.clear_plots()

            if self.settings.plotFunc == PlotFunc.NONE:
                peakF, peakL = self.__plot_all(self.data)
            elif self.settings.plotFunc == PlotFunc.MIN:
                peakF, peakL = self.__plot_min()
            elif self.settings.plotFunc == PlotFunc.MAX:
                peakF, peakL = self.__plot_max()
            elif self.settings.plotFunc == PlotFunc.AVG:
                peakF, peakL = self.__plot_avg()
            elif self.settings.plotFunc == PlotFunc.VAR:
                peakF, peakL = self.__plot_variance()
            elif self.settings.plotFunc == PlotFunc.SMOOTH:
                peakF, peakL = self.__plot_smooth()
            elif self.settings.plotFunc == PlotFunc.DIFF:
                peakF, peakL = self.__plot_diff()
            elif self.settings.plotFunc == PlotFunc.DELTA:
                peakF, peakL = self.__plot_delta()

            self.__clear_markers()

            if self.annotate:
                self.__plot_peak(peakF, peakL)

            if self.settings.peaks:
                self.__plot_peaks()

            self.parent.scale_plot()
            self.parent.redraw_plot()

        self.parent.threadPlot = None

    def __plot_all(self, spectrum):
        total = len(spectrum)
        count = 0.0
        for timeStamp in spectrum:
            if self.settings.fadeScans:
                alpha = (count + 1) / total
            else:
                alpha = 1

            data = spectrum[timeStamp].items()
            peakF, peakL = self.extent.get_peak_fl()

            segments, levels = self.__create_segments(data)
            if segments is not None:
                lc = LineCollection(segments)
                lc.set_array(numpy.array(levels))
                lc.set_norm(self.__get_norm(self.settings.autoL, self.extent))
                lc.set_cmap(self.colourMap)
                lc.set_linewidth(self.lineWidth)
                lc.set_gid('plot')
                lc.set_alpha(alpha)
                self.axes.add_collection(lc)
                count += 1

        return peakF, peakL

    def __plot_single(self, points):
        data = points.items()
        peakF, peakL = max(data, key=lambda item: item[1])

        segments, levels = self.__create_segments(data)
        lc = LineCollection(segments)
        lc.set_array(numpy.array(levels))
        lc.set_norm(self.__get_norm(self.settings.autoL, self.extent))
        lc.set_cmap(self.colourMap)
        lc.set_linewidth(self.lineWidth)
        lc.set_gid('plot')
        self.axes.add_collection(lc)

        return peakF, peakL

    def __plot_min(self):
        points = self.__calc_min()

        return self.__plot_single(points)

    def __plot_max(self):
        points = self.__calc_max()

        return self.__plot_single(points)

    def __plot_avg(self):
        points = OrderedDict()

        for timeStamp in self.data:

            for x, y in self.data[timeStamp].items():
                if x in points:
                    points[x] = (points[x] + y) / 2
                else:
                    points[x] = y

        return self.__plot_single(points)

    def __plot_variance(self):
        pointsMin = self.__calc_min()
        pointsMax = self.__calc_max()

        polys = []
        variance = []
        varMin = 1000
        varMax = 0
        lastX = None
        lastYMin = None
        lastYMax = None
        for x in pointsMin.iterkeys():
            if lastX is None:
                lastX = x
            if lastYMin is None:
                lastYMin = pointsMin[x]
            if lastYMax is None:
                lastYMax = pointsMax[x]
            polys.append([[x, pointsMin[x]],
                          [x, pointsMax[x]],
                          [lastX, lastYMax],
                          [lastX, lastYMin],
                          [x, pointsMin[x]]])
            lastX = x
            lastYMin = pointsMin[x]
            lastYMax = pointsMax[x]

            var = pointsMax[x] - pointsMin[x]
            variance.append(var)
            varMin = min(varMin, var)
            varMax = max(varMax, var)

        norm = Normalize(vmin=varMin, vmax=varMax)
        sm = ScalarMappable(norm, self.colourMap)
        colours = sm.to_rgba(variance)

        pc = PolyCollection(polys)
        pc.set_gid('plot')
        pc.set_norm(norm)
        pc.set_color(colours)
        self.axes.add_collection(pc)

        return None, None

    def __plot_smooth(self):
        data = smooth_spectrum(self.data,
                               self.settings.smoothFunc,
                               self.settings.smoothRatio)
        self.extent = Extent(data)
        return self.__plot_all(data)

    def __plot_diff(self):
        data = diff_spectrum(self.data)
        self.extent = Extent(data)
        self.parent.extent = self.extent
        return self.__plot_all(data)

    def __plot_delta(self):
        data = delta_spectrum(self.data)
        self.extent = Extent(data)
        self.parent.extent = self.extent
        return self.__plot_all(data)

    def __plot_peak(self, x, y):
        if x is None or y is None:
            return

        start, stop = self.axes.get_xlim()
        textX = ((stop - start) / 50.0) + x

        text = '{}\n{}'.format(*format_precision(self.settings, x, y,
                                                 fancyUnits=True))
        if matplotlib.__version__ < '1.3':
            self.axes.annotate(text,
                               xy=(x, y), xytext=(textX, y),
                               ha='left', va='top', size='x-small',
                               gid='peakText')
            self.axes.plot(x, y, marker='x', markersize=10, color='w',
                           mew=3, gid='peakShadow')
            self.axes.plot(x, y, marker='x', markersize=10, color='r',
                           gid='peak')
        else:
            effect = patheffects.withStroke(linewidth=2, foreground="w",
                                            alpha=0.75)
            self.axes.annotate(text,
                               xy=(x, y), xytext=(textX, y),
                               ha='left', va='top', size='x-small',
                               path_effects=[effect], gid='peakText')
            self.axes.plot(x, y, marker='x', markersize=10, color='r',
                           path_effects=[effect], gid='peak')

    def __plot_peaks(self):
        sweep, indices = get_peaks(self.data, self.settings.peaksThres)

        for i in indices:
            self.axes.plot(sweep.keys()[i], sweep.values()[i],
                           linestyle='None',
                           marker='+', markersize=10, color='r',
                           gid='peakThres')

    def __calc_min(self):
        points = OrderedDict()

        for timeStamp in self.data:
            for x, y in self.data[timeStamp].items():
                if x in points:
                    points[x] = min(points[x], y)
                else:
                    points[x] = y

        return points

    def __calc_max(self):
        points = OrderedDict()

        for timeStamp in self.data:
            for x, y in self.data[timeStamp].items():
                if x in points:
                    points[x] = max(points[x], y)
                else:
                    points[x] = y

        return points

    def __create_segments(self, points):
        segments = []
        levels = []

        if len(points):
            prev = points[0]
            for point in points:
                segment = [prev, point]
                segments.append(segment)
                levels.append((point[1] + prev[1]) / 2.0)
                prev = point

            return segments, levels

        return None, None

    def __get_norm(self, autoL, extent):
        if autoL:
            vmin, vmax = self.barBase.get_clim()
        else:
            yExtent = extent.get_l()
            vmin = yExtent[0]
            vmax = yExtent[1]

        return Normalize(vmin=vmin, vmax=vmax)

    def __get_plots(self):
        plots = []
        children = self.axes.get_children()
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() == "plot":
                    plots.append(child)

        return plots

    def __clear_markers(self):
        children = self.axes.get_children()
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() in ['peak', 'peakText',
                                       'peakShadow', 'peakThres']:
                    child.remove()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
