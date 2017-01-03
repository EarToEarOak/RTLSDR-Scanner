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

from datetime import timedelta
import math
import time

import matplotlib
from matplotlib.backend_bases import NavigationToolbar2
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg
import wx
from wx.animate import AnimationCtrl, Animation

from rtlsdr_scanner.constants import Display, PlotFunc
from rtlsdr_scanner.dialogs_toolbars import DialogSmoothPrefs, DialogPeakThreshold
from rtlsdr_scanner.events import Log
from rtlsdr_scanner.misc import get_resource
from rtlsdr_scanner.utils_mpl import get_colours
from rtlsdr_scanner.utils_wx import load_bitmap
from rtlsdr_scanner.widgets import Led


class Statusbar(wx.StatusBar):
    TEXT_GENERAL = 'Status: '
    TEXT_INFO = 'Info: '
    TEXT_GPS = 'GPS: '

    def __init__(self, parent, log):
        self.controls = [None] * 5
        self.timeStart = None
        self.log = log

        wx.StatusBar.__init__(self, parent, -1)
        self.SetFieldsCount(len(self.controls))

        self.controls[0] = wx.StaticText(self, label=self.TEXT_GENERAL,
                                         style=wx.ST_NO_AUTORESIZE)
        self.controls[1] = wx.StaticText(self, label=self.TEXT_INFO,
                                         style=wx.ST_NO_AUTORESIZE)
        self.controls[2] = Led(self, label=self.TEXT_GPS)
        self.controls[3] = wx.Gauge(self, -1,
                                    style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        animation = Animation(get_resource('busy.gif'))
        busy = AnimationCtrl(self, anim=animation)
        busy.SetToolTipString('Updating plot')
        self.controls[4] = busy

        self.controls[3].Hide()
        self.controls[4].Hide()

        self.SetStatusWidths([-1, -1, -1, -1, busy.GetSize()[0] * 4])

        self.Bind(wx.EVT_SIZE, self.__on_size)
        wx.CallAfter(self.__on_size, None)

        self.Fit()

    def __on_size(self, event):
        pos = 0
        for control in self.controls:
            rect = self.GetFieldRect(pos)
            control.SetPosition((rect.x + 10, rect.y + 2))
            control.SetSize((rect.width - 20, rect.height - 4))
            pos += 1

        if event is not None:
            event.Skip()

    def __format_tooltip(self, text):
        if len(text):
            lines = text.splitlines()
            width = max(map(len, lines))
            lines[-1] += '\n' + ' ' * (width - len(lines[-1]))
        return text

    def set_general(self, text, level=Log.INFO):
        text = self.TEXT_GENERAL + text
        self.controls[0].SetLabel(text)
        self.controls[0].SetToolTipString(self.__format_tooltip(text))
        self.controls[0].Refresh()
        self.log.add(text, level)

    def set_info(self, text, level=Log.INFO):
        text = self.TEXT_INFO + text
        self.controls[1].SetLabel(text)
        self.controls[1].SetToolTipString(self.__format_tooltip(text))
        self.controls[1].Refresh()
        self.log.add(text, level)

    def set_gps(self, text, level=Log.INFO):
        text = self.TEXT_GPS + text
        self.controls[2].SetLabel(text)
        self.controls[2].SetToolTipString(self.__format_tooltip(text))
        self.controls[2].Refresh()
        self.log.add(text, level)

    def pulse_gps(self):
        self.controls[2].pulse()

    def warn_gps(self):
        self.controls[2].on("yellow")

    def error_gps(self):
        self.controls[2].on(wx.RED)

    def enable_gps(self):
        self.controls[2].on('w')
        self.set_gps('Enabled')

    def disable_gps(self):
        self.controls[2].on('grey')
        self.set_gps('Disabled')

    def set_progress(self, progress):
        if progress == 0:
            self.timeStart = time.time()
            text = '{:.1f}%\nUnknown'.format(progress)
        else:
            timeTotal = time.time() - self.timeStart
            timeLeft = ((timeTotal / (progress)) * 100.0) - timeTotal
            delta = timedelta(seconds=math.ceil(timeLeft))
            text = '{:.1f}%\n{}'.format(progress, delta)

        self.controls[3].SetValue(progress)
        self.controls[3].SetToolTipString(self.__format_tooltip(text))

    def show_progress(self):
        self.controls[3].Show()

    def hide_progress(self):
        self.controls[3].Hide()
        self.controls[3].SetToolTipString('')

    def set_busy(self, busy):
        animCtrl = self.controls[4]
        animCtrl.Show(busy)
        if busy:
            animCtrl.Play()
        else:
            animCtrl.Stop()


class NavigationToolbar(NavigationToolbar2WxAgg):
    def __init__(self, canvas, panel, settings, callBackHideOverlay):
        self.panel = panel
        self.settings = settings
        self.callbackHide = callBackHideOverlay
        self.plot = None
        self.extraTools = []
        self.panPos = None

        NavigationToolbar2WxAgg.__init__(self, canvas)
        if matplotlib.__version__ >= '1.2':
            panId = self.wx_ids['Pan']
        else:
            panId = self.FindById(self._NTB2_PAN).GetId()

        self.ToggleTool(panId, True)
        self.pan()

        self.__add_spacer(False)

        liveId = wx.NewId()
        self.AddCheckTool(liveId, load_bitmap('auto_refresh'),
                          shortHelp='Real time plotting\n(slow and buggy)')
        self.ToggleTool(liveId, settings.liveUpdate)
        wx.EVT_TOOL(self, liveId, self.__on_check_update)

        gridId = wx.NewId()
        self.AddCheckTool(gridId, load_bitmap('grid'),
                          shortHelp='Toggle plot_line grid')
        self.ToggleTool(gridId, settings.grid)
        wx.EVT_TOOL(self, gridId, self.__on_check_grid)

        self.peakId = wx.NewId()
        self.peaksId = None

        self.autoFId = None
        self.autoLId = None
        self.autoTId = None

        self.maxId = None
        self.minId = None
        self.avgId = None
        self.varId = None
        self.smoothId = None
        self.diffId = None
        self.deltaId = None

        self.colourId = None

    def home(self, event):
        self.callbackHide()
        NavigationToolbar2.home(self, event)
        self.clear_auto()

    def back(self, event):
        self.callbackHide()
        NavigationToolbar2.back(self, event)
        self.clear_auto()

    def forward(self, event):
        self.callbackHide()
        NavigationToolbar2.forward(self, event)
        self.clear_auto()

    def drag_pan(self, event):
        if not self.panPos:
            self.panPos = (event.x, event.y)
        NavigationToolbar2.drag_pan(self, event)

    def release_pan(self, event):
        pos = (event.x, event.y)
        self.callbackHide()
        NavigationToolbar2.release_pan(self, event)
        if event.button != 2:
            if self.panPos and self.panPos != pos:
                self.clear_auto()
        self.panPos = None

    def release_zoom(self, event):
        self.callbackHide()
        NavigationToolbar2.release_zoom(self, event)
        self.clear_auto()

    def __on_check_auto_f(self, event):
        self.settings.autoF = event.Checked()
        self.panel.redraw_plot()

    def __on_check_auto_l(self, event):
        self.settings.autoL = event.Checked()
        self.panel.redraw_plot()

    def __on_check_auto_t(self, event):
        self.settings.autoT = event.Checked()
        self.panel.redraw_plot()

    def __on_check_update(self, event):
        self.settings.liveUpdate = event.Checked()

    def __on_check_grid(self, event):
        grid = event.Checked()
        self.settings.grid = grid
        self.panel.set_grid(grid)

    def __on_check_peak(self, event):
        peak = event.Checked()
        self.settings.annotate = peak
        self.panel.redraw_plot()

    def __on_check_peaks(self, event):
        peaks = event.Checked()
        self.settings.peaks = peaks
        self.panel.redraw_plot()

    def __on_check_fade(self, event):
        fade = event.Checked()
        self.settings.fadeScans = fade
        self.panel.redraw_plot()

    def __on_check_wire(self, event):
        wire = event.Checked()
        self.settings.wireframe = wire
        self.panel.create_plot()

    def __on_check_avg(self, event):
        check = event.Checked()
        if check:
            self.settings.plotFunc = PlotFunc.AVG
        else:
            self.settings.plotFunc = PlotFunc.NONE
        self.__set_func()
        self.panel.redraw_plot()

    def __on_check_min(self, event):
        check = event.Checked()
        if check:
            self.settings.plotFunc = PlotFunc.MIN
        else:
            self.settings.plotFunc = PlotFunc.NONE
        self.__set_func()
        self.panel.redraw_plot()

    def __on_check_max(self, event):
        check = event.Checked()
        if check:
            self.settings.plotFunc = PlotFunc.MAX
        else:
            self.settings.plotFunc = PlotFunc.NONE
        self.__set_func()
        self.panel.redraw_plot()

    def __on_check_var(self, event):
        check = event.Checked()
        if check:
            self.settings.plotFunc = PlotFunc.VAR
        else:
            self.settings.plotFunc = PlotFunc.NONE
        self.__set_func()
        self.panel.redraw_plot()

    def __on_check_smooth(self, event):
        check = event.Checked()
        if check:
            self.settings.plotFunc = PlotFunc.SMOOTH
        else:
            self.settings.plotFunc = PlotFunc.NONE
        self.__set_func()
        self.panel.redraw_plot()

    def __on_check_diff(self, event):
        check = event.Checked()
        if check:
            self.settings.plotFunc = PlotFunc.DIFF
        else:
            self.settings.plotFunc = PlotFunc.NONE
        self.__set_func()
        self.panel.redraw_plot()

    def __on_check_delta(self, event):
        check = event.Checked()
        if check:
            self.settings.plotFunc = PlotFunc.DELTA
        else:
            self.settings.plotFunc = PlotFunc.NONE
        self.__set_func()
        self.panel.redraw_plot()

    def __on_set_smooth(self, _event):
        dlg = DialogSmoothPrefs(self, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            self.panel.redraw_plot()

    def __on_set_peaks(self, _event):
        dlg = DialogPeakThreshold(self, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            self.panel.redraw_plot()

    def __on_colour(self, event):
        colourMap = event.GetString()
        self.settings.colourMap = colourMap
        self.plot.set_colourmap(colourMap)
        self.panel.redraw_plot()

    def __on_colour_use(self, event):
        check = event.Checked()
        self.settings.colourMapUse = check
        self.colourId.Enable(check)
        self.plot.set_colourmap_use(check)
        self.panel.redraw_plot()

    def __add_check_tool(self, bitmap, toolTip, callback, setting=None, toolId=None):
        if toolId is None:
            toolId = wx.NewId()
        self.AddCheckTool(toolId, load_bitmap(bitmap), shortHelp=toolTip)
        wx.EVT_TOOL(self, toolId, callback)
        if setting is not None:
            self.ToggleTool(toolId, setting)
        self.extraTools.append(toolId)

    def __add_spacer(self, temp=True):
        sepId = wx.NewId()
        self.AddCheckTool(sepId, load_bitmap('spacer'))
        self.EnableTool(sepId, False)
        if temp:
            self.extraTools.append(sepId)

    def __add_peak(self):
        self.__add_check_tool('peak', 'Label peak',
                              self.__on_check_peak,
                              self.settings.annotate,
                              toolId=self.peakId)

    def __add_peaks(self):
        self.peaksId = wx.NewId()
        self.__add_check_tool('peaks', 'Mark peaks above threshold '
                              '(right click for options)',
                              self.__on_check_peaks,
                              self.settings.peaks,
                              toolId=self.peaksId)
        wx.EVT_TOOL_RCLICKED(self, self.peaksId, self.__on_set_peaks)

    def __add_auto_range(self, scaleF, scaleL, scaleT):
        if scaleF:
            self.autoFId = wx.NewId()
            self.__add_check_tool('auto_f', 'Auto range frequency',
                                  self.__on_check_auto_f,
                                  self.settings.autoF,
                                  self.autoFId)

        if scaleL:
            self.autoLId = wx.NewId()
            self.__add_check_tool('auto_l', 'Auto range level',
                                  self.__on_check_auto_l,
                                  self.settings.autoL,
                                  self.autoLId)

        if scaleT:
            self.autoTId = wx.NewId()
            self.__add_check_tool('auto_t', 'Auto range time',
                                  self.__on_check_auto_t,
                                  self.settings.autoT,
                                  self.autoTId)

        self.__add_spacer()

    def __add_colourmap(self, useMapButton=True):
        if useMapButton:
            self.__add_check_tool('colourmap', 'Use colour maps',
                                  self.__on_colour_use,
                                  self.settings.colourMapUse)

        colours = get_colours()
        colourId = wx.NewId()
        self.colourId = wx.Choice(self, id=colourId, choices=colours)
        self.colourId.SetSelection(colours.index(self.settings.colourMap))
        self.AddControl(self.colourId)
        self.colourId.Enable(self.settings.colourMapUse)
        self.Bind(wx.EVT_CHOICE, self.__on_colour, self.colourId)
        self.extraTools.append(colourId)

    def __enable_tool(self, toolId, state):
        if toolId is not None:
            self.EnableTool(toolId, state)

    def __toggle_tool(self, toolId, state):
        if toolId is not None:
            self.ToggleTool(toolId, state)

    def __set_func(self):
        buttons = [self.avgId, self.minId, self.maxId,
                   self.varId, self.smoothId, self.diffId, self.deltaId]

        for button in buttons:
            self.__toggle_tool(button, False)

        if self.settings.plotFunc != PlotFunc.NONE:
            self.__toggle_tool(buttons[self.settings.plotFunc - 1], True)

        if self.settings.plotFunc == PlotFunc.NONE:
            self.__enable_tool(self.peakId, True)
            self.__enable_tool(self.peaksId, True)
        elif self.settings.plotFunc in [PlotFunc.AVG, PlotFunc.MIN,
                                        PlotFunc.MAX, PlotFunc.SMOOTH,
                                        PlotFunc.DIFF, PlotFunc.DELTA]:
            self.__enable_tool(self.peakId, True)
            self.__enable_tool(self.peaksId, False)
            self.__toggle_tool(self.peaksId, False)
            self.settings.peaks = False
        else:
            self.__enable_tool(self.peakId, False)
            self.__enable_tool(self.peaksId, False)
            self.__toggle_tool(self.peaksId, False)
            self.__toggle_tool(self.peakId, False)
            self.settings.annotate = False
            self.settings.peaks = False

    def set_auto(self, state):
        self.settings.autoF = state
        self.settings.autoL = state
        self.settings.autoT = state
        self.__toggle_tool(self.autoFId, state)
        self.__toggle_tool(self.autoLId, state)
        self.__toggle_tool(self.autoTId, state)

    def clear_auto(self):
        self.set_auto(False)

    def set_plot(self, plot):
        self.plot = plot

    def set_type(self, display):
        for toolId in self.extraTools:
            self.DeleteTool(toolId)
        self.extraTools = []

        self.__add_spacer()

        if display == Display.PLOT:
            self.__add_auto_range(True, True, False)
            self.__add_peak()
            self.__add_peaks()

            self.__add_check_tool('fade', 'Fade plots',
                                  self.__on_check_fade,
                                  self.settings.fadeScans)
            self.__add_spacer()
            self.avgId = wx.NewId()
            self.__add_check_tool('average', 'Show average',
                                  self.__on_check_avg,
                                  toolId=self.avgId)
            self.minId = wx.NewId()
            self.__add_check_tool('min', 'Show minimum',
                                  self.__on_check_min,
                                  toolId=self.minId)
            self.maxId = wx.NewId()
            self.__add_check_tool('max', 'Show maximum',
                                  self.__on_check_max,
                                  toolId=self.maxId)
            self.varId = wx.NewId()
            self.__add_check_tool('variance', 'Show variance',
                                  self.__on_check_var,
                                  toolId=self.varId)
            self.smoothId = wx.NewId()
            self.__add_check_tool('smooth', 'Smooth (right click for options)',
                                  self.__on_check_smooth,
                                  toolId=self.smoothId)
            wx.EVT_TOOL_RCLICKED(self, self.smoothId, self.__on_set_smooth)
            self.diffId = wx.NewId()
            self.__add_check_tool('diff', 'Differentiate spectrum',
                                  self.__on_check_diff,
                                  toolId=self.diffId)
            self.deltaId = wx.NewId()
            self.__add_check_tool('delta', 'Delta from first sweep',
                                  self.__on_check_delta,
                                  toolId=self.deltaId)

            self.__add_spacer()
            self.__add_colourmap()

        elif display == Display.SPECT:
            self.__add_auto_range(True, True, True)
            self.__add_peak()
            self.__add_peaks()
            self.smoothId = wx.NewId()
            self.__add_check_tool('smooth', 'Smooth (right click for options)',
                                  self.__on_check_smooth,
                                  toolId=self.smoothId)
            wx.EVT_TOOL_RCLICKED(self, self.smoothId, self.__on_set_smooth)
            self.diffId = wx.NewId()
            self.__add_check_tool('diff', 'Differentiate spectrum',
                                  self.__on_check_diff,
                                  toolId=self.diffId)
            self.__add_spacer()
            self.__add_colourmap(False)

        elif display == Display.SURFACE:
            self.__add_auto_range(True, True, True)
            self.__add_peak()
            self.__add_peaks()
            self.smoothId = wx.NewId()
            self.__add_check_tool('smooth', 'Smooth (right click for options)',
                                  self.__on_check_smooth,
                                  toolId=self.smoothId)
            wx.EVT_TOOL_RCLICKED(self, self.smoothId, self.__on_set_smooth)
            self.diffId = wx.NewId()
            self.__add_check_tool('diff', 'Differentiate spectrum',
                                  self.__on_check_diff,
                                  toolId=self.diffId)
            self.__add_spacer()
            self.__add_colourmap(False)
            self.__add_spacer()
            self.__add_check_tool('wireframe', 'Wireframe drawing',
                                  self.__on_check_wire,
                                  self.settings.wireframe)

        elif display == Display.TIMELINE:
            self.__add_auto_range(False, True, True)

        elif display == Display.PREVIEW:
            self.__add_check_tool('fade', 'Fade plots',
                                  self.__on_check_fade,
                                  self.settings.fadeScans)

        self.__set_func()

        self.Realize()


class NavigationToolbarCompare(NavigationToolbar2WxAgg):
    def __init__(self, panel):
        NavigationToolbar2WxAgg.__init__(self, panel.get_canvas())
        self.panel = panel

        self.AddSeparator()

        gridId = wx.NewId()
        self.AddCheckTool(gridId, load_bitmap('grid'),
                          shortHelp='Toggle grid')
        self.ToggleTool(gridId, True)
        wx.EVT_TOOL(self, gridId, self.__on_check_grid)

    def __on_check_grid(self, event):
        grid = event.Checked()
        self.panel.set_grid(grid)

    def clear_auto(self):
        pass


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
