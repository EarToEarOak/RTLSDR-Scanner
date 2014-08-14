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

import wx
from wx.lib import masked

from constants import F_MIN, F_MAX, Cal
from file import File, open_plot
from misc import format_precision
from panels import PanelGraphCompare, PanelLine
from utils_wx import close_modeless
from widgets import SatLevel


class DialogCompare(wx.Dialog):
    def __init__(self, parent, settings, filename):

        self.settings = settings
        self.dirname = settings.dirScans
        self.filename = filename

        wx.Dialog.__init__(self, parent=parent, title="Compare plots",
                           style=wx.DEFAULT_DIALOG_STYLE |
                           wx.RESIZE_BORDER |
                           wx.MAXIMIZE_BOX)

        self.graph = PanelGraphCompare(self, self.__on_cursor)
        self.graph.show_plot1(settings.compareOne)
        self.graph.show_plot2(settings.compareTwo)
        self.graph.show_plotdiff(settings.compareDiff)

        textPlot1 = wx.StaticText(self, label='Plot 1')
        linePlot1 = PanelLine(self, wx.BLUE)
        self.checkOne = wx.CheckBox(self, wx.ID_ANY)
        self.checkOne.SetValue(settings.compareOne)
        self.buttonPlot1 = wx.Button(self, wx.ID_ANY, 'Load...')
        self.textPlot1 = wx.StaticText(self, label="<None>")
        self.textLoc1 = wx.StaticText(self, label='\n')
        self.Bind(wx.EVT_BUTTON, self.__on_load_plot, self.buttonPlot1)

        textPlot2 = wx.StaticText(self, label='Plot 2')
        linePlot2 = PanelLine(self, wx.GREEN)
        self.checkTwo = wx.CheckBox(self, wx.ID_ANY)
        self.checkTwo.SetValue(settings.compareTwo)
        self.buttonPlot2 = wx.Button(self, wx.ID_ANY, 'Load...')
        self.textPlot2 = wx.StaticText(self, label="<None>")
        self.textLoc2 = wx.StaticText(self, label='\n')
        self.Bind(wx.EVT_BUTTON, self.__on_load_plot, self.buttonPlot2)

        textPlotDiff = wx.StaticText(self, label='Difference')
        linePlotDiff = PanelLine(self, wx.RED)
        self.checkDiff = wx.CheckBox(self, wx.ID_ANY)
        self.checkDiff.SetValue(settings.compareDiff)
        self.textLocDiff = wx.StaticText(self, label='\n')

        font = textPlot1.GetFont()
        fontSize = font.GetPointSize()
        font.SetPointSize(fontSize + 4)
        textPlot1.SetFont(font)
        textPlot2.SetFont(font)
        textPlotDiff.SetFont(font)

        fontStyle = font.GetStyle()
        fontWeight = font.GetWeight()
        font = wx.Font(fontSize, wx.FONTFAMILY_MODERN, fontStyle,
                       fontWeight)
        self.textLoc1.SetFont(font)
        self.textLoc2.SetFont(font)
        self.textLocDiff.SetFont(font)

        buttonClose = wx.Button(self, wx.ID_CLOSE, 'Close')

        self.Bind(wx.EVT_CHECKBOX, self.__on_check1, self.checkOne)
        self.Bind(wx.EVT_CHECKBOX, self.__on_check2, self.checkTwo)
        self.Bind(wx.EVT_CHECKBOX, self.__on_check_diff, self.checkDiff)
        self.Bind(wx.EVT_BUTTON, self.__on_close, buttonClose)

        grid = wx.GridBagSizer(5, 5)

        grid.Add(textPlot1, pos=(0, 0))
        grid.Add(linePlot1, pos=(0, 1), flag=wx.EXPAND)
        grid.Add(self.checkOne, pos=(0, 2), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.buttonPlot1, pos=(1, 0))
        grid.Add(self.textPlot1, pos=(2, 0))
        grid.Add(self.textLoc1, pos=(3, 0))

        grid.Add(wx.StaticLine(self), pos=(5, 0), span=(1, 3), flag=wx.EXPAND)
        grid.Add(textPlot2, pos=(6, 0))
        grid.Add(linePlot2, pos=(6, 1), flag=wx.EXPAND)
        grid.Add(self.checkTwo, pos=(6, 2), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.buttonPlot2, pos=(7, 0))
        grid.Add(self.textPlot2, pos=(8, 0))
        grid.Add(self.textLoc2, pos=(9, 0))

        grid.Add(wx.StaticLine(self), pos=(11, 0), span=(1, 3), flag=wx.EXPAND)
        grid.Add(textPlotDiff, pos=(12, 0))
        grid.Add(linePlotDiff, pos=(12, 1), flag=wx.EXPAND)
        grid.Add(self.checkDiff, pos=(12, 2), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.textLocDiff, pos=(13, 0))

        sizerV = wx.BoxSizer(wx.HORIZONTAL)
        sizerV.Add(self.graph, 1, wx.EXPAND)
        sizerV.Add(grid, 0, wx.ALL, border=5)

        sizerH = wx.BoxSizer(wx.VERTICAL)
        sizerH.Add(sizerV, 1, wx.EXPAND, border=5)
        sizerH.Add(buttonClose, 0, wx.ALL | wx.ALIGN_RIGHT, border=5)

        self.SetSizerAndFit(sizerH)

        close_modeless()

    def __on_cursor(self, locs):
        self.textLoc1.SetLabel(self.__format_loc(locs['x1'], locs['y1']))
        self.textLoc2.SetLabel(self.__format_loc(locs['x2'], locs['y2']))
        self.textLocDiff.SetLabel(self.__format_loc(locs['x3'], locs['y3']))

    def __on_load_plot(self, event):
        dlg = wx.FileDialog(self, "Open a scan", self.dirname, self.filename,
                            File.get_type_filters(File.Types.SAVE),
                            wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.dirname = dlg.GetDirectory()
            self.filename = dlg.GetFilename()
            _scanInfo, spectrum, _location = open_plot(self.dirname,
                                                       self.filename)
            if event.EventObject == self.buttonPlot1:
                self.textPlot1.SetLabel(self.filename)
                self.graph.set_spectrum1(spectrum)
            else:
                self.textPlot2.SetLabel(self.filename)
                self.graph.set_spectrum2(spectrum)

        dlg.Destroy()

    def __on_check1(self, _event):
        checked = self.checkOne.GetValue()
        self.settings.compareOne = checked
        self.graph.show_plot1(checked)

    def __on_check2(self, _event):
        checked = self.checkTwo.GetValue()
        self.settings.compareTwo = checked
        self.graph.show_plot2(checked)

    def __on_check_diff(self, _event):
        checked = self.checkDiff.GetValue()
        self.settings.compareDiff = checked
        self.graph.show_plotdiff(checked)

    def __on_close(self, _event):
        close_modeless()
        self.Destroy()

    def __format_loc(self, x, y):
        if None in [x, y]:
            return ""

        freq, level = format_precision(self.settings, x, y, units=False)

        return '{} MHz\n{}    dB/Hz'.format(freq, level)


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
        sizer.Add(text, pos=(1, 0), flag=wx.ALL, border=10)
        sizer.Add(self.textFreq, pos=(1, 1), flag=wx.ALL,
                  border=5)
        sizer.Add(self.buttonCal, pos=(2, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTRE | wx.ALL | wx.EXPAND, border=10)
        sizer.Add(self.textResult, pos=(3, 0), span=(1, 2),
                  flag=wx.ALL, border=10)
        sizer.Add(buttons, pos=(4, 0), span=(1, 2),
                  flag=wx.ALL | wx.ALIGN_RIGHT, border=10)

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

    def get_arg1(self):
        return self.textFreq.GetValue()


class DialogSats(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent=parent, title='GPS Satellite Levels')
        self.parent = parent

        self.satLevel = SatLevel(self)

        self.textSats = wx.StaticText(self)
        self.__set_text(0, 0)

        self.Bind(wx.EVT_CLOSE, self.__on_close)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.satLevel, 1, flag=wx.ALL | wx.EXPAND, border=5)
        sizer.Add(self.textSats, 0, flag=wx.ALL | wx.EXPAND, border=5)

        self.SetSizerAndFit(sizer)

    def __set_text(self, used, seen):
        self.textSats.SetLabel('Satellites: {} used, {} seen'.format(used,
                                                                     seen))

    def __on_close(self, _event):
        self.Unbind(wx.EVT_CLOSE)
        self.parent.dlgSats = None
        self.Close()

    def set_sats(self, sats):
        self.satLevel.set_sats(sats)
        used = sum(1 for sat in sats.values() if sat[1])
        self.__set_text(used, len(sats))


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
