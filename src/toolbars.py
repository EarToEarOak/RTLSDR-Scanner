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

from constants import Display
from misc import load_bitmap, get_colours


class Statusbar(wx.StatusBar):
    def __init__(self, parent):
        wx.StatusBar.__init__(self, parent, -1)
        self.SetFieldsCount(3)
        self.statusProgress = wx.Gauge(self, -1,
                                       style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.statusProgress.Hide()
        self.Bind(wx.EVT_SIZE, self.on_size)

    def on_size(self, event):
        rect = self.GetFieldRect(2)
        self.statusProgress.SetPosition((rect.x + 10, rect.y + 2))
        self.statusProgress.SetSize((rect.width - 20, rect.height - 4))
        event.Skip()

    def set_general(self, text):
        self.SetStatusText(text, 0)
        self.SetToolTipString(text)

    def set_info(self, text):
        self.SetStatusText(text, 1)

    def set_progress(self, progress):
        self.statusProgress.SetValue(progress)

    def show_progress(self):
        self.statusProgress.Show()

    def hide_progress(self):
        self.statusProgress.Hide()


class NavigationToolbar(NavigationToolbar2WxAgg):
    def __init__(self, canvas, panel, settings, onNavChange):
        self.panel = panel
        self.settings = settings
        self.onNavChange = onNavChange
        self.plot = None
        self.extraTools = []

        NavigationToolbar2WxAgg.__init__(self, canvas)
        if matplotlib.__version__ >= '1.2':
            panId = self.wx_ids['Pan']
        else:
            panId = self.FindById(self._NTB2_PAN).GetId()

        self.ToggleTool(panId, True)
        self.pan()

        self.add_spacer()

        liveId = wx.NewId()
        self.AddCheckTool(liveId, load_bitmap('auto_refresh'),
                          shortHelp='Real time plotting\n(slow and buggy)')
        self.ToggleTool(liveId, settings.liveUpdate)
        wx.EVT_TOOL(self, liveId, self.on_check_update)

        gridId = wx.NewId()
        self.AddCheckTool(gridId, load_bitmap('grid'),
                          shortHelp='Toggle plot grid')
        self.ToggleTool(gridId, settings.grid)
        wx.EVT_TOOL(self, gridId, self.on_check_grid)

        peakId = wx.NewId()
        self.AddCheckTool(peakId, load_bitmap('peak'),
                          shortHelp='Label peak')
        self.ToggleTool(peakId, settings.annotate)
        wx.EVT_TOOL(self, peakId, self.on_check_peak)

        self.add_spacer()

        self.autoFId = wx.NewId()
        self.AddCheckTool(self.autoFId, load_bitmap('auto_f'),
                          shortHelp='Auto range frequency')
        self.ToggleTool(self.autoFId, settings.autoF)
        wx.EVT_TOOL(self, self.autoFId, self.on_check_auto_f)

        self.autoLId = wx.NewId()
        self.AddCheckTool(self.autoLId, load_bitmap('auto_l'),
                          shortHelp='Auto range level')
        self.ToggleTool(self.autoLId, settings.autoL)
        wx.EVT_TOOL(self, self.autoLId, self.on_check_auto_l)

    def home(self, event):
        NavigationToolbar2.home(self, event)
        self.onNavChange(None)

    def back(self, event):
        NavigationToolbar2.back(self, event)
        self.onNavChange(None)

    def forward(self, event):
        NavigationToolbar2.forward(self, event)
        self.onNavChange(None)

    def drag_pan(self, event):
        NavigationToolbar2.drag_pan(self, event)
        self.onNavChange(None)

    def release_zoom(self, event):
        NavigationToolbar2.release_zoom(self, event)
        self.onNavChange(None)

    def on_check_auto_f(self, event):
        self.settings.autoF = event.Checked()
        self.panel.redraw_plot()

    def on_check_auto_l(self, event):
        self.settings.autoL = event.Checked()
        self.panel.redraw_plot()

    def on_check_auto_t(self, event):
        self.settings.autoT = event.Checked()
        self.panel.redraw_plot()

    def on_check_update(self, event):
        self.settings.liveUpdate = event.Checked()

    def on_check_grid(self, event):
        grid = event.Checked()
        self.panel.set_grid(grid)

    def on_check_peak(self, event):
        peak = event.Checked()
        self.settings.annotate = peak
        self.panel.redraw_plot()

    def on_check_fade(self, event):
        fade = event.Checked()
        self.settings.fadeScans = fade
        self.panel.redraw_plot()

    def on_check_wire(self, event):
        wire = event.Checked()
        self.settings.wireframe = wire
        self.panel.create_plot()

    def on_check_avg(self, event):
        avg = event.Checked()
        self.settings.average = avg
        self.panel.redraw_plot()

    def on_colour(self, event):
        colourMap = event.GetString()
        self.settings.colourMap = colourMap
        self.plot.set_colourmap(colourMap)
        self.panel.redraw_plot()

    def add_spacer(self):
        sepId = wx.NewId()
        self.AddCheckTool(sepId, load_bitmap('spacer'))
        self.EnableTool(sepId, False)
        return sepId

    def set_plot(self, plot):
        self.plot = plot

    def set_type(self, display):
        for toolId in self.extraTools:
            self.DeleteTool(toolId)
        self.extraTools = []

        if not display == Display.PLOT:
            autoTId = wx.NewId()
            self.AddCheckTool(autoTId, load_bitmap('auto_t'),
                              shortHelp='Auto range time')
            self.ToggleTool(autoTId, self.settings.autoT)
            wx.EVT_TOOL(self, autoTId, self.on_check_auto_t)
            self.extraTools.append(autoTId)

        self.extraTools.append(self.add_spacer())

        if display == Display.PLOT:
            fadeId = wx.NewId()
            self.AddCheckTool(fadeId, load_bitmap('fade'),
                              shortHelp='Fade plots')
            wx.EVT_TOOL(self, fadeId, self.on_check_fade)
            self.ToggleTool(fadeId, self.settings.fadeScans)
            self.extraTools.append(fadeId)

            avgId = wx.NewId()
            self.AddCheckTool(avgId, load_bitmap('average'),
                              shortHelp='Average plots')
            wx.EVT_TOOL(self, avgId, self.on_check_avg)
            self.ToggleTool(avgId, self.settings.average)
            self.extraTools.append(avgId)
            self.extraTools.append(self.add_spacer())

        colours = get_colours()
        colourId = wx.NewId()
        control = wx.Choice(self, id=colourId, choices=colours)
        control.SetSelection(colours.index(self.settings.colourMap))
        self.AddControl(control)
        self.Bind(wx.EVT_CHOICE, self.on_colour, control)
        self.extraTools.append(colourId)

        if display == Display.SURFACE:
            self.extraTools.append(self.add_spacer())

            wireId = wx.NewId()
            self.AddCheckTool(wireId, load_bitmap('wireframe'),
                              shortHelp='Wireframe')
            wx.EVT_TOOL(self, wireId, self.on_check_wire)
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
        wx.EVT_TOOL(self, gridId, self.on_check_grid)

    def on_check_grid(self, event):
        grid = event.Checked()
        self.panel.set_grid(grid)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
