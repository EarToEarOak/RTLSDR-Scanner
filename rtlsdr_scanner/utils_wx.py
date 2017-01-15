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

import os

import wx
from rtlsdr_scanner.misc import get_resource


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


def load_bitmap(name):
    filename = get_resource(name + '.png')

    return wx.Bitmap(filename, wx.BITMAP_TYPE_PNG)


def load_icon(name):
    filename = get_resource(name + '.png')

    return wx.Icon(filename, wx.BITMAP_TYPE_PNG)


def close_modeless():
    for child in wx.GetTopLevelWindows():
        if child.Title == 'Configure subplots':
            child.Close()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
