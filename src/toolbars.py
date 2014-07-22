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

from datetime import timedelta
import math
import time

import matplotlib
from matplotlib.backend_bases import NavigationToolbar2
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg
import wx

from constants import Display, PlotFunc
from controls import Led
from events import Log
from misc import load_bitmap, get_colours


class Statusbar(wx.StatusBar):
    TEXT_GENERAL = 'Status: '
    TEXT_INFO = 'Info: '
    TEXT_GPS = 'GPS: '

    def __init__(self, parent, log):
        self.controls = [None] * 4
        self.timeStart = None
        self.log = log

        wx.StatusBar.__init__(self, parent, -1)
        self.SetFieldsCount(4)

        self.controls[0] = wx.StaticText(self, label=Statusbar.TEXT_GENERAL,
                                         style=wx.ST_NO_AUTORESIZE)
        self.controls[1] = wx.StaticText(self, label=Statusbar.TEXT_INFO,
                                         style=wx.ST_NO_AUTORESIZE)
        self.controls[2] = Led(self, label=Statusbar.TEXT_GPS)

        self.controls[3] = wx.Gauge(self, -1,
                                    style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.controls[3].Hide()

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
        text = Statusbar.TEXT_GENERAL + text
        self.controls[0].SetLabel(text)
        self.controls[0].SetToolTipString(self.__format_tooltip(text))
        self.controls[0].Refresh()
        self.log.add(text, level)

    def set_info(self, text, level=Log.INFO):
        text = Statusbar.TEXT_INFO + text
        self.controls[1].SetLabel(text)
        self.controls[1].SetToolTipString(self.__format_tooltip(text))
        self.controls[1].Refresh()
        self.log.add(text, level)

    def set_gps(self, text, level=Log.INFO):
        text = Statusbar.TEXT_GPS + text
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

        self.__add_spacer()

        liveId = wx.NewId()
        self.AddCheckTool(liveId, load_bitmap('auto_refresh'),
                          shortHelp='Real time plotting\n(slow and buggy)')
        self.ToggleTool(liveId, settings.liveUpdate)
        wx.EVT_TOOL(self, liveId, self.__on_check_update)

        gridId = wx.NewId()
        self.AddCheckTool(gridId, load_bitmap('grid'),
                          shortHelp='Toggle plot grid')
        self.ToggleTool(gridId, settings.grid)
        wx.EVT_TOOL(self, gridId, self.__on_check_grid)

        self.autoFId = None
        self.autoLId = None
        self.autoTId = None
        self.maxId = None
        self.minId = None
        self.avgId = None
        self.varId = None
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

    def __on_check_var(self, event):
        check = event.Checked()
        if check:
            self.settings.plotFunc = PlotFunc.VAR
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

    def __add_spacer(self):
        sepId = wx.NewId()
        self.AddCheckTool(sepId, load_bitmap('spacer'))
        self.EnableTool(sepId, False)
        self.extraTools.append(sepId)

    def __set_func(self):
        buttons = [self.avgId, self.minId, self.maxId, self.varId]
        for button in buttons:
            self.ToggleTool(button, False)
        if self.settings.plotFunc != PlotFunc.NONE:
            self.ToggleTool(buttons[self.settings.plotFunc - 1], True)

    def set_auto(self, state):
        self.settings.autoF = state
        self.settings.autoL = state
        self.settings.autoT = state
        if self.autoFId is not None:
            self.ToggleTool(self.autoFId, state)
        if self.autoLId is not None:
            self.ToggleTool(self.autoLId, state)
        if self.autoTId is not None:
            self.ToggleTool(self.autoTId, state)

    def clear_auto(self):
        self.set_auto(False)

    def set_plot(self, plot):
        self.plot = plot

    def set_type(self, display):
        for toolId in self.extraTools:
            self.DeleteTool(toolId)
        self.extraTools = []

        if display != Display.STATUS:
            self.__add_check_tool('peak', 'Label peak',
                                  self.__on_check_peak,
                                  self.settings.annotate)

            self.__add_spacer()

            self.autoFId = wx.NewId()
            self.__add_check_tool('auto_f', 'Auto range frequency',
                                  self.__on_check_auto_f,
                                  self.settings.autoF,
                                  self.autoFId)
            self.autoLId = wx.NewId()
            self.__add_check_tool('auto_l', 'Auto range level',
                                  self.__on_check_auto_l,
                                  self.settings.autoL,
                                  self.autoLId)

        if  display != Display.PLOT  and display != Display.STATUS:
            self.autoTId = wx.NewId()
            self.__add_check_tool('auto_t', 'Auto range time',
                                  self.__on_check_auto_t,
                                  self.settings.autoT,
                                  self.autoTId)

        self.__add_spacer()

        if display == Display.PLOT:
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
            self.__set_func()

            self.__add_spacer()

            self.__add_check_tool('colourmap', 'Use colour maps',
                                  self.__on_colour_use,
                                  self.settings.colourMapUse)

        if display != Display.STATUS:
            colours = get_colours()
            colourId = wx.NewId()
            self.colourId = wx.Choice(self, id=colourId, choices=colours)
            self.colourId.SetSelection(colours.index(self.settings.colourMap))
            self.AddControl(self.colourId)
            if display == Display.PLOT:
                self.colourId.Enable(self.settings.colourMapUse)
            self.Bind(wx.EVT_CHOICE, self.__on_colour, self.colourId)
            self.extraTools.append(colourId)

        if display == Display.SURFACE:
            self.__add_spacer()
            self.__add_check_tool('wireframe', 'Wireframe drawing',
                                  self.__on_check_wire,
                                  self.settings.wireframe)

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
