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
from spectrum import split_spectrum_sort, slice_spectrum, Measure
from toolbars import NavigationToolbar, NavigationToolbarCompare
import wx.grid as grid


class CellRenderer(grid.PyGridCellRenderer):
    def __init__(self):
        grid.PyGridCellRenderer.__init__(self)

    def Draw(self, grid, attr, dc, rect, row, col, _isSelected):
        dc.SetBrush(wx.Brush(attr.GetBackgroundColour()))
        dc.DrawRectangleRect(rect)
        if grid.GetCellValue(row, col) == "1":
            dc.SetBrush(wx.Brush(attr.GetTextColour()))
            dc.DrawCircle(rect.x + (rect.width / 2),
                          rect.y + (rect.height / 2),
                          rect.height / 4)


class PanelGraph(wx.Panel):
    def __init__(self, panel, notify, settings, lock, callbackMotion):
        self.panel = panel
        self.notify = notify
        self.plot = None
        self.settings = settings
        self.lock = lock
        self.spectrum = None
        self.extent = None

        self.selectStart = None
        self.selectEnd = None

        self.measure = None
        self.showMinP = None
        self.showMaxP = None
        self.showAvgP = None

        wx.Panel.__init__(self, panel)

        self.figure = matplotlib.figure.Figure(facecolor='white')
        self.canvas = FigureCanvas(self, -1, self.figure)

        self.measureTable = PanelMeasure(self)

        self.toolbar = NavigationToolbar(self.canvas, self, settings)
        self.toolbar.Realize()

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.canvas, 1, wx.EXPAND | wx.ALL)
        vbox.Add(self.measureTable, 0, wx.EXPAND | wx.ALL)
        vbox.Add(self.toolbar, 0, wx.EXPAND | wx.ALL)
        self.SetSizer(vbox)
        vbox.Fit(self)

        self.create_plot()

        self.canvas.mpl_connect('motion_notify_event', callbackMotion)
        self.canvas.mpl_connect('draw_event', self.on_draw)

        self.get_axes().callbacks.connect('xlim_changed', self.on_changed)
        self.get_axes().callbacks.connect('ylim_changed', self.on_changed)

    def create_plot(self):
        if self.plot is not None:
            self.plot.close()

        if self.settings.display == Display.PLOT:
            self.plot = Plotter(self.notify, self.figure, self.settings,
                                self.lock)
        elif self.settings.display == Display.SPECT:
            self.plot = Spectrogram(self.notify, self.figure, self.settings,
                                    self.lock)
        else:
            self.plot = Plotter3d(self.notify, self.figure, self.settings,
                                  self.lock)

        self.toolbar.set_plot(self.plot)
        self.toolbar.set_type(self.settings.display)
        self.measureTable.set_type(self.settings.display)

        self.set_plot_title()
        self.redraw_plot()
        self.plot.scale_plot(True)
        self.mouseZoom = MouseZoom(self.plot, self.toolbar, self.hide_measure,
                                   self.draw_measure)
        self.mouseSelect = MouseSelect(self.plot, self.on_select)
        self.measureTable.show(self.settings.showMeasure)
        self.panel.SetFocus()

    def on_draw(self, _event):
        axes = self.plot.get_axes()
        self.background = self.canvas.copy_from_bbox(axes.bbox)

    def on_changed(self, _event):
        self.draw_measure()

    def on_select(self, start, end):
        self.on_draw(None)
        self.selectStart = start
        self.selectEnd = end
        self.measureTable.set_selected(self.spectrum, start, end)
        self.draw_measure()

    def show_measureTable(self, show):
        self.measureTable.show(show)
        self.Layout()

    def set_plot(self, spectrum, extent, annotate=False):
        self.spectrum = spectrum
        self.extent = extent
        self.plot.set_plot(spectrum, extent, annotate)
        self.measureTable.set_selected(spectrum, self.selectStart,
                                       self.selectEnd)

    def set_plot_title(self):
        if len(self.settings.devices) > 0:
            gain = self.settings.devices[self.settings.index].gain
        else:
            gain = 0
        self.plot.set_title("Frequency Spectrogram\n{0} - {1} MHz,"
                            " gain = {2}dB".format(self.settings.start,
                                                   self.settings.stop, gain))

    def redraw_plot(self):
        if self.spectrum is not None:
            self.set_plot(self.spectrum, self.extent, self.settings.annotate)

    def draw_select(self):
        if self.selectStart is not None and self.selectEnd is not None:
            self.mouseSelect.draw(self.selectStart, self.selectEnd)

    def hide_measure(self):
        self.plot.hide_measure()

    def draw_measure(self):
        if self.measure is not None and self.background is not None:
            self.plot.draw_measure(self.background,
                                   self.measure,
                                   self.showMinP,
                                   self.showMaxP,
                                   self.showAvgP)

    def set_measure(self, measure, showMinP, showMaxP, showAvgP):
        self.measure = measure
        self.showMinP = showMinP
        self.showMaxP = showMaxP
        self.showAvgP = showAvgP

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
        vbox.Add(grid, 0, wx.ALIGN_CENTRE | wx.ALL, border=5)
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

        self.checkMin = '0'
        self.checkMax = '0'
        self.checkAvg = '0'

        self.selected = None

        self.SetBackgroundColour('white')

        self.grid = grid.Grid(self)
        self.grid.CreateGrid(3, 9)
        self.grid.EnableEditing(False)
        self.grid.EnableDragGridSize(False)
        self.grid.SetColLabelSize(0)
        self.grid.SetRowLabelSize(0)

        self.locsCheck = {'min': (0, 2), 'max': (1, 2), 'avg': (0, 6)}
        checkEditor = grid.GridCellBoolEditor()
        self.set_check_editor('min', checkEditor)
        self.set_check_editor('max', checkEditor)
        self.set_check_editor('avg', checkEditor)

        colour = self.grid.GetBackgroundColour()
        self.grid.SetCellTextColour(2, 2, colour)
        self.grid.SetCellTextColour(1, 6, colour)
        self.grid.SetCellTextColour(2, 6, colour)

        self.set_check_value('min', self.checkMin)
        self.set_check_value('max', self.checkMax)
        self.set_check_value('avg', self.checkAvg)

        self.grid.SetColFormatBool(2)
        self.grid.SetColFormatBool(6)

        self.grid.SetCellValue(0, 0, 'Start')
        self.grid.SetCellValue(1, 0, 'End')
        self.grid.SetCellValue(2, 0, u'\u0394')
        self.grid.SetCellValue(0, 3, 'Min')
        self.grid.SetCellValue(1, 3, 'Max')
        self.grid.SetCellValue(2, 3, u'\u0394')
        self.grid.SetCellValue(0, 7, 'Avg')

        self.locsMeasure = {'start': (0, 1), 'end': (1, 1), 'deltaF': (2, 1),
                            'minFP': (0, 4), 'maxFP': (1, 4), 'deltaFP': (2, 4),
                            'minP': (0, 5), 'maxP': (1, 5), 'deltaP': (2, 5),
                            'avg': (0, 8)}

        font = self.grid.GetCellFont(0, 0)
        font.SetWeight(wx.BOLD)
        for x in [0, 3, 7]:
            for y in xrange(self.grid.GetNumberRows()):
                self.grid.SetCellFont(y, x, font)

        for x in [0, 2, 3, 6, 7]:
            self.grid.AutoSizeColumn(x)

        self.popupMenu = wx.Menu()
        self.popupMenuCopy = self.popupMenu.Append(wx.ID_ANY, "&Copy",
                                                   "Copy entry")
        self.Bind(wx.EVT_MENU, self.on_copy, self.popupMenuCopy)

        self.Bind(grid.EVT_GRID_CELL_RIGHT_CLICK, self.on_popup_menu,
                  self.grid)
        self.Bind(grid.EVT_GRID_RANGE_SELECT, self.on_select_range,
                  self.grid)
        self.Bind(grid.EVT_GRID_CELL_LEFT_CLICK, self.on_cell_click)

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(self.grid, 1, wx.ALIGN_CENTER)
        self.SetSizer(box)

    def set_check_editor(self, cell, editor):
        (row, col) = self.locsCheck[cell]
        self.grid.SetCellEditor(row, col, editor)

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
        self.grid.Refresh()

    def str_to_bool(self, string):
        if string == '1':
            return True
        return False

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
                        if control == 'min':
                            self.checkMin = check
                            break
                        elif control == 'max':
                            self.checkMax = check
                            break
                        elif control == 'avg':
                            self.checkAvg = check
                            break

                if self.selected is None:
                    self.selected = self.locsMeasure['start']
                    row = self.selected[0]
                    col = self.selected[1]
                    self.grid.SetGridCursor(row, col)
                self.update_plot()

        elif (row, col) in self.locsMeasure.itervalues():
            self.selected = (row, col)
            self.grid.SetGridCursor(row, col)
        else:
            self.selected = self.locsMeasure['start']
            row = self.selected[0]
            col = self.selected[1]
            self.grid.SetGridCursor(row, col)

    def on_select_range(self, _event):
        self.selected = None

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

    def update_plot(self):
        minP = self.str_to_bool(self.checkMin)
        maxP = self.str_to_bool(self.checkMax)
        avgP = self.str_to_bool(self.checkAvg)
        self.graph.set_measure(self.measure, minP, maxP, avgP)

    def set_selected(self, spectrum, start, end):
        sweep = slice_spectrum(spectrum, start, end)
        if sweep is None or len(sweep) == 0:
            for control in self.locsMeasure:
                self.set_measure_value(control, "")
            return

        minF = min(sweep)[0]
        maxF = max(sweep)[0]
        minP = min(sweep, key=lambda v: v[1])
        maxP = max(sweep, key=lambda v: v[1])
        avg = sum((v[1] for v in sweep), 0.0) / len(sweep)

        self.set_measure_value('start',
                               "{0:.6f} MHz".format(minF))
        self.set_measure_value('end',
                               "{0:.6f} MHz".format(maxF))
        self.set_measure_value('deltaF',
                               "{0:.6f} MHz".format(maxF - minF))
        self.set_measure_value('minFP',
                               "{0:.6f} MHz".format(minP[0]))
        self.set_measure_value('maxFP',
                               "{0:.6f} MHz".format(maxP[0]))
        self.set_measure_value('deltaFP',
                               "{0:.6f} MHz".format(maxP[0] - minP[0]))
        self.set_measure_value('minP',
                               "{0:.2f} dB".format(minP[1]))
        self.set_measure_value('maxP',
                               "{0:.2f} dB".format(maxP[1]))
        self.set_measure_value('deltaP',
                               "{0:.2f} dB".format(maxP[1] - minP[1]))
        self.set_measure_value('avg',
                               "{0:.2f} dB".format(avg))

        self.measure = Measure()
        self.measure.set(minP, maxP, avg)
        self.update_plot()

    def show(self, show):
        if show:
            self.Show()
        else:
            self.Hide()
        self.Layout()

    def set_type(self, display):
        if display == Display.PLOT or display == Display.SURFACE:
            self.set_check_read_only('min', False)
            self.set_check_read_only('max', False)
            self.set_check_read_only('avg', False)
        elif display == Display.SPECT:
            self.set_check_read_only('min', True)
            self.set_check_read_only('max', True)
            self.set_check_read_only('avg', True)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
