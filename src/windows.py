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
from events import EventThreadStatus, Event, post_event
from misc import  close_modeless
from plot import Plotter
from plot3d import Plotter3d
from plot_controls import MouseZoom, MouseSelect
from spectrogram import Spectrogram
from spectrum import split_spectrum_sort, slice_spectrum
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

        wx.Panel.__init__(self, panel)

        self.figure = matplotlib.figure.Figure(facecolor='white')
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.measure = PanelMeasure(self)

        self.toolbar = NavigationToolbar(self.canvas, self, settings)
        self.toolbar.Realize()

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        vbox.Add(self.measure, 0, wx.EXPAND)
        vbox.Add(self.toolbar, 0, wx.EXPAND)
        self.SetSizer(vbox)
        vbox.Fit(self)

        self.canvas.mpl_connect('motion_notify_event', callbackMotion)
        self.canvas.mpl_connect('draw_event', self.on_draw)

        self.create_plot()

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

        self.set_plot_title()
        if self.spectrum is not None:
            self.set_plot(self.spectrum, self.extent, self.settings.annotate)
        self.plot.scale_plot(True)
        self.mouseZoom = MouseZoom(self.plot, self.toolbar)
        self.mouseSelect = MouseSelect(self.plot, self.selectStart,
                                       self.selectEnd, self.on_select)
        self.measure.show(self.settings.showMeasure)
        self.panel.SetFocus()

    def on_draw(self, _event):
        post_event(self.notify, EventThreadStatus(Event.PLOTTED))

    def on_select(self, start, end):
        self.selectStart = start
        self.selectEnd = end
        self.measure.set_selected(self.spectrum, start, end)

    def set_plot(self, spectrum, extent, annotate=False):
        self.spectrum = spectrum
        self.extent = extent
        self.plot.set_plot(spectrum, extent, annotate)
        self.measure.set_plot(spectrum)

    def set_plot_title(self):
        if len(self.settings.devices) > 0:
            gain = self.settings.devices[self.settings.index].gain
        else:
            gain = 0
        self.plot.set_title("Frequency Spectrogram\n{0} - {1} MHz,"
                            " gain = {2}dB".format(self.settings.start,
                                                   self.settings.stop, gain))

    def show_measure(self, show):
        self.measure.show(show)
        self.Layout()

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
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)

        self.plot = None

        self.checkStart = '0'
        self.checkEnd = '0'
        self.checkAvg = '0'

        self.selected = None

        self.SetBackgroundColour('white')

        self.grid = grid.Grid(self)
        self.grid.CreateGrid(3, 9)
        self.grid.EnableEditing(False)
        self.grid.EnableDragGridSize(False)
        self.grid.SetColLabelSize(0)
        self.grid.SetRowLabelSize(0)

        checkEditor = grid.GridCellBoolEditor()
        self.grid.SetCellEditor(0, 2, checkEditor)
        self.grid.SetCellEditor(1, 2, checkEditor)
        self.grid.SetCellTextColour(2, 2, 'white')
        self.grid.SetCellEditor(0, 5, checkEditor)
        self.grid.SetCellTextColour(1, 5, 'white')
        self.grid.SetCellTextColour(2, 5, 'white')
        self.grid.SetCellValue(0, 2, self.checkStart)
        self.grid.SetCellValue(1, 2, self.checkEnd)
        self.grid.SetCellValue(0, 5, self.checkAvg)
        self.grid.SetColFormatBool(2)
        self.grid.SetColFormatBool(5)
        self.grid.AutoSizeColumn(2)
        self.grid.AutoSizeColumn(5)
        self.checkLocs = {(0, 2): 'start', (1, 2): 'end', (0, 5): 'avg'}

        self.grid.SetCellValue(0, 0, 'Start')
        self.grid.SetCellValue(1, 0, 'End')
        self.grid.SetCellValue(2, 0, u'\u0394')
        self.grid.SetCellValue(0, 3, 'Min')
        self.grid.SetCellValue(1, 3, 'Max')
        self.grid.SetCellValue(2, 3, u'\u0394')
        self.grid.SetCellValue(0, 6, 'Avg')

        self.popupMenu = wx.Menu()
        self.popupMenuCopy = self.popupMenu.Append(wx.ID_ANY, "&Copy",
                                                   "Copy entry")
        self.Bind(wx.EVT_MENU, self.on_copy, self.popupMenuCopy)

        self.Bind(grid.EVT_GRID_CELL_RIGHT_CLICK, self.on_popup_menu,
                  self.grid)
        self.Bind(grid.EVT_GRID_RANGE_SELECT, self.on_select_range,
                  self.grid)
        self.Bind(grid.EVT_GRID_CELL_LEFT_CLICK, self.on_cell_click)

        font = self.grid.GetCellFont(0, 0)
        font.SetWeight(wx.BOLD)
        for x in [0, 3, 6]:
            for y in xrange(self.grid.GetNumberRows()):
                self.grid.SetCellFont(y, x, font)

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(self.grid, 0, wx.ALIGN_CENTER)

        self.SetSizerAndFit(box)

    def set_plot(self, plot):
        self.plot = plot

    def str_to_bool(self, string):
        if string == '1':
            return True
        return False

    def update_plot(self):
        start = self.str_to_bool(self.checkStart)
        end = self.str_to_bool(self.checkEnd)
        avg = self.str_to_bool(self.checkAvg)

    def on_cell_click(self, event):
        row = event.GetRow()
        col = event.GetCol()
        self.selected = (row, col)
        self.grid.SetGridCursor(row, col)
        if (row, col) in self.checkLocs.keys():
            check = self.grid.GetCellValue(row, col)
            if check == '1':
                check = '0'
            else:
                check = '1'
            self.grid.SetCellValue(row, col, check)

        for (r, c), control in self.checkLocs.iteritems():
            if (r, c) == (row, col):
                if control == 'start':
                    self.checkStart = check
                    break
                elif control == 'end':
                    self.checkEnd = check
                    break
                elif control == 'avg':
                    self.checkAvg = check
                    break

        self.update_plot()

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

    def show(self, show):
        if show:
            self.Show()
        else:
            self.Hide()
        self.Layout()

    def set_selected(self, spectrum, start, end):
        sweep = slice_spectrum(spectrum, start, end)
        if sweep is None:
            self.grid.SetCellValue(0, 1, "")
            self.grid.SetCellValue(1, 1, "")
            self.grid.SetCellValue(2, 1, "")
            self.grid.SetCellValue(0, 3, "")
            self.grid.SetCellValue(1, 3, "")
            self.grid.SetCellValue(0, 4, "")
            self.grid.SetCellValue(1, 4, "")
            self.grid.SetCellValue(2, 3, "")
            self.grid.SetCellValue(2, 4, "")
            return

        minF = min(sweep)[0]
        maxF = max(sweep)[0]
        self.grid.SetCellValue(0, 1, "{0:.6f} MHz".format(minF))
        self.grid.SetCellValue(1, 1, "{0:.6f} MHz".format(maxF))
        self.grid.SetCellValue(2, 1, "{0:.6f} MHz".format(maxF - minF))

        minLoc = min(sweep, key=lambda v: v[1])
        maxLoc = max(sweep, key=lambda v: v[1])
        self.grid.SetCellValue(0, 3, "{0:.6f} MHz".format(minLoc[0]))
        self.grid.SetCellValue(1, 3, "{0:.6f} MHz".format(maxLoc[0]))
        self.grid.SetCellValue(0, 4, "{0:.2f} dB".format(minLoc[1]))
        self.grid.SetCellValue(1, 4, "{0:.2f} dB".format(maxLoc[1]))
        self.grid.SetCellValue(2, 3, "{0:.6f} MHz".format(maxLoc[0] - minLoc[0]))
        self.grid.SetCellValue(2, 4, "{0:.2f} dB".format(maxLoc[1] - minLoc[1]))

        avg = sum((v[1] for v in sweep), 0.0) / len(sweep)
        self.grid.SetCellValue(0, 7, "{0:.2f} dB".format(avg))


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
