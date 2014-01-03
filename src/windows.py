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
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas, \
    NavigationToolbar2WxAgg
from matplotlib.colorbar import ColorbarBase
from matplotlib.colors import Normalize
from matplotlib.ticker import AutoMinorLocator, ScalarFormatter
import numpy
import rtlsdr
import wx

from constants import *
from events import EventThreadStatus, Event, post_event
from misc import split_spectrum, nearest, open_plot, load_bitmap, get_colours
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
        self.AddSeparator()

        navId = wx.NewId()
        self.AddSimpleTool(navId, load_bitmap('range'),
                           'Range', 'Set plot range')
        wx.EVT_TOOL(self, navId, self.on_range)

        self.AddSeparator()

        self.autoId = wx.NewId()
        self.AddCheckTool(self.autoId, load_bitmap('auto_range'),
                          shortHelp='Auto range',
                          longHelp='Scale plot to all measurements')
        self.ToggleTool(self.autoId, self.main.settings.autoScale)
        wx.EVT_TOOL(self, self.autoId, self.on_check_auto)

        liveId = wx.NewId()
        self.AddCheckTool(liveId, load_bitmap('auto_refresh'),
                          shortHelp='Live update',
                          longHelp='Update plot in realtime (slow)')
        self.ToggleTool(liveId, self.main.settings.liveUpdate)
        wx.EVT_TOOL(self, liveId, self.on_check_update)

        gridId = wx.NewId()
        self.AddCheckTool(gridId, load_bitmap('grid'),
                          shortHelp='Grid',
                          longHelp='Toggle grid')
        self.ToggleTool(gridId, self.main.grid)
        wx.EVT_TOOL(self, gridId, self.on_check_grid)

        peakId = wx.NewId()
        self.AddCheckTool(peakId, load_bitmap('peak'),
                          shortHelp='Label peak',
                          longHelp='Label peak')
        wx.EVT_TOOL(self, peakId, self.on_check_peak)
        self.ToggleTool(peakId, self.main.settings.annotate)

    def on_range(self, _event):
        dlg = DialogRange(self, self.main)
        if dlg.ShowModal() == wx.ID_OK:
            self.main.plot.scale_plot()
            self.ToggleTool(self.autoId, self.main.settings.autoScale)
            self.main.plot.redraw_plot()
        dlg.Destroy()

    def on_check_auto(self, event):
        self.main.settings.autoScale = event.Checked()
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

    def on_colour(self, event):
        colourMap = event.GetString()
        self.main.settings.colourMap = colourMap
        self.main.plot.set_colourmap(colourMap)
        self.main.plot.redraw_plot()

    def set_type(self, isSpectrogram):
        for toolId in self.extraTools:
            self.DeleteTool(toolId)
        self.extraTools = []

        if not isSpectrogram:
            fadeId = wx.NewId()
            self.AddCheckTool(fadeId, load_bitmap('fade'),
                              shortHelp='Fade plots',
                              longHelp='Fade plots')
            wx.EVT_TOOL(self, fadeId, self.on_check_fade)
            self.ToggleTool(fadeId, self.main.settings.fadeScans)
            self.extraTools.append(fadeId)
        else:
            separator = self.AddSeparator()
            separatorId = separator.GetId()
            self.extraTools.append(separatorId)
            self.extraTools.append(separatorId)

            colours = get_colours()
            colourId = wx.NewId()
            control = wx.Choice(self, id=colourId, choices=colours)
            control.SetSelection(colours.index(self.main.settings.colourMap))
            self.AddControl(control)
            self.Bind(wx.EVT_CHOICE, self.on_colour, control)
            self.extraTools.append(colourId)

        self.Realize()


class NavigationToolbarCompare(NavigationToolbar2WxAgg):
    def __init__(self, canvas, main):
        NavigationToolbar2WxAgg.__init__(self, canvas)
        self.main = main

        self.AddSeparator()

        gridId = wx.NewId()
        self.AddCheckTool(gridId, load_bitmap('grid'),
                          shortHelp='Grid',
                          longHelp='Toggle grid')
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
        if xpos is not None and ypos is not None and len(self.main.spectrum) > 0:
            timeStamp = max(self.main.spectrum)
            spectrum = self.main.spectrum[timeStamp]
            if len(spectrum) > 0:
                x = min(spectrum.keys(), key=lambda freq: abs(freq - xpos))
                if(xpos <= max(spectrum.keys(), key=float)):
                    y = spectrum[x]
                    text = "f = {0:.6f}MHz, p = {1:.2f}dB".format(x, y)
                else:
                    text = "f = {0:.6f}MHz".format(xpos)

        self.main.status.SetStatusText(text, 1)

    def on_draw(self, _event):
        post_event(self.main, EventThreadStatus(Event.PLOTTED))

    def set_type(self, isSpectrogram):
        self.toolbar.set_type(isSpectrogram)

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
    def __init__(self, parent, device, offset):
        self.device = device
        self.offset = offset
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

    def on_ok(self, _event):
        self.EndModal(wx.ID_OK)

    def on_refresh(self, _event):
        plot = []

        dlg = wx.BusyInfo('Please wait...')

        try:
            if self.device.isDevice:
                sdr = rtlsdr.RtlSdr(self.device.index)
            else:
                sdr = RtlTcp(self.device.server, self.device.port)
            sdr.set_sample_rate(SAMPLE_RATE)
            sdr.set_center_freq(self.spinFreq.GetValue() * 1e6)
            sdr.set_gain(self.spinGain.GetValue())
            capture = sdr.read_samples(2 ** 18)
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


class DialogProperties(wx.Dialog):
    def __init__(self, parent, scanInfo):
        wx.Dialog.__init__(self, parent, title="Scan Properties")

        self.scanInfo = scanInfo

        box = wx.BoxSizer(wx.VERTICAL)

        grid = wx.GridBagSizer(0, 0)

        boxScan = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "Scan"),
                                     wx.HORIZONTAL)

        gridScan = wx.GridBagSizer(0, 0)

        textStart = wx.StaticText(self, label="Start")
        gridScan.Add(textStart, (0, 0), (1, 1), wx.ALL, 5)
        textCtrlStart = wx.TextCtrl(self, value="Unknown",
                                    style=wx.TE_READONLY)
        if scanInfo.start is not None:
            textCtrlStart.SetValue(str(scanInfo.start))
        gridScan.Add(textCtrlStart, (0, 1), (1, 1), wx.ALL, 5)
        textMHz1 = wx.StaticText(self, wx.ID_ANY, label="MHz")
        gridScan.Add(textMHz1, (0, 2), (1, 1), wx.ALL, 5)

        textStop = wx.StaticText(self, label="Stop")
        gridScan.Add(textStop, (1, 0), (1, 1), wx.ALL, 5)
        textCtrlStop = wx.TextCtrl(self, value="Unknown",
                                   style=wx.TE_READONLY)
        if scanInfo.stop is not None:
            textCtrlStop.SetValue(str(scanInfo.stop))
        gridScan.Add(textCtrlStop, (1, 1), (1, 1), wx.ALL, 5)
        textMHz2 = wx.StaticText(self, label="MHz")
        gridScan.Add(textMHz2, (1, 2), (1, 1), wx.ALL, 5)

        textDwell = wx.StaticText(self, label="Dwell")
        gridScan.Add(textDwell, (2, 0), (1, 1), wx.ALL, 5)
        textCtrlDwell = wx.TextCtrl(self, value="Unknown",
                                    style=wx.TE_READONLY)
        if scanInfo.dwell is not None:
            textCtrlDwell.SetValue(str(scanInfo.dwell))
        gridScan.Add(textCtrlDwell, (2, 1), (1, 1), wx.ALL, 5)
        textSeconds = wx.StaticText(self, label="seconds")
        gridScan.Add(textSeconds, (2, 2), (1, 1), wx.ALL, 5)

        textNfft = wx.StaticText(self, label="FFT Size")
        gridScan.Add(textNfft, (3, 0), (1, 1), wx.ALL, 5)
        textCtrlNfft = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.nfft is not None:
            textCtrlNfft.SetValue(str(scanInfo.nfft))
        gridScan.Add(textCtrlNfft, (3, 1), (1, 1), wx.ALL, 5)

        textTime = wx.StaticText(self, label="Time")
        gridScan.Add(textTime, (4, 0), (1, 1), wx.ALL, 5)
        textCtrlTime = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.time is not None:
            textCtrlTime.SetValue(scanInfo.time)
        gridScan.Add(textCtrlTime, (4, 1), (1, 1), wx.ALL, 5)

        textLat = wx.StaticText(self, label="Latitude")
        gridScan.Add(textLat, (5, 0), (1, 1), wx.ALL, 5)
        self.textCtrlLat = wx.TextCtrl(self, value="Unknown")
        self.textCtrlLat.SetValidator(ValidatorCoord(True))
        if scanInfo.lat is not None:
            self.textCtrlLat.SetValue(str(scanInfo.lat))
        gridScan.Add(self.textCtrlLat, (5, 1), (1, 1), wx.ALL, 5)

        textLon = wx.StaticText(self, label="Longitude")
        gridScan.Add(textLon, (6, 0), (1, 1), wx.ALL, 5)
        self.textCtrlLon = wx.TextCtrl(self, value="Unknown")
        self.textCtrlLon.SetValidator(ValidatorCoord(False))
        if scanInfo.lon is not None:
            self.textCtrlLon.SetValue(str(scanInfo.lon))
        gridScan.Add(self.textCtrlLon, (6, 1), (1, 1), wx.ALL, 5)

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
        gridDevice.Add(textCtrlName, (0, 1), (1, 1), wx.ALL, 5)

        textTuner = wx.StaticText(self, label="Tuner")
        gridDevice.Add(textTuner, (1, 0), (1, 1), wx.ALL, 5)

        textCtrlTuner = wx.TextCtrl(self, value="Unknown",
                                    style=wx.TE_READONLY)
        if scanInfo.tuner != -1:
            textCtrlTuner.SetValue(TUNER[scanInfo.tuner])
        gridDevice.Add(textCtrlTuner, (1, 1), (1, 1), wx.ALL, 5)

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

        self.checkRetain = wx.CheckBox(self, wx.ID_ANY,
                                      "Retain previous scans")
        self.checkRetain.SetToolTip(wx.ToolTip('Can be slow'))
        self.checkRetain.SetValue(self.settings.retainScans)
        self.Bind(wx.EVT_CHECKBOX, self.on_check, self.checkRetain)
        textWarn = wx.StaticText(self,
                                 label="(Needed for Spectrogram view)")
        textMaxScans = wx.StaticText(self, label="Max scans")
        self.spinCtrlMaxScans = wx.SpinCtrl(self)
        self.spinCtrlMaxScans.SetRange(2, 500)
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

        self.on_check(None)

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

        colourBackground = self.gridDev.GetLabelBackgroundColour()
        attributes = grid.GridCellAttr()
        attributes.SetBackgroundColour(colourBackground)
        self.gridDev.SetColAttr(self.COL_IND, attributes)

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
                                          str(nearest(device.gain, device.gains)))
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

        if settings.index >= len(self.devices):
            settings.index = len(self.devices) - 1
        self.select_row(settings.index)
        self.index = settings.index

        self.gridDev.AutoSize()

        self.Bind(grid.EVT_GRID_CELL_LEFT_CLICK, self.on_click)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.on_ok, buttonOk)

        genbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "General"),
                                     wx.VERTICAL)
        genbox.Add(self.checkSaved, 0, wx.ALL | wx.EXPAND, 10)

        congrid = wx.GridBagSizer(10, 10)
        congrid.Add(self.checkRetain, pos=(0, 0), flag=wx.ALL)
        congrid.Add(textWarn, pos=(0, 1), flag=wx.ALL)
        congrid.Add(textMaxScans, pos=(1, 0), flag=wx.ALL)
        congrid.Add(self.spinCtrlMaxScans, pos=(1, 1), flag=wx.ALL)
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
        devbox.Add(self.gridDev, 0, wx.ALL | wx.EXPAND, 10)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(genbox, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        vbox.Add(conbox, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        vbox.Add(plotbox, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        vbox.Add(specbox, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        vbox.Add(devbox, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        vbox.Add(sizerButtons, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizerAndFit(vbox)

    def on_check(self, _event):
        enabled = self.checkRetain.GetValue()
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
                               float(self.gridDev.GetCellValue(index, self.COL_OFF)))
            if dlg.ShowModal() == wx.ID_OK:
                self.gridDev.SetCellValue(index, self.COL_OFF, str(dlg.get_offset()))
            dlg.Destroy()
        else:
            self.gridDev.ForceRefresh()
            event.Skip()

    def on_ok(self, _event):
        self.settings.saveWarn = self.checkSaved.GetValue()
        self.settings.retainScans = self.checkRetain.GetValue()
        self.settings.fadeScans = self.checkFade.GetValue()
        self.settings.retainMax = self.spinCtrlMaxScans.GetValue()
        self.settings.colourMap = self.choiceColour.GetStringSelection()
        for i in range(0, self.gridDev.GetNumberRows()):
            if not self.devices[i].isDevice:
                server = self.gridDev.GetCellValue(i, self.COL_DEV)
                server = '//' + server
                url = urlparse(server)
                if url.hostname is not None:
                    self.devices[i].server = url.hostname
                else:
                    self.devices[i].port = 'localhost'
                if url.port is not None:
                    self.devices[i].port = url.port
                else:
                    self.devices[i].port = 1234
            self.devices[i].gain = float(self.gridDev.GetCellValue(i, self.COL_GAIN))
            self.devices[i].calibration = float(self.gridDev.GetCellValue(i, self.COL_CAL))
            self.devices[i].lo = float(self.gridDev.GetCellValue(i, self.COL_LO))
            self.devices[i].offset = float(self.gridDev.GetCellValue(i, self.COL_OFF)) * 1e3

        self.EndModal(wx.ID_OK)

    def select_row(self, index):
        self.gridDev.ClearSelection()
        for i in range(0, self.gridDev.GetNumberRows()):
            tick = "0"
            if i == index:
                tick = "1"
            self.gridDev.SetCellValue(i, self.COL_SEL, tick)

    def get_index(self):
        return self.index

    def get_devices(self):
        return self.devices


class DialogSaveWarn(wx.Dialog):
    def __init__(self, parent, warnType):
        self.code = -1

        wx.Dialog.__init__(self, parent=parent, title="Warning")

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

        self.checkAuto = wx.CheckBox(self, wx.ID_ANY, "Auto range")
        self.checkAuto.SetValue(self.main.settings.autoScale)
        self.Bind(wx.EVT_CHECKBOX, self.on_auto, self.checkAuto)

        textMax = wx.StaticText(self, label="Maximum (dB)")
        self.yMax = masked.NumCtrl(self, value=int(self.main.settings.yMax),
                                    fractionWidth=0, min=-100, max=20)
        textMin = wx.StaticText(self, label="Minimum (dB)")
        self.yMin = masked.NumCtrl(self, value=int(self.main.settings.yMin),
                                    fractionWidth=0, min=-100, max=20)
        self.set_enabled(not self.main.settings.autoScale)

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
        state = self.checkAuto.GetValue()
        self.set_enabled(not state)

    def on_ok(self, _event):
        self.main.settings.autoScale = self.checkAuto.GetValue()
        self.main.settings.yMin = self.yMin.GetValue()
        self.main.settings.yMax = self.yMax.GetValue()
        self.EndModal(wx.ID_OK)

    def set_enabled(self, isEnabled):
        self.yMax.Enable(isEnabled)
        self.yMin.Enable(isEnabled)


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


class ValidatorCoord(wx.PyValidator):
    def __init__(self, isLat):
        wx.PyValidator.__init__(self)
        self.isLat = isLat

    def Validate(self, _window):
        textCtrl = self.GetWindow()
        text = textCtrl.GetValue()
        if len(text) == 0 or text == '-' or text.lower() == 'unknown':
            textCtrl.SetForegroundColour("black")
            textCtrl.Refresh()
            return True

        value = None
        try:
            value = float(text)
            if self.isLat and (value < -90 or value > 90):
                raise ValueError()
            elif value < -180 or value > 180:
                raise ValueError()
        except ValueError:
            textCtrl.SetForegroundColour("red")
            textCtrl.SetFocus()
            textCtrl.Refresh()
            return False

        textCtrl.SetForegroundColour("black")
        textCtrl.Refresh()
        return True

    def TransferToWindow(self):
        return True

    def TransferFromWindow(self):
        return True

    def Clone(self):
        return ValidatorCoord(self.isLat)


def close_modeless():
    for child in wx.GetTopLevelWindows():
        if child.Title == 'Configure subplots':
            child.Close()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
