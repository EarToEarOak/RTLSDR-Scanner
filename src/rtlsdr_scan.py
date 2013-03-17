#! /usr/bin/env python

#
# rtlsdr_scan
#
# http://eartoearoak.com/software/rtlsdr-scanner
#
# Copyright 2012, 2013 Al Brown
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
matplotlib.interactive(True)
matplotlib.use('WXAgg')
from matplotlib.backends.backend_wxagg import \
    FigureCanvasWxAgg as FigureCanvas, \
    NavigationToolbar2WxAgg
from matplotlib.backends.backend_wx import _load_bitmap
import argparse
import cPickle
import itertools
import math
import numpy
import os.path
import rtlsdr
import threading
import wx
import wx.lib.masked as masked
import wx.lib.mixins.listctrl as listmix
import wx.grid as grid


F_MIN = 0
F_MAX = 9999
GAIN = 0
SAMPLE_RATE = 2e6
BANDWIDTH = 500e3
NFFT = 1024

DWELL = ["10 ms", 0.01,
         "25 ms", 0.025,
         "50 ms", 0.05,
         "100 ms", 0.1,
         "200 ms", 0.2,
         "500 ms", 0.5,
         "1 s", 1,
         "2 s", 2,
         "5 s", 5]

THREAD_STATUS_STARTING = 0
THREAD_STATUS_SCAN = 1
THREAD_STATUS_DATA = 2
THREAD_STATUS_FINISHED = 3
THREAD_STATUS_STOPPED = 4
THREAD_STATUS_ERROR = 5
THREAD_STATUS_PROCESSED = 6

WARN_SCAN = 0
WARN_OPEN = 1
WARN_EXIT = 2

CAL_START = 0
CAL_DONE = 1
CAL_OK = 2
CAL_CANCEL = 3

FILE_RFS = "RTLSDR frequency scan (*.rfs)|*.rfs"
FILE_CSV = "CSV table (*.csv)|*.csv"
FILE_HEADER = "RTLSDR Scanner"
FILE_VERSION = 1

WINDOW = matplotlib.numpy.hamming(NFFT)

EVT_THREAD_STATUS = wx.NewId()


class Device():
    def __init__(self):
        self.index = None
        self.name = None
        self.calibration = None
        self.lo = None
        self.offset = 250e3

class Settings():
    def __init__(self):
        self.cfg = None
        self.start = None
        self.stop = None
        self.calFreq = None
        self.yAuto = True
        self.yMax = 1
        self.yMin = 0
        self.devices = []
        self.index = None

        self.load()

    def load(self):
        self.cfg = wx.Config('rtlsdr-scanner')
        self.start = self.cfg.ReadInt('start', 87)
        self.stop = self.cfg.ReadInt('stop', 108)
        self.calFreq = self.cfg.ReadFloat('calFreq', 1575.42)
        self.index = self.cfg.ReadInt('index', 0)
        self.cfg.SetPath("/Devices")
        group = self.cfg.GetFirstGroup()
        while group[0]:
            self.cfg.SetPath("/Devices/" + group[1])
            device = Device()
            device.name = group[1]
            device.calibration = self.cfg.ReadFloat('calibration', 0)
            device.lo = self.cfg.ReadFloat('lo', 0)
            device.offset = self.cfg.ReadFloat('offset', 250e3)
            self.devices.append(device)
            self.cfg.SetPath("/Devices")
            group = self.cfg.GetNextGroup(group[2])


    def save(self):
        self.cfg.SetPath("/")
        self.cfg.WriteInt('start', self.start)
        self.cfg.WriteInt('stop', self.stop)
        self.cfg.WriteFloat('calFreq', self.calFreq)
        self.cfg.WriteInt('index', self.index)
        if self.devices:
            for device in self.devices:
                self.cfg.SetPath("/Devices/" + format_device_name(device.name))
                self.cfg.WriteFloat('lo', device.lo)
                self.cfg.WriteFloat('calibration', device.calibration)
                self.cfg.WriteFloat('offset', device.offset)

class Status():
    def __init__(self, status, freq, data):
        self.status = status
        self.freq = freq
        self.data = data

    def get_status(self):
        return self.status

    def get_freq(self):
        return self.freq

    def get_data(self):
        return self.data


class EventThreadStatus(wx.PyEvent):
    def __init__(self, status, freq, data):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_THREAD_STATUS)
        self.data = Status(status, freq, data)


class ThreadScan(threading.Thread):
    def __init__(self, notify, settings, devices, samples, isCal):
        threading.Thread.__init__(self)
        self.notify = notify
        self.index = settings.index
        self.fstart = settings.start * 1e6
        self.fstop = settings.stop * 1e6
        self.samples = samples
        self.isCal = isCal
        self.lo = devices[self.index].lo * 1e6
        self.offset = devices[self.index].offset
        self.cancel = False
        wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_STARTING,
                                                    None, None))
        self.start()

    def run(self):
        sdr = self.rtl_setup()
        if sdr is None:
            return
        freq = self.fstart - self.offset

        while freq <= self.fstop + self.offset:
            if self.cancel:
                wx.PostEvent(self.notify,
                             EventThreadStatus(THREAD_STATUS_STOPPED,
                                               None, None))
                sdr.close()
                return
            try:
                progress = ((freq - self.fstart + self.offset) / 
                             (self.fstop - self.fstart + BANDWIDTH)) * 100
                wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_SCAN,
                                                            None, progress))
                scan = self.scan(sdr, freq)
                wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_DATA,
                                                            freq, scan))
            except (IOError, WindowsError):
                if sdr is not None:
                    sdr.close()
                sdr = self.rtl_setup()
            except (TypeError, AttributeError) as error:
                if self.notify:
                    wx.PostEvent(self.notify,
                             EventThreadStatus(THREAD_STATUS_ERROR,
                                               None, error.message))
                return

            freq += BANDWIDTH / 2

        sdr.close()
        wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_FINISHED,
                                                    None, self.isCal))

    def abort(self):
        self.cancel = True

    def rtl_setup(self):
        sdr = None
        try:
            sdr = rtlsdr.RtlSdr(self.index)
            sdr.set_sample_rate(SAMPLE_RATE)
            sdr.set_gain(GAIN)
        except IOError as error:
            wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_ERROR,
                                                        None, error.message))

        return sdr

    def scan(self, sdr, freq):
        sdr.set_center_freq(freq + self.lo)
        capture = sdr.read_samples(self.samples)

        return capture


class ThreadProcess(threading.Thread):
    def __init__(self, notify, freq, data, settings, devices):
        threading.Thread.__init__(self)
        self.notify = notify
        self.freq = freq
        self.data = data
        self.cal = devices[settings.index].calibration

        self.start()

    def run(self):
        scan = {}
        powers, freqs = matplotlib.mlab.psd(self.data,
                         NFFT=NFFT,
                         Fs=SAMPLE_RATE / 1e6,
                         window=WINDOW)
        for pwr, freq in itertools.izip(freqs, powers):
            xr = pwr + (self.freq / 1e6)
            xr = xr + (xr * self.cal / 1e6)
            xr = int((xr * 5e4) + 0.5) / 5e4
            scan[xr] = freq
        wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_PROCESSED,
                                                            self.freq, scan))

class DropTarget(wx.FileDropTarget):
    def __init__(self, window):
        wx.FileDropTarget.__init__(self)
        self.window = window

    def OnDropFiles(self, _xPos, _yPos, filenames):
        filename = filenames[0]
        if os.path.splitext(filename)[1].lower() == ".rfs":
            self.window.dirname, self.window.filename = os.path.split(filename)
            self.window.open()

class DeviceList(wx.ListCtrl, listmix.TextEditMixin):
    def __init__(self, parent, ID=wx.ID_ANY, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0):
        wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
        listmix.TextEditMixin.__init__(self)
        
class CellRenderer(grid.PyGridCellRenderer):
    def __init__(self):
        grid.PyGridCellRenderer.__init__(self)

    def Draw(self, grid, attr, dc, rect, row, col, _isSelected):
        dc.SetBrush(wx.Brush(attr.GetBackgroundColour()))
        dc.DrawRectangleRect(rect)
        if grid.GetCellValue(row, col) == "1":
            dc.SetBrush(wx.Brush(attr.GetTextColour()))
            dc.DrawCircle(rect.x + (rect.width / 2), rect.y + (rect.height / 2),
                          rect.height / 4)

class DialogAutoCal(wx.Dialog):
    def __init__(self, parent, freq, callback):
        self.callback = callback
        self.cal = 0

        wx.Dialog.__init__(self, parent=parent, title="Auto Calibration",
                           style=wx.CAPTION)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        title = wx.StaticText(self, label="Calibrate to a known stable signal")
        font = title.GetFont()
        font.SetPointSize(font.GetPointSize() + 2)
        title.SetFont(font)
        text = wx.StaticText(self, label="Frequency (MHz)")
        self.textFreq = masked.NumCtrl(self, value=freq, fractionWidth=3,
                                        min=F_MIN, max=F_MAX)

        self.buttonCal = wx.Button(self, label="Calibrate")
        self.buttonCal.Bind(wx.EVT_BUTTON, self.on_cal)
        self.textResult = wx.StaticText(self)

        self.buttonOk = wx.Button(self, wx.ID_OK, 'OK')
        self.buttonOk.Disable()
        self.buttonCancel = wx.Button(self, wx.ID_CANCEL, 'Cancel')

        self.buttonOk.Bind(wx.EVT_BUTTON, self.on_close)
        self.buttonCancel.Bind(wx.EVT_BUTTON, self.on_close)

        buttons = wx.StdDialogButtonSizer()
        buttons.AddButton(self.buttonOk)
        buttons.AddButton(self.buttonCancel)
        buttons.Realize()

        sizer = wx.GridBagSizer(10, 10)
        sizer.Add(title, pos=(0, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        sizer.Add(text, pos=(1, 0), flag=wx.ALL | wx.EXPAND, border=10)
        sizer.Add(self.textFreq, pos=(1, 1), flag=wx.ALL | wx.EXPAND,
                  border=5)
        sizer.Add(self.buttonCal, pos=(2, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL | wx.EXPAND, border=10)
        sizer.Add(self.textResult, pos=(3, 0), span=(1, 2),
                  flag=wx.ALL | wx.EXPAND, border=10)
        sizer.Add(buttons, pos=(4, 0), span=(1, 2),
                  flag=wx.ALL | wx.EXPAND, border=10)

        self.SetSizerAndFit(sizer)

    def on_cal(self, _event):
        self.buttonCal.Disable()
        self.buttonOk.Disable()
        self.buttonCancel.Disable()
        self.textFreq.Disable()
        self.textResult.SetLabel("Calibrating...")
        self.callback(CAL_START)

    def on_close(self, event):
        status = [CAL_CANCEL, CAL_OK][event.GetId() == wx.ID_OK]
        self.callback(status)
        self.EndModal(event.GetId())
        return

    def enable_controls(self):
        self.buttonCal.Enable(True)
        self.buttonOk.Enable(True)
        self.buttonCancel.Enable(True)
        self.textFreq.Enable()

    def set_cal(self, cal):
        self.cal = cal
        self.enable_controls()
        self.textResult.SetLabel("Correction (ppm): {0:.3f}".format(cal))

    def get_cal(self):
        return self.cal

    def reset_cal(self):
        self.set_cal(self.cal)

    def get_freq(self):
        return self.textFreq.GetValue()

class DialogOffset(wx.Dialog):
    def __init__(self, parent, index, offset):
        self.index = index
        self.offset = offset
        self.band1 = None
        self.band2 = None
        
        wx.Dialog.__init__(self, parent=parent, title="Scan Offset")
        
        figure = matplotlib.figure.Figure(facecolor='white')
        self.axes = figure.add_subplot(111)
        self.canvas = FigureCanvas(self, -1, figure)
        
        textHelp = wx.StaticText(self, label="Remove the aerial and press refresh, adjust the offset so the shaded areas overlay the flattest parts of the plot.")
        
        textFreq = wx.StaticText(self, label="Test frequency (MHz)")
        self.spinFreq = wx.SpinCtrl(self)
        self.spinFreq.SetRange(F_MIN, F_MAX)
        self.spinFreq.SetValue(200)
        
        refresh = wx.Button(self, wx.ID_ANY, 'Refresh')
        self.Bind(wx.EVT_BUTTON, self.on_refresh, refresh)
        
        textOffset = wx.StaticText(self, label="Offset (kHz)")
        self.spinOffset = wx.SpinCtrl(self)
        self.spinOffset.SetRange(0, (SAMPLE_RATE - BANDWIDTH) / 1e3)
        self.spinOffset.SetValue(offset)
        self.Bind(wx.EVT_SPINCTRL, self.on_spin, self.spinOffset)
        
        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.on_ok, buttonOk)
        
        boxSizer1 = wx.BoxSizer(wx.HORIZONTAL)
        boxSizer1.Add(textFreq, border=5)
        boxSizer1.Add(self.spinFreq, border=5)
        
        boxSizer2 = wx.BoxSizer(wx.HORIZONTAL)
        boxSizer2.Add(textOffset, border=5)
        boxSizer2.Add(self.spinOffset, border=5)
        
        gridSizer = wx.GridBagSizer(5, 5)
        gridSizer.Add(self.canvas, pos=(0, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL)
        gridSizer.Add(textHelp, pos=(1, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL)
        gridSizer.Add(boxSizer1, pos=(2, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL)
        gridSizer.Add(refresh, pos=(3, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL)
        gridSizer.Add(boxSizer2, pos=(4, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL)
        gridSizer.Add(sizerButtons, pos=(5, 1), span=(1, 1),
                  flag=wx.ALIGN_RIGHT | wx.ALL)
        
        self.SetSizerAndFit(gridSizer)
        self.draw_limits()
        
    def on_ok(self, _event):

        self.EndModal(wx.ID_OK)
        
    def on_refresh(self, _event):
        plot = []
        sdr = rtlsdr.RtlSdr(int(self.index))
        sdr.set_sample_rate(SAMPLE_RATE)
        sdr.set_center_freq(self.spinFreq.GetValue() * 1e6)
        sdr.set_gain(GAIN)
        capture = sdr.read_samples(2 ** 18)
        powers, freqs = matplotlib.mlab.psd(capture,
                         NFFT=NFFT,
                         Fs=SAMPLE_RATE / 1e6,
                         window=WINDOW)
        
        for x, y in itertools.izip(freqs, powers):
            x = x * SAMPLE_RATE / 2e6
            plot.append((x, y))
        plot.sort()   
        x, y = numpy.transpose(plot)
        
        self.axes.clear()
        self.band1 = None
        self.band2 = None
        self.axes.set_xlabel("Frequency (MHz)")
        self.axes.set_ylabel('Level (dB)')
        self.axes.set_yscale('log')
        self.axes.plot(x, y, linewidth=0.4)
        self.draw_limits()
        
    def on_spin(self, _event):
        self.offset = self.spinOffset.GetValue();
        self.draw_limits()
        
    def draw_limits(self):
        limit1 = self.offset / 1e3
        limit2 = limit1 + BANDWIDTH / 1e6
        if(self.band1 is not None):
            self.band1.remove()
        if(self.band2 is not None):
            self.band2.remove()
        self.band1 = self.axes.axvspan(limit1, limit2, color='g', alpha=0.25)
        self.band2 = self.axes.axvspan(-limit1, -limit2, color='g', alpha=0.25)
        self.canvas.draw()
        
    def get_offset(self):
        return self.offset

    
class DialogPrefs(wx.Dialog):
    def __init__(self, parent, devices, settings):
        self.settings = settings
        self.index = 0

        wx.Dialog.__init__(self, parent=parent, title="Preferences")

        title = wx.StaticText(self, label="Select a device")
        font = title.GetFont()
        font.SetPointSize(font.GetPointSize() + 2)
        title.SetFont(font)

        self.devices = devices
        self.gridDev = grid.Grid(self)
        self.gridDev.CreateGrid(len(self.devices), 6)
        self.gridDev.SetRowLabelSize(0)
        self.gridDev.SetColLabelValue(0, "Select")
        self.gridDev.SetColLabelValue(1, "Device")
        self.gridDev.SetColLabelValue(2, "Index")
        self.gridDev.SetColLabelValue(3, "Calibration\n(ppm)")
        self.gridDev.SetColLabelValue(4, "LO\n(MHz)")
        self.gridDev.SetColLabelValue(5, "Band Offset\n(kHz)")
        self.gridDev.SetColFormatFloat(3, -1, 3)
        self.gridDev.SetColFormatFloat(4, -1, 3)
        self.gridDev.SetColFormatFloat(5, -1, 0)

        attributes = grid.GridCellAttr()
        attributes.SetBackgroundColour(self.gridDev.GetLabelBackgroundColour())
        self.gridDev.SetColAttr(1, attributes)
        self.gridDev.SetColAttr(2, attributes)

        i = 0
        for device in self.devices:
            self.gridDev.SetReadOnly(i, 0, True)
            self.gridDev.SetReadOnly(i, 1, True)
            self.gridDev.SetReadOnly(i, 2, True)
            self.gridDev.SetCellRenderer(i, 0, CellRenderer())
            self.gridDev.SetCellEditor(i, 3, grid.GridCellFloatEditor(-1, 3))
            self.gridDev.SetCellEditor(i, 4, grid.GridCellFloatEditor(-1, 3))
            self.gridDev.SetCellValue(i, 1, device.name)
            self.gridDev.SetCellValue(i, 2, str(i))
            self.gridDev.SetCellValue(i, 3, str(device.calibration))
            self.gridDev.SetCellValue(i, 4, str(device.lo))
            self.gridDev.SetCellValue(i, 5, str(device.offset / 1e3))
            i += 1

        if settings.index > len(self.devices):
            settings.index = len(self.devices)
        self.select_row(settings.index)

        self.gridDev.AutoSize()

        self.Bind(grid.EVT_GRID_CELL_LEFT_CLICK, self.on_click)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.on_ok, buttonOk)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(title, 0, wx.ALL | wx.EXPAND, 10)
        vbox.Add(self.gridDev, 0, wx.ALL | wx.EXPAND, 10)
        vbox.Add(sizerButtons, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizerAndFit(vbox)

    def on_click(self, event):
        col = event.GetCol()
        index = event.GetRow()
        if(col == 0):
            self.index = event.GetRow()
            self.select_row(index)
        elif(col == 5):
            dlg = DialogOffset(self, index, float(self.gridDev.GetCellValue(index, 5)))
            if dlg.ShowModal() == wx.ID_OK:
                self.gridDev.SetCellValue(index, 5, str(dlg.get_offset()))
            dlg.Destroy()
        event.Skip()

    def on_ok(self, _event):
        for i in range(0, self.gridDev.GetNumberRows()):
            self.devices[i].calibration = float(self.gridDev.GetCellValue(i, 3))
            self.devices[i].lo = float(self.gridDev.GetCellValue(i, 4))
            self.devices[i].offset = float(self.gridDev.GetCellValue(i, 5)) * 1e3

        self.EndModal(wx.ID_OK)

    def select_row(self, index):
        for i in range(0, self.gridDev.GetNumberRows()):
            tick = "0"
            if i == index:
                tick = "1"
            self.gridDev.SetCellValue(i, 0, tick)

    def get_index(self):
        return self.index

    def get_devices(self):
        return self.devices


class DialogSaveWarn(wx.Dialog):
    def __init__(self, parent, warnType):
        self.code = -1

        wx.Dialog.__init__(self, parent=parent, title="Warning",
                           style=wx.ICON_EXCLAMATION)

        prompt = ["scanning again", "opening a file", "exiting"][warnType]
        text = wx.StaticText(self, label="Save plot before {0}?".format(prompt))
        icon = wx.StaticBitmap(self, wx.ID_ANY,
                               wx.ArtProvider.GetBitmap(wx.ART_INFORMATION,
                                                        wx.ART_MESSAGE_BOX))

        tbox = wx.BoxSizer(wx.HORIZONTAL)
        tbox.Add(text)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(icon, 0, wx.ALL, 5)
        hbox.Add(tbox, 0, wx.ALL, 5)

        buttonYes = wx.Button(self, wx.ID_YES, 'Yes')
        buttonNo = wx.Button(self, wx.ID_NO, 'No')
        buttonCancel = wx.Button(self, wx.ID_CANCEL, 'Cancel')

        buttonYes.Bind(wx.EVT_BUTTON, self.on_close)
        buttonNo.Bind(wx.EVT_BUTTON, self.on_close)

        buttons = wx.StdDialogButtonSizer()
        buttons.AddButton(buttonYes)
        buttons.AddButton(buttonNo)
        buttons.AddButton(buttonCancel)
        buttons.Realize()

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(hbox, 1, wx.ALL | wx.EXPAND, 10)
        vbox.Add(buttons, 1, wx.ALL | wx.EXPAND, 10)

        self.SetSizerAndFit(vbox)

    def on_close(self, event):
        self.EndModal(event.GetId())
        return

    def get_code(self):
        return self.code

class DialogRange(wx.Dialog):
    def __init__(self, parent, main):
        self.main = main
        
        wx.Dialog.__init__(self, parent=parent, title="Plot Range")

        self.checkAuto = wx.CheckBox(self, wx.ID_ANY, "Auto Range")
        self.checkAuto.SetValue(self.main.settings.yAuto)
        self.Bind(wx.EVT_CHECKBOX, self.on_auto, self.checkAuto)

        textMax = wx.StaticText(self, label="Maximum (dB)")
        self.yMax = masked.NumCtrl(self, value=int(self.main.settings.yMax),
                                    fractionWidth=0, min= -100, max=20)
        textMin = wx.StaticText(self, label="Minimum (dB)")
        self.yMin = masked.NumCtrl(self, value=int(self.main.settings.yMin),
                                    fractionWidth=0, min= -100, max=20)
        self.set_enabled(not self.main.settings.yAuto)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.on_ok, buttonOk)


        sizer = wx.GridBagSizer(10, 10)
        sizer.Add(self.checkAuto, pos=(0, 0), span=(1, 1),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        sizer.Add(textMax, pos=(1, 0), span=(1, 1),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        sizer.Add(self.yMax, pos=(1, 1), span=(1, 1),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        sizer.Add(textMin, pos=(2, 0), span=(1, 1),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        sizer.Add(self.yMin, pos=(2, 1), span=(1, 1),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        sizer.Add(sizerButtons, pos=(3, 0), span=(1, 2),
                  flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        self.SetSizerAndFit(sizer)

    def on_auto(self, _event):
        self.set_enabled(not self.checkAuto.GetValue())

    def on_ok(self, _event):
        self.main.settings.yAuto = self.checkAuto.GetValue()
        self.main.settings.yMin = self.yMin.GetValue()
        self.main.settings.yMax = self.yMax.GetValue()
        self.EndModal(wx.ID_OK)

    def set_enabled(self, isEnabled):
        self.yMax.Enable(isEnabled)
        self.yMin.Enable(isEnabled)

class NavigationToolbar(NavigationToolbar2WxAgg):
    def __init__(self, canvas, main):
        self.main = main

        navId = wx.NewId()
        NavigationToolbar2WxAgg.__init__(self, canvas)
        self.AddSimpleTool(navId, _load_bitmap('subplots.png'),
                           'Range', 'Set plot range')
        wx.EVT_TOOL(self, navId, self.on_range)

    def on_range(self, _event):

        dlg = DialogRange(self, self.main)
        dlg.ShowModal()
        dlg.Destroy()
        self.canvas.draw()
        self.main.draw_plot()


class PanelGraph(wx.Panel):
    def __init__(self, parent, main):
        self.main = main

        wx.Panel.__init__(self, parent)

        self.figure = matplotlib.figure.Figure(facecolor='white')
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.toolbar = NavigationToolbar(self.canvas, self.main)
        self.toolbar.Realize()
        self.toolbar.DeleteToolByPos(1)
        self.toolbar.DeleteToolByPos(1)
        self.toolbar.DeleteToolByPos(4)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        vbox.Add(self.toolbar, 0, wx.EXPAND)

        self.SetSizer(vbox)
        vbox.Fit(self)

    def on_motion(self, event):
        if self.main.thread:
            return
        xpos = event.xdata
        ypos = event.ydata
        text = ""
        if xpos is not None:
            spectrum = self.main.spectrum
            if len(spectrum) > 0:
                xpos = min(spectrum.keys(), key=lambda freq: abs(freq - xpos))
                ypos = spectrum[xpos]
                text = "f = {0:.3f}MHz, p = {1:.2f}dB".format(xpos, ypos)

        self.main.status.SetStatusText(text, 1)

    def get_canvas(self):
        return self.canvas

    def get_axes(self):
        return self.axes

    def get_toolbar(self):
        return self.toolbar


class FrameMain(wx.Frame):
    def __init__(self, title):

        self.update = False
        self.grid = False

        self.thread = None

        self.dlgCal = None

        self.menuOpen = None
        self.menuSave = None
        self.menuExport = None
        self.menuStart = None
        self.menuStop = None
        self.menuPref = None
        self.menuCal = None

        self.panel = None
        self.graph = None
        self.canvas = None
        self.buttonStart = None
        self.buttonStop = None
        self.choiceDwell = None
        self.spinCtrlStart = None
        self.spinCtrlStop = None
        self.checkUpdate = None
        self.checkGrid = None

        self.filename = ""
        self.dirname = "."

        self.spectrum = {}
        self.isSaved = True

        self.settings = Settings()
        self.devices = self.get_devices()
        self.oldCal = 0

        displaySize = wx.DisplaySize()
        wx.Frame.__init__(self, None, title=title, size=(displaySize[0] / 1.5,
                                                         displaySize[1] / 2))

        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_CLOSE, self.on_exit)

        self.status = self.CreateStatusBar()
        self.status.SetFieldsCount(2)
        self.statusProgress = wx.Gauge(self.status, -1,
                                        style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.statusProgress.Hide()

        self.create_widgets()
        self.create_menu()
        self.set_controls(True)
        self.menuSave.Enable(False)
        self.menuExport.Enable(False)
        self.Show()

        size = self.panel.GetSize()
        size[1] += displaySize[1] / 4
        self.SetMinSize(size)

        thread_event_handler(self, EVT_THREAD_STATUS, self.on_thread_status)

        self.SetDropTarget(DropTarget(self))

    def create_widgets(self):
        panel = wx.Panel(self)

        self.panel = wx.Panel(panel)
        self.graph = PanelGraph(panel, self)

        self.buttonStart = wx.Button(self.panel, wx.ID_ANY, 'Start')
        self.buttonStop = wx.Button(self.panel, wx.ID_ANY, 'Stop')
        self.buttonStart.SetToolTip(wx.ToolTip('Start scan'))
        self.buttonStop.SetToolTip(wx.ToolTip('Stop scan'))
        self.Bind(wx.EVT_BUTTON, self.on_start, self.buttonStart)
        self.Bind(wx.EVT_BUTTON, self.on_stop, self.buttonStop)

        textRange = wx.StaticText(self.panel, label="Range (MHz)",
                                  style=wx.ALIGN_CENTER)
        textStart = wx.StaticText(self.panel, label="Start")
        textStop = wx.StaticText(self.panel, label="Stop")

        self.spinCtrlStart = wx.SpinCtrl(self.panel)
        self.spinCtrlStop = wx.SpinCtrl(self.panel)
        self.spinCtrlStart.SetToolTip(wx.ToolTip('Start frequency'))
        self.spinCtrlStop.SetToolTip(wx.ToolTip('Stop frequency'))
        self.spinCtrlStart.SetRange(F_MIN, F_MAX - 1)
        self.spinCtrlStop.SetRange(F_MIN + 1, F_MAX)
        self.set_range()
        self.Bind(wx.EVT_SPINCTRL, self.on_spin, self.spinCtrlStart)
        self.Bind(wx.EVT_SPINCTRL, self.on_spin, self.spinCtrlStop)

        textDwell = wx.StaticText(self.panel, label="Dwell")
        self.choiceDwell = wx.Choice(self.panel, choices=DWELL[::2])
        self.choiceDwell.SetToolTip(wx.ToolTip('Scan time per step'))
        self.choiceDwell.SetSelection(DWELL[1::2].index(0.1))

        self.checkUpdate = wx.CheckBox(self.panel, wx.ID_ANY,
                                        "Continuous update")
        self.checkUpdate.SetToolTip(wx.ToolTip('Very slow, not recommended'))
        self.checkUpdate.SetValue(self.update)
        self.Bind(wx.EVT_CHECKBOX, self.on_check_update, self.checkUpdate)

        self.checkGrid = wx.CheckBox(self.panel, wx.ID_ANY, "Grid")
        self.checkGrid.SetToolTip(wx.ToolTip('Draw grid'))
        self.checkGrid.SetValue(self.grid)
        self.Bind(wx.EVT_CHECKBOX, self.on_check_grid, self.checkGrid)

        grid = wx.GridBagSizer(5, 5)

        grid.Add(self.buttonStart, pos=(0, 0), span=(2, 1),
                 flag=wx.ALIGN_CENTER)
        grid.Add(self.buttonStop, pos=(0, 1), span=(2, 1),
                 flag=wx.ALIGN_CENTER)

        grid.Add((20, 1), pos=(0, 2))

        grid.Add(textRange, pos=(0, 3), span=(1, 4), flag=wx.ALIGN_CENTER)
        grid.Add(textStart, pos=(1, 3), flag=wx.ALIGN_CENTER)
        grid.Add(self.spinCtrlStart, pos=(1, 4))
        grid.Add(textStop, pos=(1, 5), flag=wx.ALIGN_CENTER)
        grid.Add(self.spinCtrlStop, pos=(1, 6))

        grid.Add((20, 1), pos=(0, 7))

        grid.Add(textDwell, pos=(0, 8), flag=wx.ALIGN_CENTER)
        grid.Add(self.choiceDwell, pos=(1, 8), flag=wx.ALIGN_CENTER)

        grid.Add((20, 1), pos=(0, 9))

        grid.Add(self.checkUpdate, pos=(0, 10))
        grid.Add(self.checkGrid, pos=(1, 10))

        self.panel.SetSizer(grid)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.graph, 1, wx.EXPAND)
        sizer.Add(self.panel, 0, wx.ALIGN_CENTER)
        panel.SetSizer(sizer)

    def create_menu(self):
        menuFile = wx.Menu()
        self.menuOpen = menuFile.Append(wx.ID_OPEN, "&Open...", "Open plot")
        self.menuSave = menuFile.Append(wx.ID_SAVE, "&Save As...",
                                          "Save plot")
        self.menuExport = menuFile.Append(wx.ID_ANY, "&Export...",
                                            "Export plot")
        menuExit = menuFile.Append(wx.ID_EXIT, "E&xit", "Exit the program")

        menuScan = wx.Menu()
        self.menuStart = menuScan.Append(wx.ID_ANY, "&Start", "Start scan")
        self.menuStop = menuScan.Append(wx.ID_ANY, "S&top", "Stop scan")

        menuView = wx.Menu()
        self.menuPref = menuView.Append(wx.ID_ANY, "&Preferences...",
                                   "Preferences")

        menuTools = wx.Menu()
        self.menuCal = menuTools.Append(wx.ID_ANY, "&Auto Calibration...",
                               "Automatically calibrate to a known frequency")

        menuHelp = wx.Menu()
        menuAbout = menuHelp.Append(wx.ID_ABOUT, "&About...",
                                            "Information about this program")

        menuBar = wx.MenuBar()
        menuBar.Append(menuFile, "&File")
        menuBar.Append(menuScan, "&Scan")
        menuBar.Append(menuView, "&View")
        menuBar.Append(menuTools, "&Tools")
        menuBar.Append(menuHelp, "&Help")
        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.on_open, self.menuOpen)
        self.Bind(wx.EVT_MENU, self.on_save, self.menuSave)
        self.Bind(wx.EVT_MENU, self.on_export, self.menuExport)
        self.Bind(wx.EVT_MENU, self.on_exit, menuExit)
        self.Bind(wx.EVT_MENU, self.on_start, self.menuStart)
        self.Bind(wx.EVT_MENU, self.on_stop, self.menuStop)
        self.Bind(wx.EVT_MENU, self.on_pref, self.menuPref)
        self.Bind(wx.EVT_MENU, self.on_cal, self.menuCal)
        self.Bind(wx.EVT_MENU, self.on_about, menuAbout)

    def on_open(self, _event):
        if self.save_warn(WARN_OPEN):
            return
        dlg = wx.FileDialog(self, "Open a scan", self.dirname, self.filename,
                            FILE_RFS, wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.open(dlg.GetDirectory(), dlg.GetFilename())
        dlg.Destroy()

    def on_save(self, _event):
        dlg = wx.FileDialog(self, "Save a scan", self.dirname,
                            self.filename + ".rfs", FILE_RFS,
                            wx.SAVE | wx.OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            self.status.SetStatusText("Saving", 0)
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()
            handle = open(os.path.join(self.dirname, self.filename), 'wb')
            cPickle.dump(FILE_HEADER, handle)
            cPickle.dump(FILE_VERSION, handle)
            cPickle.dump(self.settings.start, handle)
            cPickle.dump(self.settings.stop, handle)
            cPickle.dump(self.spectrum, handle)
            handle.close()
            self.isSaved = True
            self.status.SetStatusText("Finished", 0)
        dlg.Destroy()

    def on_export(self, _event):
        dlg = wx.FileDialog(self, "Export a scan", self.dirname,
                            self.filename + ".csv", FILE_CSV, wx.SAVE)
        if dlg.ShowModal() == wx.ID_OK:
            self.status.SetStatusText("Exporting", 0)
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()
            handle = open(os.path.join(self.dirname, self.filename), 'wb')
            handle.write("Frequency (MHz),Level (dB)\n")
            for freq, pwr in self.spectrum.iteritems():
                handle.write("{0},{1}\n".format(freq, pwr))
            handle.close()
            self.status.SetStatusText("Finished", 0)
        dlg.Destroy()

    def on_exit(self, _event):
        self.Unbind(wx.EVT_CLOSE)
        if self.save_warn(WARN_EXIT):
            self.Bind(wx.EVT_CLOSE, self.on_exit)
            return
        self.get_range()
        self.settings.devices = self.devices
        self.settings.save()
        self.Close(True)

    def on_pref(self, _event):
        self.devices = self.refresh_devices()
        dlg = DialogPrefs(self, self.devices, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            self.devices = dlg.get_devices()
            self.settings.index = dlg.get_index()
        dlg.Destroy()

    def on_cal(self, _event):
        self.dlgCal = DialogAutoCal(self, self.settings.calFreq, self.auto_cal)
        self.dlgCal.ShowModal()

    def on_about(self, _event):
        dlg = wx.MessageDialog(self, "RTLSDR Scanner",
                               "About", wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def on_spin(self, event):
        control = event.GetEventObject()
        if control == self.spinCtrlStart:
            self.spinCtrlStop.SetRange(self.spinCtrlStart.GetValue() + 1,
                                          F_MAX)

    def on_start(self, _event):
        self.scan_start(False)

    def on_stop(self, _event):
        if self.thread:
            self.status.SetStatusText("Stopping", 0)
            self.thread.abort()

    def on_check_update(self, _event):
        self.update = self.checkUpdate.GetValue()

    def on_check_grid(self, _event):
        self.grid = self.checkGrid.GetValue()
        self.draw_plot()

    def on_thread_status(self, event):
        status = event.data.get_status()
        freq = event.data.get_freq()
        data = event.data.get_data()
        if status == THREAD_STATUS_STARTING:
            self.status.SetStatusText("Starting", 0)
        elif status == THREAD_STATUS_SCAN:
            self.status.SetStatusText("Scanning", 0)
            self.statusProgress.Show()
            self.statusProgress.SetValue(data)
        elif status == THREAD_STATUS_STOPPED:
            self.statusProgress.Hide()
            self.status.SetStatusText("Stopped", 0)
            self.thread = None
            self.set_controls(True)
            self.draw_plot()
        elif status == THREAD_STATUS_FINISHED:
            self.statusProgress.Hide()
            self.status.SetStatusText("Finished", 0)
            self.thread = None
            self.set_controls(True)
            self.draw_plot()
            if data:
                self.auto_cal(CAL_DONE)
        elif status == THREAD_STATUS_ERROR:
            self.statusProgress.Hide()
            self.status.SetStatusText("Dongle error: {0}".format(data), 0)
            self.thread = None
            self.set_controls(True)
            if self.dlgCal is not None:
                self.dlgCal.Destroy()
                self.dlgCal = None
        elif status == THREAD_STATUS_DATA:
            self.isSaved = False
            ThreadProcess(self, freq, data, self.settings, self.devices)
        elif status == THREAD_STATUS_PROCESSED:
            self.update_scan(freq, data)
            if self.update:
                self.draw_plot()

    def on_size(self, event):
        rect = self.status.GetFieldRect(1)
        self.statusProgress.SetPosition((rect.x + 10, rect.y + 2))
        self.statusProgress.SetSize((rect.width - 20, rect.height - 4))
        event.Skip()

    def open(self, dirname, filename):
        self.filename = filename
        self.dirname = dirname
        self.status.SetStatusText("Opening: {0}".format(filename), 0)
        try:
            handle = open(os.path.join(dirname, filename), 'rb')
            header = cPickle.load(handle)
            if header != FILE_HEADER:
                wx.MessageBox('Invalid or corrupted file', 'Warning',
                          wx.OK | wx.ICON_WARNING)
                self.status.SetStatusText("Open failed", 0)
                return
            _version = cPickle.load(handle)
            self.settings.start = cPickle.load(handle)
            self.settings.stop = cPickle.load(handle)
            self.spectrum = cPickle.load(handle)
        except:
            wx.MessageBox('File could not be opened', 'Warning',
                          wx.OK | wx.ICON_WARNING)
            self.status.SetStatusText("Open failed", 0)
            return
        self.isSaved = True
        self.set_range()
        self.draw_plot()
        handle.close()
        self.status.SetStatusText("Finished", 0)

    def auto_cal(self, status):
        freq = self.dlgCal.get_freq()
        if self.dlgCal is not None:
            if status == CAL_START:
                self.spinCtrlStart.SetValue(freq - 1)
                self.spinCtrlStop.SetValue(freq + 1)
                self.oldCal = self.devices[self.settings.index].calibration
                self.devices[self.settings.index].calibration = 0
                if not self.scan_start(True):
                    self.dlgCal.reset_cal()
            elif status == CAL_DONE:
                ppm = self.calc_ppm(freq)
                self.dlgCal.set_cal(ppm)
            elif status == CAL_OK:
                self.devices[self.settings.index].calibration = self.dlgCal.get_cal()
                self.settings.calFreq = freq
                self.dlgCal = None
            elif status == CAL_CANCEL:
                self.dlgCal = None
                self.devices[self.settings.index].calibration = self.oldCal

    def calc_ppm(self, freq):
        spectrum = self.spectrum.copy()
        for x, y in spectrum.iteritems():
            spectrum[x] = (((x - freq) * (x - freq)) + 1) * y

        peak = max(spectrum, key=spectrum.get)

        return ((freq - peak) / freq) * 1e6

    def scan_start(self, isCal):
        if self.save_warn(WARN_SCAN):
            return False

        self.devices = self.refresh_devices()
        if(len(self.devices) == 0):
            wx.MessageBox('No devices found',
                          'Error', wx.OK | wx.ICON_ERROR)
            return

        self.get_range()
        if self.settings.start >= self.settings.stop:
            wx.MessageBox('Stop frequency must be greater that start',
                          'Warning', wx.OK | wx.ICON_WARNING)
            return

        choice = self.choiceDwell.GetSelection()

        if not self.thread or not self.thread.is_alive():

            self.set_controls(False)
            dwell = DWELL[1::2][choice]
            samples = dwell * SAMPLE_RATE
            samples = next_2_to_pow(int(samples))
            self.spectrum = {}
            self.status.SetStatusText("", 1)
            self.thread = ThreadScan(self, self.settings, self.devices,
                                     samples, isCal)
            self.filename = "Scan {0:.1f}-{1:.1f}MHz".format(self.settings.start,
                                                            self.settings.stop)

            return True

    def update_scan(self, freqCentre, scan):
        offset = self.settings.devices[self.settings.index].offset
        upperStart = freqCentre + offset
        upperEnd = freqCentre + offset + BANDWIDTH / 2
        lowerStart = freqCentre - offset - BANDWIDTH / 2
        lowerEnd = freqCentre - offset

        for freq in scan:
            if self.settings.start < freq < self.settings.stop:
                power = 10 * math.log10(scan[freq])
                if upperStart < freq * 1e6 < upperEnd:
                    self.spectrum[freq] = power
                if lowerStart < freq * 1e6 < lowerEnd:
                    if freq in self.spectrum:
                        self.spectrum[freq] = (self.spectrum[freq] + power) / 2
                    else:
                        self.spectrum[freq] = power

    def set_controls(self, state):
        self.spinCtrlStart.Enable(state)
        self.spinCtrlStop.Enable(state)
        self.choiceDwell.Enable(state)
        self.buttonStart.Enable(state)
        self.buttonStop.Enable(not state)
        self.menuOpen.Enable(state)
        self.menuSave.Enable(state)
        self.menuExport.Enable(state)
        self.menuStart.Enable(state)
        self.menuStop.Enable(not state)
        self.menuPref.Enable(state)
        self.menuCal.Enable(state)

    def draw_plot(self):
        axes = self.graph.get_axes()
        if len(self.spectrum) > 0:
            freqs = self.spectrum.keys()
            freqs.sort()
            powers = map(self.spectrum.get, freqs)
            axes.clear()
            axes.set_title("Frequency Scan\n{0} - {1} MHz".format(self.settings.start,
                                                                self.settings.stop))
            axes.set_xlabel("Frequency (MHz)")
            axes.set_ylabel('Level (dB)')
            axes.plot(freqs, powers, linewidth=0.4)
            self.graph.get_toolbar().update()
        axes.grid(self.grid)
        if(self.settings.yAuto):
            axes.set_ylim(auto=True)
            self.settings.yMin, self.settings.yMax = axes.get_ylim()
        else:
            axes.set_ylim(self.settings.yMin, self.settings.yMax)
        self.graph.get_canvas().draw()

    def save_warn(self, warnType):
        if not self.isSaved:
            dlg = DialogSaveWarn(self, warnType)
            code = dlg.ShowModal()
            if code == wx.ID_YES:
                self.on_save(None)
                if self.isSaved:
                    return False
                else:
                    return True
            elif code == wx.ID_NO:
                return False
            else:
                return True

        return False

    def set_range(self):
        self.spinCtrlStart.SetValue(self.settings.start)
        self.spinCtrlStop.SetValue(self.settings.stop)

    def get_range(self):
        self.settings.start = self.spinCtrlStart.GetValue()
        self.settings.stop = self.spinCtrlStop.GetValue()

    def refresh_devices(self):
        self.settings.devices = self.devices
        self.settings.save()
        return self.get_devices()

    def get_devices(self):
        devices = []
        count = rtlsdr.librtlsdr.rtlsdr_get_device_count()

        for dev in range(0, count):
            device = Device()
            device.index = dev
            device.name = format_device_name(rtlsdr.librtlsdr.rtlsdr_get_device_name(dev))
            device.calibration = 0.0
            device.lo = 0.0
            for conf in self.settings.devices:
                # TODO: better matching than just name?
                if device.name == conf.name:
                    device.calibration = conf.calibration
                    device.lo = conf.lo
                    device.offset = conf.offset
                    break

            devices.append(device)

        return devices

def format_device_name(name):
    remove = ["/", "\\"]
    for char in remove:
        name = name.replace(char, " ")

    return name

def thread_event_handler(win, event, function):
    win.Connect(-1, -1, event, function)


def next_2_to_pow(val):
    val -= 1
    val |= val >> 1
    val |= val >> 2
    val |= val >> 4
    val |= val >> 8
    val |= val >> 16
    return val + 1


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="plot filename", nargs='?')
    args = parser.parse_args()

    filename = None
    directory = None
    if args.file != None:
        directory, filename = os.path.split(args.file)

    return directory, filename


if __name__ == '__main__':
    app = wx.App(False)
    frame = FrameMain("RTLSDR Scanner")
    directory, filename = arguments()

    if filename != None:
        frame.open(directory, filename)
    app.MainLoop()
