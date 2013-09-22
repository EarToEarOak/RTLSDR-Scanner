#! /usr/bin/env python
#
# rtlsdr_scan
#
# http://eartoearoak.com/software/rtlsdr-scanner
#
# Copyright 2012, 2013 Al Brown
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

try:
    input = raw_input
except:
    pass

try:
    import matplotlib
    matplotlib.interactive(True)
    matplotlib.use('WXAgg')
    from matplotlib.backends.backend_wxagg import \
        FigureCanvasWxAgg as FigureCanvas, \
        NavigationToolbar2WxAgg
    from matplotlib.backends.backend_wx import _load_bitmap
    from matplotlib.ticker import AutoMinorLocator, ScalarFormatter
    import argparse
    import cPickle
    import itertools
    import math
    import numpy
    import os.path
    import rtlsdr
    import webbrowser
    import wx
    import wx.lib.masked as masked
    import wx.lib.mixins.listctrl as listmix
    import wx.grid as grid
except ImportError as error:
    print('Import error: {0}'.format(error))
    input('\nError importing libraries\nPress [Return] to exit')
    exit(1)

from constants import *
from misc import split_spectrum, open_plot, format_device_name, setup_plot, \
    scale_plot
from settings import Settings, Device
from threads import EVT_THREAD_STATUS, ThreadProcess, ThreadScan, ThreadPlot


MODE = ["Single", 0,
        "Continuous", 1]
NFFT = [128,
        512,
        1024,
        2048,
        4096,
        8192,
        16384,
        32768]
DWELL = ["10 ms", 0.01,
         "25 ms", 0.025,
         "50 ms", 0.05,
         "100 ms", 0.1,
         "200 ms", 0.2,
         "500 ms", 0.5,
         "1 s", 1,
         "2 s", 2,
         "5 s", 5]


class DropTarget(wx.FileDropTarget):
    def __init__(self, window):
        wx.FileDropTarget.__init__(self)
        self.window = window

    def OnDropFiles(self, _xPos, _yPos, filenames):
        filename = filenames[0]
        if os.path.splitext(filename)[1].lower() == ".rfs":
            self.window.dirname, self.window.filename = os.path.split(filename)
            self.window.open()


class DeviceList(wx.ListCtrl, listmix.TextEditMixin):
    def __init__(self, parent, ID=wx.ID_ANY, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0):
        wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
        listmix.TextEditMixin.__init__(self)


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


class NavigationToolbar(NavigationToolbar2WxAgg):
    def __init__(self, canvas, main):
        self.main = main

        navId = wx.NewId()
        NavigationToolbar2WxAgg.__init__(self, canvas)
        self.DeleteToolByPos(3)
        self.AddSimpleTool(navId, _load_bitmap('subplots.png'),
                           'Range', 'Set plot range')
        wx.EVT_TOOL(self, navId, self.on_range)

    def on_range(self, _event):

        dlg = DialogRange(self, self.main)
        dlg.ShowModal()
        dlg.Destroy()
        self.canvas.draw()
        self.main.draw_plot()


class NavigationToolbarCompare(NavigationToolbar2WxAgg):
    def __init__(self, canvas):
        NavigationToolbar2WxAgg.__init__(self, canvas)


class PanelGraph(wx.Panel):
    def __init__(self, parent, main):
        self.main = main

        wx.Panel.__init__(self, parent)

        self.figure = matplotlib.figure.Figure(facecolor='white')
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.Bind(wx.EVT_ENTER_WINDOW, self.on_enter)
        self.toolbar = NavigationToolbar(self.canvas, self.main)
        self.toolbar.Realize()
        self.toolbar.DeleteToolByPos(1)
        self.toolbar.DeleteToolByPos(1)
        self.toolbar.DeleteToolByPos(4)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        vbox.Add(self.toolbar, 0, wx.EXPAND)

        self.SetSizer(vbox)
        vbox.Fit(self)

    def on_motion(self, event):
        xpos = event.xdata
        ypos = event.ydata
        text = ""
        if xpos is not None and ypos is not None:
            spectrum = self.main.spectrum
            if len(spectrum) > 0:
                x = min(spectrum.keys(), key=lambda freq: abs(freq - xpos))
                if(xpos <= max(spectrum.keys(), key=float)):
                    y = spectrum[x]
                    text = "f = {0:.3f}MHz, p = {1:.2f}dB".format(x, y)
                else:
                    text = "f = {0:.3f}MHz".format(xpos)

        self.main.status.SetStatusText(text, 1)

    def on_enter(self, _event):
        self.canvas.SetCursor(wx.StockCursor(wx.CURSOR_CROSS))

    def get_canvas(self):
        return self.canvas

    def get_axes(self):
        return self.axes

    def get_toolbar(self):
        return self.toolbar


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
        self.canvas.Bind(wx.EVT_ENTER_WINDOW, self.on_enter)

        self.check1 = wx.CheckBox(self, wx.ID_ANY, "Scan 1")
        self.check2 = wx.CheckBox(self, wx.ID_ANY, "Scan 2")
        self.checkDiff = wx.CheckBox(self, wx.ID_ANY, "Difference")
        self.checkGrid = wx.CheckBox(self, wx.ID_ANY, "Grid")
        self.check1.SetValue(True)
        self.check2.SetValue(True)
        self.checkDiff.SetValue(True)
        self.checkGrid.SetValue(True)
        self.on_check_grid(None)
        self.Bind(wx.EVT_CHECKBOX, self.on_check1, self.check1)
        self.Bind(wx.EVT_CHECKBOX, self.on_check2, self.check2)
        self.Bind(wx.EVT_CHECKBOX, self.on_check_diff, self.checkDiff)
        self.Bind(wx.EVT_CHECKBOX, self.on_check_grid, self.checkGrid)

        grid = wx.GridBagSizer(5, 5)
        grid.Add(self.check1, pos=(0, 0), flag=wx.ALIGN_CENTER)
        grid.Add(self.check2, pos=(0, 1), flag=wx.ALIGN_CENTER)
        grid.Add((20, 1), pos=(0, 2))
        grid.Add(self.checkDiff, pos=(0, 3), flag=wx.ALIGN_CENTER)
        grid.Add((20, 1), pos=(0, 4))
        grid.Add(self.checkGrid, pos=(0, 5), flag=wx.ALIGN_CENTER)

        toolbar = NavigationToolbarCompare(self.canvas)
        toolbar.Realize()

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        vbox.Add(grid, 0, wx.ALIGN_CENTRE | wx.ALL, border=5)
        vbox.Add(toolbar, 0, wx.EXPAND)

        self.SetSizer(vbox)
        vbox.Fit(self)

    def on_enter(self, _event):
        self.canvas.SetCursor(wx.StockCursor(wx.CURSOR_CROSS))

    def on_check1(self, _event):
        self.plotScan1.set_visible(self.check1.GetValue())
        self.canvas.draw()

    def on_check2(self, _event):
        self.plotScan2.set_visible(self.check2.GetValue())
        self.canvas.draw()

    def on_check_diff(self, _event):
        self.plotDiff.set_visible(self.checkDiff.GetValue())
        self.canvas.draw()

    def on_check_grid(self, _event):
        self.axesDiff.grid(self.checkGrid.GetValue())
        self.canvas.draw()

    def plot_diff(self):
        diff = {}

        if self.spectrum1 is not None and self.spectrum2 is not None:
            set1 = set(self.spectrum1)
            set2 = set(self.spectrum2)
            intersect = set1.intersection(set2)
            for freq in intersect:
                diff[freq] = self.spectrum1[freq] - self.spectrum2[freq]
            freqs, powers = split_spectrum(diff)
            self.plotDiff.set_xdata(freqs)
            self.plotDiff.set_ydata(powers)
        elif self.spectrum1 is None:
            freqs, powers = split_spectrum(self.spectrum2)
            self.plotDiff.set_xdata(freqs)
            self.plotDiff.set_ydata([0] * len(freqs))
        else:
            freqs, powers = split_spectrum(self.spectrum1)
            self.plotDiff.set_xdata(freqs)
            self.plotDiff.set_ydata([0] * len(freqs))

        self.axesDiff.relim()
        self.axesDiff.autoscale_view()

    def set_spectrum1(self, spectrum):
        self.spectrum1 = spectrum
        freqs, powers = split_spectrum(spectrum)
        self.plotScan1.set_xdata(freqs)
        self.plotScan1.set_ydata(powers)
        self.plot_diff()
        self.axesScan.relim()
        self.axesScan.autoscale_view()
        self.canvas.draw()

    def set_spectrum2(self, spectrum):
        self.spectrum2 = spectrum
        freqs, powers = split_spectrum(spectrum)
        self.plotScan2.set_xdata(freqs)
        self.plotScan2.set_ydata(powers)
        self.plot_diff()
        self.axesScan.relim()
        self.axesScan.autoscale_view()
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

    def on_load_plot(self, event):
        dlg = wx.FileDialog(self, "Open a scan", self.dirname, self.filename,
                            FILE_RFS, wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            _start, _stop, spectrum = open_plot(dlg.GetDirectory(),
                                                dlg.GetFilename())
            if(event.EventObject == self.buttonPlot1):
                self.textPlot1.SetLabel(dlg.GetFilename())
                self.graph.set_spectrum1(spectrum)
            else:
                self.textPlot2.SetLabel(dlg.GetFilename())
                self.graph.set_spectrum2(spectrum)
        dlg.Destroy()

    def on_close(self, _event):
        self.EndModal(wx.ID_CLOSE)
        return


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
        self.callback(CAL_START)

    def on_close(self, event):
        status = [CAL_CANCEL, CAL_OK][event.GetId() == wx.ID_OK]
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
    def __init__(self, parent, index, offset):
        self.index = index
        self.offset = offset
        self.band1 = None
        self.band2 = None

        wx.Dialog.__init__(self, parent=parent, title="Scan Offset")

        figure = matplotlib.figure.Figure(facecolor='white')
        self.axes = figure.add_subplot(111)
        self.canvas = FigureCanvas(self, -1, figure)
        self.canvas.Bind(wx.EVT_ENTER_WINDOW, self.on_enter)

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
                  flag=wx.ALIGN_CENTER | wx.ALL)
        gridSizer.Add(textHelp, pos=(1, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL)
        gridSizer.Add(boxSizer1, pos=(2, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL)
        gridSizer.Add(refresh, pos=(3, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL)
        gridSizer.Add(boxSizer2, pos=(4, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL)
        gridSizer.Add(sizerButtons, pos=(5, 1), span=(1, 1),
                  flag=wx.ALIGN_RIGHT | wx.ALL)

        self.SetSizerAndFit(gridSizer)
        self.draw_limits()

    def on_enter(self, _event):
        self.canvas.SetCursor(wx.StockCursor(wx.CURSOR_CROSS))

    def on_ok(self, _event):

        self.EndModal(wx.ID_OK)

    def on_refresh(self, _event):
        plot = []

        dlg = wx.BusyInfo('Please wait...')

        try:
            sdr = rtlsdr.RtlSdr(int(self.index))
            sdr.set_sample_rate(SAMPLE_RATE)
            sdr.set_center_freq(self.spinFreq.GetValue() * 1e6)
            sdr.set_gain(self.spinGain.GetValue())
            capture = sdr.read_samples(2 ** 18)
        except IOError as error:
            dlg.Destroy()
            dlg = wx.MessageDialog(self,
                                   'Capture failed:\n{0}'.format(error.message),
                                   'Error',
                                   wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return

        powers, freqs = matplotlib.mlab.psd(capture,
                         NFFT=1024,
                         Fs=SAMPLE_RATE / 1e6,
                         window=matplotlib.numpy.hamming(1024))

        for x, y in itertools.izip(freqs, powers):
            x = x * SAMPLE_RATE / 2e6
            plot.append((x, y))
        plot.sort()
        x, y = numpy.transpose(plot)

        self.axes.clear()
        self.band1 = None
        self.band2 = None
        self.axes.set_xlabel("Frequency (MHz)")
        self.axes.set_ylabel('Level (dB)')
        self.axes.set_yscale('log')
        self.axes.plot(x, y, linewidth=0.4)
        self.axes.grid(True)
        self.draw_limits()

        dlg.Destroy()

    def on_spin(self, _event):
        self.offset = self.spinOffset.GetValue()
        self.draw_limits()

    def draw_limits(self):
        limit1 = self.offset / 1e3
        limit2 = limit1 + BANDWIDTH / 1e6
        if(self.band1 is not None):
            self.band1.remove()
        if(self.band2 is not None):
            self.band2.remove()
        self.band1 = self.axes.axvspan(limit1, limit2, color='g', alpha=0.25)
        self.band2 = self.axes.axvspan(-limit1, -limit2, color='g', alpha=0.25)
        self.canvas.draw()

    def get_offset(self):
        return self.offset


class DialogPrefs(wx.Dialog):
    def __init__(self, parent, devices, settings):
        self.settings = settings
        self.index = 0

        wx.Dialog.__init__(self, parent=parent, title="Preferences")

        self.checkSaved = wx.CheckBox(self, wx.ID_ANY,
                                      "Save warning")
        self.checkSaved.SetValue(self.settings.saveWarn)
        self.checkSaved.SetToolTip(wx.ToolTip('Prompt to save scan on exit'))
        self.checkAnnotate = wx.CheckBox(self, wx.ID_ANY,
                                      "Label peak level")
        self.checkAnnotate.SetValue(self.settings.annotate)
        self.checkAnnotate.SetToolTip(wx.ToolTip('Annotate scan peak value'))

        self.checkRetain = wx.CheckBox(self, wx.ID_ANY,
                                      "Display previous scans*")
        self.checkRetain.SetToolTip(wx.ToolTip('Can be slow'))
        self.checkRetain.SetValue(self.settings.retainScans)
        self.Bind(wx.EVT_CHECKBOX, self.on_check, self.checkRetain)
        self.checkFade = wx.CheckBox(self, wx.ID_ANY,
                                      "Fade previous scans")
        self.checkFade.SetValue(self.settings.fadeScans)
        self.on_check(None)
        textWarn = wx.StaticText(self, label="*Only the most recent scan is saved")

        self.devices = devices
        self.gridDev = grid.Grid(self)
        self.gridDev.CreateGrid(len(self.devices), 7)
        self.gridDev.SetRowLabelSize(0)
        self.gridDev.SetColLabelValue(0, "Select")
        self.gridDev.SetColLabelValue(1, "Device")
        self.gridDev.SetColLabelValue(2, "Index")
        self.gridDev.SetColLabelValue(3, "Gain\n(dB)")
        self.gridDev.SetColLabelValue(4, "Calibration\n(ppm)")
        self.gridDev.SetColLabelValue(5, "LO\n(MHz)")
        self.gridDev.SetColLabelValue(6, "Band Offset\n(kHz)")
        self.gridDev.SetColFormatFloat(3, -1, 1)
        self.gridDev.SetColFormatFloat(4, -1, 3)
        self.gridDev.SetColFormatFloat(5, -1, 3)
        self.gridDev.SetColFormatFloat(6, -1, 0)

        attributes = grid.GridCellAttr()
        attributes.SetBackgroundColour(self.gridDev.GetLabelBackgroundColour())
        self.gridDev.SetColAttr(1, attributes)
        self.gridDev.SetColAttr(2, attributes)

        i = 0
        for device in self.devices:
            self.gridDev.SetReadOnly(i, 0, True)
            self.gridDev.SetReadOnly(i, 1, True)
            self.gridDev.SetReadOnly(i, 2, True)
            self.gridDev.SetCellRenderer(i, 0, CellRenderer())
            self.gridDev.SetCellEditor(i, 3, grid.GridCellFloatEditor(-1, 1))
            self.gridDev.SetCellEditor(i, 4, grid.GridCellFloatEditor(-1, 3))
            self.gridDev.SetCellEditor(i, 5, grid.GridCellFloatEditor(-1, 3))
            self.gridDev.SetCellValue(i, 1, device.name)
            self.gridDev.SetCellValue(i, 2, str(i))
            self.gridDev.SetCellValue(i, 3, str(device.gain))
            self.gridDev.SetCellValue(i, 4, str(device.calibration))
            self.gridDev.SetCellValue(i, 5, str(device.lo))
            self.gridDev.SetCellValue(i, 6, str(device.offset / 1e3))
            i += 1

        if settings.index > len(self.devices):
            settings.index = len(self.devices)
        self.select_row(settings.index)

        self.gridDev.AutoSize()

        self.Bind(grid.EVT_GRID_CELL_LEFT_CLICK, self.on_click)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.on_ok, buttonOk)

        optbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "General"),
                                     wx.VERTICAL)
        optbox.Add(self.checkSaved, 0, wx.ALL | wx.EXPAND, 10)
        optbox.Add(self.checkAnnotate, 0, wx.ALL | wx.EXPAND, 10)

        conbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "Continuous scans"),
                                     wx.HORIZONTAL)
        conbox.Add(self.checkRetain, 0, wx.ALL | wx.EXPAND, 10)
        conbox.Add(self.checkFade, 0, wx.ALL | wx.EXPAND, 10)
        conbox.Add(textWarn, 0, wx.ALL | wx.EXPAND, 10)

        devbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "Devices"),
                                     wx.VERTICAL)
        devbox.Add(self.gridDev, 0, wx.ALL | wx.EXPAND, 10)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(optbox, 0, wx.ALL | wx.EXPAND, 10)
        vbox.Add(conbox, 0, wx.ALL | wx.EXPAND, 10)
        vbox.Add(devbox, 0, wx.ALL | wx.EXPAND, 10)
        vbox.Add(sizerButtons, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizerAndFit(vbox)

    def on_check(self, _event):

        self.checkFade.Enable(self.checkRetain.GetValue())

    def on_click(self, event):
        col = event.GetCol()
        index = event.GetRow()
        if(col == 0):
            self.index = event.GetRow()
            self.select_row(index)
        elif(col == 6):
            dlg = DialogOffset(self, index,
                               float(self.gridDev.GetCellValue(index, 6)))
            if dlg.ShowModal() == wx.ID_OK:
                self.gridDev.SetCellValue(index, 6, str(dlg.get_offset()))
            dlg.Destroy()
        event.Skip()

    def on_ok(self, _event):
        self.settings.saveWarn = self.checkSaved.GetValue()
        self.settings.annotate = self.checkAnnotate.GetValue()
        self.settings.retainScans = self.checkRetain.GetValue()
        self.settings.fadeScans = self.checkFade.GetValue()
        for i in range(0, self.gridDev.GetNumberRows()):
            self.devices[i].gain = float(self.gridDev.GetCellValue(i, 3))
            self.devices[i].calibration = float(self.gridDev.GetCellValue(i, 4))
            self.devices[i].lo = float(self.gridDev.GetCellValue(i, 5))
            self.devices[i].offset = float(self.gridDev.GetCellValue(i, 6)) * 1e3

        self.EndModal(wx.ID_OK)

    def select_row(self, index):
        for i in range(0, self.gridDev.GetNumberRows()):
            tick = "0"
            if i == index:
                tick = "1"
            self.gridDev.SetCellValue(i, 0, tick)

    def get_index(self):
        return self.index

    def get_devices(self):
        return self.devices


class DialogSaveWarn(wx.Dialog):
    def __init__(self, parent, warnType):
        self.code = -1

        wx.Dialog.__init__(self, parent=parent, title="Warning",
                           style=wx.ICON_EXCLAMATION)

        prompt = ["scanning again", "opening a file", "exiting"][warnType]
        text = wx.StaticText(self, label="Save plot before {0}?".format(prompt))
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


class DialogRange(wx.Dialog):
    def __init__(self, parent, main):
        self.main = main

        wx.Dialog.__init__(self, parent=parent, title="Plot Range")

        self.checkAuto = wx.CheckBox(self, wx.ID_ANY, "Auto Range")
        self.checkAuto.SetValue(self.main.settings.yAuto)
        self.Bind(wx.EVT_CHECKBOX, self.on_auto, self.checkAuto)

        textMax = wx.StaticText(self, label="Maximum (dB)")
        self.yMax = masked.NumCtrl(self, value=int(self.main.settings.yMax),
                                    fractionWidth=0, min=-100, max=20)
        textMin = wx.StaticText(self, label="Minimum (dB)")
        self.yMin = masked.NumCtrl(self, value=int(self.main.settings.yMin),
                                    fractionWidth=0, min=-100, max=20)
        self.set_enabled(not self.main.settings.yAuto)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.on_ok, buttonOk)

        sizer = wx.GridBagSizer(10, 10)
        sizer.Add(self.checkAuto, pos=(0, 0), span=(1, 1),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        sizer.Add(textMax, pos=(1, 0), span=(1, 1),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        sizer.Add(self.yMax, pos=(1, 1), span=(1, 1),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        sizer.Add(textMin, pos=(2, 0), span=(1, 1),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        sizer.Add(self.yMin, pos=(2, 1), span=(1, 1),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        sizer.Add(sizerButtons, pos=(3, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)

    def on_auto(self, _event):
        self.set_enabled(not self.checkAuto.GetValue())

    def on_ok(self, _event):
        self.main.settings.yAuto = self.checkAuto.GetValue()
        self.main.settings.yMin = self.yMin.GetValue()
        self.main.settings.yMax = self.yMax.GetValue()
        self.EndModal(wx.ID_OK)

    def set_enabled(self, isEnabled):
        self.yMax.Enable(isEnabled)
        self.yMin.Enable(isEnabled)


class FrameMain(wx.Frame):
    def __init__(self, title):

        self.grid = True

        self.threadScan = None
        self.threadProcess = []
        self.threadPlot = None
        self.pendingPlot = False

        self.dlgCal = None

        self.menuOpen = None
        self.menuSave = None
        self.menuExport = None
        self.menuStart = None
        self.menuStop = None
        self.menuPref = None
        self.menuCompare = None
        self.menuCal = None

        self.panel = None
        self.graph = None
        self.canvas = None
        self.buttonStart = None
        self.buttonStop = None
        self.choiceMode = None
        self.choiceDwell = None
        self.choiceNfft = None
        self.spinCtrlStart = None
        self.spinCtrlStop = None
        self.checkUpdate = None
        self.checkGrid = None

        self.filename = ""
        self.dirname = "."

        self.spectrum = {}
        self.isSaved = True

        self.settings = Settings()
        self.devices = self.get_devices()
        self.oldCal = 0

        displaySize = wx.DisplaySize()
        wx.Frame.__init__(self, None, title=title, size=(displaySize[0] / 1.5,
                                                         displaySize[1] / 2))

        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_CLOSE, self.on_exit)

        self.status = self.CreateStatusBar()
        self.status.SetFieldsCount(3)
        self.statusProgress = wx.Gauge(self.status, -1,
                                        style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.statusProgress.Hide()

        self.create_widgets()
        self.create_menu()
        self.set_controls(True)
        self.menuSave.Enable(False)
        self.menuExport.Enable(False)
        self.Show()

        size = self.panel.GetSize()
        size[1] += displaySize[1] / 4
        self.SetMinSize(size)

        self.Connect(-1, -1, EVT_THREAD_STATUS, self.on_thread_status)

        self.SetDropTarget(DropTarget(self))

    def create_widgets(self):
        panel = wx.Panel(self)

        self.panel = wx.Panel(panel)
        self.graph = PanelGraph(panel, self)
        setup_plot(self.graph, self.settings, self.grid)

        self.buttonStart = wx.Button(self.panel, wx.ID_ANY, 'Start')
        self.buttonStop = wx.Button(self.panel, wx.ID_ANY, 'Stop')
        self.buttonStart.SetToolTip(wx.ToolTip('Start scan'))
        self.buttonStop.SetToolTip(wx.ToolTip('Stop scan'))
        self.Bind(wx.EVT_BUTTON, self.on_start, self.buttonStart)
        self.Bind(wx.EVT_BUTTON, self.on_stop, self.buttonStop)

        textRange = wx.StaticText(self.panel, label="Range (MHz)",
                                  style=wx.ALIGN_CENTER)
        textStart = wx.StaticText(self.panel, label="Start")
        textStop = wx.StaticText(self.panel, label="Stop")

        self.spinCtrlStart = wx.SpinCtrl(self.panel)
        self.spinCtrlStop = wx.SpinCtrl(self.panel)
        self.spinCtrlStart.SetToolTip(wx.ToolTip('Start frequency'))
        self.spinCtrlStop.SetToolTip(wx.ToolTip('Stop frequency'))
        self.spinCtrlStart.SetRange(F_MIN, F_MAX - 1)
        self.spinCtrlStop.SetRange(F_MIN + 1, F_MAX)
        self.set_range()
        self.Bind(wx.EVT_SPINCTRL, self.on_spin, self.spinCtrlStart)
        self.Bind(wx.EVT_SPINCTRL, self.on_spin, self.spinCtrlStop)

        textMode = wx.StaticText(self.panel, label="Mode")
        self.choiceMode = wx.Choice(self.panel, choices=MODE[::2])
        self.choiceMode.SetToolTip(wx.ToolTip('Scanning mode'))
        self.choiceMode.SetSelection(MODE[1::2].index(self.settings.mode))

        textDwell = wx.StaticText(self.panel, label="Dwell")
        self.choiceDwell = wx.Choice(self.panel, choices=DWELL[::2])
        self.choiceDwell.SetToolTip(wx.ToolTip('Scan time per step'))
        self.choiceDwell.SetSelection(DWELL[1::2].index(self.settings.dwell))

        textNfft = wx.StaticText(self.panel, label="FFT size")
        self.choiceNfft = wx.Choice(self.panel, choices=map(str, NFFT))
        self.choiceNfft.SetToolTip(wx.ToolTip('Higher values for greater precision'))
        self.choiceNfft.SetSelection(NFFT.index(self.settings.nfft))

        self.checkUpdate = wx.CheckBox(self.panel, wx.ID_ANY,
                                        "Live update")
        self.checkUpdate.SetToolTip(wx.ToolTip('Update plot with live samples'))
        self.checkUpdate.SetValue(self.settings.liveUpdate)
        self.Bind(wx.EVT_CHECKBOX, self.on_check_update, self.checkUpdate)

        self.checkGrid = wx.CheckBox(self.panel, wx.ID_ANY, "Grid")
        self.checkGrid.SetToolTip(wx.ToolTip('Draw grid'))
        self.checkGrid.SetValue(self.grid)
        self.Bind(wx.EVT_CHECKBOX, self.on_check_grid, self.checkGrid)

        grid = wx.GridBagSizer(5, 5)

        grid.Add(self.buttonStart, pos=(0, 0), span=(2, 1),
                 flag=wx.ALIGN_CENTER)
        grid.Add(self.buttonStop, pos=(0, 1), span=(2, 1),
                 flag=wx.ALIGN_CENTER)

        grid.Add((20, 1), pos=(0, 2))

        grid.Add(textRange, pos=(0, 3), span=(1, 4), flag=wx.ALIGN_CENTER)
        grid.Add(textStart, pos=(1, 3), flag=wx.ALIGN_CENTER)
        grid.Add(self.spinCtrlStart, pos=(1, 4))
        grid.Add(textStop, pos=(1, 5), flag=wx.ALIGN_CENTER)
        grid.Add(self.spinCtrlStop, pos=(1, 6))

        grid.Add((20, 1), pos=(0, 7))

        grid.Add(textMode, pos=(0, 8), flag=wx.ALIGN_CENTER)
        grid.Add(self.choiceMode, pos=(1, 8), flag=wx.ALIGN_CENTER)

        grid.Add(textDwell, pos=(0, 9), flag=wx.ALIGN_CENTER)
        grid.Add(self.choiceDwell, pos=(1, 9), flag=wx.ALIGN_CENTER)

        grid.Add(textNfft, pos=(0, 10), flag=wx.ALIGN_CENTER)
        grid.Add(self.choiceNfft, pos=(1, 10), flag=wx.ALIGN_CENTER)

        grid.Add((20, 1), pos=(0, 11))

        grid.Add(self.checkUpdate, pos=(0, 12))
        grid.Add(self.checkGrid, pos=(1, 12))

        self.panel.SetSizer(grid)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.graph, 1, wx.EXPAND)
        sizer.Add(self.panel, 0, wx.ALIGN_CENTER)
        panel.SetSizer(sizer)

    def create_menu(self):
        menuFile = wx.Menu()
        self.menuOpen = menuFile.Append(wx.ID_OPEN, "&Open...", "Open plot")
        self.menuSave = menuFile.Append(wx.ID_SAVE, "&Save As...",
                                          "Save plot")
        self.menuExport = menuFile.Append(wx.ID_ANY, "&Export...",
                                            "Export plot")
        menuExit = menuFile.Append(wx.ID_EXIT, "E&xit", "Exit the program")

        menuScan = wx.Menu()
        self.menuStart = menuScan.Append(wx.ID_ANY, "&Start", "Start scan")
        self.menuStop = menuScan.Append(wx.ID_ANY, "S&top", "Stop scan")

        menuView = wx.Menu()
        self.menuPref = menuView.Append(wx.ID_ANY, "&Preferences...",
                                   "Preferences")

        menuTools = wx.Menu()
        self.menuCompare = menuTools.Append(wx.ID_ANY, "&Compare...",
                                            "Compare plots")
        self.menuCal = menuTools.Append(wx.ID_ANY, "&Auto Calibration...",
                               "Automatically calibrate to a known frequency")

        menuHelp = wx.Menu()
        menuHelpLink = menuHelp.Append(wx.ID_HELP, "&Help...",
                                            "Link to help")
        menuAbout = menuHelp.Append(wx.ID_ABOUT, "&About...",
                                            "Information about this program")

        menuBar = wx.MenuBar()
        menuBar.Append(menuFile, "&File")
        menuBar.Append(menuScan, "&Scan")
        menuBar.Append(menuView, "&View")
        menuBar.Append(menuTools, "&Tools")
        menuBar.Append(menuHelp, "&Help")
        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.on_open, self.menuOpen)
        self.Bind(wx.EVT_MENU, self.on_save, self.menuSave)
        self.Bind(wx.EVT_MENU, self.on_export, self.menuExport)
        self.Bind(wx.EVT_MENU, self.on_exit, menuExit)
        self.Bind(wx.EVT_MENU, self.on_start, self.menuStart)
        self.Bind(wx.EVT_MENU, self.on_stop, self.menuStop)
        self.Bind(wx.EVT_MENU, self.on_pref, self.menuPref)
        self.Bind(wx.EVT_MENU, self.on_compare, self.menuCompare)
        self.Bind(wx.EVT_MENU, self.on_cal, self.menuCal)
        self.Bind(wx.EVT_MENU, self.on_about, menuAbout)
        self.Bind(wx.EVT_MENU, self.on_help, menuHelpLink)

        idF1 = wx.wx.NewId()
        self.Bind(wx.EVT_MENU, self.on_help, id=idF1)
        accelTable = wx.AcceleratorTable([(wx.ACCEL_NORMAL, wx.WXK_F1, idF1)])
        self.SetAcceleratorTable(accelTable)

    def on_open(self, _event):
        if self.save_warn(WARN_OPEN):
            return
        dlg = wx.FileDialog(self, "Open a scan", self.dirname, self.filename,
                            FILE_RFS, wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.open(dlg.GetDirectory(), dlg.GetFilename())
        dlg.Destroy()

    def on_save(self, _event):
        dlg = wx.FileDialog(self, "Save a scan", self.dirname,
                            self.filename + ".rfs", FILE_RFS,
                            wx.SAVE | wx.OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            self.status.SetStatusText("Saving", 0)
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()
            handle = open(os.path.join(self.dirname, self.filename), 'wb')
            cPickle.dump(FILE_HEADER, handle)
            cPickle.dump(FILE_VERSION, handle)
            cPickle.dump(self.settings.start, handle)
            cPickle.dump(self.settings.stop, handle)
            cPickle.dump(self.spectrum, handle)
            handle.close()
            self.isSaved = True
            self.status.SetStatusText("Finished", 0)
        dlg.Destroy()

    def on_export(self, _event):
        dlg = wx.FileDialog(self, "Export a scan", self.dirname,
                            self.filename + ".csv", FILE_CSV, wx.SAVE)
        if dlg.ShowModal() == wx.ID_OK:
            self.status.SetStatusText("Exporting", 0)
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()
            handle = open(os.path.join(self.dirname, self.filename), 'wb')
            handle.write("Frequency (MHz),Level (dB)\n")
            for freq, pwr in self.spectrum.iteritems():
                handle.write("{0},{1}\n".format(freq, pwr))
            handle.close()
            self.status.SetStatusText("Finished", 0)
        dlg.Destroy()

    def on_exit(self, _event):
        self.Unbind(wx.EVT_CLOSE)
        if self.save_warn(WARN_EXIT):
            self.Bind(wx.EVT_CLOSE, self.on_exit)
            return
        self.stop_scan()
        self.wait_threads()
        self.get_range()
        self.settings.dwell = DWELL[1::2][self.choiceDwell.GetSelection()]
        self.settings.nfft = NFFT[self.choiceNfft.GetSelection()]
        self.settings.devices = self.devices
        self.settings.save()
        self.Close(True)

    def on_pref(self, _event):
        self.devices = self.refresh_devices()
        dlg = DialogPrefs(self, self.devices, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            self.devices = dlg.get_devices()
            self.settings.index = dlg.get_index()
        dlg.Destroy()

    def on_compare(self, _event):
        dlg = DialogCompare(self, self.dirname, self.filename)
        dlg.ShowModal()
        dlg.Destroy()

    def on_cal(self, _event):
        self.dlgCal = DialogAutoCal(self, self.settings.calFreq, self.auto_cal)
        self.dlgCal.ShowModal()

    def on_about(self, _event):
        dlg = wx.MessageDialog(self,
            "A tool for scanning frequency ranges "
            "with an RTL-SDR compatible USB dongle",
            "RTLSDR Scanner",
            wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def on_help(self, _event):
        webbrowser.open("http://eartoearoak.com/software/rtlsdr-scanner")

    def on_spin(self, event):
        control = event.GetEventObject()
        if control == self.spinCtrlStart:
            self.spinCtrlStop.SetRange(self.spinCtrlStart.GetValue() + 1,
                                          F_MAX)

    def on_start(self, _event):
        self.get_range()
        self.graph.get_axes().clear()
        scale_plot(self.graph, self.settings)
        self.scan_start(False)

    def on_stop(self, _event):
        self.stop_scan()

    def on_check_update(self, _event):
        self.settings.liveUpdate = self.checkUpdate.GetValue()

    def on_check_grid(self, _event):
        self.grid = self.checkGrid.GetValue()
        self.draw_plot()

    def on_thread_status(self, event):
        status = event.data.get_status()
        freq = event.data.get_freq()
        data = event.data.get_data()
        thread = event.data.get_thread()
        if status == THREAD_STATUS_STARTING:
            self.status.SetStatusText("Starting", 0)
        elif status == THREAD_STATUS_SCAN:
            self.status.SetStatusText("Scanning", 0)
            self.statusProgress.Show()
            self.statusProgress.SetValue(data)
        elif status == THREAD_STATUS_DATA:
            self.isSaved = False
            fftChoice = self.choiceNfft.GetSelection()
            nfft = NFFT[fftChoice]
            self.threadProcess.append(ThreadProcess(self, freq, data,
                                                    self.settings,
                                                    self.devices, nfft))
        elif status == THREAD_STATUS_FINISHED:
            self.statusProgress.Hide()
            self.status.SetStatusText("Finished", 0)
            self.threadScan = None
            self.scanFinished = True
            if self.settings.mode != 1:
                self.set_controls(True)
            if data:
                self.auto_cal(CAL_DONE)
        elif status == THREAD_STATUS_STOPPED:
            self.statusProgress.Hide()
            self.status.SetStatusText("Stopped", 0)
            self.threadScan = None
            self.set_controls(True)
            self.draw_plot()
        elif status == THREAD_STATUS_ERROR:
            self.statusProgress.Hide()
            self.status.SetStatusText("Dongle error: {0}".format(data), 0)
            self.threadScan = None
            self.set_controls(True)
            if self.dlgCal is not None:
                self.dlgCal.Destroy()
                self.dlgCal = None
        elif status == THREAD_STATUS_PROCESSED:
            self.threadProcess.remove(thread)
            self.update_scan(freq, data)
            if self.settings.liveUpdate or freq > self.settings.stop * 1e6:
                self.draw_plot()
            if self.settings.mode == 1 and freq > self.settings.stop * 1e6:
                if self.dlgCal is None:
                    self.draw_plot(True)
                    self.scan_start(False)
        elif status == THREAD_STATUS_PLOTTED:
            self.threadPlot = None
            if self.pendingPlot:
                self.draw_plot()

    def on_size(self, event):
        rect = self.status.GetFieldRect(2)
        self.statusProgress.SetPosition((rect.x + 10, rect.y + 2))
        self.statusProgress.SetSize((rect.width - 20, rect.height - 4))
        event.Skip()

    def open(self, dirname, filename):
        self.filename = filename
        self.dirname = dirname
        self.status.SetStatusText("Opening: {0}".format(filename), 0)

        start, stop, spectrum = open_plot(dirname, filename)

        if len(spectrum) > 0:
            self.settings.start = start
            self.settings.stop = stop
            self.spectrum = spectrum
            self.isSaved = True
            self.set_range()
            self.set_controls(True)
            self.draw_plot()
            self.status.SetStatusText("Finished", 0)
        else:
            self.status.SetStatusText("Open failed", 0)

    def auto_cal(self, status):
        freq = self.dlgCal.get_freq()
        if self.dlgCal is not None:
            if status == CAL_START:
                self.spinCtrlStart.SetValue(freq - 1)
                self.spinCtrlStop.SetValue(freq + 1)
                self.oldCal = self.devices[self.settings.index].calibration
                self.devices[self.settings.index].calibration = 0
                if not self.scan_start(True):
                    self.dlgCal.reset_cal()
            elif status == CAL_DONE:
                ppm = self.calc_ppm(freq)
                self.dlgCal.set_cal(ppm)
                self.set_controls(True)
            elif status == CAL_OK:
                self.devices[self.settings.index].calibration = self.dlgCal.get_cal()
                self.settings.calFreq = freq
                self.dlgCal = None
            elif status == CAL_CANCEL:
                self.dlgCal = None
                if len(self.devices) > 0:
                    self.devices[self.settings.index].calibration = self.oldCal

    def calc_ppm(self, freq):
        spectrum = self.spectrum.copy()
        for x, y in spectrum.iteritems():
            spectrum[x] = (((x - freq) * (x - freq)) + 1) * y

        peak = max(spectrum, key=spectrum.get)

        return ((freq - peak) / freq) * 1e6

    def scan_start(self, isCal):
        if self.save_warn(WARN_SCAN):
            return False

        self.devices = self.refresh_devices()
        if(len(self.devices) == 0):
            wx.MessageBox('No devices found',
                          'Error', wx.OK | wx.ICON_ERROR)
            return

        if self.settings.start >= self.settings.stop:
            wx.MessageBox('Stop frequency must be greater that start',
                          'Warning', wx.OK | wx.ICON_WARNING)
            return

        choiceDwell = self.choiceDwell.GetSelection()

        if not self.threadScan or not self.threadScan.is_alive():

            self.set_controls(False)
            dwell = DWELL[1::2][choiceDwell]
            samples = dwell * SAMPLE_RATE
            samples = next_2_to_pow(int(samples))
            self.spectrum.clear()
            self.scanFinished = False
            self.status.SetStatusText("", 1)
            self.threadScan = ThreadScan(self, self.settings, self.devices,
                                     samples, isCal)
            self.filename = "Scan {0:.1f}-{1:.1f}MHz".format(self.settings.start,
                                                            self.settings.stop)

            return True

    def stop_scan(self):
        if self.threadScan and self.threadScan.isAlive():
            self.status.SetStatusText("Stopping", 0)
            self.threadScan.abort()

    def update_scan(self, freqCentre, scan):
        offset = self.settings.devices[self.settings.index].offset
        upperStart = freqCentre + offset
        upperEnd = freqCentre + offset + BANDWIDTH / 2
        lowerStart = freqCentre - offset - BANDWIDTH / 2
        lowerEnd = freqCentre - offset

        for freq in scan:
            if self.settings.start < freq < self.settings.stop:
                power = 10 * math.log10(scan[freq])
                if upperStart < freq * 1e6 < upperEnd:
                    self.spectrum[freq] = power
                if lowerStart < freq * 1e6 < lowerEnd:
                    if freq in self.spectrum:
                        self.spectrum[freq] = (self.spectrum[freq] + power) / 2
                    else:
                        self.spectrum[freq] = power

    def set_controls(self, state):
        self.spinCtrlStart.Enable(state)
        self.spinCtrlStop.Enable(state)
        self.choiceMode.Enable(state)
        self.choiceDwell.Enable(state)
        self.choiceNfft.Enable(state)
        self.buttonStart.Enable(state)
        self.buttonStop.Enable(not state)
        self.menuOpen.Enable(state)
        self.menuSave.Enable(state)
        self.menuExport.Enable(state)
        self.menuStart.Enable(state)
        self.menuStop.Enable(not state)
        self.menuPref.Enable(state)
        self.menuCal.Enable(state)

    def draw_plot(self, full=False):

        if len(self.spectrum) > 0:
            if full and self.threadPlot is not None:
                self.threadPlot.join()
                self.threadPlot = None

            if self.threadPlot is None:
                self.threadPlot = ThreadPlot(self, self.graph, self.spectrum,
                                             self.settings, self.grid, full)
                self.pendingPlot = False
            else:
                self.pendingPlot = True

    def save_warn(self, warnType):
        if self.settings.saveWarn and not self.isSaved:
            dlg = DialogSaveWarn(self, warnType)
            code = dlg.ShowModal()
            if code == wx.ID_YES:
                self.on_save(None)
                if self.isSaved:
                    return False
                else:
                    return True
            elif code == wx.ID_NO:
                return False
            else:
                return True

        return False

    def wait_threads(self):
        self.Disconnect(-1, -1, EVT_THREAD_STATUS, self.on_thread_status)
        if self.threadScan:
            self.threadScan.join()
            self.threadScan = None
        if self.threadPlot:
            self.threadPlot.join()
            self.threadPlot = None
        if len(self.threadProcess) > 0:
            for thread in self.threadProcess:
                thread.join()

    def set_range(self):
        self.spinCtrlStart.SetValue(self.settings.start)
        self.spinCtrlStop.SetValue(self.settings.stop)

    def get_range(self):
        choiceMode = self.choiceMode.GetSelection()

        self.settings.mode = MODE[1::2][choiceMode]
        self.settings.start = self.spinCtrlStart.GetValue()
        self.settings.stop = self.spinCtrlStop.GetValue()

    def refresh_devices(self):
        self.settings.devices = self.devices
        self.settings.save()
        return self.get_devices()

    def get_devices(self):
        devices = []
        count = rtlsdr.librtlsdr.rtlsdr_get_device_count()

        for dev in range(0, count):
            device = Device()
            device.index = dev
            device.name = format_device_name(rtlsdr.librtlsdr.rtlsdr_get_device_name(dev))
            device.calibration = 0.0
            device.lo = 0.0
            for conf in self.settings.devices:
                # TODO: better matching than just name?
                if device.name == conf.name:
                    device.gain = conf.gain
                    device.calibration = conf.calibration
                    device.lo = conf.lo
                    device.offset = conf.offset
                    break

            devices.append(device)

        return devices


def next_2_to_pow(val):
    val -= 1
    val |= val >> 1
    val |= val >> 2
    val |= val >> 4
    val |= val >> 8
    val |= val >> 16
    return val + 1


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="plot filename", nargs='?')
    args = parser.parse_args()

    filename = None
    directory = None
    if args.file != None:
        directory, filename = os.path.split(args.file)

    return directory, filename


if __name__ == '__main__':
    app = wx.App(False)
    frame = FrameMain("RTLSDR Scanner")
    directory, filename = arguments()

    if filename != None:
        frame.open(directory, filename)
    app.MainLoop()
