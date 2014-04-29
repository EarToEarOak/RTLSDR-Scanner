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
import itertools
from urlparse import urlparse

import matplotlib
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
import numpy
import rtlsdr
from wx import grid
import wx
from wx.lib import masked
from wx.lib.agw.cubecolourdialog import CubeColourDialog
from wx.lib.masked.numctrl import NumCtrl

from constants import File, F_MIN, F_MAX, Cal, SAMPLE_RATE, BANDWIDTH, WINFUNC, \
    TUNER
from devices import DeviceRTL
from file import open_plot
from misc import close_modeless, format_time, ValidatorCoord, get_colours, \
    nearest, load_bitmap, get_version_timestamp
from rtltcp import RtlTcp
from windows import PanelGraphCompare, PanelColourBar, CellRenderer


class DialogCompare(wx.Dialog):
    def __init__(self, parent, dirname, filename):

        self.dirname = dirname
        self.filename = filename

        wx.Dialog.__init__(self, parent=parent, title="Compare plots",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)

        self.graph = PanelGraphCompare(self)

        self.buttonPlot1 = wx.Button(self, wx.ID_ANY, 'Load plot #1')
        self.buttonPlot2 = wx.Button(self, wx.ID_ANY, 'Load plot #2')
        self.Bind(wx.EVT_BUTTON, self.__on_load_plot, self.buttonPlot1)
        self.Bind(wx.EVT_BUTTON, self.__on_load_plot, self.buttonPlot2)
        self.textPlot1 = wx.StaticText(self, label="<None>")
        self.textPlot2 = wx.StaticText(self, label="<None>")

        buttonClose = wx.Button(self, wx.ID_CLOSE, 'Close')
        self.Bind(wx.EVT_BUTTON, self.__on_close, buttonClose)

        grid = wx.GridBagSizer(5, 5)
        grid.AddGrowableCol(2, 0)
        grid.Add(self.buttonPlot1, pos=(0, 0), flag=wx.ALIGN_CENTRE)
        grid.Add(self.textPlot1, pos=(0, 1), span=(1, 2))
        grid.Add(self.buttonPlot2, pos=(1, 0), flag=wx.ALIGN_CENTRE)
        grid.Add(self.textPlot2, pos=(1, 1), span=(1, 2))
        grid.Add(buttonClose, pos=(2, 3), flag=wx.ALIGN_RIGHT)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.graph, 1, wx.EXPAND)
        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, border=5)
        self.SetSizerAndFit(sizer)

        close_modeless()

    def __on_load_plot(self, event):
        dlg = wx.FileDialog(self, "Open a scan", self.dirname, self.filename,
                            File.RFS, wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.dirname = dlg.GetDirectory()
            self.filename = dlg.GetFilename()
            _scanInfo, spectrum = open_plot(self.dirname,
                                            self.filename)
            if event.EventObject == self.buttonPlot1:
                self.textPlot1.SetLabel(self.filename)
                self.graph.set_spectrum1(spectrum)
            else:
                self.textPlot2.SetLabel(self.filename)
                self.graph.set_spectrum2(spectrum)

        dlg.Destroy()

    def __on_close(self, _event):
        close_modeless()
        self.EndModal(wx.ID_CLOSE)


class DialogAutoCal(wx.Dialog):
    def __init__(self, parent, freq, callbackCal):
        self.callback = callbackCal
        self.cal = 0

        wx.Dialog.__init__(self, parent=parent, title="Auto Calibration",
                           style=wx.CAPTION)
        self.Bind(wx.EVT_CLOSE, self.__on_close)

        title = wx.StaticText(self, label="Calibrate to a known stable signal")
        font = title.GetFont()
        font.SetPointSize(font.GetPointSize() + 2)
        title.SetFont(font)
        text = wx.StaticText(self, label="Frequency (MHz)")
        self.textFreq = masked.NumCtrl(self, value=freq, fractionWidth=3,
                                        min=F_MIN, max=F_MAX)

        self.buttonCal = wx.Button(self, label="Calibrate")
        if len(parent.devicesRtl) == 0:
            self.buttonCal.Disable()
        self.buttonCal.Bind(wx.EVT_BUTTON, self.__on_cal)
        self.textResult = wx.StaticText(self)

        self.buttonOk = wx.Button(self, wx.ID_OK, 'OK')
        self.buttonOk.Disable()
        self.buttonCancel = wx.Button(self, wx.ID_CANCEL, 'Cancel')

        self.buttonOk.Bind(wx.EVT_BUTTON, self.__on_close)
        self.buttonCancel.Bind(wx.EVT_BUTTON, self.__on_close)

        buttons = wx.StdDialogButtonSizer()
        buttons.AddButton(self.buttonOk)
        buttons.AddButton(self.buttonCancel)
        buttons.Realize()

        sizer = wx.GridBagSizer(10, 10)
        sizer.Add(title, pos=(0, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTRE | wx.ALL, border=10)
        sizer.Add(text, pos=(1, 0), flag=wx.ALL | wx.EXPAND, border=10)
        sizer.Add(self.textFreq, pos=(1, 1), flag=wx.ALL | wx.EXPAND,
                  border=5)
        sizer.Add(self.buttonCal, pos=(2, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTRE | wx.ALL | wx.EXPAND, border=10)
        sizer.Add(self.textResult, pos=(3, 0), span=(1, 2),
                  flag=wx.ALL | wx.EXPAND, border=10)
        sizer.Add(buttons, pos=(4, 0), span=(1, 2),
                  flag=wx.ALL | wx.EXPAND, border=10)

        self.SetSizerAndFit(sizer)

    def __on_cal(self, _event):
        self.buttonCal.Disable()
        self.buttonOk.Disable()
        self.buttonCancel.Disable()
        self.textFreq.Disable()
        self.textResult.SetLabel("Calibrating...")
        self.callback(Cal.START)

    def __on_close(self, event):
        status = [Cal.CANCEL, Cal.OK][event.GetId() == wx.ID_OK]
        self.callback(status)
        self.EndModal(event.GetId())
        return

    def __enable_controls(self):
        self.buttonCal.Enable(True)
        self.buttonOk.Enable(True)
        self.buttonCancel.Enable(True)
        self.textFreq.Enable()

    def set_cal(self, cal):
        self.cal = cal
        self.__enable_controls()
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
        self.Bind(wx.EVT_BUTTON, self.__on_refresh, refresh)

        textOffset = wx.StaticText(self, label="Offset (kHz)")
        self.spinOffset = wx.SpinCtrl(self)
        self.spinOffset.SetRange(0, ((SAMPLE_RATE / 2) - BANDWIDTH) / 1e3)
        self.spinOffset.SetValue(offset)
        self.Bind(wx.EVT_SPINCTRL, self.__on_spin, self.spinOffset)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

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
                  flag=wx.ALIGN_CENTRE | wx.ALL, border=5)
        gridSizer.Add(textHelp, pos=(1, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTRE | wx.ALL, border=5)
        gridSizer.Add(boxSizer1, pos=(2, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTRE | wx.ALL, border=5)
        gridSizer.Add(refresh, pos=(3, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTRE | wx.ALL, border=5)
        gridSizer.Add(boxSizer2, pos=(4, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTRE | wx.ALL, border=5)
        gridSizer.Add(sizerButtons, pos=(5, 1), span=(1, 1),
                  flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(gridSizer)
        self.__draw_limits()

        self.__setup_plot()

    def __setup_plot(self):
        self.axes.clear()
        self.band1 = None
        self.band2 = None
        self.axes.set_xlabel("Frequency (MHz)")
        self.axes.set_ylabel('Level ($\mathsf{dB/\sqrt{Hz}}$)')
        self.axes.set_yscale('log')
        self.axes.set_xlim(-1, 1)
        self.axes.set_ylim(auto=True)
        self.axes.grid(True)
        self.__draw_limits()

    def __plot(self, capture):
        self.__setup_plot()
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

    def __on_ok(self, _event):
        self.EndModal(wx.ID_OK)

    def __on_refresh(self, _event):

        dlg = wx.BusyInfo('Please wait...')

        try:
            if self.device.isDevice:
                sdr = rtlsdr.RtlSdr(self.device.indexRtl)
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

        self.__plot(capture)

        dlg.Destroy()

    def __on_spin(self, _event):
        self.offset = self.spinOffset.GetValue() * 1e3
        self.__draw_limits()

    def __draw_limits(self):
        limit1 = self.offset
        limit2 = limit1 + BANDWIDTH / 2
        limit1 /= 1e6
        limit2 /= 1e6
        if self.band1 is not None:
            self.band1.remove()
        if self.band2 is not None:
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

        textRbw = wx.StaticText(self, label="RBW")
        gridScan.Add(textRbw, (6, 0), (1, 1), wx.ALL, 5)
        rbw = ((SAMPLE_RATE / scanInfo.nfft) / 1000.0) * 2.0
        textCtrlStop = wx.TextCtrl(self, value="{0:.3f}".format(rbw),
                                   style=wx.TE_READONLY)
        gridScan.Add(textCtrlStop, (6, 1), (1, 1), wx.ALL, 5)
        textKHz = wx.StaticText(self, label="kHz")
        gridScan.Add(textKHz, (6, 2), (1, 1), wx.ALL, 5)

        textTime = wx.StaticText(self, label="First scan")
        gridScan.Add(textTime, (7, 0), (1, 1), wx.ALL, 5)
        textCtrlTime = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.timeFirst is not None:
            textCtrlTime.SetValue(format_time(scanInfo.timeFirst, True))
        gridScan.Add(textCtrlTime, (7, 1), (1, 1), wx.ALL, 5)

        textTime = wx.StaticText(self, label="Last scan")
        gridScan.Add(textTime, (8, 0), (1, 1), wx.ALL, 5)
        textCtrlTime = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.timeLast is not None:
            textCtrlTime.SetValue(format_time(scanInfo.timeLast, True))
        gridScan.Add(textCtrlTime, (8, 1), (1, 1), wx.ALL, 5)

        textLat = wx.StaticText(self, label="Latitude")
        gridScan.Add(textLat, (9, 0), (1, 1), wx.ALL, 5)
        self.textCtrlLat = wx.TextCtrl(self, value="Unknown")
        self.textCtrlLat.SetValidator(ValidatorCoord(True))
        if scanInfo.lat is not None:
            self.textCtrlLat.SetValue(str(scanInfo.lat))
        gridScan.Add(self.textCtrlLat, (9, 1), (1, 1), wx.ALL, 5)

        textLon = wx.StaticText(self, label="Longitude")
        gridScan.Add(textLon, (10, 0), (1, 1), wx.ALL, 5)
        self.textCtrlLon = wx.TextCtrl(self, value="Unknown")
        self.textCtrlLon.SetValidator(ValidatorCoord(False))
        if scanInfo.lon is not None:
            self.textCtrlLon.SetValue(str(scanInfo.lon))
        gridScan.Add(self.textCtrlLon, (10, 1), (1, 1), wx.ALL, 5)

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
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)
        box.Add(sizerButtons, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.SetSizerAndFit(box)

    def __on_ok(self, _event):
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

    def __init__(self, parent, settings):
        self.settings = settings
        self.index = 0

        wx.Dialog.__init__(self, parent=parent, title="Preferences")

        self.colours = get_colours()
        self.winFunc = settings.winFunc
        self.background = settings.background

        self.checkSaved = wx.CheckBox(self, wx.ID_ANY,
                                      "Save warning")
        self.checkSaved.SetValue(settings.saveWarn)
        self.checkSaved.SetToolTip(wx.ToolTip('Prompt to save scan on exit'))
        self.checkAlert = wx.CheckBox(self, wx.ID_ANY,
                                      "Level alert (dB)")
        self.checkAlert.SetValue(settings.alert)
        self.checkAlert.SetToolTip(wx.ToolTip('Play alert when level exceeded'))
        self.Bind(wx.EVT_CHECKBOX, self.__on_alert, self.checkAlert)
        self.spinLevel = wx.SpinCtrl(self, wx.ID_ANY, min=-100, max=20)
        self.spinLevel.SetValue(settings.alertLevel)
        self.spinLevel.Enable(settings.alert)
        self.spinLevel.SetToolTip(wx.ToolTip('Alert threshold'))
        textBackground = wx.StaticText(self, label='Background colour')
        self.buttonBackground = wx.Button(self, wx.ID_ANY)
        self.buttonBackground.SetBackgroundColour(self.background)
        self.Bind(wx.EVT_BUTTON, self.__on_background, self.buttonBackground)
        textColour = wx.StaticText(self, label="Colour map")
        self.choiceColour = wx.Choice(self, choices=self.colours)
        self.choiceColour.SetSelection(self.colours.index(settings.colourMap))
        self.Bind(wx.EVT_CHOICE, self.__on_choice, self.choiceColour)
        self.colourBar = PanelColourBar(self, settings.colourMap)
        self.checkPoints = wx.CheckBox(self, wx.ID_ANY,
                                      "Limit points")
        self.checkPoints.SetValue(settings.pointsLimit)
        self.checkPoints.SetToolTip(wx.ToolTip('Limit the resolution of plots'))
        self.Bind(wx.EVT_CHECKBOX, self.__on_points, self.checkPoints)
        self.spinPoints = wx.SpinCtrl(self, wx.ID_ANY, min=1000, max=100000)
        self.spinPoints.Enable(settings.pointsLimit)
        self.spinPoints.SetValue(settings.pointsMax)
        self.spinPoints.SetToolTip(wx.ToolTip('Maximum number of points to plot'))
        textDpi = wx.StaticText(self, label='Export DPI')
        self.spinDpi = wx.SpinCtrl(self, wx.ID_ANY, min=72, max=6000)
        self.spinDpi.SetValue(settings.exportDpi)
        self.spinDpi.SetToolTip(wx.ToolTip('DPI of exported images'))

        self.radioAvg = wx.RadioButton(self, wx.ID_ANY, 'Average Scans',
                                       style=wx.RB_GROUP)
        self.radioAvg.SetToolTip(wx.ToolTip('Average level with each scan'))
        self.Bind(wx.EVT_RADIOBUTTON, self.__on_radio, self.radioAvg)
        self.radioRetain = wx.RadioButton(self, wx.ID_ANY,
                                          'Retain previous scans')
        self.radioRetain.SetToolTip(wx.ToolTip('Can be slow'))
        self.Bind(wx.EVT_RADIOBUTTON, self.__on_radio, self.radioRetain)
        self.radioRetain.SetValue(settings.retainScans)

        textMaxScans = wx.StaticText(self, label="Max scans")
        self.spinCtrlMaxScans = wx.SpinCtrl(self)
        self.spinCtrlMaxScans.SetRange(1, 500)
        self.spinCtrlMaxScans.SetValue(settings.retainMax)
        self.spinCtrlMaxScans.SetToolTip(wx.ToolTip('Maximum previous scans'
                                                    ' to display'))

        self.checkFade = wx.CheckBox(self, wx.ID_ANY,
                                      "Fade previous scans")
        self.checkFade.SetValue(settings.fadeScans)
        textWidth = wx.StaticText(self, label="Line width")
        self.ctrlWidth = NumCtrl(self, integerWidth=2, fractionWidth=1)
        self.ctrlWidth.SetValue(settings.lineWidth)

        self.__on_radio(None)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

        gengrid = wx.GridBagSizer(10, 10)
        gengrid.Add(self.checkSaved, pos=(0, 0))
        gengrid.Add(self.checkAlert, pos=(1, 0), flag=wx.ALIGN_CENTRE)
        gengrid.Add(self.spinLevel, pos=(1, 1))
        gengrid.Add(textBackground, pos=(2, 0), flag=wx.ALIGN_CENTRE)
        gengrid.Add(self.buttonBackground, pos=(2, 1))
        gengrid.Add(textColour, pos=(3, 0))
        gengrid.Add(self.choiceColour, pos=(3, 1))
        gengrid.Add(self.colourBar, pos=(3, 2))
        gengrid.Add(self.checkPoints, pos=(4, 0))
        gengrid.Add(self.spinPoints, pos=(4, 1))
        gengrid.Add(textDpi, pos=(5, 0))
        gengrid.Add(self.spinDpi, pos=(5, 1))
        genbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "General"))
        genbox.Add(gengrid, 0, wx.ALL | wx.ALIGN_CENTRE_VERTICAL, 10)

        congrid = wx.GridBagSizer(10, 10)
        congrid.Add(self.radioAvg, pos=(0, 0))
        congrid.Add(self.radioRetain, pos=(1, 0))
        congrid.Add(textMaxScans, pos=(2, 0),
                    flag=wx.ALIGN_CENTRE_VERTICAL)
        congrid.Add(self.spinCtrlMaxScans, pos=(2, 1))
        conbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY,
                                                "Continuous Scans"),
                                   wx.VERTICAL)
        conbox.Add(congrid, 0, wx.ALL | wx.EXPAND, 10)

        plotgrid = wx.GridBagSizer(10, 10)
        plotgrid.Add(self.checkFade, pos=(0, 0))
        plotgrid.Add(textWidth, pos=(1, 0))
        plotgrid.Add(self.ctrlWidth, pos=(1, 1))
        plotbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "Plot View"),
                                     wx.HORIZONTAL)
        plotbox.Add(plotgrid, 0, wx.ALL | wx.EXPAND, 10)

        grid = wx.GridBagSizer(10, 10)
        grid.AddGrowableCol(0, 1)
        grid.AddGrowableCol(1, 0)
        grid.Add(genbox, pos=(0, 0), span=(1, 2), flag=wx.EXPAND)
        grid.Add(conbox, pos=(1, 0), span=(1, 2), flag=wx.EXPAND)
        grid.Add(plotbox, pos=(2, 0), span=(1, 2), flag=wx.EXPAND)
        grid.Add(sizerButtons, pos=(3, 1), flag=wx.EXPAND)

        box = wx.BoxSizer()
        box.Add(grid, flag=wx.ALL | wx.ALIGN_CENTRE, border=10)

        self.SetSizerAndFit(box)

    def __on_alert(self, _event):
        enabled = self.checkAlert.GetValue()
        self.spinLevel.Enable(enabled)

    def __on_points(self, _event):
        enabled = self.checkPoints.GetValue()
        self.spinPoints.Enable(enabled)

    def __on_background(self, _event):
        colour = wx.ColourData()
        colour.SetColour(self.background)

        dlg = CubeColourDialog(self, colour, 0)
        if dlg.ShowModal() == wx.ID_OK:
            newColour = dlg.GetColourData().GetColour()
            self.background = newColour.GetAsString(wx.C2S_HTML_SYNTAX)
            self.buttonBackground.SetBackgroundColour(self.background)
        dlg.Destroy()

    def __on_radio(self, _event):
        enabled = self.radioRetain.GetValue()
        self.checkFade.Enable(enabled)
        self.spinCtrlMaxScans.Enable(enabled)

    def __on_choice(self, _event):
        self.colourBar.set_map(self.choiceColour.GetStringSelection())
        self.choiceColour.SetFocus()

    def __on_ok(self, _event):
        self.settings.saveWarn = self.checkSaved.GetValue()
        self.settings.alert = self.checkAlert.GetValue()
        self.settings.alertLevel = self.spinLevel.GetValue()
        self.settings.pointsLimit = self.checkPoints.GetValue()
        self.settings.pointsMax = self.spinPoints.GetValue()
        self.settings.exportDpi = self.spinDpi.GetValue()
        self.settings.retainScans = self.radioRetain.GetValue()
        self.settings.fadeScans = self.checkFade.GetValue()
        self.settings.lineWidth = self.ctrlWidth.GetValue()
        self.settings.retainMax = self.spinCtrlMaxScans.GetValue()
        self.settings.colourMap = self.choiceColour.GetStringSelection()
        self.settings.background = self.background

        self.EndModal(wx.ID_OK)


class DialogAdvPrefs(wx.Dialog):
    def __init__(self, parent, settings):
        self.settings = settings

        wx.Dialog.__init__(self, parent=parent, title="Advanced Preferences")

        self.winFunc = settings.winFunc

        textOverlap = wx.StaticText(self, label='PSD Overlap (%)')
        self.slideOverlap = wx.Slider(self, wx.ID_ANY,
                                      settings.overlap * 100,
                                      0, 75,
                                      style=wx.SL_LABELS)
        self.slideOverlap.SetToolTip(wx.ToolTip('Power spectral density'
                                                    ' overlap'))
        textWindow = wx.StaticText(self, label='Window')
        self.buttonWindow = wx.Button(self, wx.ID_ANY, self.winFunc)
        self.Bind(wx.EVT_BUTTON, self.__on_window, self.buttonWindow)

        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons = wx.StdDialogButtonSizer()
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

        advgrid = wx.GridBagSizer(10, 10)
        advgrid.Add(textOverlap, pos=(0, 0),
                    flag=wx.ALL | wx.ALIGN_CENTRE)
        advgrid.Add(self.slideOverlap, pos=(0, 1), flag=wx.EXPAND)
        advgrid.Add(textWindow, pos=(1, 0), flag=wx.EXPAND)
        advgrid.Add(self.buttonWindow, pos=(1, 1))
        advgrid.Add(sizerButtons, pos=(2, 1), flag=wx.EXPAND)

        advBox = wx.BoxSizer()
        advBox.Add(advgrid, flag=wx.ALL | wx.ALIGN_CENTRE, border=10)

        self.SetSizerAndFit(advBox)

    def __on_window(self, _event):
        dlg = DialogWinFunc(self, self.winFunc)
        if dlg.ShowModal() == wx.ID_OK:
            self.winFunc = dlg.get_win_func()
            self.buttonWindow.SetLabel(self.winFunc)
        dlg.Destroy()

    def __on_ok(self, _event):
        self.settings.overlap = self.slideOverlap.GetValue() / 100.0
        self.settings.winFunc = self.winFunc

        self.EndModal(wx.ID_OK)


class DialogDevicesRTL(wx.Dialog):
    COL_SEL, COL_DEV, COL_TUN, COL_SER, COL_IND, \
    COL_GAIN, COL_CAL, COL_LO, COL_OFF = range(9)

    def __init__(self, parent, devices, settings):
        self.devices = copy.copy(devices)
        self.settings = settings
        self.index = None

        wx.Dialog.__init__(self, parent=parent, title="Devices")

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

        self.__set_dev_grid()
        self.Bind(grid.EVT_GRID_CELL_LEFT_CLICK, self.__on_click)

        serverSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonAdd = wx.Button(self, wx.ID_ADD)
        self.buttonDel = wx.Button(self, wx.ID_DELETE)
        self.Bind(wx.EVT_BUTTON, self.__on_add, buttonAdd)
        self.Bind(wx.EVT_BUTTON, self.__on_del, self.buttonDel)
        serverSizer.Add(buttonAdd, 0, wx.ALL)
        serverSizer.Add(self.buttonDel, 0, wx.ALL)
        self.__button_state()

        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons = wx.StdDialogButtonSizer()
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

        self.devbox = wx.BoxSizer(wx.VERTICAL)
        self.devbox.Add(self.gridDev, 1, wx.ALL | wx.EXPAND, 10)
        self.devbox.Add(serverSizer, 0, wx.ALL | wx.EXPAND, 10)
        self.devbox.Add(sizerButtons, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizerAndFit(self.devbox)

    def __set_dev_grid(self):
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
                cell = grid.GridCellChoiceEditor(map(str, device.gains),
                                                 allowOthers=False)
                self.gridDev.SetCellEditor(i, self.COL_GAIN, cell)
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

        if self.settings.indexRtl >= len(self.devices):
            self.settings.indexRtl = len(self.devices) - 1
        self.__select_row(self.settings.indexRtl)
        self.index = self.settings.indexRtl

        self.gridDev.AutoSize()

    def __get_dev_grid(self):
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

    def __button_state(self):
        if len(self.devices) > 0:
            if self.devices[self.index].isDevice:
                self.buttonDel.Disable()
            else:
                self.buttonDel.Enable()

    def __warn_duplicates(self):
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

    def __on_click(self, event):
        col = event.GetCol()
        index = event.GetRow()
        if col == self.COL_SEL:
            self.index = event.GetRow()
            self.__select_row(index)
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

        self.__button_state()

    def __on_ok(self, _event):
        self.__get_dev_grid()
        if self.__warn_duplicates():
            return

        self.EndModal(wx.ID_OK)

    def __on_add(self, _event):
        device = DeviceRTL()
        device.isDevice = False
        self.devices.append(device)
        self.gridDev.AppendRows(1)
        self.__set_dev_grid()
        self.SetSizerAndFit(self.devbox)

    def __on_del(self, _event):
        del self.devices[self.index]
        self.gridDev.DeleteRows(self.index)
        self.__set_dev_grid()
        self.SetSizerAndFit(self.devbox)
        self.__button_state()

    def __select_row(self, index):
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

        self.figure = matplotlib.figure.Figure(facecolor='white',
                                               figsize=(5, 4))
        self.figure.suptitle('Window Function')
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.axesWin = self.figure.add_subplot(211)
        self.axesFft = self.figure.add_subplot(212)

        text = wx.StaticText(self, label='Function')

        self.choice = wx.Choice(self, choices=WINFUNC[::2])
        self.choice.SetSelection(WINFUNC[::2].index(winFunc))

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

        sizerFunction = wx.BoxSizer(wx.HORIZONTAL)
        sizerFunction.Add(text, flag=wx.ALL, border=5)
        sizerFunction.Add(self.choice, flag=wx.ALL, border=5)

        sizerGrid = wx.GridBagSizer(5, 5)
        sizerGrid.Add(self.canvas, pos=(0, 0), span=(1, 2), border=5)
        sizerGrid.Add(sizerFunction, pos=(1, 0), span=(1, 2),
                      flag=wx.ALIGN_CENTRE | wx.ALL, border=5)
        sizerGrid.Add(sizerButtons, pos=(2, 1),
                  flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.Bind(wx.EVT_CHOICE, self.__on_choice, self.choice)
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

        self.__plot()

        self.SetSizerAndFit(sizerGrid)

    def __plot(self):
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
        self.axesFft.set_ylabel('$\mathsf{dB/\sqrt{Hz}}$')
        self.axesFft.set_xlim(-256, 256)
        self.axesFft.set_xticklabels([])
        self.figure.tight_layout()

        self.canvas.draw()

    def __on_choice(self, _event):
        self.winFunc = WINFUNC[::2][self.choice.GetSelection()]
        self.plot()

    def __on_ok(self, _event):
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

        buttonYes.Bind(wx.EVT_BUTTON, self.__on_close)
        buttonNo.Bind(wx.EVT_BUTTON, self.__on_close)

        buttons = wx.StdDialogButtonSizer()
        buttons.AddButton(buttonYes)
        buttons.AddButton(buttonNo)
        buttons.AddButton(buttonCancel)
        buttons.Realize()

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(hbox, 1, wx.ALL | wx.EXPAND, 10)
        vbox.Add(buttons, 1, wx.ALL | wx.EXPAND, 10)

        self.SetSizerAndFit(vbox)

    def __on_close(self, event):
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
        box.Add(icon, flag=wx.ALIGN_CENTRE | wx.ALL, border=10)
        box.Add(text, flag=wx.ALIGN_CENTRE | wx.ALL, border=10)

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
                 flag=wx.ALIGN_CENTRE | wx.ALL, border=10)
        grid.Add(textLink, pos=(1, 1), span=(1, 2),
                 flag=wx.ALIGN_CENTRE | wx.ALL, border=10)
        grid.Add(textTimestamp, pos=(2, 1), span=(1, 2),
                 flag=wx.ALIGN_CENTRE | wx.ALL, border=10)
        grid.Add(buttonOk, pos=(3, 2), span=(1, 1),
                 flag=wx.ALIGN_RIGHT | wx.ALL, border=10)

        self.SetSizerAndFit(grid)
        self.Centre()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
