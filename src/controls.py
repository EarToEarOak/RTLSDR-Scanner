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
from wx.grid import PyGridCellRenderer


class Led(wx.PyControl):
    def __init__(self, parent, id=wx.ID_ANY, label=''):
        self.on = False

        wx.PyControl.__init__(self, parent=parent, id=id, size=wx.DefaultSize,
                              style=wx.NO_BORDER)

        self.SetLabel(label)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.__on_timer, self.timer)

        self.Bind(wx.EVT_PAINT, self.__on_paint)
        self.Bind(wx.EVT_SIZE, self.__on_size)

    def __on_paint(self, _event):
        dc = wx.BufferedPaintDC(self)
        self.__draw(dc)

    def __on_size(self, _event):
        self.Refresh()

    def __on_timer(self, _event):
        self.timer.Stop()
        self.on = False
        self.Refresh()

    def __draw(self, dc):
        colour = self.GetBackgroundColour()
        brush = wx.Brush(colour, wx.SOLID)
        dc.SetBackground(brush)
        dc.SetFont(self.GetFont())
        dc.Clear()

        label = self.GetLabel()
        _width, height = self.GetClientSize()
        ledRadius = height / 3
        _textWidth, textHeight = dc.GetTextExtent(label)

        gc = wx.GraphicsContext.Create(dc)
        gc.SetPen(wx.BLACK_PEN)

        if self.on:
            brush = wx.Brush(wx.GREEN, wx.SOLID)
            gc.SetBrush(brush)

        path = gc.CreatePath()
        path.AddCircle(height / 2, height / 2, ledRadius)
        path.CloseSubpath()

        gc.FillPath(path)
        gc.StrokePath(path)

        dc.DrawText(self.GetLabel(), height + 10, (height - textHeight) / 2)

    def pulse(self):

        self.on = True
        self.Refresh()
        self.timer.Start(250)


class CellRenderer(PyGridCellRenderer):
    def __init__(self):
        PyGridCellRenderer.__init__(self)

    def Draw(self, grid, attr, dc, rect, row, col, _isSelected):
        dc.SetBrush(wx.Brush(attr.GetBackgroundColour()))
        dc.DrawRectangleRect(rect)
        if grid.GetCellValue(row, col) == "1":
            dc.SetBrush(wx.Brush(attr.GetTextColour()))
            dc.DrawCircle(rect.x + (rect.width / 2),
                          rect.y + (rect.height / 2),
                          rect.height / 4)


# Based on http://wiki.wxpython.org/wxGrid%20ToolTips
class GridToolTips(object):
    def __init__(self, grid, toolTips):
        self.lastPos = (None, None)
        self.grid = grid
        self.toolTips = toolTips

        grid.GetGridWindow().Bind(wx.EVT_MOTION, self.__on_motion)

    def __on_motion(self, event):
        x, y = self.grid.CalcUnscrolledPosition(event.GetPosition())
        row = self.grid.YToRow(y)
        col = self.grid.XToCol(x)

        if (row, col) != self.lastPos:
            if row >= 0 and col >= 0:
                self.lastPos = (row, col)
                if (row, col) in self.toolTips:
                    toolTip = self.toolTips[(row, col)]
                else:
                    toolTip = ''
                self.grid.GetGridWindow().SetToolTipString(toolTip)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
