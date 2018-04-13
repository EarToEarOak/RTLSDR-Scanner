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

import copy
import math
import os
import re
import threading

from matplotlib import cm
import matplotlib
import matplotlib.animation
from matplotlib.backends.backend_wxagg import \
    FigureCanvasWxAgg as FigureCanvas
from matplotlib.colorbar import ColorbarBase
from matplotlib.colors import Normalize
from matplotlib.dates import num2epoch
from matplotlib.lines import Line2D
from matplotlib.ticker import AutoMinorLocator, ScalarFormatter
import wx
import wx.grid as wxGrid

from rtlsdr_scanner.constants import Display
from rtlsdr_scanner.misc import format_precision
from rtlsdr_scanner.plot_3d import Plotter3d
from rtlsdr_scanner.plot_controls import MouseZoom, MouseSelect
from rtlsdr_scanner.plot_line import Plotter
from rtlsdr_scanner.plot_preview import PlotterPreview
from rtlsdr_scanner.plot_spect import Spectrogram
from rtlsdr_scanner.plot_status import PlotterStatus
from rtlsdr_scanner.plot_time import PlotterTime
from rtlsdr_scanner.spectrum import split_spectrum_sort, Measure, reduce_points
from rtlsdr_scanner.toolbars import NavigationToolbar, NavigationToolbarCompare
from rtlsdr_scanner.utils_mpl import find_artists
from rtlsdr_scanner.utils_wx import close_modeless
from rtlsdr_scanner.widgets import GridToolTips, CheckBoxCellRenderer


class PanelGraph(wx.Panel):

    def __init__(self, panel, notify, settings, status, remoteControl):
        self.panel = panel
        self.notify = notify
        self.plot = None
        self.settings = settings
        self.status = status
        self.remoteControl = remoteControl
        self.spectrum = None
        self.isLimited = None
        self.limit = None
        self.extent = None
        self.annotate = None

        self.isDrawing = False

        self.toolTip = wx.ToolTip('')

        self.mouseSelect = None
        self.mouseZoom = None
        self.measureTable = None

        self.background = None

        self.selectStart = None
        self.selectEnd = None

        self.menuClearSelect = []

        self.measure = None
        self.show = None

        self.doDraw = False

        wx.Panel.__init__(self, panel)

        self.figure = matplotlib.figure.Figure(facecolor='white')
        self.figure.set_size_inches(0, 0)
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.canvas.SetToolTip(self.toolTip)

        self.measureTable = PanelMeasure(self, settings)

        self.toolbar = NavigationToolbar(self.canvas, self, settings,
                                         self.__hide_overlay)
        self.toolbar.Realize()

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.canvas, 1, wx.EXPAND)
        vbox.Add(self.measureTable, 0, wx.EXPAND)
        vbox.Add(self.toolbar, 0, wx.EXPAND)
        self.SetSizer(vbox)
        vbox.Fit(self)

        self.create_plot()

        self.canvas.mpl_connect('button_press_event', self.__on_press)
        self.canvas.mpl_connect('figure_enter_event', self.__on_enter)
        self.canvas.mpl_connect('axes_leave_event', self.__on_leave)
        self.canvas.mpl_connect('motion_notify_event', self.__on_motion)
        self.canvas.mpl_connect('draw_event', self.__on_draw)
        self.Bind (wx.EVT_IDLE, self.__on_idle)
        self.Bind(wx.EVT_SIZE, self.__on_size)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.__on_timer, self.timer)
  
    def __set_fonts(self):
        axes = self.plot.get_axes()
        if axes is not None:
            axes.xaxis.label.set_size('small')
            axes.yaxis.label.set_size('small')
            if self.settings.display == Display.SURFACE:
                axes.zaxis.label.set_size('small')
            axes.tick_params(axis='both', which='major', labelsize='small')
        axes = self.plot.get_axes_bar()
        if axes is not None:
            axes.tick_params(axis='both', which='major', labelsize='small')

    def __enable_menu(self, state):
        for menu in self.menuClearSelect:
            menu.Enable(state)

    def __on_press(self, event):
        if self.settings.clickTune and matplotlib.__version__ >= '1.2' and event.dblclick:
            frequency = int(event.xdata * 1e6)
            self.remoteControl.tune(frequency)
        elif isinstance(self.plot, PlotterPreview):
            self.plot.to_front()

    def __on_enter(self, _event):
        self.toolTip.Enable(False)

    def __on_leave(self, _event):
        self.toolTip.Enable(True)
        self.status.set_info('', level=None)

    def __on_motion(self, event):
        axes = self.plot.get_axes()
        axesBar = self.plot.get_axes_bar()
        xpos = event.xdata
        ypos = event.ydata
        text = ""

        if (xpos is None or ypos is None or
                self.spectrum is None or event.inaxes is None):
            spectrum = None
        elif event.inaxes == axesBar:
            spectrum = None
            level = self.plot.get_bar().norm.inverse(ypos)
            text = "{}".format(format_precision(self.settings,
                                                level=level))
        elif self.settings.display == Display.PLOT:
            timeStamp = max(self.spectrum)
            spectrum = self.spectrum[timeStamp]
        elif self.settings.display == Display.SPECT:
            timeStamp = num2epoch(ypos)
            if timeStamp in self.spectrum:
                spectrum = self.spectrum[timeStamp]
            else:
                nearest = min(self.spectrum.keys(),
                              key=lambda k: abs(k - timeStamp))
                spectrum = self.spectrum[nearest]
        elif self.settings.display == Display.SURFACE:
            spectrum = None
            coords = axes.format_coord(event.xdata,
                                       event.ydata)
            match = re.match('x=([-|0-9|\.]+).*y=([0-9|\:]+).*z=([-|0-9|\.]+)',
                             coords)
            if match is not None and match.lastindex == 3:
                freq = float(match.group(1))
                level = float(match.group(3))
                text = "{}, {}".format(*format_precision(self.settings,
                                                         freq, level))
        else:
            spectrum = None

        if spectrum is not None and len(spectrum) > 0:
            x = min(spectrum.keys(), key=lambda freq: abs(freq - xpos))
            if min(spectrum.keys(), key=float) <= xpos <= max(spectrum.keys(),
                                                              key=float):
                y = spectrum[x]
                text = "{}, {}".format(*format_precision(self.settings, x, y))
            else:
                text = format_precision(self.settings, xpos)

            markers = find_artists(self.figure, 'peak')
            markers.extend(find_artists(self.figure, 'peakThres'))
            hit = False
            for marker in markers:
                if isinstance(marker, Line2D):
                    location = marker.get_path().vertices[0]
                    markX, markY = axes.transData.transform(location)
                    dist = abs(math.hypot(event.x - markX, event.y - markY))
                    if dist <= 5:
                        if self.settings.display == Display.PLOT:
                            tip = "{}, {}".format(*format_precision(self.settings,
                                                                    location[0],
                                                                    location[1]))
                        else:
                            tip = "{}".format(format_precision(self.settings,
                                                               location[0]))
                        self.toolTip.SetTip(tip)
                        hit = True
                        break
            self.toolTip.Enable(hit)

        self.status.set_info(text, level=None)

    def __on_size(self, event):
        ppi = wx.ScreenDC().GetPPI()
        size = [float(v) for v in self.canvas.GetSize()]
        width = size[0] / ppi[0]
        height = size[1] / ppi[1]
        self.figure.set_figwidth(width)
        self.figure.set_figheight(height)
        self.figure.set_dpi(ppi[0])
        event.Skip()

    def __on_draw(self, _event):
        axes = self.plot.get_axes()
        if axes is not None:
            self.background = self.canvas.copy_from_bbox(axes.bbox)
            self.__draw_overlay()

    def __on_idle(self, _event):
        if self.doDraw and self.plot.get_plot_thread() is None:
            self.__hide_overlay()
            self.doDraw = False
            if os.name == 'nt':
                threading.Thread(target=self.__draw_canvas, name='Draw').start()
            else:
                self.__draw_canvas()

    def __on_timer(self, _event):
        self.timer.Stop()
        self.set_plot(None, None, None, None, self.annotate)

    def __draw_canvas(self):
        try:
            self.isDrawing = True
            self.canvas.draw()
        except wx.PyDeadObjectError:
            pass

        self.isDrawing = False
        wx.CallAfter(self.status.set_busy, False)

    def __draw_overlay(self):
        if self.background is not None:
            self.canvas.restore_region(self.background)
            self.__draw_select()
            self.draw_measure()
            axes = self.plot.get_axes()
            if axes is not None:
                self.canvas.blit(axes.bbox)

    def __draw_select(self):
        if self.selectStart is not None and self.selectEnd is not None:
            self.mouseSelect.draw(self.selectStart, self.selectEnd)

    def __hide_overlay(self):
        if self.plot is not None:
            self.plot.hide_measure()
        self.__hide_select()

    def __hide_select(self):
        if self.mouseSelect is not None:
            self.mouseSelect.hide()

    def create_plot(self):
        if self.plot is not None:
            self.plot.close()

        self.toolbar.set_auto(True)

        if self.settings.display == Display.PLOT:
            self.plot = Plotter(self.notify, self.figure, self.settings)
        elif self.settings.display == Display.SPECT:
            self.plot = Spectrogram(self.notify, self.figure, self.settings)
        elif self.settings.display == Display.SURFACE:
            self.plot = Plotter3d(self.notify, self.figure, self.settings)
        elif self.settings.display == Display.STATUS:
            self.plot = PlotterStatus(self.notify, self.figure, self.settings)
        elif self.settings.display == Display.TIMELINE:
            self.plot = PlotterTime(self.notify, self.figure, self.settings)
        elif self.settings.display == Display.PREVIEW:
            self.plot = PlotterPreview(self.notify, self.figure, self.settings)
            self.plot.set_window(self)

        self.__set_fonts()

        self.toolbar.set_plot(self.plot)
        self.toolbar.set_type(self.settings.display)
        self.measureTable.set_type(self.settings.display)

        self.set_plot_title()
        self.figure.subplots_adjust(top=0.85)
        self.redraw_plot()
        self.plot.scale_plot(True)
        self.mouseZoom = MouseZoom(self.toolbar, plot=self.plot,
                                   callbackHide=self.__hide_overlay)
        self.mouseSelect = MouseSelect(self.plot, self.on_select,
                                       self.on_selected)
        self.measureTable.show(self.settings.showMeasure)
        self.panel.SetFocus()

    def on_select(self):
        self.hide_measure()

    def on_selected(self, start, end):
        self.__enable_menu(True)
        self.selectStart = start
        self.selectEnd = end
        self.measureTable.set_selected(self.spectrum, start, end)

    def add_menu_clear_select(self, menu):
        self.menuClearSelect.append(menu)
        menu.Enable(False)

    def draw(self):
        self.doDraw = True

    def show_measure_table(self, show):
        self.measureTable.show(show)
        self.Layout()

    def set_plot(self, spectrum, isLimited, limit, extent, annotate=False):
        if spectrum is not None and extent is not None:
            if isLimited is not None and limit is not None:
                self.spectrum = copy.copy(spectrum)
                self.extent = extent
                self.annotate = annotate
                self.isLimited = isLimited
                self.limit = limit

        if self.plot.get_plot_thread() is None and not self.isDrawing:
            self.timer.Stop()
            self.measureTable.set_selected(self.spectrum, self.selectStart,
                                           self.selectEnd)

            if isLimited:
                self.spectrum = reduce_points(spectrum, limit)

            self.status.set_busy(True)
            self.plot.set_plot(self.spectrum, self.extent, annotate)
            if self.settings.display == Display.PREVIEW:
                self.status.set_busy(False)

        else:
            self.timer.Start(200, oneShot=True)

    def set_plot_title(self):
        if len(self.settings.devicesRtl) > 0:
            gain = self.settings.devicesRtl[self.settings.indexRtl].gain
        else:
            gain = 0
        self.plot.set_title("Frequency Spectrogram\n{} - {} MHz,"
                            " gain = {}dB".format(self.settings.start,
                                                  self.settings.stop, gain))

    def redraw_plot(self):
        if self.spectrum is not None:
            self.set_plot(self.spectrum,
                          self.settings.pointsLimit,
                          self.settings.pointsMax,
                          self.extent, self.settings.annotate)

    def set_grid(self, on):
        self.plot.set_grid(on)

    def set_selected(self, start, end):
        self.selectStart = start
        self.selectEnd = end
        self.__draw_select()

    def hide_toolbar(self, hide):
        self.toolbar.Show(not hide)

    def hide_measure(self):
        if self.plot is not None:
            self.plot.hide_measure()

    def draw_measure(self):
        if self.measure is not None and self.measure.is_valid():
            self.plot.draw_measure(self.measure, self.show)

    def update_measure(self, measure=None, show=None):
        if not measure and not show:
            self.measureTable.update_measure()
        else:
            self.measure = measure
            self.show = show
            self.__draw_overlay()

    def get_figure(self):
        return self.figure

    def get_axes(self):
        return self.plot.get_axes()

    def get_canvas(self):
        return self.canvas

    def get_toolbar(self):
        return self.toolbar

    def get_mouse_select(self):
        return self.mouseSelect

    def scale_plot(self, force=False):
        self.plot.scale_plot(force)

    def clear_plots(self):
        self.plot.clear_plots()
        self.spectrum = None
        self.doDraw = True

    def clear_selection(self):
        self.measure = None
        self.measureTable.clear_measurement()
        self.selectStart = None
        self.selectEnd = None
        self.mouseSelect.clear()
        self.__enable_menu(False)

    def close(self):
        self.plot.close()
        close_modeless()


class PanelGraphCompare(wx.Panel):

    def __init__(self, parent, callback):
        self.callback = callback

        self.spectrum1 = None
        self.spectrum2 = None
        self.spectrumDiff = None

        self.mouseZoom = None

        formatter = ScalarFormatter(useOffset=False)

        wx.Panel.__init__(self, parent)

        figure = matplotlib.figure.Figure(facecolor='white')
        figure.set_size_inches(8, 4.5)
        if matplotlib.__version__ >= '1.2':
            figure.set_tight_layout(True)

        self.axesScan = figure.add_subplot(111)
        self.axesScan.xaxis.set_minor_locator(AutoMinorLocator(10))
        self.axesScan.yaxis.set_minor_locator(AutoMinorLocator(10))
        self.axesScan.xaxis.set_major_formatter(formatter)
        self.axesScan.yaxis.set_major_formatter(formatter)
        self.axesDiff = self.axesScan.twinx()
        self.axesDiff.yaxis.set_minor_locator(AutoMinorLocator(10))
        self.plotScan1, = self.axesScan.plot([], [], 'b-',
                                                     linewidth=0.4)
        self.plotScan2, = self.axesScan.plot([], [], 'g-',
                                                     linewidth=0.4)
        self.plotDiff, = self.axesDiff.plot([], [], 'r-', linewidth=0.4)
        self.axesScan.set_ylim(auto=True)
        self.axesDiff.set_ylim(auto=True)

        self.axesScan.set_title("Level Comparison")
        self.axesScan.set_xlabel("Frequency (MHz)")
        self.axesScan.set_ylabel('Level (dB/Hz)')
        self.axesDiff.set_ylabel('Difference (dB/Hz)')

        self.canvas = FigureCanvas(self, -1, figure)

        self.set_grid(True)

        self.textIntersect = wx.StaticText(self, label="Intersections: ")

        toolbar = NavigationToolbarCompare(self)
        toolbar.Realize()
        self.mouseZoom = MouseZoom(toolbar, figure=figure)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        vbox.Add(self.textIntersect, 0, wx.EXPAND | wx.ALL, border=5)
        vbox.Add(toolbar, 0, wx.EXPAND)

        self.SetSizer(vbox)
        vbox.Fit(self)

        self.canvas.mpl_connect('motion_notify_event', self.__on_motion)
        self.canvas.mpl_connect('axes_leave_event', self.__on_leave)

    def __on_motion(self, event):
        xpos = event.xdata
        ypos = event.ydata
        if xpos is None or ypos is None:
            return

        locs = dict.fromkeys(['x1', 'y1', 'x2', 'y2', 'x3', 'y3'], None)

        if self.spectrum1 is not None and len(self.spectrum1) > 0:
            locs['x1'] = min(self.spectrum1.keys(),
                             key=lambda freq: abs(freq - xpos))
            locs['y1'] = self.spectrum1[locs['x1']]

        if self.spectrum2 is not None and len(self.spectrum2) > 0:
            locs['x2'] = min(self.spectrum2.keys(),
                             key=lambda freq: abs(freq - xpos))
            locs['y2'] = self.spectrum2[locs['x2']]

        if self.spectrumDiff is not None and len(self.spectrumDiff) > 0:
            locs['x3'] = min(self.spectrumDiff.keys(),
                             key=lambda freq: abs(freq - xpos))
            locs['y3'] = self.spectrumDiff[locs['x3']]

        self.callback(locs)

    def __on_leave(self, event):
        self.callback(None)

    def __relim(self):
        self.axesScan.relim()
        self.axesDiff.relim()

    def __plot_diff(self):
        diff = {}
        intersections = 0

        if self.spectrum1 is not None and self.spectrum2 is not None:
            set1 = set(self.spectrum1)
            set2 = set(self.spectrum2)
            intersect = set1.intersection(set2)
            intersections = len(intersect)
            for freq in intersect:
                diff[freq] = self.spectrum1[freq] - self.spectrum2[freq]
            freqs, powers = split_spectrum_sort(diff)
            self.plotDiff.set_xdata(freqs)
            self.plotDiff.set_ydata(powers)
        elif self.spectrum1 is None:
            freqs, powers = split_spectrum_sort(self.spectrum2)
            intersections = len(freqs)
            self.plotDiff.set_xdata(freqs)
            self.plotDiff.set_ydata([0] * intersections)
        else:
            freqs, powers = split_spectrum_sort(self.spectrum1)
            intersections = len(freqs)
            self.plotDiff.set_xdata(freqs)
            self.plotDiff.set_ydata([0] * intersections)

        self.spectrumDiff = diff

        self.textIntersect.SetLabel('Intersections: {}'.format(intersections))

    def get_canvas(self):
        return self.canvas

    def show_plot1(self, enable):
        self.plotScan1.set_visible(enable)
        self.canvas.draw()

    def show_plot2(self, enable):
        self.plotScan2.set_visible(enable)
        self.canvas.draw()

    def show_plotdiff(self, enable):
        self.plotDiff.set_visible(enable)
        self.canvas.draw()

    def set_spectrum1(self, spectrum):
        timeStamp = max(spectrum)
        self.spectrum1 = spectrum[timeStamp]
        freqs, powers = split_spectrum_sort(self.spectrum1)
        self.plotScan1.set_xdata(freqs)
        self.plotScan1.set_ydata(powers)
        self.__plot_diff()
        self.__relim()
        self.autoscale()

    def set_spectrum2(self, spectrum):
        timeStamp = max(spectrum)
        self.spectrum2 = spectrum[timeStamp]
        freqs, powers = split_spectrum_sort(self.spectrum2)
        self.plotScan2.set_xdata(freqs)
        self.plotScan2.set_ydata(powers)
        self.__plot_diff()
        self.__relim()
        self.autoscale()

    def set_grid(self, grid):
        self.axesScan.grid(grid)
        self.canvas.draw()

    def autoscale(self):
        self.axesScan.autoscale_view()
        self.axesDiff.autoscale_view()
        self.canvas.draw()


class PanelColourBar(wx.Panel):

    def __init__(self, parent, colourMap):
        wx.Panel.__init__(self, parent)
        dpi = wx.ScreenDC().GetPPI()[0]
        figure = matplotlib.figure.Figure(facecolor='white', dpi=dpi)
        figure.set_size_inches(200.0 / dpi, 25.0 / dpi)
        self.canvas = FigureCanvas(self, -1, figure)
        axes = figure.add_subplot(111)
        figure.subplots_adjust(0, 0, 1, 1)
        norm = Normalize(vmin=0, vmax=1)
        self.bar = ColorbarBase(axes, norm=norm, orientation='horizontal',
                                cmap=cm.get_cmap(colourMap))
        axes.xaxis.set_visible(False)

    def set_map(self, colourMap):
        self.bar.set_cmap(colourMap)
        self.bar.changed()
        self.bar.draw_all()
        self.canvas.draw()


class PanelLine(wx.Panel):

    def __init__(self, parent, colour):
        self.colour = colour

        wx.Panel.__init__(self, parent)
        self.Bind(wx.EVT_PAINT, self.__on_paint)

    def __on_paint(self, _event):
        dc = wx.BufferedPaintDC(self)
        width, height = self.GetClientSize()
        if not width or not height:
            return

        pen = wx.Pen(self.colour, 2)
        dc.SetPen(pen)
        colourBack = self.GetBackgroundColour()
        brush = wx.Brush(colourBack, wx.SOLID)
        dc.SetBackground(brush)

        dc.Clear()
        dc.DrawLine(0, height / 2., width, height / 2.)


class PanelMeasure(wx.Panel):

    def __init__(self, graph, settings):
        wx.Panel.__init__(self, graph)

        self.spectrum = None
        self.graph = graph
        self.settings = settings

        self.measure = None

        self.checked = {Measure.MIN: None,
                        Measure.MAX: None,
                        Measure.AVG: None,
                        Measure.GMEAN: None,
                        Measure.HBW: None,
                        Measure.OBW: None}

        self.selected = None

        self.SetBackgroundColour('white')

        self.grid = wxGrid.Grid(self)
        self.grid.CreateGrid(3, 19)
        self.grid.EnableEditing(True)
        self.grid.EnableDragGridSize(False)
        self.grid.SetColLabelSize(1)
        self.grid.SetRowLabelSize(1)
        self.grid.SetColMinimalAcceptableWidth(1)
        self.grid.SetColSize(2, 1)
        self.grid.SetColSize(7, 1)
        self.grid.SetColSize(11, 1)
        self.grid.SetColSize(15, 1)
        self.grid.SetMargins(0, wx.SystemSettings_GetMetric(wx.SYS_HSCROLL_Y))

        for x in range(self.grid.GetNumberRows()):
            self.grid.SetRowLabelValue(x, '')
        for y in range(self.grid.GetNumberCols()):
            self.grid.SetColLabelValue(y, '')

        for row in range(self.grid.GetNumberRows()):
            for col in range(self.grid.GetNumberCols()):
                    self.grid.SetReadOnly(row, col, True)

        self.locsDesc = {'F Start': (0, 0),
                         'F End': (1, 0),
                         'F Delta': (2, 0),
                         'P Min': (0, 4),
                         'P Max': (1, 4),
                         'P Delta': (2, 4),
                         'Mean': (0, 9),
                         'GMean': (1, 9),
                         'Flatness': (2, 9),
                         '-3dB Start': (0, 13),
                         '-3dB End': (1, 13),
                         '-3dB Delta': (2, 13),
                         'OBW Start': (0, 17),
                         'OBW End': (1, 17),
                         'OBW Delta': (2, 17)}
        self.__set_descs()

        self.locsCheck = {Measure.MIN: (0, 3), Measure.MAX: (1, 3),
                          Measure.AVG: (0, 8), Measure.GMEAN: (1, 8),
                          Measure.HBW: (0, 12),
                          Measure.OBW: (0, 16)}
        self.__set_check_editor()

        self.locsFreq = [(0, 1), (1, 1)]
        self.__set_freq_editor()

        colour = self.grid.GetBackgroundColour()
        self.grid.SetCellTextColour(2, 3, colour)
        self.grid.SetCellTextColour(2, 8, colour)
        self.grid.SetCellTextColour(1, 12, colour)
        self.grid.SetCellTextColour(2, 12, colour)
        self.grid.SetCellTextColour(1, 16, colour)
        self.grid.SetCellTextColour(2, 16, colour)

        self.__clear_checks()

        self.locsMeasure = {'start': (0, 1), 'end': (1, 1), 'deltaF': (2, 1),
                            'minFP': (0, 5), 'maxFP': (1, 5), 'deltaFP': (2, 5),
                            'minP': (0, 6), 'maxP': (1, 6), 'deltaP': (2, 6),
                            'avg': (0, 10), 'gmean': (1, 10), 'flat': (2, 10),
                            'hbwstart': (0, 14), 'hbwend': (1, 14), 'hbwdelta': (2, 14),
                            'obwstart': (0, 18), 'obwend': (1, 18), 'obwdelta': (2, 18)}

        fontCell = self.grid.GetDefaultCellFont()
        fontSize = fontCell.GetPointSize()
        fontStyle = fontCell.GetStyle()
        fontWeight = fontCell.GetWeight()
        font = wx.Font(fontSize, wx.FONTFAMILY_MODERN, fontStyle,
                       fontWeight)
        dc = wx.WindowDC(self.grid)
        dc.SetFont(font)
        widthMHz = dc.GetTextExtent('###.######')[0] * 1.2
        widthdB = dc.GetTextExtent('-##.##')[0] * 1.2
        for _desc, (_row, col) in self.locsDesc.iteritems():
            self.grid.AutoSizeColumn(col)
        for col in [1, 5, 14, 18]:
            self.grid.SetColSize(col, widthMHz)
            for row in xrange(self.grid.GetNumberRows()):
                self.grid.SetCellFont(row, col, font)
        for col in [6, 10]:
            self.grid.SetColSize(col, widthdB)
            for row in xrange(self.grid.GetNumberRows()):
                self.grid.SetCellFont(row, col, font)
        for _desc, (_row, col) in self.locsCheck.iteritems():
            self.grid.AutoSizeColumn(col)

        toolTips = {}
        toolTips[self.locsMeasure['start']] = 'Selection start (MHz)'
        toolTips[self.locsMeasure['end']] = 'Selection end (MHz)'
        toolTips[self.locsMeasure['deltaF']] = 'Selection bandwidth (MHz)'
        toolTips[self.locsMeasure['minFP']] = 'Minimum power location (MHz)'
        toolTips[self.locsMeasure['maxFP']] = 'Maximum power location (MHz)'
        toolTips[self.locsMeasure['deltaFP']] = 'Power location difference (MHz)'
        toolTips[self.locsMeasure['minP']] = 'Minimum power (dB)'
        toolTips[self.locsMeasure['maxP']] = 'Maximum power (dB)'
        toolTips[self.locsMeasure['deltaP']] = 'Power difference (dB)'
        toolTips[self.locsMeasure['avg']] = 'Mean power (dB)'
        toolTips[self.locsMeasure['gmean']] = 'Geometric mean power (dB)'
        toolTips[self.locsMeasure['flat']] = 'Spectral flatness'
        toolTips[self.locsMeasure['hbwstart']] = '-3db start location (MHz)'
        toolTips[self.locsMeasure['hbwend']] = '-3db end location (MHz)'
        toolTips[self.locsMeasure['hbwdelta']] = '-3db bandwidth (MHz)'
        toolTips[self.locsMeasure['obwstart']] = '99% start location (MHz)'
        toolTips[self.locsMeasure['obwend']] = '99% end location (MHz)'
        toolTips[self.locsMeasure['obwdelta']] = '99% bandwidth (MHz)'

        self.toolTips = GridToolTips(self.grid, toolTips)

        self.popupMenu = wx.Menu()
        self.popupMenuCopy = self.popupMenu.Append(wx.ID_ANY, "&Copy",
                                                   "Copy entry")
        self.Bind(wx.EVT_MENU, self.__on_copy, self.popupMenuCopy)

        self.Bind(wxGrid.EVT_GRID_CELL_RIGHT_CLICK, self.__on_popup_menu)
        self.Bind(wxGrid.EVT_GRID_CELL_LEFT_CLICK, self.__on_cell_click)
        if wx.VERSION >= (3, 0, 0, 0):
            self.Bind(wxGrid.EVT_GRID_CELL_CHANGED, self.__on_cell_change)

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(self.grid, 0, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT,
                border=10)
        self.SetSizer(box)

    def __set_descs(self):
        font = self.grid.GetCellFont(0, 0)
        font.SetWeight(wx.BOLD)

        for desc, (row, col) in self.locsDesc.iteritems():
            self.grid.SetCellValue(row, col, desc)
            self.grid.SetCellFont(row, col, font)

    def __set_check_editor(self):
        for _desc, (row, col) in self.locsCheck.iteritems():
            self.grid.SetCellEditor(row, col, wxGrid.GridCellBoolEditor())
            self.grid.SetCellAlignment(row, col, wx.ALIGN_RIGHT, wx.ALIGN_CENTRE)
            self.grid.SetCellRenderer(row, col, CheckBoxCellRenderer(self))

    def __set_freq_editor(self):
        for (row, col) in self.locsFreq:
            self.grid.SetReadOnly(row, col, False)
            self.grid.SetCellAlignment(row, col, wx.ALIGN_RIGHT, wx.ALIGN_CENTRE)
            self.grid.SetCellEditor(row, col, wxGrid.GridCellFloatEditor(precision=4))

    def __set_check_value(self, cell, value):
        (row, col) = self.locsCheck[cell]
        self.grid.SetCellValue(row, col, value)

    def __set_measure_value(self, cell, value):
        (row, col) = self.locsMeasure[cell]
        try:
            self.grid.SetCellValue(row, col, value)
        except TypeError:
            pass

    def __set_check_enable(self, cell, enable):
        (row, col) = self.locsCheck[cell]
        renderer = self.grid.GetCellRenderer(row, col)
        renderer.Enable(not enable)

    def __get_checks(self):
        checks = {}
        for cell in self.checked:
            if self.checked[cell] == '1':
                checks[cell] = True
            else:
                checks[cell] = False

        return checks

    def __update_checks(self):
        for cell in self.checked:
            self.__set_check_value(cell, self.checked[cell])

    def __clear_checks(self):
        for cell in self.checked:
            self.checked[cell] = '0'
        self.__update_checks()

    def __on_cell_click(self, event):
        self.grid.ClearSelection()
        row = event.GetRow()
        col = event.GetCol()

        if (row, col) in self.locsCheck.values():
            if self.grid.GetCellRenderer(row, col).enabled and self.measure is not None:
                check = self.grid.GetCellValue(row, col)
                if check == '1':
                    check = '0'
                else:
                    check = '1'
                self.grid.SetCellValue(row, col, check)

                for control, (r, c) in self.locsCheck.iteritems():
                    if (r, c) == (row, col):
                        self.checked[control] = check

                if self.selected is None:
                    self.selected = self.locsMeasure['start']
                    row = self.selected[0]
                    col = self.selected[1]
                    self.grid.SetGridCursor(row, col)
                self.update_measure()
        elif (row, col) in self.locsMeasure.itervalues():
            self.selected = (row, col)
            self.grid.SetGridCursor(row, col)
        elif self.selected is None:
            self.selected = self.locsMeasure['start']
            row = self.selected[0]
            col = self.selected[1]
            self.grid.SetGridCursor(row, col)

    def __on_cell_change(self, event):
        row = event.GetRow()
        col = event.GetCol()

        if (row, col) in self.locsFreq:
            start = None
            end = None

            try:
                start = float(self.grid.GetCellValue(self.locsFreq[0][0], self.locsFreq[0][1]))
            except ValueError:
                pass
            try:
                end = float(self.grid.GetCellValue(self.locsFreq[1][0], self.locsFreq[1][1]))
            except ValueError:
                pass

            if start is None and end is None:
                return
            elif start is None and end is not None:
                start = end - 1
            elif start is not None and end is None:
                end = start + 1
            if start > end:
                swap = start
                start = end
                end = swap

            self.graph.set_selected(start, end)
            self.set_selected(self.spectrum, start, end)

    def __on_popup_menu(self, _event):
        if self.selected:
            self.popupMenuCopy.Enable(True)
        else:
            self.popupMenuCopy.Enable(False)
        self.PopupMenu(self.popupMenu)

    def __on_copy(self, _event):
        value = self.grid.GetCellValue(self.selected[0], self.selected[1])
        clip = wx.TextDataObject(value)
        wx.TheClipboard.Open()
        wx.TheClipboard.SetData(clip)
        wx.TheClipboard.Close()

    def update_measure(self):
        show = self.__get_checks()
        self.graph.update_measure(self.measure, show)

    def clear_measurement(self):
        for control in self.locsMeasure:
            self.__set_measure_value(control, "")
        self.__clear_checks()
        self.update_measure()
        self.measure = None

    def set_selected(self, spectrum, start, end):
        self.spectrum = spectrum
        if start is None:
            return

        self.measure = Measure(spectrum, start, end)
        if not self.measure.is_valid():
            self.clear_measurement()
            return

        minF, maxF = self.measure.get_f()
        minP = self.measure.get_min_p()
        maxP = self.measure.get_max_p()
        avgP = self.measure.get_avg_p()
        gMeanP = self.measure.get_gmean_p()
        flatness = self.measure.get_flatness()
        hbw = self.measure.get_hpw()
        obw = self.measure.get_obw()

        self.__set_measure_value('start',
                                 format_precision(self.settings,
                                                  minF,
                                                  units=False))
        self.__set_measure_value('end',
                                 format_precision(self.settings,
                                                  maxF,
                                                  units=False))
        self.__set_measure_value('deltaF',
                                 format_precision(self.settings,
                                                  maxF - minF,
                                                  units=False))
        self.__set_measure_value('minFP',
                                 format_precision(self.settings,
                                                  minP[0],
                                                  units=False))
        self.__set_measure_value('maxFP',
                                 format_precision(self.settings,
                                                  maxP[0],
                                                  units=False))
        self.__set_measure_value('deltaFP',
                                 format_precision(self.settings,
                                                  maxP[0] - minP[0],
                                                  units=False))
        self.__set_measure_value('minP',
                                 format_precision(self.settings,
                                                  level=minP[1],
                                                  units=False))
        self.__set_measure_value('maxP',
                                 format_precision(self.settings,
                                                  level=maxP[1],
                                                  units=False))
        self.__set_measure_value('deltaP',
                                 format_precision(self.settings,
                                                  level=maxP[1] - minP[1],
                                                  units=False))
        self.__set_measure_value('avg',
                                 format_precision(self.settings,
                                                  level=avgP,
                                                  units=False))
        self.__set_measure_value('gmean',
                                 format_precision(self.settings,
                                                  level=gMeanP,
                                                  units=False))
        self.__set_measure_value('flat',
                                 "{0:.4f}".format(flatness))

        if hbw[0] is not None:
            text = format_precision(self.settings, hbw[0], units=False)
        else:
            text = ''
        self.__set_measure_value('hbwstart', text)
        if hbw[1] is not None:
            text = format_precision(self.settings, hbw[1], units=False)
        else:
            text = ''
        self.__set_measure_value('hbwend', text)
        if hbw[0] is not None and hbw[1] is not None:
            text = format_precision(self.settings, hbw[1] - hbw[0], units=False)
        else:
            text = ''
        self.__set_measure_value('hbwdelta', text)

        if obw[0] is not None:
            text = format_precision(self.settings, obw[0], units=False)
        else:
            text = ''
        self.__set_measure_value('obwstart', text)
        if obw[1] is not None:
            text = text = format_precision(self.settings, obw[1], units=False)
        else:
            text = ''
        self.__set_measure_value('obwend', text)
        if obw[0] is not None and obw[1] is not None:
            text = text = format_precision(self.settings, obw[1] - obw[0],
                                           units=False)
        else:
            text = ''
        self.__set_measure_value('obwdelta', text)

        self.update_measure()

    def show(self, show):
        if show:
            self.Show()
        else:
            self.Hide()
        self.Layout()

    def set_type(self, display):
        for cell in self.locsCheck:
            self.__set_check_enable(cell, True)
        if display == Display.PLOT:
            for cell in self.locsCheck:
                self.__set_check_enable(cell, False)
        elif display == Display.SPECT:
            self.__set_check_enable(Measure.HBW, False)
            self.__set_check_enable(Measure.OBW, False)

        self.grid.Refresh()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
