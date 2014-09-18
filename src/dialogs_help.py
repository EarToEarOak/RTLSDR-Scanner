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

import multiprocessing
import platform
import textwrap

from PIL import Image
import matplotlib
import numpy
import serial
from wx import grid
import wx

from misc import get_version_timestamp, format_time
from utils_wx import load_bitmap


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


        try:
            import visvis as vv
            visvisVer = vv.__version__
        except ImportError:
            visvisVer = 'Not installed'

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
        grid.Add(buttonOk, pos=(3, 2),
                 flag=wx.ALIGN_RIGHT | wx.ALL, border=10)

        self.SetSizerAndFit(grid)
        self.Centre()


class DialogLog(wx.Dialog):
    def __init__(self, parent, log):
        wx.Dialog.__init__(self, parent=parent, title="Log")

        self.parent = parent
        self.log = log

        self.gridLog = grid.Grid(self)
        self.gridLog.CreateGrid(log.MAX_ENTRIES, 3)
        self.gridLog.SetRowLabelSize(0)
        self.gridLog.SetColLabelValue(0, "Time")
        self.gridLog.SetColLabelValue(1, "Level")
        self.gridLog.SetColLabelValue(2, "Event")
        self.gridLog.EnableEditing(False)

        textFilter = wx.StaticText(self, label='Level')
        self.choiceFilter = wx.Choice(self,
                                      choices=['All'] + self.log.TEXT_LEVEL)
        self.choiceFilter.SetSelection(0)
        self.choiceFilter.SetToolTipString('Filter log level')
        self.Bind(wx.EVT_CHOICE, self.__on_filter, self.choiceFilter)
        sizerFilter = wx.BoxSizer()
        sizerFilter.Add(textFilter, flag=wx.ALL, border=5)
        sizerFilter.Add(self.choiceFilter, flag=wx.ALL, border=5)

        buttonRefresh = wx.Button(self, wx.ID_ANY, label='Refresh')
        buttonRefresh.SetToolTipString('Refresh the log')
        buttonClose = wx.Button(self, wx.ID_CLOSE)
        self.Bind(wx.EVT_BUTTON, self.__on_refresh, buttonRefresh)
        self.Bind(wx.EVT_BUTTON, self.__on_close, buttonClose)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.gridLog, 1, flag=wx.ALL | wx.EXPAND, border=5)
        sizer.Add(sizerFilter, 0, flag=wx.ALL, border=5)
        sizer.Add(buttonRefresh, 0, flag=wx.ALL, border=5)
        sizer.Add(buttonClose, 0, flag=wx.ALL | wx.ALIGN_RIGHT, border=5)

        self.sizer = sizer
        self.__update_grid()
        self.SetSizer(sizer)

        self.Bind(wx.EVT_CLOSE, self.__on_close)

    def __on_filter(self, _event):
        selection = self.choiceFilter.GetSelection()
        if selection == 0:
            level = None
        else:
            level = selection - 1
        self.__update_grid(level)

    def __on_refresh(self, _event):
        self.__update_grid()

    def __on_close(self, _event):
        self.Unbind(wx.EVT_CLOSE)
        self.parent.dlgLog = None
        self.Close()

    def __update_grid(self, level=None):
        self.gridLog.ClearGrid()

        fontCell = self.gridLog.GetDefaultCellFont()
        fontSize = fontCell.GetPointSize()
        fontStyle = fontCell.GetStyle()
        fontWeight = fontCell.GetWeight()
        font = wx.Font(fontSize, wx.FONTFAMILY_MODERN, fontStyle,
                       fontWeight)

        i = 0
        for event in self.log.get(level):
            self.gridLog.SetCellValue(i, 0, format_time(event[0], True))
            self.gridLog.SetCellValue(i, 1, self.log.TEXT_LEVEL[event[1]])
            eventText = '\n'.join(textwrap.wrap(event[2], width=70))
            self.gridLog.SetCellValue(i, 2, eventText)
            self.gridLog.SetCellFont(i, 0, font)
            self.gridLog.SetCellFont(i, 1, font)
            self.gridLog.SetCellFont(i, 2, font)
            self.gridLog.SetCellAlignment(i, 0, wx.ALIGN_LEFT, wx.ALIGN_CENTRE)
            self.gridLog.SetCellAlignment(i, 1, wx.ALIGN_LEFT, wx.ALIGN_CENTRE)
            i += 1

        self.gridLog.AppendRows()
        self.gridLog.SetCellValue(i, 0, '#' * 18)
        self.gridLog.SetCellValue(i, 1, '#' * 5)
        self.gridLog.SetCellValue(i, 2, '#' * 80)
        self.gridLog.AutoSize()
        self.gridLog.DeleteRows(i)

        size = self.gridLog.GetBestSize()
        size.width += wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X) + 10
        size.height = 400
        self.SetClientSize(size)
        self.sizer.Layout()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
