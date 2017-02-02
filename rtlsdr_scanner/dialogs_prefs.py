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

import itertools

import matplotlib
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
import numpy
import rtlsdr
import wx
from wx.lib.agw.cubecolourdialog import CubeColourDialog
from wx.lib.masked.numctrl import NumCtrl

from rtlsdr_scanner.constants import F_MIN, F_MAX, SAMPLE_RATE, BANDWIDTH, WINFUNC
from rtlsdr_scanner.panels import PanelColourBar
from rtlsdr_scanner.rtltcp import RtlTcp
from rtlsdr_scanner.utils_mpl import get_colours


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
                                 "of the plot_line.")

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
        gridSizer.Add(sizerButtons, pos=(5, 1),
                      flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(gridSizer)
        self.__draw_limits()

        self.__setup_plot()

    def __setup_plot(self):
        self.axes.clear()
        self.band1 = None
        self.band2 = None
        self.axes.set_xlabel("Frequency (MHz)")
        self.axes.set_ylabel('Level (dB/Hz)')
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
                sdr = RtlTcp(self.device.server, self.device.port, None)
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
                                   'Capture failed:\n{}'.format(message),
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
        self.checkBackup = wx.CheckBox(self, wx.ID_ANY,
                                       "Backup")
        self.checkBackup.SetValue(settings.backup)
        self.checkBackup.SetToolTipString('Backup data after crash')
        self.checkAlert = wx.CheckBox(self, wx.ID_ANY,
                                      "Level alert (dB)")
        self.checkAlert.SetValue(settings.alert)
        self.checkAlert.SetToolTipString('Play alert when level exceeded')
        self.Bind(wx.EVT_CHECKBOX, self.__on_alert, self.checkAlert)
        self.spinLevel = wx.SpinCtrl(self, wx.ID_ANY, min=-100, max=20)
        self.spinLevel.SetValue(settings.alertLevel)
        self.spinLevel.Enable(settings.alert)
        self.spinLevel.SetToolTipString('Alert threshold')
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
        self.checkPoints.SetToolTipString('Limit the resolution of plots')
        self.Bind(wx.EVT_CHECKBOX, self.__on_points, self.checkPoints)
        self.spinPoints = wx.SpinCtrl(self, wx.ID_ANY, min=1000, max=100000)
        self.spinPoints.Enable(settings.pointsLimit)
        self.spinPoints.SetValue(settings.pointsMax)
        self.spinPoints.SetToolTipString('Maximum number of points to plot_line')
        textDpi = wx.StaticText(self, label='Export DPI')
        self.spinDpi = wx.SpinCtrl(self, wx.ID_ANY, min=72, max=6000)
        self.spinDpi.SetValue(settings.exportDpi)
        self.spinDpi.SetToolTipString('DPI of exported images')
        self.checkTune = wx.CheckBox(self, wx.ID_ANY,
                                     "Tune SDR#")
        self.checkTune.SetValue(settings.clickTune)
        self.checkTune.SetToolTipString('Double click plot_line to tune SDR#')
        textPlugin = wx.HyperlinkCtrl(self, wx.ID_ANY,
                                      label="(Requires plugin)",
                                      url="http://eartoearoak.com/software/sdrsharp-net-remote")

        self.radioAvg = wx.RadioButton(self, wx.ID_ANY, 'Average Scans',
                                       style=wx.RB_GROUP)
        self.radioAvg.SetToolTipString('Average level with each scan')
        self.Bind(wx.EVT_RADIOBUTTON, self.__on_radio, self.radioAvg)
        self.radioRetain = wx.RadioButton(self, wx.ID_ANY,
                                          'Retain previous scans')
        self.radioRetain.SetToolTipString('Can be slow')
        self.Bind(wx.EVT_RADIOBUTTON, self.__on_radio, self.radioRetain)
        self.radioRetain.SetValue(settings.retainScans)

        textMaxScans = wx.StaticText(self, label="Max scans")
        self.spinCtrlMaxScans = wx.SpinCtrl(self)
        self.spinCtrlMaxScans.SetRange(1, 5000)
        self.spinCtrlMaxScans.SetValue(settings.retainMax)
        self.spinCtrlMaxScans.SetToolTipString('Maximum previous scans'
                                               ' to display')

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
        gengrid.Add(self.checkBackup, pos=(1, 0))
        gengrid.Add(self.checkAlert, pos=(2, 0), flag=wx.ALIGN_CENTRE)
        gengrid.Add(self.spinLevel, pos=(2, 1))
        gengrid.Add(textBackground, pos=(3, 0), flag=wx.ALIGN_CENTRE)
        gengrid.Add(self.buttonBackground, pos=(3, 1))
        gengrid.Add(textColour, pos=(4, 0))
        gengrid.Add(self.choiceColour, pos=(4, 1))
        gengrid.Add(self.colourBar, pos=(4, 2))
        gengrid.Add(self.checkPoints, pos=(5, 0))
        gengrid.Add(self.spinPoints, pos=(5, 1))
        gengrid.Add(textDpi, pos=(6, 0))
        gengrid.Add(self.spinDpi, pos=(6, 1))
        gengrid.Add(self.checkTune, pos=(7, 0))
        gengrid.Add(textPlugin, pos=(7, 1))
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
        plotgrid.Add(textWidth, pos=(0, 0))
        plotgrid.Add(self.ctrlWidth, pos=(0, 1))
        plotbox = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "Plot View"),
                                    wx.HORIZONTAL)
        plotbox.Add(plotgrid, 0, wx.ALL | wx.EXPAND, 10)

        grid = wx.GridBagSizer(10, 10)
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
        self.spinCtrlMaxScans.Enable(enabled)

    def __on_choice(self, _event):
        self.colourBar.set_map(self.choiceColour.GetStringSelection())
        self.choiceColour.SetFocus()

    def __on_ok(self, _event):
        self.settings.saveWarn = self.checkSaved.GetValue()
        self.settings.backup = self.checkBackup.GetValue()
        self.settings.alert = self.checkAlert.GetValue()
        self.settings.alertLevel = self.spinLevel.GetValue()
        self.settings.clickTune = self.checkTune.GetValue()
        self.settings.pointsLimit = self.checkPoints.GetValue()
        self.settings.pointsMax = self.spinPoints.GetValue()
        self.settings.exportDpi = self.spinDpi.GetValue()
        self.settings.retainScans = self.radioRetain.GetValue()
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
        self.slideOverlap.SetToolTipString('Power spectral density'
                                           ' overlap')
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


class DialogFormatting(wx.Dialog):
    def __init__(self, parent, settings):
        self.settings = settings

        wx.Dialog.__init__(self, parent=parent, title="Number formatting")

        textFreq = wx.StaticText(self, label='Frequency precision')
        self.spinFreq = wx.SpinCtrl(self, wx.ID_ANY, min=0, max=6)
        self.spinFreq.SetValue(settings.precisionFreq)
        self.spinFreq.SetToolTipString('Displayed frequency decimal precision')

        textLevel = wx.StaticText(self, label='Level precision')
        self.spinLevel = wx.SpinCtrl(self, wx.ID_ANY, min=0, max=2)
        self.spinLevel.SetValue(settings.precisionLevel)
        self.spinLevel.SetToolTipString('Displayed level decimal precision')

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

        sizer = wx.GridBagSizer(5, 5)
        sizer.Add(textFreq, pos=(0, 0),
                  flag=wx.ALL, border=5)
        sizer.Add(self.spinFreq, pos=(0, 1),
                  flag=wx.ALL, border=5)
        sizer.Add(textLevel, pos=(1, 0),
                  flag=wx.ALL, border=5)
        sizer.Add(self.spinLevel, pos=(1, 1),
                  flag=wx.ALL, border=5)
        sizer.Add(sizerButtons, pos=(2, 0), span=(1, 2),
                  flag=wx.ALL | wx.ALIGN_RIGHT, border=5)

        self.SetSizerAndFit(sizer)

    def __on_ok(self, _event):
        self.settings.precisionFreq = self.spinFreq.GetValue()
        self.settings.precisionLevel = self.spinLevel.GetValue()

        self.EndModal(wx.ID_OK)


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
        self.axesFft.set_ylabel('dB/Hz')
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


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
