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

import copy

from matplotlib import cm
import matplotlib
from matplotlib.backends.backend_wxagg import \
    FigureCanvasWxAgg as FigureCanvas
from matplotlib.colorbar import ColorbarBase
from matplotlib.colors import Normalize
from matplotlib.ticker import AutoMinorLocator, ScalarFormatter
import wx

from constants import Display
from misc import  close_modeless
from plot import Plotter
from plot3d import Plotter3d
from plot_controls import MouseZoom, MouseSelect
from spectrogram import Spectrogram
from spectrum import split_spectrum_sort, Measure, reduce_points
from toolbars import NavigationToolbar, NavigationToolbarCompare
import wx.grid as wxGrid


class CellRenderer(wxGrid.PyGridCellRenderer):
    def __init__(self):
        wxGrid.PyGridCellRenderer.__init__(self)

    def Draw(self, grid, attr, dc, rect, row, col, _isSelected):
        dc.SetBrush(wx.Brush(attr.GetBackgroundColour()))
        dc.DrawRectangleRect(rect)
        if grid.GetCellValue(row, col) == "1":
            dc.SetBrush(wx.Brush(attr.GetTextColour()))
            dc.DrawCircle(rect.x + (rect.width / 2),
                          rect.y + (rect.height / 2),
                          rect.height / 4)


# Based on http://wiki.wxpython.org/wxGrid%20ToolTips
class GridToolTips():
    def __init__(self, grid, toolTips):
        self.lastPos = (None, None)
        self.grid = grid
        self.toolTips = toolTips

        grid.GetGridWindow().Bind(wx.EVT_MOTION, self.on_motion)

    def on_motion(self, event):
        x, y = self.grid.CalcUnscrolledPosition(event.GetPosition())
        row = self.grid.YToRow(y)
        col = self.grid.XToCol(x)

        if (row, col) != self.lastPos:
            if row >= 0 and col >= 0:
                self.lastPos = (row, col)
                if (row, col) in self.toolTips:
                    toolTip = self.toolTips[(row, col)]
                else:
                    toolTip = ''
                self.grid.GetGridWindow().SetToolTipString(toolTip)


class PanelGraph(wx.Panel):
    def __init__(self, panel, notify, settings, callbackMotion):
        self.panel = panel
        self.notify = notify
        self.plot = None
        self.settings = settings
        self.spectrum = None
        self.isLimited = None
        self.limit = None
        self.extent = None

        self.background = None

        self.selectStart = None
        self.selectEnd = None

        self.menuClearSelect = []

        self.measure = None
        self.show = None

        self.doDraw = False

        wx.Panel.__init__(self, panel)

        self.figure = matplotlib.figure.Figure(facecolor='white')
        self.canvas = FigureCanvas(self, -1, self.figure)

        self.measureTable = PanelMeasure(self)

        self.toolbar = NavigationToolbar(self.canvas, self, settings,
                                         self.on_nav_changed)
        self.toolbar.Realize()

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.canvas, 1, wx.EXPAND)
        vbox.Add(self.measureTable, 0, wx.EXPAND)
        vbox.Add(self.toolbar, 0, wx.EXPAND)
        self.SetSizer(vbox)
        vbox.Fit(self)

        self.create_plot()

        self.canvas.mpl_connect('motion_notify_event', callbackMotion)
        self.canvas.mpl_connect('draw_event', self.on_draw)
        self.canvas.mpl_connect('idle_event', self.on_idle)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)

    def create_plot(self):
        if self.plot is not None:
            self.plot.close()

        if self.settings.display == Display.PLOT:
            self.plot = Plotter(self.notify, self.figure, self.settings)
        elif self.settings.display == Display.SPECT:
            self.plot = Spectrogram(self.notify, self.figure, self.settings)
        else:
            self.plot = Plotter3d(self.notify, self.figure, self.settings)

        self.toolbar.set_plot(self.plot)
        self.toolbar.set_type(self.settings.display)
        self.measureTable.set_type(self.settings.display)

        self.set_plot_title()
        self.redraw_plot()
        self.plot.scale_plot(True)
        self.mouseZoom = MouseZoom(self.plot, self.toolbar, self.hide_measure,
                                   self.draw_measure)
        self.mouseSelect = MouseSelect(self.plot, self.on_select,
                                       self.on_selected)
        self.clear_selection()
        self.measureTable.show(self.settings.showMeasure)
        self.panel.SetFocus()

    def add_menu_clear_select(self, menu):
        self.menuClearSelect.append(menu)
        menu.Enable(False)

    def enable_menu(self, state):
        for menu in self.menuClearSelect:
            menu.Enable(state)

    def on_draw(self, _event):
        axes = self.plot.get_axes()
        self.background = self.canvas.copy_from_bbox(axes.bbox)
        self.mouseSelect.set_background(self.background)
        self.draw_measure()

    def on_nav_changed(self, _event):
        self.draw_measure()

    def on_select(self):
        self.hide_measure()

    def on_selected(self, start, end):
        self.enable_menu(True)
        self.on_draw(None)
        self.selectStart = start
        self.selectEnd = end
        self.measureTable.set_selected(self.spectrum, start, end)
        self.draw_measure()

    def on_idle(self, _event):
        if self.doDraw and self.plot.get_plot_thread() is None:
            self.canvas.draw()
            self.doDraw = False

    def on_timer(self, _event):
        self.timer.Stop()
        self.set_plot(None, None, None, None, self.annotate)

    def draw(self):
        self.doDraw = True

    def show_measureTable(self, show):
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

        if self.plot.get_plot_thread() is None:
            self.timer.Stop()
            self.measureTable.set_selected(spectrum, self.selectStart,
                                           self.selectEnd)
            if isLimited:
                spectrum = reduce_points(spectrum, limit)
            self.plot.set_plot(spectrum, extent, annotate)

            self.draw_select()
        else:
            self.timer.Start(200, oneShot=True)

    def set_plot_title(self):
        if len(self.settings.devices) > 0:
            gain = self.settings.devices[self.settings.index].gain
        else:
            gain = 0
        self.figure.suptitle("Frequency Spectrogram\n{0} - {1} MHz,"
                             " gain = {2}dB".format(self.settings.start,
                                                    self.settings.stop, gain))

    def redraw_plot(self):
        if self.spectrum is not None:
            self.set_plot(self.spectrum,
                          self.settings.pointsLimit,
                          self.settings.pointsMax,
                          self.extent, self.settings.annotate)

    def draw_select(self):
        if self.selectStart is not None and self.selectEnd is not None:
            self.mouseSelect.draw(self.selectStart, self.selectEnd)

    def hide_measure(self):
        self.plot.hide_measure()

    def draw_measure(self):
        if self.measure is not None and self.background is not None:
            self.plot.draw_measure(self.background, self.measure, self.show)

    def update_measure(self, measure, show):
        self.measure = measure
        self.show = show
        self.draw_measure()

    def get_figure(self):
        return self.figure

    def get_axes(self):
        return self.plot.get_axes()

    def get_canvas(self):
        return self.canvas

    def get_toolbar(self):
        return self.toolbar

    def scale_plot(self, force=False):
        self.plot.scale_plot(force)

    def clear_plots(self):
        self.plot.clear_plots()

    def clear_selection(self):
        self.measure = None
        self.measureTable.clear_measurement()
        self.selectStart = None
        self.selectEnd = None
        self.mouseSelect.clear()
        self.enable_menu(False)

    def close(self):
        close_modeless()


class PanelGraphCompare(wx.Panel):
    def __init__(self, parent):

        self.spectrum1 = None
        self.spectrum2 = None

        formatter = ScalarFormatter(useOffset=False)

        wx.Panel.__init__(self, parent)

        figure = matplotlib.figure.Figure(facecolor='white')

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
        self.axesScan.set_ylabel('Level (dB)')
        self.axesDiff.set_ylabel('Difference (db)')

        self.canvas = FigureCanvas(self, -1, figure)

        self.check1 = wx.CheckBox(self, wx.ID_ANY, "Scan 1")
        self.check2 = wx.CheckBox(self, wx.ID_ANY, "Scan 2")
        self.checkDiff = wx.CheckBox(self, wx.ID_ANY, "Difference")
        self.check1.SetValue(True)
        self.check2.SetValue(True)
        self.checkDiff.SetValue(True)
        self.set_grid(True)
        self.Bind(wx.EVT_CHECKBOX, self.on_check1, self.check1)
        self.Bind(wx.EVT_CHECKBOX, self.on_check2, self.check2)
        self.Bind(wx.EVT_CHECKBOX, self.on_check_diff, self.checkDiff)

        self.textIntersect = wx.StaticText(self, label="Intersections: ")

        grid = wx.GridBagSizer(5, 5)
        grid.Add(self.check1, pos=(0, 0), flag=wx.ALIGN_CENTRE)
        grid.Add(self.check2, pos=(0, 1), flag=wx.ALIGN_CENTRE)
        grid.Add((20, 1), pos=(0, 2))
        grid.Add(self.checkDiff, pos=(0, 3), flag=wx.ALIGN_CENTRE)
        grid.Add((20, 1), pos=(0, 4))
        grid.Add((20, 1), pos=(0, 5))
        grid.Add(self.textIntersect, pos=(0, 6), span=(1, 1))

        toolbar = NavigationToolbarCompare(self)
        toolbar.Realize()

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        vbox.Add(grid, 0, wx.EXPAND | wx.ALL, border=5)
        vbox.Add(toolbar, 0, wx.EXPAND)

        self.SetSizer(vbox)
        vbox.Fit(self)

    def on_check1(self, _event):
        self.plotScan1.set_visible(self.check1.GetValue())
        self.canvas.draw()

    def on_check2(self, _event):
        self.plotScan2.set_visible(self.check2.GetValue())
        self.canvas.draw()

    def on_check_diff(self, _event):
        self.plotDiff.set_visible(self.checkDiff.GetValue())
        self.canvas.draw()

    def set_grid(self, grid):
        self.axesDiff.grid(grid)
        self.canvas.draw()

    def get_canvas(self):
        return self.canvas

    def plot_diff(self):
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

        if intersections > 0:
            self.axesDiff.relim()
        self.textIntersect.SetLabel('Intersections: {0}'.format(intersections))

    def set_spectrum1(self, spectrum):
        timeStamp = max(spectrum)
        self.spectrum1 = spectrum[timeStamp]
        freqs, powers = split_spectrum_sort(self.spectrum1)
        self.plotScan1.set_xdata(freqs)
        self.plotScan1.set_ydata(powers)
        self.axesScan.relim()
        self.plot_diff()
        self.autoscale()

    def set_spectrum2(self, spectrum):
        timeStamp = max(spectrum)
        self.spectrum2 = spectrum[timeStamp]
        freqs, powers = split_spectrum_sort(self.spectrum2)
        self.plotScan2.set_xdata(freqs)
        self.plotScan2.set_ydata(powers)
        self.axesScan.relim()
        self.plot_diff()
        self.autoscale()

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


class PanelMeasure(wx.Panel):
    def __init__(self, graph):
        wx.Panel.__init__(self, graph)

        self.graph = graph

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
        self.grid.EnableEditing(False)
        self.grid.EnableDragGridSize(False)
        self.grid.SetColLabelSize(1)
        self.grid.SetRowLabelSize(1)
        self.grid.SetColMinimalAcceptableWidth(1)
        self.grid.SetColSize(2, 1)
        self.grid.SetColSize(7, 1)
        self.grid.SetColSize(11, 1)
        self.grid.SetColSize(15, 1)
        self.grid.SetMargins(0, wx.SystemSettings_GetMetric(wx.SYS_HSCROLL_Y))

        for x in xrange(self.grid.GetNumberRows()):
            self.grid.SetRowLabelValue(x, '')
        for y in xrange(self.grid.GetNumberCols()):
            self.grid.SetColLabelValue(y, '')

        self.locsDesc = {'Start': (0, 0),
                         'End': (1, 0),
                         u'\u0394': (2, 0),
                         u'Min': (0, 4),
                         u'Max': (1, 4),
                         u'\u0394': (2, 4),
                         u'Mean': (0, 9),
                         u'GMean': (1, 9),
                         u'Flatness': (2, 9),
                         u'-3dB Start': (0, 13),
                         u'-3dB End': (1, 13),
                         u'-3dB \u0394': (2, 13),
                         u'OBW Start': (0, 17),
                         u'OBW End': (1, 17),
                         u'OBW \u0394': (2, 17)}
        self.set_descs()

        self.locsCheck = {Measure.MIN: (0, 3), Measure.MAX: (1, 3),
                          Measure.AVG: (0, 8), Measure.GMEAN: (1, 8),
                          Measure.HBW: (0, 12),
                          Measure.OBW: (0, 16)}
        self.set_check_editor()

        colour = self.grid.GetBackgroundColour()
        self.grid.SetCellTextColour(2, 3, colour)
        self.grid.SetCellTextColour(2, 8, colour)
        self.grid.SetCellTextColour(1, 12, colour)
        self.grid.SetCellTextColour(2, 12, colour)
        self.grid.SetCellTextColour(1, 16, colour)
        self.grid.SetCellTextColour(2, 16, colour)

        self.clear_checks()

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
        self.Bind(wx.EVT_MENU, self.on_copy, self.popupMenuCopy)

        self.Bind(wxGrid.EVT_GRID_CELL_RIGHT_CLICK, self.on_popup_menu)
        self.Bind(wxGrid.EVT_GRID_CELL_LEFT_CLICK, self.on_cell_click)

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(self.grid, 0, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT,
                border=10)
        self.SetSizer(box)

    def set_descs(self):
        font = self.grid.GetCellFont(0, 0)
        font.SetWeight(wx.BOLD)

        for desc, (row, col) in self.locsDesc.iteritems():
            self.grid.SetCellValue(row, col, desc)
            self.grid.SetCellFont(row, col, font)

    def set_check_editor(self):
        editor = wxGrid.GridCellBoolEditor()
        for _desc, (row, col) in self.locsCheck.iteritems():
            self.grid.SetCellEditor(row, col, editor)
            self.grid.SetCellAlignment(row, col, wx.ALIGN_RIGHT, wx.ALIGN_CENTRE)
            self.grid.SetColFormatBool(col)

    def set_check_value(self, cell, value):
        (row, col) = self.locsCheck[cell]
        self.grid.SetCellValue(row, col, value)

    def set_measure_value(self, cell, value):
        (row, col) = self.locsMeasure[cell]
        self.grid.SetCellValue(row, col, value)

    def set_check_read_only(self, cell, readOnly):
        (row, col) = self.locsCheck[cell]
        self.grid.SetReadOnly(row, col, readOnly)
        if readOnly:
            colour = 'grey'
        else:
            colour = self.grid.GetDefaultCellTextColour()

        self.grid.SetCellTextColour(row, col, colour)

    def get_checks(self):
        checks = {}
        for cell in self.checked:
            if self.checked[cell] == '1':
                checks[cell] = True
            else:
                checks[cell] = False

        return checks

    def update_checks(self):
        for cell in self.checked:
            self.set_check_value(cell, self.checked[cell])

    def clear_checks(self):
        for cell in self.checked:
            self.checked[cell] = '0'
        self.update_checks()

    def on_cell_click(self, event):
        self.grid.ClearSelection()
        row = event.GetRow()
        col = event.GetCol()

        if (row, col) in self.locsCheck.values():
            if not self.grid.IsReadOnly(row, col) and self.measure is not None:
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

    def on_popup_menu(self, _event):
        if self.selected:
            self.popupMenuCopy.Enable(True)
        else:
            self.popupMenuCopy.Enable(False)
        self.PopupMenu(self.popupMenu)

    def on_copy(self, _event):
        value = self.grid.GetCellValue(self.selected[0], self.selected[1])
        clip = wx.TextDataObject(value)
        wx.TheClipboard.Open()
        wx.TheClipboard.SetData(clip)
        wx.TheClipboard.Close()

    def update_measure(self):
        show = self.get_checks()
        self.graph.update_measure(self.measure, show)

    def clear_measurement(self):
        self.clear_checks()
        for control in self.locsMeasure:
                    self.set_measure_value(control, "")
        self.update_measure()
        self.measure = None

    def set_selected(self, spectrum, start, end):
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

        self.set_measure_value('start',
                               "{0:10.6f}".format(minF))
        self.set_measure_value('end',
                               "{0:10.6f}".format(maxF))
        self.set_measure_value('deltaF',
                               "{0:10.6f}".format(maxF - minF))

        self.set_measure_value('minFP',
                               "{0:10.6f}".format(minP[0]))
        self.set_measure_value('maxFP',
                               "{0:10.6f}".format(maxP[0]))
        self.set_measure_value('deltaFP',
                               "{0:10.6f}".format(maxP[0] - minP[0]))
        self.set_measure_value('minP',
                               "{0:6.2f}".format(minP[1]))
        self.set_measure_value('maxP',
                               "{0:6.2f}".format(maxP[1]))
        self.set_measure_value('deltaP',
                               "{0:6.2f}".format(maxP[1] - minP[1]))

        self.set_measure_value('avg',
                               "{0:6.2f}".format(avgP))
        self.set_measure_value('gmean',
                               "{0:6.2f}".format(gMeanP))
        self.set_measure_value('flat',
                               "{0:.4f}".format(flatness))

        if hbw[0] is not None:
            text = "{0:10.6f}".format(hbw[0])
        else:
            text = ''
        self.set_measure_value('hbwstart', text)
        if hbw[1] is not None:
            text = "{0:10.6f}".format(hbw[1])
        else:
            text = ''
        self.set_measure_value('hbwend', text)
        if hbw[0] is not None and hbw[1] is not None:
            text = "{0:10.6f}".format(hbw[1] - hbw[0])
        else:
            text = ''
        self.set_measure_value('hbwdelta', text)

        if obw[0] is not None:
            text = "{0:10.6f}".format(obw[0])
        else:
            text = ''
        self.set_measure_value('obwstart', text)
        if obw[1] is not None:
            text = "{0:10.6f}".format(obw[1])
        else:
            text = ''
        self.set_measure_value('obwend', text)
        if obw[0] is not None and obw[1] is not None:
            text = "{0:10.6f}".format(obw[1] - obw[0])
        else:
            text = ''
        self.set_measure_value('obwdelta', text)

        self.update_measure()

    def show(self, show):
        if show:
            self.Show()
        else:
            self.Hide()
        self.Layout()

    def set_type(self, display):
        for cell in self.locsCheck:
                self.set_check_read_only(cell, True)
        if display == Display.PLOT:
            for cell in self.locsCheck:
                self.set_check_read_only(cell, False)
        elif display == Display.SPECT:
            self.set_check_read_only(Measure.HBW, False)
            self.set_check_read_only(Measure.OBW, False)

        self.grid.Refresh()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
