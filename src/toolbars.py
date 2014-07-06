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

import matplotlib
from matplotlib.backend_bases import NavigationToolbar2
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg
import wx

from constants import Display, PlotFunc
from misc import load_bitmap, get_colours


class Statusbar(wx.StatusBar):
    def __init__(self, parent):
        self.controls = [None] * 4

        wx.StatusBar.__init__(self, parent, -1)
        self.SetFieldsCount(4)

        for i in range(0, 3):
            self.controls[i] = wx.StaticText(self, label='')

        self.controls[3] = wx.Gauge(self, -1,
                                    style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.controls[3].Hide()

        self.Bind(wx.EVT_SIZE, self.__on_size)

    def __on_size(self, event):
        pos = 0
        for control in self.controls:
            rect = self.GetFieldRect(pos)
            control.SetPosition((rect.x + 10, rect.y + 2))
            control.SetSize((rect.width - 20, rect.height - 4))
            pos += 1

        event.Skip()

    def set_general(self, text):
        self.controls[0].SetLabel(text)
        self.controls[0].SetToolTipString(text)

    def set_info(self, text):
        self.controls[1].SetLabel(text)
        self.controls[1].SetToolTipString(text)

    def set_gps(self, text):
        self.controls[2].SetLabel(text)
        self.controls[2].SetToolTipString(text)

    def set_progress(self, progress):
        self.controls[3].SetValue(progress)

    def show_progress(self):
        self.controls[3].Show()

    def hide_progress(self):
        self.controls[3].Hide()


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

        peakId = wx.NewId()
        self.AddCheckTool(peakId, load_bitmap('peak'),
                          shortHelp='Label peak')
        self.ToggleTool(peakId, settings.annotate)
        wx.EVT_TOOL(self, peakId, self.__on_check_peak)

        self.__add_spacer()

        self.autoFId = wx.NewId()
        self.AddCheckTool(self.autoFId, load_bitmap('auto_f'),
                          shortHelp='Auto range frequency')
        self.ToggleTool(self.autoFId, settings.autoF)
        wx.EVT_TOOL(self, self.autoFId, self.__on_check_auto_f)

        self.autoLId = wx.NewId()
        self.AddCheckTool(self.autoLId, load_bitmap('auto_l'),
                          shortHelp='Auto range level')
        self.ToggleTool(self.autoLId, settings.autoL)
        wx.EVT_TOOL(self, self.autoLId, self.__on_check_auto_l)

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

    def __add_spacer(self):
        sepId = wx.NewId()
        self.AddCheckTool(sepId, load_bitmap('spacer'))
        self.EnableTool(sepId, False)
        return sepId

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
        self.ToggleTool(self.autoFId, state)
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

        if not display == Display.PLOT:
            self.autoTId = wx.NewId()
            self.AddCheckTool(self.autoTId, load_bitmap('auto_t'),
                              shortHelp='Auto range time')
            self.ToggleTool(self.autoTId, self.settings.autoT)
            wx.EVT_TOOL(self, self.autoTId, self.__on_check_auto_t)
            self.extraTools.append(self.autoTId)

        self.extraTools.append(self.__add_spacer())

        if display == Display.PLOT:
            fadeId = wx.NewId()
            self.AddCheckTool(fadeId, load_bitmap('fade'),
                              shortHelp='Fade plots')
            wx.EVT_TOOL(self, fadeId, self.__on_check_fade)
            self.ToggleTool(fadeId, self.settings.fadeScans)
            self.extraTools.append(fadeId)

            self.extraTools.append(self.__add_spacer())

            self.avgId = wx.NewId()
            self.AddCheckTool(self.avgId, load_bitmap('average'),
                              shortHelp='Show average')
            wx.EVT_TOOL(self, self.avgId, self.__on_check_avg)
            self.extraTools.append(self.avgId)
            self.minId = wx.NewId()
            self.AddCheckTool(self.minId, load_bitmap('min'),
                              shortHelp='Show minimum')
            wx.EVT_TOOL(self, self.minId, self.__on_check_min)
            self.extraTools.append(self.minId)
            self.maxId = wx.NewId()
            self.AddCheckTool(self.maxId, load_bitmap('max'),
                              shortHelp='Show maximum')
            wx.EVT_TOOL(self, self.maxId, self.__on_check_max)
            self.extraTools.append(self.maxId)
            self.varId = wx.NewId()
            self.AddCheckTool(self.varId, load_bitmap('variance'),
                              shortHelp='Show variance')
            wx.EVT_TOOL(self, self.varId, self.__on_check_var)
            self.extraTools.append(self.varId)

            self.__set_func()

            self.extraTools.append(self.__add_spacer())

        if display == Display.PLOT:
            colourUseId = wx.NewId()
            self.AddCheckTool(colourUseId, load_bitmap('colourmap'),
                              shortHelp='Use colour maps')
            wx.EVT_TOOL(self, colourUseId, self.__on_colour_use)
            self.ToggleTool(colourUseId, self.settings.colourMapUse)
            self.extraTools.append(colourUseId)

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
            self.extraTools.append(self.__add_spacer())

            wireId = wx.NewId()
            self.AddCheckTool(wireId, load_bitmap('wireframe'),
                              shortHelp='Wireframe')
            wx.EVT_TOOL(self, wireId, self.__on_check_wire)
            self.ToggleTool(wireId, self.settings.wireframe)
            self.extraTools.append(wireId)

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
