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

import wx
from wx.lib.masked.numctrl import NumCtrl

from rtlsdr_scanner.constants import WINFUNC


class DialogSmoothPrefs(wx.Dialog):
    def __init__(self, parent, settings):
        wx.Dialog.__init__(self, parent=parent, title='Smoothing')

        self.settings = settings

        textFunc = wx.StaticText(self, label='Window function')
        self.choiceFunc = wx.Choice(self, choices=WINFUNC[::2])
        self.choiceFunc.SetSelection(WINFUNC[::2].index(settings.smoothFunc))

        textRatio = wx.StaticText(self, label='Smoothing')
        self.slideRatio = wx.Slider(self, value=settings.smoothRatio,
                                    minValue=2, maxValue=100,
                                    style=wx.SL_INVERSE)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()

        sizerGrid = wx.GridBagSizer(5, 5)
        sizerGrid.Add(textFunc, pos=(0, 0),
                      flag=wx.ALL, border=5)
        sizerGrid.Add(self.choiceFunc, pos=(0, 1),
                      flag=wx.ALL | wx.EXPAND, border=5)
        sizerGrid.Add(textRatio, pos=(1, 0),
                      flag=wx.ALL, border=5)
        sizerGrid.Add(self.slideRatio, pos=(1, 1),
                      flag=wx.ALL | wx.EXPAND, border=5)
        sizerGrid.Add(sizerButtons, pos=(2, 1),
                      flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(sizerGrid)

        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

    def __on_ok(self, _event):
        self.settings.smoothFunc = self.choiceFunc.GetStringSelection()
        self.settings.smoothRatio = self.slideRatio.GetValue()

        self.EndModal(wx.ID_OK)


class DialogPeakThreshold(wx.Dialog):
    def __init__(self, parent, settings):
        wx.Dialog.__init__(self, parent=parent, title='Peak Thresold')

        self.settings = settings

        textThres = wx.StaticText(self, label='Threshold (dB)')
        self.ctrlThres = NumCtrl(self, integerWidth=3)
        self.ctrlThres.SetValue(settings.peaksThres)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()

        sizerGrid = wx.GridBagSizer(5, 5)
        sizerGrid.Add(textThres, pos=(0, 0),
                      flag=wx.ALL, border=5)
        sizerGrid.Add(self.ctrlThres, pos=(0, 1),
                      flag=wx.ALL | wx.EXPAND, border=5)
        sizerGrid.Add(sizerButtons, pos=(1, 1),
                      flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(sizerGrid)

        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

    def __on_ok(self, _event):
        self.settings.peaksThres = self.ctrlThres.GetValue()

        self.EndModal(wx.ID_OK)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
