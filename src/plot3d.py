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
from matplotlib.dates import DateFormatter, seconds
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator
import numpy

from events import post_event, EventThreadStatus, Event
from misc import epoch_to_mpl, split_spectrum
from mpl_toolkits.mplot3d import Axes3D  # @UnresolvedImport @UnusedImport


MPL_SECOND = seconds(1)


class Plotter3d():
    def __init__(self, notify, graph, settings, grid, lock):
        self.notify = notify
        self.settings = settings
        self.graph = graph
        self.lock = lock
        self.figure = self.graph.get_figure()
        self.axes = None
        self.plot = None
        self.threadPlot = None
        self.extent = None
        self.wireframe = settings.wireframe
        self.setup_plot()
        self.set_grid(grid)

    def setup_plot(self):
        gs = GridSpec(1, 2, width_ratios=[9.5, 0.5])
        self.axes = self.figure.add_subplot(gs[0], projection='3d')

        numformatter = ScalarFormatter(useOffset=False)
        timeFormatter = DateFormatter("%H:%M:%S")

        self.axes.set_xlabel("Frequency (MHz)")
        self.axes.set_ylabel('Time')
        self.axes.set_zlabel('Level (dB)')
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
        self.barBase.set_label('Level (dB)')

    def scale_plot(self, force=False):
        if self.extent is not None:
            with self.lock:
                if self.settings.autoScale or force:
                    self.axes.set_xlim(self.extent.get_x())
                    self.axes.set_ylim(self.extent.get_y())
                    self.axes.set_zlim(self.extent.get_z())
                    self.plot.set_clim(self.extent.get_z())
                    self.settings.yMin, self.settings.yMax = self.extent.get_z()
                else:
                    self.axes.set_zlim(self.settings.yMin, self.settings.yMax)

                vmin, vmax = self.axes.get_zlim()
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
        peakX = None
        peakY = None
        peakZ = None

        with self.lock:
            if self.abort:
                return
            total = len(self.data)
            if total > 0:
                timeMin = min(self.data)
                plotFirst = self.data[timeMin]
                if len(plotFirst) == 0:
                    return
                width = len(plotFirst)

                x = numpy.empty((width, total + 1)) * numpy.nan
                y = numpy.empty((width, total + 1)) * numpy.nan
                z = numpy.empty((width, total + 1)) * numpy.nan
                self.parent.clear_plots()
                j = 1
                extent = Extent()
                peakY = max(self.data)
                for ys in sorted(self.data):
                    mplTime = epoch_to_mpl(ys)
                    xs, zs = split_spectrum(self.data[ys])
                    extent.update(xs, ys, zs)
                    for i in range(len(xs)):
                        if self.abort:
                            return
                        x[i, j] = xs[i]
                        y[i, j] = mplTime
                        z[i, j] = zs[i]
                    j += 1

                x[:, 0] = x[:, 1]
                y[:, 0] = y[:, 1] - MPL_SECOND
                z[:, 0] = z[:, 1]

                pos = numpy.argmax(z[:, 1])
                peakX = x[:, 1][pos]
                peakZ = z[:, 1][pos]

                if self.autoScale:
                    vmin = self.min
                    vmax = self.max
                else:
                    zExtent = extent.get_z()
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
                self.parent.extent = extent

                if self.annotate:
                    self.annotate_plot(peakX, peakY, peakZ)

        if total > 0:
            self.parent.scale_plot()
            self.parent.redraw_plot()

    def annotate_plot(self, x, y, z):
        when = time.strftime('%H:%M:%S', time.gmtime(y))
        yPos = epoch_to_mpl(y)
        if(matplotlib.__version__ < '1.3'):
            self.axes.text(x, yPos, z,
                           '{0:.6f}MHz\n{1:.2f}dB\n{2}'.format(x, z, when),
                           ha='left', va='bottom', size='small', gid='peak')
            self.axes.plot([x], [yPos], [z], marker='x', markersize=10,
                           mew=3, color='w', gid='peak')
            self.axes.plot([x], [yPos], [z], marker='x', markersize=10,
                           color='r', gid='peak')
        else:
            effect = patheffects.withStroke(linewidth=3, foreground="w",
                                            alpha=0.75)
            self.axes.text(x, epoch_to_mpl(y), z,
                           '{0:.6f}MHz\n{1:.2f}dB\n{2}'.format(x, z, when),
                           ha='left', va='bottom', size='small', gid='peak',
                           path_effects=[effect])
            self.axes.plot([x], [yPos], [z], marker='x', markersize=10,
                           color='r', gid='peak', path_effects=[effect])

    def clear_markers(self):
        children = self.axes.get_children()
        for child in children:
                if child.get_gid() is not None:
                    if child.get_gid() == 'peak':
                        child.remove()

    def cancel(self):
        self.abort = True


class Extent():
    def __init__(self):
        self.clear()

    def clear(self):
        self.xMin = float('inf')
        self.xMax = float('-inf')
        self.yMin = float('inf')
        self.yMax = float('-inf')
        self.zMin = float('inf')
        self.zMax = float('-inf')

    def update(self, x, y, z):
        if len(x) > 0:
            self.xMin = min(self.xMin, min(x))
            self.xMax = max(self.xMax, max(x))
        self.yMin = min(self.yMin, y)
        self.yMax = max(self.yMax, y)
        if len(z) > 0:
            self.zMin = min(self.zMin, min(z))
            self.zMax = max(self.zMax, max(z))

    def get_x(self):
        if self.xMin == self.xMax:
            return self.xMin, self.xMax - 0.001
        return self.xMin, self.xMax

    def get_y(self):
        return epoch_to_mpl(self.yMax), epoch_to_mpl(self.yMin - 1)

    def get_z(self):
        if self.yMin == self.yMax:
            return self.zMin, self.zMax - 0.001
        return self.zMin, self.zMax


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
