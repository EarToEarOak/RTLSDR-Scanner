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

import itertools
from urlparse import urlparse

from matplotlib import cm
import matplotlib
from matplotlib.backends.backend_wxagg import \
    FigureCanvasWxAgg as FigureCanvas, NavigationToolbar2WxAgg
from matplotlib.colorbar import ColorbarBase
from matplotlib.colors import Normalize
from matplotlib.dates import num2epoch
from matplotlib.ticker import AutoMinorLocator, ScalarFormatter
import rtlsdr
import wx

from constants import *
from devices import Device
from events import EventThreadStatus, Event, post_event
from misc import split_spectrum, nearest, open_plot, load_bitmap, \
    get_colours, format_time, ValidatorCoord, get_version_timestamp
from rtltcp import RtlTcp
import wx.grid as grid
import wx.lib.masked as masked


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


class Statusbar(wx.StatusBar):
    def __init__(self, parent):
        wx.StatusBar.__init__(self, parent, -1)
        self.SetFieldsCount(3)
        self.statusProgress = wx.Gauge(self, -1,
                                       style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.statusProgress.Hide()
        self.Bind(wx.EVT_SIZE, self.on_size)

    def on_size(self, event):
        rect = self.GetFieldRect(2)
        self.statusProgress.SetPosition((rect.x + 10, rect.y + 2))
        self.statusProgress.SetSize((rect.width - 20, rect.height - 4))
        event.Skip()

    def set_general(self, text):
        self.SetStatusText(text, 0)
        self.SetToolTipString(text)

    def set_info(self, text):
        self.SetStatusText(text, 1)

    def set_progress(self, progress):
        self.statusProgress.SetValue(progress)

    def show_progress(self):
        self.statusProgress.Show()

    def hide_progress(self):
        self.statusProgress.Hide()


class NavigationToolbar(NavigationToolbar2WxAgg):
    def __init__(self, canvas, main):
        self.main = main
        self.extraTools = []

        NavigationToolbar2WxAgg.__init__(self, canvas)
        self.add_spacer()

        liveId = wx.NewId()
        self.AddCheckTool(liveId, load_bitmap('auto_refresh'),
                          shortHelp='Live update')
        self.ToggleTool(liveId, self.main.settings.liveUpdate)
        wx.EVT_TOOL(self, liveId, self.on_check_update)

        gridId = wx.NewId()
        self.AddCheckTool(gridId, load_bitmap('grid'),
                          shortHelp='Grid')
        self.ToggleTool(gridId, self.main.grid)
        wx.EVT_TOOL(self, gridId, self.on_check_grid)

        peakId = wx.NewId()
        self.AddCheckTool(peakId, load_bitmap('peak'),
                          shortHelp='Label peak')
        self.ToggleTool(peakId, self.main.settings.annotate)
        wx.EVT_TOOL(self, peakId, self.on_check_peak)

        self.add_spacer()

        self.autoFId = wx.NewId()
        self.AddCheckTool(self.autoFId, load_bitmap('auto_f'),
                          shortHelp='Auto range frequency')
        self.ToggleTool(self.autoFId, self.main.settings.autoF)
        wx.EVT_TOOL(self, self.autoFId, self.on_check_auto_f)

        self.autoLId = wx.NewId()
        self.AddCheckTool(self.autoLId, load_bitmap('auto_l'),
                          shortHelp='Auto range level')
        self.ToggleTool(self.autoLId, self.main.settings.autoL)
        wx.EVT_TOOL(self, self.autoLId, self.on_check_auto_l)

    def on_check_auto_f(self, event):
        self.main.settings.autoF = event.Checked()
        self.main.plot.redraw_plot()

    def on_check_auto_l(self, event):
        self.main.settings.autoL = event.Checked()
        self.main.plot.redraw_plot()

    def on_check_auto_t(self, event):
        self.main.settings.autoT = event.Checked()
        self.main.plot.redraw_plot()

    def on_check_update(self, event):
        self.main.settings.liveUpdate = event.Checked()

    def on_check_grid(self, event):
        grid = event.Checked()
        self.main.plot.set_grid(grid)

    def on_check_peak(self, event):
        peak = event.Checked()
        self.main.settings.annotate = peak
        self.main.plot.redraw_plot()

    def on_check_fade(self, event):
        fade = event.Checked()
        self.main.settings.fadeScans = fade
        self.main.plot.redraw_plot()

    def on_check_wire(self, event):
        wire = event.Checked()
        self.main.settings.wireframe = wire
        self.main.create_plot()

    def on_check_avg(self, event):
        avg = event.Checked()
        self.main.settings.average = avg
        self.main.create_plot()

    def on_colour(self, event):
        colourMap = event.GetString()
        self.main.settings.colourMap = colourMap
        self.main.plot.set_colourmap(colourMap)
        self.main.plot.redraw_plot()

    def add_spacer(self):
        sepId = wx.NewId()
        self.AddCheckTool(sepId, load_bitmap('spacer'))
        self.EnableTool(sepId, False)
        return sepId

    def set_type(self, display):
        for toolId in self.extraTools:
            self.DeleteTool(toolId)
        self.extraTools = []

        if not display == Display.PLOT:
            autoTId = wx.NewId()
            self.AddCheckTool(autoTId, load_bitmap('auto_t'),
                              shortHelp='Auto range time')
            self.ToggleTool(autoTId, self.main.settings.autoT)
            wx.EVT_TOOL(self, autoTId, self.on_check_auto_t)
            self.extraTools.append(autoTId)

        self.extraTools.append(self.add_spacer())

        if display == Display.PLOT:
            fadeId = wx.NewId()
            self.AddCheckTool(fadeId, load_bitmap('fade'),
                              shortHelp='Fade plots')
            wx.EVT_TOOL(self, fadeId, self.on_check_fade)
            self.ToggleTool(fadeId, self.main.settings.fadeScans)
            self.extraTools.append(fadeId)

            avgId = wx.NewId()
            self.AddCheckTool(avgId, load_bitmap('average'),
                              shortHelp='Average plots')
            wx.EVT_TOOL(self, avgId, self.on_check_avg)
            self.ToggleTool(avgId, self.main.settings.average)
            self.extraTools.append(avgId)
        else:
            colours = get_colours()
            colourId = wx.NewId()
            control = wx.Choice(self, id=colourId, choices=colours)
            control.SetSelection(colours.index(self.main.settings.colourMap))
            self.AddControl(control)
            self.Bind(wx.EVT_CHOICE, self.on_colour, control)
            self.extraTools.append(colourId)

        if display == Display.SURFACE:
            self.extraTools.append(self.add_spacer())

            wireId = wx.NewId()
            self.AddCheckTool(wireId, load_bitmap('wireframe'),
                              shortHelp='Wireframe')
            wx.EVT_TOOL(self, wireId, self.on_check_wire)
            self.ToggleTool(wireId, self.main.settings.wireframe)
            self.extraTools.append(wireId)

        self.Realize()


class NavigationToolbarCompare(NavigationToolbar2WxAgg):
    def __init__(self, canvas, main):
        NavigationToolbar2WxAgg.__init__(self, canvas)
        self.main = main

        self.AddSeparator()

        gridId = wx.NewId()
        self.AddCheckTool(gridId, load_bitmap('grid'),
                          shortHelp='Toggle grid')
        self.ToggleTool(gridId, True)
        wx.EVT_TOOL(self, gridId, self.on_check_grid)

    def on_check_grid(self, event):
        self.grid = event.Checked()
        self.main.set_grid(self.grid)


class PanelGraph(wx.Panel):
    def __init__(self, parent, main):
        self.parent = parent
        self.main = main
        self.resize = False
        self.display = None

        wx.Panel.__init__(self, self.parent)

        self.figure = matplotlib.figure.Figure(facecolor='white')
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('draw_event', self.on_draw)
        self.toolbar = NavigationToolbar(self.canvas, self.main)
        self.toolbar.Realize()

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        vbox.Add(self.toolbar, 0, wx.EXPAND)

        self.SetSizer(vbox)
        vbox.Fit(self)

    def on_motion(self, event):
        xpos = event.xdata
        ypos = event.ydata
        text = ""
        if xpos is None or ypos is  None or  len(self.main.spectrum) == 0:
            return

        if self.display == Display.PLOT:
            timeStamp = max(self.main.spectrum)
            spectrum = self.main.spectrum[timeStamp]
        elif self.display == Display.SPECT:
            timeStamp = num2epoch(ypos)
            if timeStamp in self.main.spectrum:
                spectrum = self.main.spectrum[timeStamp]
            else:
                nearest = min(self.main.spectrum.keys(),
                              key=lambda k: abs(k - timeStamp))
                spectrum = self.main.spectrum[nearest]
        else:
            spectrum = None

        if spectrum is not None and len(spectrum) > 0:
            x = min(spectrum.keys(), key=lambda freq: abs(freq - xpos))
            if(xpos <= max(spectrum.keys(), key=float)):
                y = spectrum[x]
                text = "f = {0:.6f}MHz, p = {1:.2f}dB".format(x, y)
            else:
                text = "f = {0:.6f}MHz".format(xpos)

        self.main.status.SetStatusText(text, 1)

    def on_draw(self, _event):
        post_event(self.main, EventThreadStatus(Event.PLOTTED))

    def set_type(self, display):
        self.display = display
        self.toolbar.set_type(display)

    def get_figure(self):
        return self.figure

    def get_canvas(self):
        return self.canvas

    def get_toolbar(self):
        return self.toolbar

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
        grid.Add(self.check1, pos=(0, 0), flag=wx.ALIGN_CENTER)
        grid.Add(self.check2, pos=(0, 1), flag=wx.ALIGN_CENTER)
        grid.Add((20, 1), pos=(0, 2))
        grid.Add(self.checkDiff, pos=(0, 3), flag=wx.ALIGN_CENTER)
        grid.Add((20, 1), pos=(0, 4))
        grid.Add((20, 1), pos=(0, 5))
        grid.Add(self.textIntersect, pos=(0, 6), span=(1, 1))

        toolbar = NavigationToolbarCompare(self.canvas, self)
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
            freqs, powers = split_spectrum(diff)
            self.plotDiff.set_xdata(freqs)
            self.plotDiff.set_ydata(powers)
        elif self.spectrum1 is None:
            freqs, powers = split_spectrum(self.spectrum2)
            intersections = len(freqs)
            self.plotDiff.set_xdata(freqs)
            self.plotDiff.set_ydata([0] * intersections)
        else:
            freqs, powers = split_spectrum(self.spectrum1)
            intersections = len(freqs)
            self.plotDiff.set_xdata(freqs)
            self.plotDiff.set_ydata([0] * intersections)

        if intersections > 0:
            self.axesDiff.relim()
        self.textIntersect.SetLabel('Intersections: {0}'.format(intersections))

    def set_spectrum1(self, spectrum):
        timeStamp = max(spectrum)
        self.spectrum1 = spectrum[timeStamp]
        freqs, powers = split_spectrum(self.spectrum1)
        self.plotScan1.set_xdata(freqs)
        self.plotScan1.set_ydata(powers)
        self.axesScan.relim()
        self.plot_diff()
        self.autoscale()

    def set_spectrum2(self, spectrum):
        timeStamp = max(spectrum)
        self.spectrum2 = spectrum[timeStamp]
        freqs, powers = split_spectrum(self.spectrum2)
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


class DialogCompare(wx.Dialog):
    def __init__(self, parent, dirname, filename):

        self.dirname = dirname
        self.filename = filename

        wx.Dialog.__init__(self, parent=parent, title="Compare plots",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)

        self.graph = PanelGraphCompare(self)

        self.buttonPlot1 = wx.Button(self, wx.ID_ANY, 'Load plot #1')
        self.buttonPlot2 = wx.Button(self, wx.ID_ANY, 'Load plot #2')
        self.Bind(wx.EVT_BUTTON, self.on_load_plot, self.buttonPlot1)
        self.Bind(wx.EVT_BUTTON, self.on_load_plot, self.buttonPlot2)
        self.textPlot1 = wx.StaticText(self, label="<None>")
        self.textPlot2 = wx.StaticText(self, label="<None>")

        buttonClose = wx.Button(self, wx.ID_CLOSE, 'Close')
        self.Bind(wx.EVT_BUTTON, self.on_close, buttonClose)

        grid = wx.GridBagSizer(5, 5)
        grid.AddGrowableCol(2, 0)
        grid.Add(self.buttonPlot1, pos=(0, 0), flag=wx.ALIGN_CENTER)
        grid.Add(self.textPlot1, pos=(0, 1), span=(1, 2))
        grid.Add(self.buttonPlot2, pos=(1, 0), flag=wx.ALIGN_CENTER)
        grid.Add(self.textPlot2, pos=(1, 1), span=(1, 2))
        grid.Add(buttonClose, pos=(2, 3), flag=wx.ALIGN_RIGHT)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.graph, 1, wx.EXPAND)
        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, border=5)
        self.SetSizerAndFit(sizer)

        close_modeless()

    def on_load_plot(self, event):
        dlg = wx.FileDialog(self, "Open a scan", self.dirname, self.filename,
                            File.RFS, wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.dirname = dlg.GetDirectory()
            self.filename = dlg.GetFilename()
            _scanInfo, spectrum = open_plot(self.dirname,
                                                self.filename)
            if(event.EventObject == self.buttonPlot1):
                self.textPlot1.SetLabel(self.filename)
                self.graph.set_spectrum1(spectrum)
            else:
                self.textPlot2.SetLabel(self.filename)
                self.graph.set_spectrum2(spectrum)

        dlg.Destroy()

    def on_close(self, _event):
        close_modeless()
        self.EndModal(wx.ID_CLOSE)


class DialogAutoCal(wx.Dialog):
    def __init__(self, parent, freq, callback):
        self.callback = callback
        self.cal = 0

        wx.Dialog.__init__(self, parent=parent, title="Auto Calibration",
                           style=wx.CAPTION)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        title = wx.StaticText(self, label="Calibrate to a known stable signal")
        font = title.GetFont()
        font.SetPointSize(font.GetPointSize() + 2)
        title.SetFont(font)
        text = wx.StaticText(self, label="Frequency (MHz)")
        self.textFreq = masked.NumCtrl(self, value=freq, fractionWidth=3,
                                        min=F_MIN, max=F_MAX)

        self.buttonCal = wx.Button(self, label="Calibrate")
        if len(parent.devices) == 0:
            self.buttonCal.Disable()
        self.buttonCal.Bind(wx.EVT_BUTTON, self.on_cal)
        self.textResult = wx.StaticText(self)

        self.buttonOk = wx.Button(self, wx.ID_OK, 'OK')
        self.buttonOk.Disable()
        self.buttonCancel = wx.Button(self, wx.ID_CANCEL, 'Cancel')

        self.buttonOk.Bind(wx.EVT_BUTTON, self.on_close)
        self.buttonCancel.Bind(wx.EVT_BUTTON, self.on_close)

        buttons = wx.StdDialogButtonSizer()
        buttons.AddButton(self.buttonOk)
        buttons.AddButton(self.buttonCancel)
        buttons.Realize()

        sizer = wx.GridBagSizer(10, 10)
        sizer.Add(title, pos=(0, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        sizer.Add(text, pos=(1, 0), flag=wx.ALL | wx.EXPAND, border=10)
        sizer.Add(self.textFreq, pos=(1, 1), flag=wx.ALL | wx.EXPAND,
                  border=5)
        sizer.Add(self.buttonCal, pos=(2, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL | wx.EXPAND, border=10)
        sizer.Add(self.textResult, pos=(3, 0), span=(1, 2),
                  flag=wx.ALL | wx.EXPAND, border=10)
        sizer.Add(buttons, pos=(4, 0), span=(1, 2),
                  flag=wx.ALL | wx.EXPAND, border=10)

        self.SetSizerAndFit(sizer)

    def on_cal(self, _event):
        self.buttonCal.Disable()
        self.buttonOk.Disable()
        self.buttonCancel.Disable()
        self.textFreq.Disable()
        self.textResult.SetLabel("Calibrating...")
        self.callback(Cal.START)

    def on_close(self, event):
        status = [Cal.CANCEL, Cal.OK][event.GetId() == wx.ID_OK]
        self.callback(status)
        self.EndModal(event.GetId())
        return

    def enable_controls(self):
        self.buttonCal.Enable(True)
        self.buttonOk.Enable(True)
        self.buttonCancel.Enable(True)
        self.textFreq.Enable()

    def set_cal(self, cal):
        self.cal = cal
        self.enable_controls()
        self.textResult.SetLabel("Correction (ppm): {0:.3f}".format(cal))

    def get_cal(self):
        return self.cal

    def reset_cal(self):
        self.set_cal(self.cal)

    def get_freq(self):
        return self.textFreq.GetValue()


class DialogOffset(wx.Dialog):
    def __init__(self, parent, device, offset, winFunc):
        self.device = device
        self.offset = offset * 1e3
        self.winFunc = winFunc
        self.band1 = None
        self.band2 = None

        wx.Dialog.__init__(self, parent=parent, title="Scan Offset")

        figure = matplotlib.figure.Figure(facecolor='white')
        self.axes = figure.add_subplot(111)
        self.canvas = FigureCanvas(self, -1, figure)

        textHelp = wx.StaticText(self,
            label="Remove the aerial and press refresh, "
            "adjust the offset so the shaded areas overlay the flattest parts "
            "of the plot.")

        textFreq = wx.StaticText(self, label="Test frequency (MHz)")
        self.spinFreq = wx.SpinCtrl(self)
        self.spinFreq.SetRange(F_MIN, F_MAX)
        self.spinFreq.SetValue(200)

        textGain = wx.StaticText(self, label="Test gain (dB)")
        self.spinGain = wx.SpinCtrl(self)
        self.spinGain.SetRange(-100, 200)
        self.spinGain.SetValue(200)

        refresh = wx.Button(self, wx.ID_ANY, 'Refresh')
        self.Bind(wx.EVT_BUTTON, self.on_refresh, refresh)

        textOffset = wx.StaticText(self, label="Offset (kHz)")
        self.spinOffset = wx.SpinCtrl(self)
        self.spinOffset.SetRange(0, ((SAMPLE_RATE / 2) - BANDWIDTH) / 1e3)
        self.spinOffset.SetValue(offset)
        self.Bind(wx.EVT_SPINCTRL, self.on_spin, self.spinOffset)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.on_ok, buttonOk)

        boxSizer1 = wx.BoxSizer(wx.HORIZONTAL)
        boxSizer1.Add(textFreq, border=5)
        boxSizer1.Add(self.spinFreq, border=5)
        boxSizer1.Add(textGain, border=5)
        boxSizer1.Add(self.spinGain, border=5)

        boxSizer2 = wx.BoxSizer(wx.HORIZONTAL)
        boxSizer2.Add(textOffset, border=5)
        boxSizer2.Add(self.spinOffset, border=5)

        gridSizer = wx.GridBagSizer(5, 5)
        gridSizer.Add(self.canvas, pos=(0, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=5)
        gridSizer.Add(textHelp, pos=(1, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=5)
        gridSizer.Add(boxSizer1, pos=(2, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=5)
        gridSizer.Add(refresh, pos=(3, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=5)
        gridSizer.Add(boxSizer2, pos=(4, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=5)
        gridSizer.Add(sizerButtons, pos=(5, 1), span=(1, 1),
                  flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(gridSizer)
        self.draw_limits()

        self.setup_plot()

    def setup_plot(self):
        self.axes.clear()
        self.band1 = None
        self.band2 = None
        self.axes.set_xlabel("Frequency (MHz)")
        self.axes.set_ylabel('Level (dB)')
        self.axes.set_yscale('log')
        self.axes.set_xlim(-1, 1)
        self.axes.set_ylim(auto=True)
        self.axes.grid(True)
        self.draw_limits()

    def plot(self, capture):
        self.setup_plot()
        pos = WINFUNC[::2].index(self.winFunc)
        function = WINFUNC[1::2][pos]
        powers, freqs = matplotlib.mlab.psd(capture,
                         NFFT=1024,
                         Fs=SAMPLE_RATE / 1e6,
                         window=function(1024))

        plot = []
        for x, y in itertools.izip(freqs, powers):
            plot.append((x, y))
        plot.sort()
        x, y = numpy.transpose(plot)
        self.axes.plot(x, y, linewidth=0.4)
        self.canvas.draw()

    def on_ok(self, _event):
        self.EndModal(wx.ID_OK)

    def on_refresh(self, _event):

        dlg = wx.BusyInfo('Please wait...')

        try:
            if self.device.isDevice:
                sdr = rtlsdr.RtlSdr(self.device.index)
            else:
                sdr = RtlTcp(self.device.server, self.device.port)
            sdr.set_sample_rate(SAMPLE_RATE)
            sdr.set_center_freq(self.spinFreq.GetValue() * 1e6)
            sdr.set_gain(self.spinGain.GetValue())
            capture = sdr.read_samples(2 ** 21)
            sdr.close()
        except IOError as error:
            if self.device.isDevice:
                message = error.message
            else:
                message = error
            dlg.Destroy()
            dlg = wx.MessageDialog(self,
                                   'Capture failed:\n{0}'.format(message),
                                   'Error',
                                   wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return

        self.plot(capture)

        dlg.Destroy()

    def on_spin(self, _event):
        self.offset = self.spinOffset.GetValue() * 1e3
        self.draw_limits()

    def draw_limits(self):
        limit1 = self.offset
        limit2 = limit1 + BANDWIDTH / 2
        limit1 /= 1e6
        limit2 /= 1e6
        if(self.band1 is not None):
            self.band1.remove()
        if(self.band2 is not None):
            self.band2.remove()
        self.band1 = self.axes.axvspan(limit1, limit2, color='g', alpha=0.25)
        self.band2 = self.axes.axvspan(-limit1, -limit2, color='g', alpha=0.25)
        self.canvas.draw()

    def get_offset(self):
        return self.offset / 1e3


class DialogProperties(wx.Dialog):
    def __init__(self, parent, scanInfo):
        wx.Dialog.__init__(self, parent, title="Scan Properties")

        self.scanInfo = scanInfo

        box = wx.BoxSizer(wx.VERTICAL)

        grid = wx.GridBagSizer(0, 0)

        boxScan = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "Scan"),
                                     wx.HORIZONTAL)

        gridScan = wx.GridBagSizer(0, 0)

        textDesc = wx.StaticText(self, label="Description")
        gridScan.Add(textDesc, (0, 0), (1, 1), wx.ALL, 5)
        self.textCtrlDesc = wx.TextCtrl(self, value=scanInfo.desc,
                                        style=wx.TE_MULTILINE)
        gridScan.Add(self.textCtrlDesc, (0, 1), (2, 2), wx.ALL | wx.EXPAND, 5)

        textStart = wx.StaticText(self, label="Start")
        gridScan.Add(textStart, (2, 0), (1, 1), wx.ALL, 5)
        textCtrlStart = wx.TextCtrl(self, value="Unknown",
                                    style=wx.TE_READONLY)
        if scanInfo.start is not None:
            textCtrlStart.SetValue(str(scanInfo.start))
        gridScan.Add(textCtrlStart, (2, 1), (1, 1), wx.ALL, 5)
        textMHz1 = wx.StaticText(self, wx.ID_ANY, label="MHz")
        gridScan.Add(textMHz1, (2, 2), (1, 1), wx.ALL, 5)

        textStop = wx.StaticText(self, label="Stop")
        gridScan.Add(textStop, (3, 0), (1, 1), wx.ALL, 5)
        textCtrlStop = wx.TextCtrl(self, value="Unknown",
                                   style=wx.TE_READONLY)
        if scanInfo.stop is not None:
            textCtrlStop.SetValue(str(scanInfo.stop))
        gridScan.Add(textCtrlStop, (3, 1), (1, 1), wx.ALL, 5)
        textMHz2 = wx.StaticText(self, label="MHz")
        gridScan.Add(textMHz2, (3, 2), (1, 1), wx.ALL, 5)

        textDwell = wx.StaticText(self, label="Dwell")
        gridScan.Add(textDwell, (4, 0), (1, 1), wx.ALL, 5)
        textCtrlDwell = wx.TextCtrl(self, value="Unknown",
                                    style=wx.TE_READONLY)
        if scanInfo.dwell is not None:
            textCtrlDwell.SetValue(str(scanInfo.dwell))
        gridScan.Add(textCtrlDwell, (4, 1), (1, 1), wx.ALL, 5)
        textSeconds = wx.StaticText(self, label="seconds")
        gridScan.Add(textSeconds, (4, 2), (1, 1), wx.ALL, 5)

        textNfft = wx.StaticText(self, label="FFT Size")
        gridScan.Add(textNfft, (5, 0), (1, 1), wx.ALL, 5)
        textCtrlNfft = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.nfft is not None:
            textCtrlNfft.SetValue(str(scanInfo.nfft))
        gridScan.Add(textCtrlNfft, (5, 1), (1, 1), wx.ALL, 5)

        textTime = wx.StaticText(self, label="First scan")
        gridScan.Add(textTime, (6, 0), (1, 1), wx.ALL, 5)
        textCtrlTime = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.timeFirst is not None:
            textCtrlTime.SetValue(format_time(scanInfo.timeFirst, True))
        gridScan.Add(textCtrlTime, (6, 1), (1, 1), wx.ALL, 5)

        textTime = wx.StaticText(self, label="Last scan")
        gridScan.Add(textTime, (7, 0), (1, 1), wx.ALL, 5)
        textCtrlTime = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.timeLast is not None:
            textCtrlTime.SetValue(format_time(scanInfo.timeLast, True))
        gridScan.Add(textCtrlTime, (7, 1), (1, 1), wx.ALL, 5)

        textLat = wx.StaticText(self, label="Latitude")
        gridScan.Add(textLat, (8, 0), (1, 1), wx.ALL, 5)
        self.textCtrlLat = wx.TextCtrl(self, value="Unknown")
        self.textCtrlLat.SetValidator(ValidatorCoord(True))
        if scanInfo.lat is not None:
            self.textCtrlLat.SetValue(str(scanInfo.lat))
        gridScan.Add(self.textCtrlLat, (8, 1), (1, 1), wx.ALL, 5)

        textLon = wx.StaticText(self, label="Longitude")
        gridScan.Add(textLon, (9, 0), (1, 1), wx.ALL, 5)
        self.textCtrlLon = wx.TextCtrl(self, value="Unknown")
        self.textCtrlLon.SetValidator(ValidatorCoord(False))
        if scanInfo.lon is not None:
            self.textCtrlLon.SetValue(str(scanInfo.lon))
        gridScan.Add(self.textCtrlLon, (9, 1), (1, 1), wx.ALL, 5)

        boxScan.Add(gridScan, 0, 0, 5)

        grid.Add(boxScan, (0, 0), (1, 1), wx.ALL | wx.EXPAND, 5)

        boxDevice = wx.StaticBoxSizer(wx.StaticBox(self, label="Device"),
                                      wx.VERTICAL)

        gridDevice = wx.GridBagSizer(0, 0)

        textName = wx.StaticText(self, label="Name")
        gridDevice.Add(textName, (0, 0), (1, 1), wx.ALL, 5)
        textCtrlName = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.name is not None:
            textCtrlName.SetValue(scanInfo.name)
        gridDevice.Add(textCtrlName, (0, 1), (1, 2), wx.ALL | wx.EXPAND, 5)

        textTuner = wx.StaticText(self, label="Tuner")
        gridDevice.Add(textTuner, (1, 0), (1, 1), wx.ALL, 5)
        textCtrlTuner = wx.TextCtrl(self, value="Unknown",
                                    style=wx.TE_READONLY)
        if scanInfo.tuner != -1:
            textCtrlTuner.SetValue(TUNER[scanInfo.tuner])
        gridDevice.Add(textCtrlTuner, (1, 1), (1, 2), wx.ALL | wx.EXPAND, 5)

        testGain = wx.StaticText(self, label="Gain")
        gridDevice.Add(testGain, (2, 0), (1, 1), wx.ALL, 5)
        textCtrlGain = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.gain is not None:
            textCtrlGain.SetValue(str(scanInfo.gain))
        gridDevice.Add(textCtrlGain, (2, 1), (1, 1), wx.ALL, 5)
        textDb = wx.StaticText(self, label="dB")
        gridDevice.Add(textDb, (2, 2), (1, 1), wx.ALL, 5)

        textLo = wx.StaticText(self, label="LO")
        gridDevice.Add(textLo, (3, 0), (1, 1), wx.ALL, 5)
        textCtrlLo = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.lo is not None:
            textCtrlLo.SetValue(str(scanInfo.lo))
        gridDevice.Add(textCtrlLo, (3, 1), (1, 1), wx.ALL, 5)
        textMHz3 = wx.StaticText(self, label="MHz")
        gridDevice.Add(textMHz3, (3, 2), (1, 1), wx.ALL, 5)

        textCal = wx.StaticText(self, label="Calibration")
        gridDevice.Add(textCal, (4, 0), (1, 1), wx.ALL, 5)
        textCtrlCal = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.calibration is not None:
            textCtrlCal.SetValue(str(scanInfo.calibration))
        gridDevice.Add(textCtrlCal, (4, 1), (1, 1), wx.ALL, 5)
        testPpm = wx.StaticText(self, label="ppm")
        gridDevice.Add(testPpm, (4, 2), (1, 1), wx.ALL, 5)

        boxDevice.Add(gridDevice, 1, wx.EXPAND, 5)

        grid.Add(boxDevice, (1, 0), (1, 1), wx.ALL | wx.EXPAND, 5)

        box.Add(grid, 1, wx.ALL | wx.EXPAND, 5)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.on_ok, buttonOk)
        box.Add(sizerButtons, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.SetSizerAndFit(box)

    def on_ok(self, _event):
        self.scanInfo.desc = self.textCtrlDesc.GetValue()
        if self.Validate():
            lat = self.textCtrlLat.GetValue()
            if len(lat) == 0 or lat == "-" or lat.lower() == "unknown":
                self.scanInfo.lat = None
            else:
                self.scanInfo.lat = float(lat)

            lon = self.textCtrlLon.GetValue()
            if len(lon) == 0 or lon == "-" or lon.lower() == "unknown":
                self.scanInfo.lon = None
            else:
                self.scanInfo.lon = float(lon)

            self.EndModal(wx.ID_CLOSE)


class DialogPrefs(wx.Dialog):
    COL_SEL, COL_DEV, COL_TUN, COL_SER, COL_IND, \
    COL_GAIN, COL_CAL, COL_LO, COL_OFF = range(9)

    def __init__(self, parent, devices, settings):
        self.settings = settings
        self.index = 0

        wx.Dialog.__init__(self, parent=parent, title="Preferences")

        self.colours = get_colours()

        self.checkSaved = wx.CheckBox(self, wx.ID_ANY,
                                      "Save warning")
        self.checkSaved.SetValue(self.settings.saveWarn)
        self.checkSaved.SetToolTip(wx.ToolTip('Prompt to save scan on exit'))

        self.checkAlert = wx.CheckBox(self, wx.ID_ANY,
                                      "Level alert (dB)")
        self.checkAlert.SetValue(self.settings.alert)
        self.checkAlert.SetToolTip(wx.ToolTip('Play alert when level exceeded'))
        self.Bind(wx.EVT_CHECKBOX, self.on_alert, self.checkAlert)
        self.spinLevel = wx.SpinCtrl(self, wx.ID_ANY, min=-100, max=20)
        self.spinLevel.SetValue(settings.alertLevel)
        self.spinLevel.Enable(self.settings.alert)
        self.spinLevel.SetToolTip(wx.ToolTip('Alert threshold'))

        textOverlap = wx.StaticText(self, label='PSD Overlap (%)')
        self.slideOverlap = wx.Slider(self, wx.ID_ANY,
                                      self.settings.overlap * 100,
                                      0, 75,
                                      style=wx.SL_AUTOTICKS | wx.SL_LABELS)
        self.slideOverlap.SetToolTip(wx.ToolTip('Power spectral density'
                                                    ' overlap'))

        self.radioAvg = wx.RadioButton(self, wx.ID_ANY, 'Average Scans',
                                       style=wx.RB_GROUP)
        self.radioAvg.SetToolTip(wx.ToolTip('Average level with each scan'))
        self.Bind(wx.EVT_RADIOBUTTON, self.on_radio, self.radioAvg)
        self.radioRetain = wx.RadioButton(self, wx.ID_ANY,
                                          'Retain previous scans')
        self.radioRetain.SetToolTip(wx.ToolTip('Can be slow'))
        self.Bind(wx.EVT_RADIOBUTTON, self.on_radio, self.radioRetain)
        self.radioRetain.SetValue(self.settings.retainScans)

        textMaxScans = wx.StaticText(self, label="Max scans")
        self.spinCtrlMaxScans = wx.SpinCtrl(self)
        self.spinCtrlMaxScans.SetRange(1, 500)
        self.spinCtrlMaxScans.SetValue(self.settings.retainMax)
        self.spinCtrlMaxScans.SetToolTip(wx.ToolTip('Maximum previous scans'
                                                    ' to display'))

        self.checkFade = wx.CheckBox(self, wx.ID_ANY,
                                      "Fade previous scans")
        self.checkFade.SetValue(self.settings.fadeScans)

        textColour = wx.StaticText(self, label="Colour map")
        self.choiceColour = wx.Choice(self, choices=self.colours)
        self.choiceColour.SetSelection(self.colours.index(self.settings.colourMap))
        self.Bind(wx.EVT_CHOICE, self.on_choice, self.choiceColour)
        self.colourBar = PanelColourBar(self, self.settings.colourMap)

        self.on_radio(None)

        self.devices = devices

        self.gridDev = grid.Grid(self)
        self.gridDev.CreateGrid(len(self.devices), 9)
        self.gridDev.SetRowLabelSize(0)
        self.gridDev.SetColLabelValue(self.COL_SEL, "Select")
        self.gridDev.SetColLabelValue(self.COL_DEV, "Device")
        self.gridDev.SetColLabelValue(self.COL_TUN, "Tuner")
        self.gridDev.SetColLabelValue(self.COL_SER, "Serial Number")
        self.gridDev.SetColLabelValue(self.COL_IND, "Index")
        self.gridDev.SetColLabelValue(self.COL_GAIN, "Gain\n(dB)")
        self.gridDev.SetColLabelValue(self.COL_CAL, "Calibration\n(ppm)")
        self.gridDev.SetColLabelValue(self.COL_LO, "LO\n(MHz)")
        self.gridDev.SetColLabelValue(self.COL_OFF, "Band Offset\n(kHz)")
        self.gridDev.SetColFormatFloat(self.COL_GAIN, -1, 1)
        self.gridDev.SetColFormatFloat(self.COL_CAL, -1, 3)
        self.gridDev.SetColFormatFloat(self.COL_LO, -1, 3)
        self.gridDev.SetColFormatFloat(self.COL_OFF, -1, 0)

        self.set_dev_grid()

        self.Bind(grid.EVT_GRID_CELL_LEFT_CLICK, self.on_click)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.on_ok, buttonOk)

        gengrid = wx.GridBagSizer(10, 10)
        gengrid.Add(self.checkSaved, pos=(0, 0), flag=wx.ALL)
        gengrid.Add(self.checkAlert, pos=(1, 0), flag=wx.ALL | wx.ALIGN_CENTER)
        gengrid.Add(self.spinLevel, pos=(1, 1), flag=wx.ALL | wx.ALIGN_CENTER)
        genbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "General"))
        genbox.Add(gengrid, 0, wx.ALL | wx.EXPAND, 10)

        advbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "Advanced"))
        advbox.Add(textOverlap, 0, wx.ALL | wx.CENTRE, 10)
        advbox.Add(self.slideOverlap, 1, wx.ALL | wx.EXPAND, 10)

        congrid = wx.GridBagSizer(10, 10)
        congrid.Add(self.radioAvg, pos=(0, 0), flag=wx.ALL)
        congrid.Add(self.radioRetain, pos=(1, 0), flag=wx.ALL)
        congrid.Add(textMaxScans, pos=(2, 0), flag=wx.ALL)
        congrid.Add(self.spinCtrlMaxScans, pos=(2, 1), flag=wx.ALL)
        conbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY,
                                                "Continuous Scans"),
                                   wx.VERTICAL)
        conbox.Add(congrid, 0, wx.ALL | wx.EXPAND, 10)

        plotbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "Plot View"),
                                     wx.HORIZONTAL)
        plotbox.Add(self.checkFade, 0, wx.ALL | wx.EXPAND, 10)

        specbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY,
                                                 "Spectrogram View"),
                                    wx.HORIZONTAL)
        specbox.Add(textColour, 0, wx.ALL | wx.EXPAND, 10)
        specbox.Add(self.choiceColour, 0, wx.ALL | wx.EXPAND, 10)
        specbox.Add(self.colourBar, 0, wx.ALL | wx.EXPAND, 10)

        devbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "Devices"),
                                     wx.VERTICAL)

        serverSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonAdd = wx.Button(self, wx.ID_ADD)
        self.buttonDel = wx.Button(self, wx.ID_DELETE)
        self.Bind(wx.EVT_BUTTON, self.on_add, buttonAdd)
        self.Bind(wx.EVT_BUTTON, self.on_del, self.buttonDel)
        serverSizer.Add(buttonAdd, 0, wx.ALL)
        serverSizer.Add(self.buttonDel, 0, wx.ALL)
        self.button_state()

        devbox.Add(self.gridDev, 0, wx.ALL | wx.EXPAND, 10)
        devbox.Add(serverSizer, 0, wx.ALL | wx.EXPAND, 10)

        self.vbox = wx.GridBagSizer(10, 10)
        self.vbox.Add(genbox, pos=(0, 0), flag=wx.LEFT | wx.RIGHT | wx.EXPAND)
        self.vbox.Add(advbox, pos=(0, 1), flag=wx.LEFT | wx.RIGHT | wx.EXPAND)
        self.vbox.Add(conbox, pos=(1, 0), span=(1, 2),
                      flag=wx.LEFT | wx.RIGHT | wx.EXPAND)
        self.vbox.Add(plotbox, pos=(2, 0), span=(1, 2),
                      flag=wx.LEFT | wx.RIGHT | wx.EXPAND)
        self.vbox.Add(specbox, pos=(3, 0), span=(1, 2),
                      flag=wx.LEFT | wx.RIGHT | wx.EXPAND)
        self.vbox.Add(devbox, pos=(4, 0), span=(2, 2),
                      flag=wx.LEFT | wx.RIGHT | wx.EXPAND)
        self.vbox.Add(sizerButtons, pos=(6, 1), flag=wx.ALL | wx.EXPAND)

        self.SetSizerAndFit(self.vbox)

    def set_dev_grid(self):
        colourBackground = self.gridDev.GetLabelBackgroundColour()
        attributes = grid.GridCellAttr()
        attributes.SetBackgroundColour(colourBackground)
        self.gridDev.SetColAttr(self.COL_IND, attributes)

        self.gridDev.ClearGrid()

        i = 0
        for device in self.devices:
            self.gridDev.SetReadOnly(i, self.COL_SEL, True)
            self.gridDev.SetReadOnly(i, self.COL_DEV, device.isDevice)
            self.gridDev.SetReadOnly(i, self.COL_TUN, True)
            self.gridDev.SetReadOnly(i, self.COL_SER, True)
            self.gridDev.SetReadOnly(i, self.COL_IND, True)
            self.gridDev.SetCellRenderer(i, self.COL_SEL, CellRenderer())
            if device.isDevice:
                self.gridDev.SetCellEditor(i, self.COL_GAIN,
                                           grid.GridCellChoiceEditor(map(str, device.gains),
                                                                     allowOthers=False))
            self.gridDev.SetCellEditor(i, self.COL_CAL,
                                       grid.GridCellFloatEditor(-1, 3))
            self.gridDev.SetCellEditor(i, self.COL_LO,
                                       grid.GridCellFloatEditor(-1, 3))
            if device.isDevice:
                self.gridDev.SetCellValue(i, self.COL_DEV, device.name)
                self.gridDev.SetCellValue(i, self.COL_SER, str(device.serial))
                self.gridDev.SetCellValue(i, self.COL_IND, str(i))
                self.gridDev.SetCellBackgroundColour(i, self.COL_DEV,
                                                     colourBackground)
                self.gridDev.SetCellValue(i, self.COL_GAIN,
                                          str(nearest(device.gain,
                                                      device.gains)))
            else:
                self.gridDev.SetCellValue(i, self.COL_DEV,
                                          '{0}:{1}'.format(device.server,
                                                           device.port))
                self.gridDev.SetCellValue(i, self.COL_SER, '')
                self.gridDev.SetCellValue(i, self.COL_IND, '')
                self.gridDev.SetCellValue(i, self.COL_GAIN, str(device.gain))
            self.gridDev.SetCellBackgroundColour(i, self.COL_SER,
                                                 colourBackground)

            self.gridDev.SetCellValue(i, self.COL_TUN, TUNER[device.tuner])
            self.gridDev.SetCellValue(i, self.COL_CAL, str(device.calibration))
            self.gridDev.SetCellValue(i, self.COL_LO, str(device.lo))
            self.gridDev.SetCellValue(i, self.COL_OFF, str(device.offset / 1e3))
            i += 1

        if self.settings.index >= len(self.devices):
            self.settings.index = len(self.devices) - 1
        self.select_row(self.settings.index)
        self.index = self.settings.index

        self.gridDev.AutoSize()

    def get_dev_grid(self):
        i = 0
        for device in self.devices:
            if not device.isDevice:
                server = self.gridDev.GetCellValue(i, self.COL_DEV)
                server = '//' + server
                url = urlparse(server)
                if url.hostname is not None:
                    device.server = url.hostname
                else:
                    device.port = 'localhost'
                if url.port is not None:
                    device.port = url.port
                else:
                    device.port = 1234
            device.gain = float(self.gridDev.GetCellValue(i, self.COL_GAIN))
            device.calibration = float(self.gridDev.GetCellValue(i, self.COL_CAL))
            device.lo = float(self.gridDev.GetCellValue(i, self.COL_LO))
            device.offset = float(self.gridDev.GetCellValue(i, self.COL_OFF)) * 1e3
            i += 1

    def button_state(self):
        if len(self.devices) > 0:
            if self.devices[self.index].isDevice:
                self.buttonDel.Disable()
            else:
                self.buttonDel.Enable()

    def warn_duplicates(self):
        servers = []
        for device in self.devices:
            if not device.isDevice:
                servers.append("{0}:{1}".format(device.server, device.port))

        dupes = set(servers)
        if len(dupes) != len(servers):
            message = "Duplicate server found:\n'{0}'".format(dupes.pop())
            dlg = wx.MessageDialog(self, message, "Warning",
                                   wx.OK | wx.ICON_WARNING)
            dlg.ShowModal()
            dlg.Destroy()
            return True

        return False

    def on_alert(self, _event):
        enabled = self.checkAlert.GetValue()
        self.spinLevel.Enable(enabled)

    def on_radio(self, _event):
        enabled = self.radioRetain.GetValue()
        self.checkFade.Enable(enabled)
        self.spinCtrlMaxScans.Enable(enabled)

    def on_choice(self, _event):
        self.colourBar.set_map(self.choiceColour.GetStringSelection())
        self.choiceColour.SetFocus()

    def on_click(self, event):
        col = event.GetCol()
        index = event.GetRow()
        if col == self.COL_SEL:
            self.index = event.GetRow()
            self.select_row(index)
        elif col == self.COL_OFF:
            device = self.devices[index]
            dlg = DialogOffset(self, device,
                               float(self.gridDev.GetCellValue(index,
                                                               self.COL_OFF)),
                               self.settings.winFunc)
            if dlg.ShowModal() == wx.ID_OK:
                self.gridDev.SetCellValue(index, self.COL_OFF,
                                          str(dlg.get_offset()))
            dlg.Destroy()
        else:
            self.gridDev.ForceRefresh()
            event.Skip()

        self.button_state()

    def on_add(self, _event):
        device = Device()
        device.isDevice = False
        self.devices.append(device)
        self.gridDev.AppendRows(1)
        self.set_dev_grid()
        self.SetSizerAndFit(self.vbox)

    def on_del(self, _event):
        del self.devices[self.index]
        self.gridDev.DeleteRows(self.index)
        self.set_dev_grid()
        self.button_state()

    def on_ok(self, _event):
        self.get_dev_grid()
        if self.warn_duplicates():
            return
        self.settings.saveWarn = self.checkSaved.GetValue()
        self.settings.alert = self.checkAlert.GetValue()
        self.settings.alertLevel = self.spinLevel.GetValue()
        self.settings.overlap = self.slideOverlap.GetValue() / 100.0
        self.settings.retainScans = self.radioRetain.GetValue()
        self.settings.fadeScans = self.checkFade.GetValue()
        self.settings.retainMax = self.spinCtrlMaxScans.GetValue()
        self.settings.colourMap = self.choiceColour.GetStringSelection()

        self.EndModal(wx.ID_OK)

    def select_row(self, index):
        self.gridDev.ClearSelection()
        for i in range(0, len(self.devices)):
            tick = "0"
            if i == index:
                tick = "1"
            self.gridDev.SetCellValue(i, self.COL_SEL, tick)

    def get_index(self):
        return self.index

    def get_devices(self):
        return self.devices


class DialogWinFunc(wx.Dialog):
    def __init__(self, parent, winFunc):
        self.winFunc = winFunc
        x = numpy.linspace(-numpy.pi, numpy.pi, 1000)
        self.data = numpy.sin(x) + 0j

        wx.Dialog.__init__(self, parent=parent, title="Window Function")

        figure = matplotlib.figure.Figure(facecolor='white',
                                          figsize=(5, 4), tight_layout=True)
        figure.suptitle('Window Function')
        self.canvas = FigureCanvas(self, -1, figure)
        self.axesWin = figure.add_subplot(211)
        self.axesFft = figure.add_subplot(212)

        text = wx.StaticText(self, label='Function')

        self.choice = wx.Choice(self, choices=WINFUNC[::2])
        self.choice.SetSelection(WINFUNC[::2].index(winFunc))

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.on_ok, buttonOk)

        sizerFunction = wx.BoxSizer(wx.HORIZONTAL)
        sizerFunction.Add(text, flag=wx.ALL, border=5)
        sizerFunction.Add(self.choice, flag=wx.ALL, border=5)

        sizerGrid = wx.GridBagSizer(5, 5)
        sizerGrid.Add(self.canvas, pos=(0, 0), span=(1, 2), border=5)
        sizerGrid.Add(sizerFunction, pos=(1, 0), span=(1, 2),
                      flag=wx.ALIGN_CENTER | wx.ALL, border=5)
        sizerGrid.Add(sizerButtons, pos=(2, 1),
                  flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.Bind(wx.EVT_CHOICE, self.on_choice, self.choice)
        self.Bind(wx.EVT_BUTTON, self.on_ok, buttonOk)

        self.plot()

        self.SetSizerAndFit(sizerGrid)

    def plot(self):
        pos = WINFUNC[::2].index(self.winFunc)
        function = WINFUNC[1::2][pos](512)

        self.axesWin.clear()
        self.axesWin.plot(function, 'g')
        self.axesWin.set_xlabel('Time')
        self.axesWin.set_ylabel('Multiplier')
        self.axesWin.set_xlim(0, 512)
        self.axesWin.set_xticklabels([])
        self.axesFft.clear()
        self.axesFft.psd(self.data, NFFT=512, Fs=1000, window=function)
        self.axesFft.set_xlabel('Frequency')
        self.axesFft.set_ylabel('dB')
        self.axesFft.set_xlim(-256, 256)
        self.axesFft.set_xticklabels([])

        self.canvas.draw()

    def on_choice(self, _event):
        self.winFunc = WINFUNC[::2][self.choice.GetSelection()]
        self.plot()

    def on_ok(self, _event):
        self.EndModal(wx.ID_OK)

    def get_win_func(self):
        return self.winFunc


class DialogSaveWarn(wx.Dialog):
    def __init__(self, parent, warnType):
        self.code = -1

        wx.Dialog.__init__(self, parent=parent, title="Warning")

        prompt = ["scanning again", "opening a file", "exiting"][warnType]
        text = wx.StaticText(self,
                             label="Save plot before {0}?".format(prompt))
        icon = wx.StaticBitmap(self, wx.ID_ANY,
                               wx.ArtProvider.GetBitmap(wx.ART_INFORMATION,
                                                        wx.ART_MESSAGE_BOX))

        tbox = wx.BoxSizer(wx.HORIZONTAL)
        tbox.Add(text)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(icon, 0, wx.ALL, 5)
        hbox.Add(tbox, 0, wx.ALL, 5)

        buttonYes = wx.Button(self, wx.ID_YES, 'Yes')
        buttonNo = wx.Button(self, wx.ID_NO, 'No')
        buttonCancel = wx.Button(self, wx.ID_CANCEL, 'Cancel')

        buttonYes.Bind(wx.EVT_BUTTON, self.on_close)
        buttonNo.Bind(wx.EVT_BUTTON, self.on_close)

        buttons = wx.StdDialogButtonSizer()
        buttons.AddButton(buttonYes)
        buttons.AddButton(buttonNo)
        buttons.AddButton(buttonCancel)
        buttons.Realize()

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(hbox, 1, wx.ALL | wx.EXPAND, 10)
        vbox.Add(buttons, 1, wx.ALL | wx.EXPAND, 10)

        self.SetSizerAndFit(vbox)

    def on_close(self, event):
        self.EndModal(event.GetId())
        return

    def get_code(self):
        return self.code


class DialogRefresh(wx.Dialog):
    def __init__(self, parent):

        wx.Dialog.__init__(self, parent=parent, style=0)

        text = wx.StaticText(self, label="Refreshing plot, please wait...")
        icon = wx.StaticBitmap(self, wx.ID_ANY,
                               wx.ArtProvider.GetBitmap(wx.ART_INFORMATION,
                                                        wx.ART_MESSAGE_BOX))

        box = wx.BoxSizer(wx.HORIZONTAL)
        box.Add(icon, flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        box.Add(text, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        self.SetSizerAndFit(box)
        self.Centre()


class DialogAbout(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent=parent, title="About")

        bitmapIcon = wx.StaticBitmap(self, bitmap=load_bitmap('icon'))
        textAbout = wx.StaticText(self, label="A simple spectrum analyser for "
                                  "scanning\n with a RTL-SDR compatible USB "
                                  "device", style=wx.ALIGN_CENTRE)
        textLink = wx.HyperlinkCtrl(self, wx.ID_ANY,
                                    label="http://eartoearoak.com/software/rtlsdr-scanner",
                                    url="http://eartoearoak.com/software/rtlsdr-scanner")
        textTimestamp = wx.StaticText(self,
                                      label="Updated: " + get_version_timestamp())
        buttonOk = wx.Button(self, wx.ID_OK)

        grid = wx.GridBagSizer(10, 10)
        grid.Add(bitmapIcon, pos=(0, 0), span=(3, 1),
                 flag=wx.ALIGN_LEFT | wx.ALL, border=10)
        grid.Add(textAbout, pos=(0, 1), span=(1, 2),
                 flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        grid.Add(textLink, pos=(1, 1), span=(1, 2),
                 flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        grid.Add(textTimestamp, pos=(2, 1), span=(1, 2),
                 flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        grid.Add(buttonOk, pos=(3, 2), span=(1, 1),
                 flag=wx.ALIGN_RIGHT | wx.ALL, border=10)

        self.SetSizerAndFit(grid)
        self.Centre()


def close_modeless():
    for child in wx.GetTopLevelWindows():
        if child.Title == 'Configure subplots':
            child.Close()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
