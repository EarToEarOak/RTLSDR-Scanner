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

import matplotlib
from matplotlib.patches import Rectangle

from rtlsdr_scanner.plot_3d import Plotter3d
from rtlsdr_scanner.plot_preview import PlotterPreview
from rtlsdr_scanner.plot_status import PlotterStatus
from rtlsdr_scanner.plot_time import PlotterTime


class MouseZoom():
    SCALE_STEP = 1.3

    def __init__(self, toolbar, figure=None, plot=None, callbackHide=None):
        if figure is None:
            if isinstance(plot, (Plotter3d, PlotterStatus, PlotterPreview)):
                return

            self.axes = plot.get_axes()
            self.figure = self.axes.get_figure()
        else:
            self.axes = figure.get_axes()[0]
            self.figure = figure

        self.callbackHide = callbackHide
        self.toolbar = toolbar
        self.figure.canvas.mpl_connect('scroll_event', self.__zoom)

    def __zoom(self, event):
        if event.button == 'up':
            scale = 1 / self.SCALE_STEP
        elif event.button == 'down':
            scale = self.SCALE_STEP
        else:
            return

        if self.callbackHide is not None:
            self.callbackHide()
        self.toolbar.clear_auto()

        if self.toolbar._views.empty():
            self.toolbar.push_current()

        xLim = self.axes.get_xlim()
        yLim = self.axes.get_ylim()
        xPos = event.xdata
        yPos = event.ydata
        if not yLim[0] <= yPos <= yLim[1]:
            yPos = yLim[0] + (yLim[1] - yLim[0]) / 2

        xPosRel = (xLim[1] - xPos) / (xLim[1] - xLim[0])
        yPosRel = (yLim[1] - yPos) / (yLim[1] - yLim[0])

        newXLim = (xLim[1] - xLim[0]) * scale
        newYLim = (yLim[1] - yLim[0]) * scale
        xStart = xPos - newXLim * (1 - xPosRel)
        xStop = xPos + newXLim * xPosRel
        yStart = yPos - newYLim * (1 - yPosRel)
        yStop = yPos + newYLim * yPosRel

        self.axes.set_xlim([xStart, xStop])
        self.axes.set_ylim([yStart, yStop])

        self.toolbar.push_current()
        self.figure.canvas.draw()


class MouseSelect():
    def __init__(self, plot, callbackPre, callbackPost):
        self.selector = None
        if isinstance(plot, (Plotter3d, PlotterStatus,
                             PlotterTime, PlotterPreview)):
            return

        axes = plot.get_axes()
        self.selector = RangeSelector(axes, callbackPre, callbackPost)

    def draw(self, xMin, xMax):
        if self.selector is not None:
            self.selector.draw(xMin, xMax)

    def hide(self):
        if self.selector is not None:
            self.selector.hide()

    def clear(self):
        if self.selector is not None:
            self.selector.clear()


# Based on http://matplotlib.org/1.3.1/users/event_handling.html
class RangeSelector():
    def __init__(self, axes, callbackPre, callbackPost):
        self.axes = axes
        self.callbackPre = callbackPre
        self.callbackPost = callbackPost

        self.eventPressed = None
        self.eventReleased = None

        props = dict(facecolor='red', edgecolor='white', alpha=0.25, fill=True,
                     zorder=100, gid='range')
        self.rect = Rectangle((0, 0), 0, 0, **props)
        self.axes.add_patch(self.rect)

        figure = self.axes.get_figure()
        figure.canvas.mpl_connect('motion_notify_event', self.__on_move)
        figure.canvas.mpl_connect('button_press_event', self.__on_press)
        figure.canvas.mpl_connect('button_release_event', self.__on_release)

    def __on_press(self, event):
        if self.__skip_event(event):
            return

        self.eventPressed = event
        self.callbackPre()
        self.rect.set_visible(True)
        return

    def __on_move(self, event):
        if self.eventPressed is None or self.__skip_event(event):
            return

        xMin = self.eventPressed.xdata
        xMax = event.xdata
        if xMin > xMax:
            xMin, xMax = xMax, xMin
        self.callbackPost(xMin, xMax)

        return

    def __on_release(self, event):
        if self.eventPressed is None or self.__skip_event(event):
            return

        self.eventReleased = event
        xMin, xMax = self.eventPressed.xdata, self.eventReleased.xdata
        if xMin > xMax:
            xMin, xMax = xMax, xMin
        self.callbackPost(xMin, xMax)
        self.eventPressed = None
        self.eventReleased = None
        return

    def __skip_event(self, event):
        if matplotlib.__version__ >= '1.2' and event.dblclick:
            return True

        if event.button != 2:
            return True

        if self.eventPressed is None:
            return event.inaxes != self.axes

        if event.button == self.eventPressed.button and event.inaxes != self.axes:
            transform = self.axes.transData.inverted()
            (x, _y) = transform.transform_point((event.x, event.y))
            x0, x1 = self.axes.get_xbound()
            x = max(x0, x)
            x = min(x1, x)
            event.xdata = x
            return False

        return (event.inaxes != self.axes or
                event.button != self.eventPressed.button)

    def draw(self, xMin, xMax):
        self.rect.set_visible(True)
        yMin, yMax = self.axes.get_ylim()
        height = yMax - yMin
        yMin -= height * 100.0
        yMax += height * 100.0
        self.rect.set_x(xMin)
        self.rect.set_y(yMin)
        self.rect.set_width(xMax - xMin)
        self.rect.set_height(yMax - yMin)

        if self.axes._cachedRenderer is not None:
            self.axes.draw_artist(self.rect)

    def hide(self):
        self.rect.set_visible(False)

    def clear(self):
        self.rect.set_visible(False)
        canvas = self.axes.get_figure().canvas
        canvas.draw()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
