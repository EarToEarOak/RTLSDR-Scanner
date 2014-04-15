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
from matplotlib.colors import Normalize, hex2color
from matplotlib.dates import DateFormatter
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator

from events import post_event, EventThreadStatus, Event
from misc import format_time
from mpl_toolkits.mplot3d import Axes3D  # @UnresolvedImport @UnusedImport
from spectrum import epoch_to_mpl, create_mesh


class Plotter3d():
    def __init__(self, notify, figure, settings):
        self.notify = notify
        self.figure = figure
        self.settings = settings
        self.axes = None
        self.plot = None
        self.extent = None
        self.threadPlot = None
        self.wireframe = settings.wireframe
        self.setup_plot()
        self.set_grid(settings.grid)

    def setup_plot(self):
        gs = GridSpec(1, 2, width_ratios=[9.5, 0.5])
        self.axes = self.figure.add_subplot(gs[0], projection='3d')

        numformatter = ScalarFormatter(useOffset=False)
        timeFormatter = DateFormatter("%H:%M:%S")

        self.axes.set_xlabel("Frequency (MHz)")
        self.axes.set_ylabel('Time')
        self.axes.set_zlabel('Level (dB)')
        self.axes.w_xaxis.set_pane_color(hex2color(self.settings.background))
        self.axes.w_yaxis.set_pane_color(hex2color(self.settings.background))
        self.axes.w_zaxis.set_pane_color(hex2color(self.settings.background))
        self.axes.xaxis.set_major_formatter(numformatter)
        self.axes.yaxis.set_major_formatter(timeFormatter)
        self.axes.zaxis.set_major_formatter(numformatter)
        self.axes.xaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.yaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.zaxis.set_minor_locator(AutoMinorLocator(10))
        self.axes.set_xlim(self.settings.start, self.settings.stop)
        now = time.time()
        self.axes.set_ylim(epoch_to_mpl(now), epoch_to_mpl(now - 10))
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
                                     self.settings.autoF,
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
            x, y, z = create_mesh(self.data, True)
            self.parent.clear_plots()

            if self.autoL:
                vmin, vmax = self.barBase.get_clim()
            else:
                zExtent = self.extent.get_l()
                vmin = zExtent[0]
                vmax = zExtent[1]
            if self.parent.wireframe:
                self.parent.plot = \
                self.axes.plot_wireframe(x, y, z,
                                         rstride=1, cstride=1,
                                         linewidth=0.1,
                                         cmap=cm.get_cmap(self.colourMap),
                                         gid='plot',
                                         antialiased=True,
                                         alpha=1)
            else:
                self.parent.plot = \
                self.axes.plot_surface(x, y, z,
                                       rstride=1, cstride=1,
                                       vmin=vmin, vmax=vmax,
                                       linewidth=0,
                                       cmap=cm.get_cmap(self.colourMap),
                                       gid='plot',
                                       antialiased=True,
                                       alpha=1)

            if self.annotate:
                self.annotate_plot()

        if total > 0:
            self.parent.scale_plot()
            self.parent.redraw_plot()

        self.parent.threadPlot = None

    def annotate_plot(self):
        f, l, t = self.extent.get_peak_flt()
        when = format_time(t)
        tPos = epoch_to_mpl(t)
        if(matplotlib.__version__ < '1.3'):
            self.axes.text(f, tPos, l,
                           '{0:.6f}MHz\n{1:.2f}dB\n{2}'.format(f, l, when),
                           ha='left', va='bottom', size='small', gid='peak')
            self.axes.plot([f], [tPos], [l], marker='x', markersize=10,
                           mew=3, color='w', gid='peak')
            self.axes.plot([f], [tPos], [l], marker='x', markersize=10,
                           color='r', gid='peak')
        else:
            effect = patheffects.withStroke(linewidth=3, foreground="w",
                                            alpha=0.75)
            self.axes.text(f, tPos, l,
                           '{0:.6f}MHz\n{1:.2f}dB\n{2}'.format(f, l, when),
                           ha='left', va='bottom', size='small', gid='peak',
                           path_effects=[effect])
            self.axes.plot([f], [tPos], [l], marker='x', markersize=10,
                           color='r', gid='peak', path_effects=[effect])

    def clear_markers(self):
        children = self.axes.get_children()
        for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == 'peak':
                        child.remove()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
