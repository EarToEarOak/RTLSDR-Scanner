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

try:
    import visvis as vv
    from visvis.core.line import Line
    app = vv.use('wx')
    vvPresent = True
except ImportError as error:
    vvPresent = False


class PlotterPreview(object):
    def __init__(self, notify, figure, _settings):
        self.notify = notify
        self.figure = figure
        self.axes = None
        self.window = None
        self.preview = None

        self.__setup_plot()
        self.__setup_window()
        self.set_plot(None, None, None)

    def __setup_plot(self):
        self.axes = self.figure.add_subplot(111)
        self.axes.set_axis_off()
        if not vvPresent:
            self.axes.text(0.5, 0.5, '"visvis" is not installed',
                           ha='center', va='center')

    def __setup_window(self):
        if vvPresent:
            self.preview = DialogPreview(self.window)
            self.preview.Show()

    def draw_measure(self, _measure, _show):
        pass

    def hide_measure(self):
        pass

    def scale_plot(self, _force=False):
        pass

    def redraw_plot(self):
        pass

    def get_axes(self):
        return None

    def get_axes_bar(self):
        return None

    def get_plot_thread(self):
        return None

    def set_window(self, window):
        self.window = window

    def set_title(self, title):
        if self.preview is not None:
            self.preview.set_title(title)

    def set_plot(self, spectrum, _extent, _annotate=False):
        if spectrum is not None and self.preview is not None:
            self.preview.set_plot(spectrum)

    def clear_plots(self):
        if self.preview is not None:
            self.preview.clear_plots()

    def set_grid(self, _on):
        pass

    def close(self):
        if self.preview is not None:
            self.preview.Destroy()
        self.figure.clear()
        self.figure = None


class DialogPreview(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent=parent, title="Preview",
                           style=wx.RESIZE_BORDER | wx.CAPTION |
                           wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX | wx.SYSTEM_MENU)
        self.Lower()

        Figure = app.GetFigureClass()
        fig = Figure(self)
        fig.bgcolor = (1, 1, 1)
        self.__setup_plot()

        sizer = wx.BoxSizer()
        sizer.Add(fig._widget, 1, wx.EXPAND | wx.ALL, border=5)

        self.SetSizer(sizer)
        self.SetAutoLayout(True)
        self.Layout()

    def __setup_plot(self):
        axes = vv.gca()
        axes.axis.showGrid = True
        axes.axis.xLabel = 'Frequency (MHz)'
        axes.axis.yLabel = 'Level (dB)'

    def clear_plots(self):
        for wobject in vv.gca().wobjects:
            if isinstance(wobject, Line):
                wobject.Destroy()

    def set_plot(self, spectrum):
        self.clear_plots()

        total = len(spectrum)
        count = 0.
        for _time, sweep in spectrum.items():
            alpha = (total - count) / total
            vv.plot(sweep.keys(), sweep.values(), lw=1, alpha=alpha)
            count += 1

    def set_title(self, title):
        vv.title(title.replace('\n', ' '))
