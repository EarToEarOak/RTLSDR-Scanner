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

try:
    input = raw_input
except:
    pass

try:
    import matplotlib
    matplotlib.interactive(True)
    matplotlib.use('WXAgg')
    import argparse
    import cPickle
    import math
    import multiprocessing
    import os.path
    import rtlsdr
    import webbrowser
except ImportError as error:
    print('Import error: {0}'.format(error))
    input('\nError importing libraries\nPress [Return] to exit')
    exit(1)

from constants import *
from events import *
from misc import format_device_name, next_2_to_pow
from plot import setup_plot, scale_plot
from scan import anaylse_data
from settings import Settings, Device
from threads import ThreadScan, ThreadPlot
from windows import PanelGraph, DialogPrefs, DialogCompare, DialogAutoCal, \
    DialogSaveWarn


MODE = ["Single", 0,
        "Continuous", 1]
NFFT = [128,
        512,
        1024,
        2048,
        4096,
        8192,
        16384,
        32768]
DWELL = ["10 ms", 0.01,
         "25 ms", 0.025,
         "50 ms", 0.05,
         "100 ms", 0.1,
         "200 ms", 0.2,
         "500 ms", 0.5,
         "1 s", 1,
         "2 s", 2,
         "5 s", 5]


class FrameMain(wx.Frame):
    def __init__(self, title, pool):

        self.grid = True

        self.pool = pool
        self.threadScan = None
        self.threadPlot = None
        self.processAnalyse = []
        self.pendingScan = False
        self.pendingPlot = Plot.NONE
        self.stopAtEnd = False
        self.stopScan = False

        self.dlgCal = None

        self.menuOpen = None
        self.menuSave = None
        self.menuExport = None
        self.menuStart = None
        self.menuStop = None
        self.menuStopEnd = None
        self.menuPref = None
        self.menuCompare = None
        self.menuCal = None

        self.popupMenu = None
        self.popupMenuStart = None
        self.popupMenuStop = None
        self.popupMenuStopEnd = None

        self.panel = None
        self.graph = None
        self.canvas = None
        self.buttonStart = None
        self.buttonStop = None
        self.choiceMode = None
        self.choiceDwell = None
        self.choiceNfft = None
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
        self.status.SetFieldsCount(3)
        self.statusProgress = wx.Gauge(self.status, -1,
                                        style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.statusProgress.Hide()

        self.create_widgets()
        self.create_menu()
        self.create_popup_menu()
        self.set_controls(True)
        self.menuSave.Enable(False)
        self.menuExport.Enable(False)
        self.Show()

        size = self.panel.GetSize()
        size[1] += displaySize[1] / 4
        self.SetMinSize(size)

        self.Connect(-1, -1, EVT_THREAD_STATUS, self.on_event)

        self.SetDropTarget(DropTarget(self))

    def create_widgets(self):
        panel = wx.Panel(self)

        self.panel = wx.Panel(panel)
        self.graph = PanelGraph(panel, self)
        setup_plot(self.graph, self.settings, self.grid)
        axes = self.graph.get_axes()
        axes.set_xlim(self.settings.start, self.settings.stop)
        axes.set_ylim(self.settings.yMin, self.settings.yMax)

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

        textMode = wx.StaticText(self.panel, label="Mode")
        self.choiceMode = wx.Choice(self.panel, choices=MODE[::2])
        self.choiceMode.SetToolTip(wx.ToolTip('Scanning mode'))
        self.choiceMode.SetSelection(MODE[1::2].index(self.settings.mode))

        textDwell = wx.StaticText(self.panel, label="Dwell")
        self.choiceDwell = wx.Choice(self.panel, choices=DWELL[::2])
        self.choiceDwell.SetToolTip(wx.ToolTip('Scan time per step'))
        self.choiceDwell.SetSelection(DWELL[1::2].index(self.settings.dwell))

        textNfft = wx.StaticText(self.panel, label="FFT size")
        self.choiceNfft = wx.Choice(self.panel, choices=map(str, NFFT))
        self.choiceNfft.SetToolTip(wx.ToolTip('Higher values for greater precision'))
        self.choiceNfft.SetSelection(NFFT.index(self.settings.nfft))

        self.checkAuto = wx.CheckBox(self.panel, wx.ID_ANY,
                                        "Auto range")
        self.checkAuto.SetToolTip(wx.ToolTip('Scale the axes to fit all data'))
        self.checkAuto.SetValue(self.settings.autoScale)
        self.Bind(wx.EVT_CHECKBOX, self.on_check_auto, self.checkAuto)

        self.checkUpdate = wx.CheckBox(self.panel, wx.ID_ANY,
                                        "Live update")
        self.checkUpdate.SetToolTip(wx.ToolTip('Update update_plot with live samples '
                                               '(Can be slow)'))
        self.checkUpdate.SetValue(self.settings.liveUpdate)
        self.Bind(wx.EVT_CHECKBOX, self.on_check_update, self.checkUpdate)

        self.checkGrid = wx.CheckBox(self.panel, wx.ID_ANY, "Grid")
        self.checkGrid.SetToolTip(wx.ToolTip('Draw grid'))
        self.checkGrid.SetValue(self.grid)
        self.Bind(wx.EVT_CHECKBOX, self.on_check_grid, self.checkGrid)

        grid = wx.GridBagSizer(5, 5)

        grid.Add(self.buttonStart, pos=(0, 0), span=(3, 1),
                 flag=wx.ALIGN_CENTER)
        grid.Add(self.buttonStop, pos=(0, 1), span=(3, 1),
                 flag=wx.ALIGN_CENTER)

        grid.Add((20, 1), pos=(0, 2))

        grid.Add(textRange, pos=(0, 3), span=(1, 4), flag=wx.ALIGN_CENTER)
        grid.Add(textStart, pos=(1, 3), flag=wx.ALIGN_CENTER)
        grid.Add(self.spinCtrlStart, pos=(1, 4))
        grid.Add(textStop, pos=(1, 5), flag=wx.ALIGN_CENTER)
        grid.Add(self.spinCtrlStop, pos=(1, 6))

        grid.Add((20, 1), pos=(0, 7))

        grid.Add(textMode, pos=(0, 8), flag=wx.ALIGN_CENTER)
        grid.Add(self.choiceMode, pos=(1, 8), flag=wx.ALIGN_CENTER)

        grid.Add(textDwell, pos=(0, 9), flag=wx.ALIGN_CENTER)
        grid.Add(self.choiceDwell, pos=(1, 9), flag=wx.ALIGN_CENTER)

        grid.Add(textNfft, pos=(0, 10), flag=wx.ALIGN_CENTER)
        grid.Add(self.choiceNfft, pos=(1, 10), flag=wx.ALIGN_CENTER)

        grid.Add((20, 1), pos=(0, 11))

        grid.Add(self.checkAuto, pos=(0, 12), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.checkUpdate, pos=(1, 12), flag=wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.checkGrid, pos=(2, 12), flag=wx.ALIGN_CENTER_VERTICAL)

        self.panel.SetSizer(grid)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.graph, 1, wx.EXPAND)
        sizer.Add(self.panel, 0, wx.ALIGN_CENTER)
        panel.SetSizer(sizer)

    def create_menu(self):
        menuFile = wx.Menu()
        self.menuOpen = menuFile.Append(wx.ID_OPEN, "&Open...", "Open update_plot")
        self.menuSave = menuFile.Append(wx.ID_SAVE, "&Save As...",
                                          "Save update_plot")
        self.menuExport = menuFile.Append(wx.ID_ANY, "&Export...",
                                            "Export update_plot")
        menuExit = menuFile.Append(wx.ID_EXIT, "E&xit", "Exit the program")

        menuScan = wx.Menu()
        self.menuStart = menuScan.Append(wx.ID_ANY, "&Start", "Start scan")
        self.menuStop = menuScan.Append(wx.ID_ANY, "S&top",
                                        "Stop scan immediately")
        self.menuStopEnd = menuScan.Append(wx.ID_ANY, "Stop at &end",
                                           "Complete current sweep before stopping")

        menuView = wx.Menu()
        self.menuPref = menuView.Append(wx.ID_ANY, "&Preferences...",
                                   "Preferences")

        menuTools = wx.Menu()
        self.menuCompare = menuTools.Append(wx.ID_ANY, "&Compare...",
                                            "Compare plots")
        self.menuCal = menuTools.Append(wx.ID_ANY, "&Auto Calibration...",
                               "Automatically calibrate to a known frequency")

        menuHelp = wx.Menu()
        menuHelpLink = menuHelp.Append(wx.ID_HELP, "&Help...",
                                            "Link to help")
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
        self.Bind(wx.EVT_MENU, self.on_stop_end, self.menuStopEnd)
        self.Bind(wx.EVT_MENU, self.on_pref, self.menuPref)
        self.Bind(wx.EVT_MENU, self.on_compare, self.menuCompare)
        self.Bind(wx.EVT_MENU, self.on_cal, self.menuCal)
        self.Bind(wx.EVT_MENU, self.on_about, menuAbout)
        self.Bind(wx.EVT_MENU, self.on_help, menuHelpLink)

        idF1 = wx.wx.NewId()
        self.Bind(wx.EVT_MENU, self.on_help, id=idF1)
        accelTable = wx.AcceleratorTable([(wx.ACCEL_NORMAL, wx.WXK_F1, idF1)])
        self.SetAcceleratorTable(accelTable)

    def create_popup_menu(self):
        self.popupMenu = wx.Menu()
        self.popupMenuStart = self.popupMenu.Append(wx.ID_ANY, "&Start",
                                                    "Start scan")
        self.popupMenuStop = self.popupMenu.Append(wx.ID_ANY, "S&top",
                                                   "Stop scan immediately")
        self.popupMenuStopEnd = self.popupMenu.Append(wx.ID_ANY, "Stop at &end",
                                                      "Complete current sweep before stopping")

        self.Bind(wx.EVT_MENU, self.on_start, self.popupMenuStart)
        self.Bind(wx.EVT_MENU, self.on_stop, self.popupMenuStop)
        self.Bind(wx.EVT_MENU, self.on_stop_end, self.popupMenuStopEnd)

        self.Bind(wx.EVT_CONTEXT_MENU, self.on_popup_menu)

    def on_popup_menu(self, event):
        pos = event.GetPosition()
        pos = self.ScreenToClient(pos)
        self.PopupMenu(self.popupMenu, pos)

    def on_open(self, _event):
        if self.save_warn(Warn.OPEN):
            return
        dlg = wx.FileDialog(self, "Open a scan", self.dirname, self.filename,
                            File.RFS, wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.open(dlg.GetDirectory(), dlg.GetFilename())
        dlg.Destroy()

    def on_save(self, _event):
        dlg = wx.FileDialog(self, "Save a scan", self.dirname,
                            self.filename + ".rfs", File.RFS,
                            wx.SAVE | wx.OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            self.status.SetStatusText("Saving", 0)
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()
            handle = open(os.path.join(self.dirname, self.filename), 'wb')
            cPickle.dump(File.HEADER, handle)
            cPickle.dump(File.VERSION, handle)
            cPickle.dump(self.settings.start, handle)
            cPickle.dump(self.settings.stop, handle)
            cPickle.dump(self.spectrum, handle)
            handle.close()
            self.isSaved = True
            self.status.SetStatusText("Finished", 0)
        dlg.Destroy()

    def on_export(self, _event):
        dlg = wx.FileDialog(self, "Export a scan", self.dirname,
                            self.filename + ".csv", File.CSV, wx.SAVE)
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
        if self.save_warn(Warn.EXIT):
            self.Bind(wx.EVT_CLOSE, self.on_exit)
            return
        self.stop_scan()
        self.wait_background()
        self.get_range()
        self.settings.dwell = DWELL[1::2][self.choiceDwell.GetSelection()]
        self.settings.nfft = NFFT[self.choiceNfft.GetSelection()]
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

    def on_compare(self, _event):
        dlg = DialogCompare(self, self.dirname, self.filename)
        dlg.ShowModal()
        dlg.Destroy()

    def on_cal(self, _event):
        self.dlgCal = DialogAutoCal(self, self.settings.calFreq, self.auto_cal)
        self.dlgCal.ShowModal()

    def on_about(self, _event):
        dlg = wx.MessageDialog(self,
            "A tool for scanning frequency ranges "
            "with an RTL-SDR compatible USB dongle",
            "RTLSDR Scanner",
            wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def on_help(self, _event):
        webbrowser.open("http://eartoearoak.com/software/rtlsdr-scanner")

    def on_spin(self, event):
        control = event.GetEventObject()
        if control == self.spinCtrlStart:
            self.spinCtrlStop.SetRange(self.spinCtrlStart.GetValue() + 1,
                                          F_MAX)

    def on_start(self, _event):
        self.get_range()
        self.graph.get_axes().clear()
        scale_plot(self.graph, self.settings)
        self.start_scan()

    def on_stop(self, _event):
        self.stopScan = True
        self.stopAtEnd = False
        self.stop_scan()

    def on_stop_end(self, _event):
        self.stopAtEnd = True

    def on_check_auto(self, _event):
        self.settings.autoScale = self.checkAuto.GetValue()

    def on_check_update(self, _event):
        self.settings.liveUpdate = self.checkUpdate.GetValue()

    def on_check_grid(self, _event):
        self.grid = self.checkGrid.GetValue()
        self.update_plot()

    def on_event(self, event):
        status = event.data.get_status()
        freq = event.data.get_freq()
        data = event.data.get_data()
        if status == Event.STARTING:
            self.status.SetStatusText("Starting", 0)
        elif status == Event.SCAN:
            if self.stopAtEnd:
                self.status.SetStatusText("Stopping", 0)
            else:
                self.status.SetStatusText("Scanning", 0)
            self.statusProgress.Show()
            self.statusProgress.SetValue(data)
        elif status == Event.DATA:
            self.isSaved = False
            fftChoice = self.choiceNfft.GetSelection()
            cal = self.devices[self.settings.index].calibration
            nfft = NFFT[fftChoice]
            self.processAnalyse.append(freq)
            pool.apply_async(anaylse_data, (freq, data, cal, nfft),
                             callback=self.on_process_done)
        elif status == Event.FINISHED:
            self.statusProgress.Hide()
            if self.settings.mode == Mode.SINGLE or self.stopAtEnd:
                self.status.SetStatusText("Finished", 0)
            self.threadScan = None
            if self.settings.mode == Mode.SINGLE:
                self.set_controls(True)
            if data:
                self.auto_cal(Cal.DONE)
        elif status == Event.STOPPED:
            self.statusProgress.Hide()
            self.status.SetStatusText("Stopped", 0)
            self.threadScan = None
            self.set_controls(True)
            self.update_plot()
        elif status == Event.ERROR:
            self.statusProgress.Hide()
            self.status.SetStatusText("Dongle error: {0}".format(data), 0)
            self.threadScan = None
            self.set_controls(True)
            if self.dlgCal is not None:
                self.dlgCal.Destroy()
                self.dlgCal = None
        elif status == Event.DRAW:
            self.graph.get_canvas().draw()
        elif status == Event.PLOTTED:
            self.threadPlot = None
            self.next_plot()
        elif status == Event.PLOTTED_FULL:
            self.next_plot()
            if self.pendingScan:
                self.start_scan()

    def on_process_done(self, data):
        freq, scan = data
        self.update_spectrum(freq, scan)
        self.processAnalyse.remove(freq)
        if self.threadScan is None and len(self.processAnalyse) == 0:
            if self.settings.mode == Mode.CONTIN and not self.stopScan:
                if self.dlgCal is None and not self.stopAtEnd:
                    self.pendingScan = True
            else:
                self.stopAtEnd = False
                self.stopScan = False
                self.set_controls(True)
            self.update_plot(True)
        elif self.settings.liveUpdate:
            self.update_plot()

    def on_size(self, event):
        rect = self.status.GetFieldRect(2)
        self.statusProgress.SetPosition((rect.x + 10, rect.y + 2))
        self.statusProgress.SetSize((rect.width - 20, rect.height - 4))
        event.Skip()

    def open(self, dirname, filename):
        self.filename = filename
        self.dirname = dirname
        self.status.SetStatusText("Opening: {0}".format(filename), 0)

        start, stop, spectrum = self.open_plot(dirname, filename)

        if len(spectrum) > 0:
            self.settings.start = start
            self.settings.stop = stop
            self.spectrum = spectrum
            self.isSaved = True
            self.set_range()
            self.set_controls(True)
            self.update_plot()
            self.status.SetStatusText("Finished", 0)
        else:
            self.status.SetStatusText("Open failed", 0)

    def open_plot(self, dirname, filename):
        try:
            handle = open(os.path.join(dirname, filename), 'rb')
            header = cPickle.load(handle)
            if header != File.HEADER:
                wx.MessageBox('Invalid or corrupted file', 'Warning',
                          wx.OK | wx.ICON_WARNING)
                return
            _version = cPickle.load(handle)
            start = cPickle.load(handle)
            stop = cPickle.load(handle)
            spectrum = cPickle.load(handle)
        except:
            wx.MessageBox('File could not be opened', 'Warning',
                          wx.OK | wx.ICON_WARNING)

        return start, stop, spectrum

    def auto_cal(self, status):
        freq = self.dlgCal.get_freq()
        if self.dlgCal is not None:
            if status == Cal.START:
                self.spinCtrlStart.SetValue(freq - 1)
                self.spinCtrlStop.SetValue(freq + 1)
                self.oldCal = self.devices[self.settings.index].calibration
                self.devices[self.settings.index].calibration = 0
                self.get_range()
                self.graph.get_axes().clear()
                if not self.start_scan(isCal=True):
                    self.dlgCal.reset_cal()
            elif status == Cal.DONE:
                ppm = self.calc_ppm(freq)
                self.dlgCal.set_cal(ppm)
                self.set_controls(True)
            elif status == Cal.OK:
                self.devices[self.settings.index].calibration = self.dlgCal.get_cal()
                self.settings.calFreq = freq
                self.dlgCal = None
            elif status == Cal.CANCEL:
                self.dlgCal = None
                if len(self.devices) > 0:
                    self.devices[self.settings.index].calibration = self.oldCal

    def calc_ppm(self, freq):
        spectrum = self.spectrum.copy()
        for x, y in spectrum.iteritems():
            spectrum[x] = (((x - freq) * (x - freq)) + 1) * y

        peak = max(spectrum, key=spectrum.get)

        return ((freq - peak) / freq) * 1e6

    def start_scan(self, isCal=False):
        if self.save_warn(Warn.SCAN):
            return False

        self.devices = self.refresh_devices()
        if(len(self.devices) == 0):
            wx.MessageBox('No devices found',
                          'Error', wx.OK | wx.ICON_ERROR)
            return

        if self.settings.start >= self.settings.stop:
            wx.MessageBox('Stop frequency must be greater that start',
                          'Warning', wx.OK | wx.ICON_WARNING)
            return

        choiceDwell = self.choiceDwell.GetSelection()

        if not self.threadScan or not self.threadScan.isAlive():

            self.set_controls(False)
            dwell = DWELL[1::2][choiceDwell]
            samples = dwell * SAMPLE_RATE
            samples = next_2_to_pow(int(samples))
            self.spectrum.clear()
            self.status.SetStatusText("", 1)
            self.pendingScan = False
            self.threadScan = ThreadScan(self, self.settings, self.devices,
                                     samples, isCal)
            self.filename = "Scan {0:.1f}-{1:.1f}MHz".format(self.settings.start,
                                                            self.settings.stop)

            return True

    def stop_scan(self):
        if self.threadScan:
            self.status.SetStatusText("Stopping", 0)
            self.threadScan.abort()

    def update_spectrum(self, freqCentre, scan):
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
        self.choiceMode.Enable(state)
        self.choiceDwell.Enable(state)
        self.choiceNfft.Enable(state)
        self.buttonStart.Enable(state)
        self.buttonStop.Enable(not state)
        self.menuOpen.Enable(state)
        self.menuSave.Enable(state)
        self.menuExport.Enable(state)
        self.menuStart.Enable(state)
        self.popupMenuStart.Enable(state)
        self.menuStop.Enable(not state)
        self.popupMenuStop.Enable(not state)
        if self.settings.mode == Mode.CONTIN:
            self.menuStopEnd.Enable(not state)
            self.popupMenuStopEnd.Enable(not state)
        else:
            self.menuStopEnd.Enable(False)
            self.popupMenuStopEnd.Enable(False)
        self.menuPref.Enable(state)
        self.menuCal.Enable(state)

    def plot(self, full):
        if self.threadPlot is None:
            if self.settings.mode == Mode.CONTIN:
                fade = True
            else:
                fade = False
            self.threadPlot = ThreadPlot(self, self.graph, self.spectrum,
                                        self.settings, self.grid, full, fade)
            return True
        else:
            return False

    def update_plot(self, full=False, updateScale=False):
        scale_plot(self.graph, self.settings, updateScale)

        if full:
            if not self.plot(True):
                self.pendingPlot = Plot.FULL
            else:
                self.pendingPlot = Plot.NONE
        else:
            if self.pendingPlot == Plot.FULL:
                if not self.plot(True):
                    self.pendingPlot = Plot.FULL
                else:
                    self.pendingPlot = Plot.NONE
            else:
                if not self.plot(False):
                    self.pendingPlot = Plot.PARTIAL
                else:
                    self.pendingPlot = Plot.NONE

    def next_plot(self):
        self.threadPlot = None
        if self.pendingPlot == Plot.PARTIAL:
            self.update_plot(False)
        elif self.pendingPlot == Plot.FULL:
            self.update_plot(True)

    def save_warn(self, warnType):
        if self.settings.saveWarn and not self.isSaved:
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
        choiceMode = self.choiceMode.GetSelection()

        self.settings.mode = MODE[1::2][choiceMode]
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
                    device.gain = conf.gain
                    device.calibration = conf.calibration
                    device.lo = conf.lo
                    device.offset = conf.offset
                    break

            devices.append(device)

        return devices

    def wait_background(self):
        self.Disconnect(-1, -1, EVT_THREAD_STATUS, self.on_event)
        if self.threadScan:
            self.threadScan.join()
            self.threadScan = None
        if self.threadPlot:
            self.threadPlot.join()
            self.threadPlot = None
        self.pool.close()
        self.pool.join()


class RtlsdrScanner(wx.App):
    def __init__(self, pool):
        self.pool = pool
        wx.App.__init__(self, redirect=False)


class DropTarget(wx.FileDropTarget):
    def __init__(self, window):
        wx.FileDropTarget.__init__(self)
        self.window = window

    def OnDropFiles(self, _xPos, _yPos, filenames):
        filename = filenames[0]
        if os.path.splitext(filename)[1].lower() == ".rfs":
            self.window.dirname, self.window.filename = os.path.split(filename)
            self.window.open()


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="update_plot filename", nargs='?')
    args = parser.parse_args()

    filename = None
    directory = None
    if args.file != None:
        directory, filename = os.path.split(args.file)

    return directory, filename


if __name__ == '__main__':
    multiprocessing.freeze_support()
    pool = multiprocessing.Pool()
    app = RtlsdrScanner(pool)
    frame = FrameMain("RTLSDR Scanner", pool)
    directory, filename = arguments()

    if filename != None:
        frame.open(directory, filename)
    app.MainLoop()
