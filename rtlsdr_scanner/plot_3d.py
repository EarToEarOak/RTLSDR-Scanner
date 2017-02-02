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

from matplotlib import cm, patheffects
import matplotlib
from matplotlib.colorbar import ColorbarBase
from matplotlib.colors import Normalize, hex2color
from matplotlib.dates import DateFormatter
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator
from mpl_toolkits.mplot3d import Axes3D  # @UnresolvedImport @UnusedImport

from rtlsdr_scanner.constants import PlotFunc
from rtlsdr_scanner.events import post_event, EventThread, Event
from rtlsdr_scanner.misc import format_time, format_precision
from rtlsdr_scanner.spectrum import create_mesh, smooth_spectrum, Extent, diff_spectrum, \
    get_peaks
from rtlsdr_scanner.utils_mpl import utc_to_mpl


class Plotter3d(object):
    def __init__(self, notify, figure, settings):
        self.notify = notify
        self.figure = figure
        self.settings = settings
        self.axes = None
        self.bar = None
        self.barBase = None
        self.plot = None
        self.extent = None
        self.threadPlot = None
        self.__setup_plot()
        self.set_grid(settings.grid)

    def __setup_plot(self):
        gs = GridSpec(1, 2, width_ratios=[9.5, 0.5])
        self.axes = self.figure.add_subplot(gs[0], projection='3d')

        numformatter = ScalarFormatter(useOffset=False)
        timeFormatter = DateFormatter("%H:%M:%S")

        self.axes.set_xlabel("Frequency (MHz)")
        self.axes.set_ylabel('Time')
        self.axes.set_zlabel('Level (dB/Hz)')
        colour = hex2color(self.settings.background)
        colour += (1,)
        self.axes.w_xaxis.set_pane_color(colour)
        self.axes.w_yaxis.set_pane_color(colour)
        self.axes.w_zaxis.set_pane_color(colour)
        self.axes.xaxis.set_major_formatter(numformatter)
        self.axes.yaxis.set_major_formatter(timeFormatter)
        self.axes.zaxis.set_major_formatter(numformatter)
        self.axes.xaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.yaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.zaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.set_xlim(self.settings.start, self.settings.stop)
        now = time.time()
        self.axes.set_ylim(utc_to_mpl(now), utc_to_mpl(now - 10))
        self.axes.set_zlim(-50, 0)

        self.bar = self.figure.add_subplot(gs[1])
        norm = Normalize(vmin=-50, vmax=0)
        self.barBase = ColorbarBase(self.bar, norm=norm,
                                    cmap=cm.get_cmap(self.settings.colourMap))

    def scale_plot(self, force=False):
        if self.extent is not None and self.plot is not None:
            if self.settings.autoF or force:
                self.axes.set_xlim(self.extent.get_f())
            if self.settings.autoL or force:
                self.axes.set_zlim(self.extent.get_l())
                self.plot.set_clim(self.extent.get_l())
                self.barBase.set_clim(self.extent.get_l())
                try:
                    self.barBase.draw_all()
                except:
                    pass
            if self.settings.autoT or force:
                self.axes.set_ylim(self.extent.get_t())

    def draw_measure(self, *args):
        pass

    def hide_measure(self):
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

    def clear_plots(self):
        children = self.axes.get_children()
        for child in children:
            if child.get_gid() is not None:
                if child.get_gid() == "plot_line" or child.get_gid() == "peak":
                    child.remove()

    def set_grid(self, on):
        self.axes.grid(on)
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
            if self.settings.plotFunc == PlotFunc.NONE:
                peakF, peakL, peakT = self.__plot(self.data)
            elif self.settings.plotFunc == PlotFunc.SMOOTH:
                peakF, peakL, peakT = self.__plot_smooth()
            elif self.settings.plotFunc == PlotFunc.DIFF:
                peakF, peakL, peakT = self.__plot_diff()

            self.__clear_markers()

            if self.annotate:
                self.__plot_peak(peakF, peakL, peakT)

            if self.settings.peaks:
                self.__plot_peaks()

            self.parent.scale_plot()
            self.parent.redraw_plot()

        self.parent.threadPlot = None

    def __plot(self, spectrum):
        x, y, z = create_mesh(spectrum, True)
        self.parent.clear_plots()

        if self.settings.autoL:
            vmin, vmax = self.barBase.get_clim()
        else:
            zExtent = self.extent.get_l()
            vmin = zExtent[0]
            vmax = zExtent[1]
        if self.parent.settings.wireframe:
            self.parent.plot = \
                self.axes.plot_wireframe(x, y, z,
                                         rstride=1, cstride=1,
                                         linewidth=0.1,
                                         cmap=cm.get_cmap(self.settings.colourMap),
                                         gid='plot_line',
                                         antialiased=True,
                                         alpha=1)
        else:
            self.parent.plot = \
                self.axes.plot_surface(x, y, z,
                                       rstride=1, cstride=1,
                                       vmin=vmin, vmax=vmax,
                                       linewidth=0,
                                       cmap=cm.get_cmap(self.settings.colourMap),
                                       gid='plot_line',
                                       antialiased=True,
                                       alpha=1)

        return self.extent.get_peak_flt()

    def __plot_smooth(self):
        data = smooth_spectrum(self.data,
                               self.settings.smoothFunc,
                               self.settings.smoothRatio)
        self.extent = Extent(data)
        return self.__plot(data)

    def __plot_diff(self):
        data = diff_spectrum(self.data)
        self.extent = Extent(data)
        self.parent.extent = self.extent
        return self.__plot(data)

    def __plot_peak(self, peakF, peakL, peakT):
        when = format_time(peakT)
        tPos = utc_to_mpl(peakT)

        text = '{}\n{}\n{when}'.format(*format_precision(self.settings,
                                                         peakF, peakL,
                                                         fancyUnits=True),
                                       when=when)
        if matplotlib.__version__ < '1.3':
            self.axes.text(peakF, tPos, peakL,
                           text,
                           ha='left', va='bottom', size='x-small', gid='peakText')
            self.axes.plot([peakF], [tPos], [peakL], marker='x', markersize=10,
                           mew=3, color='w', gid='peak')
            self.axes.plot([peakF], [tPos], [peakL], marker='x', markersize=10,
                           color='r', gid='peakShadow')
        else:
            effect = patheffects.withStroke(linewidth=2, foreground="w",
                                            alpha=0.75)
            self.axes.text(peakF, tPos, peakL,
                           text,
                           ha='left', va='bottom', size='x-small', gid='peakText',
                           path_effects=[effect])
            self.axes.plot([peakF], [tPos], [peakL], marker='x', markersize=10,
                           color='r', gid='peak', path_effects=[effect])

    def __plot_peaks(self):
        sweep, indices = get_peaks(self.data, self.settings.peaksThres)
        lastTime = utc_to_mpl(max(self.data))

        for i in indices:
            self.axes.plot([sweep.keys()[i]], [lastTime], [sweep.values()[i]],
                           linestyle='None',
                           marker='+', markersize=10, color='r',
                           gid='peakThres')

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
