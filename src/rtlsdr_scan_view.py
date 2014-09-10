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

from file import File, open_plot
from spectrum import sort_spectrum
import visvis as vv


app = vv.use('wx')


class MainWindow(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, -1, 'RTLSDR Scanner Viewer', size=(800, 600))

        Figure = app.GetFigureClass()
        fig = Figure(self)

        panel = wx.Panel(self)
        button = wx.Button(panel, wx.ID_ANY, 'Open')
        button.Bind(wx.EVT_BUTTON, self.__on_open)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(fig._widget, 1, wx.EXPAND | wx.ALL, border=5)
        sizer.Add(panel, 0, wx.EXPAND | wx.ALL, border=5)

        self.SetSizer(sizer)
        self.SetAutoLayout(True)
        self.Layout()

        self.Show()

    def __on_open(self, _event):
        dlg = wx.FileDialog(self, "Open a scan", '.',
                            '',
                            File.get_type_filters(File.Types.SAVE),
                            wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.__open(dlg.GetDirectory(), dlg.GetFilename())
        dlg.Destroy()

    def __open(self, dirname, filename):
        _info, spectrum, _locs = open_plot(dirname, filename)
        self.__plot(sort_spectrum(spectrum))

    def __plot(self, spectrum):
        vv.clf()
        axes = vv.gca()
        axes.axis.showGrid = 1
        axes.axis.xlabel = 'Frequency (MHz)'
        axes.axis.ylabel = 'Level (dB)'

        total = len(spectrum)
        count = 0.
        for _time, sweep in spectrum.items():
            alpha = (total - count) / total
            plot = vv.plot(sweep.keys(), sweep.values(), lw=1, alpha=alpha)
            count += 1


if __name__ == '__main__':
    wxApp = wx.App()
    m = MainWindow()
    wxApp.MainLoop()
