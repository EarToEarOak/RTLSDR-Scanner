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

import multiprocessing
import platform
import sys

from PIL import Image
import matplotlib
import numpy
import serial
import wx

from rtlsdr_scanner.utils_wx import load_bitmap
from rtlsdr_scanner.version import VERSION


class DialogSysInfo(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent=parent, title="System Information")

        textVersions = wx.TextCtrl(self,
                                   style=wx.TE_MULTILINE |
                                   wx.TE_READONLY |
                                   wx.TE_DONTWRAP |
                                   wx.TE_NO_VSCROLL)
        buttonOk = wx.Button(self, wx.ID_OK)

        self.__populate_versions(textVersions)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(textVersions, 1, flag=wx.ALL, border=10)
        sizer.Add(buttonOk, 0, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
        self.SetSizerAndFit(sizer)
        self.Centre()

    def __populate_versions(self, control):
        imageType = 'Pillow'
        try:
            imageVer = Image.PILLOW_VERSION
        except AttributeError:
            imageType = 'PIL'
            imageVer = Image.VERSION

        visvisVer = 'Not installed'
        if not hasattr(sys, 'frozen'):
            try:
                import visvis as vv
                visvisVer = vv.__version__
            except ImportError:
                pass

        versions = ('Hardware:\n'
                    '\tProcessor: {}, {} cores\n\n'
                    'Software:\n'
                    '\tOS: {}, {}\n'
                    '\tPython: {}\n'
                    '\tmatplotlib: {}\n'
                    '\tNumPy: {}\n'
                    '\t{}: {}\n'
                    '\tpySerial: {}\n'
                    '\tvisvis: {}\n'
                    '\twxPython: {}\n'
                    ).format(platform.processor(), multiprocessing.cpu_count(),
                             platform.platform(), platform.machine(),
                             platform.python_version(),
                             matplotlib.__version__,
                             numpy.version.version,
                             imageType, imageVer,
                             serial.VERSION,
                             visvisVer,
                             wx.version())

        control.SetValue(versions)

        dc = wx.WindowDC(control)
        extent = list(dc.GetMultiLineTextExtent(versions, control.GetFont()))
        extent[0] += wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X) * 2
        extent[1] += wx.SystemSettings.GetMetric(wx.SYS_HSCROLL_Y) * 2
        control.SetMinSize((extent[0], extent[1]))
        self.Layout()


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
        textVersion = wx.StaticText(self,
                                    label='v' + '.'.join([str(x) for x in VERSION]))
        buttonOk = wx.Button(self, wx.ID_OK)

        grid = wx.GridBagSizer(10, 10)
        grid.Add(bitmapIcon, pos=(0, 0), span=(3, 1),
                 flag=wx.ALIGN_LEFT | wx.ALL, border=10)
        grid.Add(textAbout, pos=(0, 1), span=(1, 2),
                 flag=wx.ALIGN_CENTRE | wx.ALL, border=10)
        grid.Add(textLink, pos=(1, 1), span=(1, 2),
                 flag=wx.ALIGN_CENTRE | wx.ALL, border=10)
        grid.Add(textVersion, pos=(2, 1), span=(1, 2),
                 flag=wx.ALIGN_CENTRE | wx.ALL, border=10)
        grid.Add(buttonOk, pos=(3, 2),
                 flag=wx.ALIGN_RIGHT | wx.ALL, border=10)

        self.SetSizerAndFit(grid)
        self.Centre()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
