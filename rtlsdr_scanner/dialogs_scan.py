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


class DialogScanDelay(wx.Dialog):
    def __init__(self, parent, settings):
        wx.Dialog.__init__(self, parent=parent, title='Smoothing')

        self.settings = settings

        textDelay = wx.StaticText(self, label='Scan delay (s)')
        self.spinDelay = wx.SpinCtrl(self, value=str(settings.scanDelay),
                                     min=0, max=86400)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(textDelay, flag=wx.ALL, border=5)
        sizer.Add(self.spinDelay, flag=wx.ALL, border=5)
        sizer.Add(sizerButtons, flag=wx.ALL, border=5)

        self.SetSizerAndFit(sizer)

        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

    def __on_ok(self, _event):
        self.settings.scanDelay = self.spinDelay.GetValue()

        self.EndModal(wx.ID_OK)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
