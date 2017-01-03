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

from collections import OrderedDict

import wx
from wx.grid import PyGridCellRenderer


class MultiButton(wx.PyControl):
    PADDING = 5
    ARROW_SIZE = 6

    def __init__(self, parent, options, tips=None, selected=0):
        wx.PyControl.__init__(self, parent=parent, size=wx.DefaultSize,
                              style=wx.NO_BORDER)
        self.options = options
        self.tips = tips
        self.pressed = False
        self.selected = selected
        self.isOverArrow = False

        self.menu = wx.Menu()
        for option in options:
            item = self.menu.Append(wx.ID_ANY, option)
            self.Bind(wx.EVT_MENU, self.__on_menu, item)

        self.Bind(wx.EVT_PAINT, self.__on_paint)
        self.Bind(wx.EVT_SIZE, self.__on_size)
        self.Bind(wx.EVT_LEFT_DOWN, self.__on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.__on_left_up)
        self.Bind(wx.EVT_MOTION, self.__on_motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.__on_leave)
        self.Bind(wx.EVT_CONTEXT_MENU, self.__on_context)

    def __on_paint(self, _event):
        dc = wx.GCDC(wx.PaintDC(self))
        self.__draw(dc)

    def __on_size(self, _event):
        self.Refresh()

    def __on_left_down(self, event):
        if not self.__is_over_arrow(event):
            self.pressed = True
            self.Refresh()

    def __on_left_up(self, event):
        if self.__is_over_arrow(event):
            self.__show_menu()
        else:
            self.pressed = False
            event = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED,
                                    self.GetId())
            event.SetEventObject(self)
            event.SetInt(self.selected)
            event.SetString(self.GetLabel())
            self.Refresh()
            self.GetEventHandler().ProcessEvent(event)

    def __on_motion(self, event):
        if self.isOverArrow != self.__is_over_arrow(event):
            self.isOverArrow = self.__is_over_arrow(event)
            self.Refresh()

    def __on_leave(self, _event):
        self.isOverArrow = False
        self.Refresh()

    def __on_menu(self, event):
        item = self.menu.FindItemById(event.Id)
        label = item.GetLabel()
        self.selected = self.options.index(label)
        self.__set_text()

    def __on_context(self, _event):
        self.__show_menu()

    def __show_menu(self):
        self.PopupMenu(self.menu)

    def __set_text(self):
        self.SetLabel(self.options[self.selected])
        if self.tips is not None:
            self.SetToolTipString(self.tips[self.selected])
        self.Refresh()

    def __is_over_arrow(self, event):
        x = event.GetPosition()[0]
        y = event.GetPosition()[1]
        width = event.GetEventObject().GetSize()[0]
        height = event.GetEventObject().GetSize()[1]

        top = 0
        bottom = height
        right = width - self.PADDING
        left = right - self.ARROW_SIZE - self.PADDING * 3

        if (right >= x >= left) and (bottom >= y >= top):
            return True
        return False

    def __draw(self, dc):
        renderer = wx.RendererNative.Get()
        rect = self.GetClientRect()
        rect.Left += self.PADDING
        rect.Right -= self.PADDING * 2
        if self.pressed:
            flags = wx.CONTROL_PRESSED
        else:
            flags = 0
        renderer.DrawPushButton(self, dc, rect, flags)

        dc.SetFont(self.GetFont())

        if self.IsEnabled():
            colour = self.GetForegroundColour()
        else:
            colour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
        if not self.isOverArrow:
            brush = wx.Brush(colour, wx.SOLID)
            dc.SetBrush(brush)
        pen = wx.Pen(colour)
        dc.SetPen(pen)
        dc.SetTextForeground(colour)

        label = self.GetLabel()
        _textWidth, textHeight = dc.GetTextExtent(label)

        dc.DrawText(self.GetLabel(),
                    self.PADDING * 2,
                    (rect.height - textHeight) / 2)

        top = (rect.height / 2) - (self.ARROW_SIZE / 4)
        bottom = top + self.ARROW_SIZE / 2
        right = rect.width - self.PADDING
        left = right - self.ARROW_SIZE
        dc.DrawPolygon([(right, top),
                        (left, top),
                        (left + self.ARROW_SIZE / 2, bottom)])
        left = right - (self.ARROW_SIZE * 2)
        top = rect.height / 4
        bottom = rect.height * 3 / 4
        dc.DrawLine(left, top, left, bottom)

    def DoGetBestSize(self):
        label = max(self.options, key=len)
        font = self.GetFont()
        dc = wx.ClientDC(self)
        dc.SetFont(font)
        textWidth, textHeight = dc.GetTextExtent(label)
        width = textWidth + self.ARROW_SIZE * 3 + self.PADDING * 6
        height = textHeight + self.PADDING * 2

        return wx.Size(width, height)

    def Enable(self, enabled):
        self.Enabled = enabled
        self.Refresh()

    def SetSelected(self, selected):
        self.selected = selected
        self.__set_text()

    def GetSelected(self):
        return self.selected


class Led(wx.PyControl):
    PULSE_TIME = 250

    def __init__(self, parent, id=wx.ID_ANY, label=''):
        self.lit = False
        self.colour = wx.GREEN

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
        self.lit = False
        self.Refresh()

    def __draw(self, dc):
        colour = self.GetBackgroundColour()
        brush = wx.Brush(colour, wx.SOLID)
        dc.SetBackground(brush)
        dc.SetFont(self.GetFont())
        attr = self.GetClassDefaultAttributes()
        dc.SetTextForeground(attr.colFg)
        dc.Clear()

        label = self.GetLabel()
        _width, height = self.GetClientSize()
        ledRadius = height / 3
        _textWidth, textHeight = dc.GetTextExtent(label)

        gc = wx.GraphicsContext.Create(dc)
        gc.SetPen(wx.Pen(attr.colFg))

        if self.lit:
            brush = wx.Brush(self.colour, wx.SOLID)
            gc.SetBrush(brush)

        path = gc.CreatePath()
        path.AddCircle(height / 2, height / 2, ledRadius)
        path.CloseSubpath()

        gc.FillPath(path)
        gc.StrokePath(path)

        dc.DrawText(label, height + 10, (height - textHeight) / 2)

    def on(self, colour=wx.GREEN):
        self.timer.Stop()
        self.lit = True
        self.colour = colour
        self.Refresh()

    def pulse(self, colour=wx.GREEN):
        self.lit = True
        self.colour = colour
        self.Refresh()
        self.timer.Start(self.PULSE_TIME)


class SatLevel(wx.PyControl):
    BAR_WIDTH = 10
    BAR_HEIGHT = 75
    PADDING = 5

    def __init__(self, parent, id=wx.ID_ANY, barCount=16):
        wx.PyControl.__init__(self, parent=parent, id=id, size=wx.DefaultSize,
                              style=wx.NO_BORDER)

        self.barCount = barCount
        self.sats = None

        self.Bind(wx.EVT_ERASE_BACKGROUND, self.__on_erase)
        self.Bind(wx.EVT_PAINT, self.__on_paint)

    def __on_erase(self, _event):
        pass

    def __on_paint(self, _event):
        dc = wx.BufferedPaintDC(self)
        self.__draw(dc)

    def __draw(self, dc):
        colour = self.GetBackgroundColour()
        brush = wx.Brush(colour, wx.SOLID)
        dc.SetBackground(brush)
        dc.SetFont(self.GetFont())
        attr = self.GetClassDefaultAttributes()
        dc.SetTextForeground(attr.colFg)
        dc.Clear()

        font = self.GetFont()
        font.SetPointSize(self.BAR_WIDTH)
        dc.SetFont(font)

        width, height = self.GetClientSize()
        widthTextFull, _height = dc.GetTextExtent('###')
        heightBar = height - widthTextFull - (self.PADDING * 2.0)
        widthBar = width / (self.barCount * 2.0)

        gc = wx.GraphicsContext.Create(dc)
        gc.SetPen(wx.GREY_PEN)
        gc.SetBrush(wx.BLUE_BRUSH)

        for i in range(self.barCount):
            x = self.PADDING + (widthBar * i * 2.0)

            if self.sats is not None and i < len(self.sats):
                sat = self.sats.items()[i]
                prn = sat[0]
                level = sat[1][0]
                used = sat[1][1]
                gc.SetBrush(wx.BLUE_BRUSH)
                if level is not None:
                    if used:
                        gc.SetBrush(wx.GREEN_BRUSH)
                    heightLevel = (level / 99.0) * heightBar
                else:
                    gc.SetBrush(wx.Brush(wx.BLUE, wx.CROSSDIAG_HATCH))
                    heightLevel = heightBar

                path = gc.CreatePath()
                path.AddRectangle(x,
                                  heightBar - heightLevel + self.PADDING,
                                  widthBar,
                                  heightLevel)
                gc.FillPath(path)
                text = '{:3d}'.format(prn)
            else:
                text = '  |'

            widthText, heightText = dc.GetTextExtent(text)
            dc.DrawRotatedText(text,
                               x + widthBar / 2 - heightText / 2,
                               height - widthText + self.PADDING * 2,
                               90)

            path = gc.CreatePath()
            path.AddRectangle(x,
                              self.PADDING,
                              widthBar,
                              heightBar)
            gc.StrokePath(path)

    def DoGetBestSize(self):
        font = self.GetFont()
        font.SetPointSize(self.BAR_WIDTH)
        dc = wx.ClientDC(self)
        dc.SetFont(font)
        widthText, heightText = dc.GetTextExtent('###')

        height = widthText + self.BAR_HEIGHT + self.PADDING * 2
        barWidth = max(heightText, self.BAR_WIDTH + self.PADDING)
        width = (barWidth + self.PADDING) * self.barCount

        return wx.Size(width, height)

    def set_sats(self, sats):
        self.sats = OrderedDict(sorted(sats.items()))
        self.Refresh()

    def clear_sats(self):
        self.sats = None
        self.Refresh()


class TickCellRenderer(PyGridCellRenderer):
    SIZE = 5
    PADDING = 3

    def __init__(self):
        PyGridCellRenderer.__init__(self)

    def GetBestSize(self, _grid, _attr, _dc, _row, _col):
        return wx.Size(self.SIZE + self.PADDING, self.SIZE + self.PADDING)

    def Draw(self, grid, attr, dc, rect, row, col, _isSelected):
        dc.SetBrush(wx.Brush(attr.GetBackgroundColour()))
        dc.DrawRectangleRect(rect)

        gc = wx.GraphicsContext.Create(dc)
        gc.SetPen(wx.Pen(attr.GetTextColour()))

        pad = self.PADDING
        x = rect.x + pad
        y = rect.y + pad
        w = rect.height - pad * 2.0

        if grid.GetCellValue(row, col) == "1":
            pathTick = gc.CreatePath()
            pathTick.MoveToPoint(1, 3)
            pathTick.AddLineToPoint(2, 4)
            pathTick.AddLineToPoint(4, 1)
            scale = w / 5.0
            transform = gc.CreateMatrix()
            transform.Set(a=scale, d=scale, tx=x, ty=y)
            pathTick.Transform(transform)
            gc.StrokePath(pathTick)


class CheckBoxCellRenderer(PyGridCellRenderer):
    SIZE = 8

    def __init__(self, parent, showBox=True):
        self.parent = parent
        self.showBox = showBox
        self.enabled = True

        PyGridCellRenderer.__init__(self)

    def GetBestSize(self, _grid, _attr, _dc, _row, _col):
        return wx.Size(self.SIZE * 2, self.SIZE)

    def Draw(self, grid, _attr, dc, rect, row, col, _isSelected):
        flags = 0
        if grid.GetCellValue(row, col) == "1":
            flags = wx.CONTROL_CHECKED
        if not self.enabled:
            flags |= wx.CONTROL_DISABLED

        dc.DrawRectangleRect(rect)
        renderer = wx.RendererNative.Get()
        renderer.DrawCheckBox(self.parent, dc, rect, flags)

    def Enable(self, enabled):
        self.enabled = enabled


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
            else:
                toolTip = ''

            self.grid.GetGridWindow().SetToolTipString(toolTip)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
