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
    import rtlsdr
    import wx
except ImportError as error:
    print 'Import error: {0}'.format(error)
    input('\nError importing libraries\nPress [Return] to exit')
    exit(1)

import os.path
import threading
import webbrowser

from constants import *
from devices import get_devices
from events import EVT_THREAD_STATUS, Event
from misc import calc_samples, calc_real_dwell
from plot import setup_plot, scale_plot, open_plot, save_plot, export_plot, \
    ThreadPlot, clear_plot
from scan import ThreadScan, anaylse_data, update_spectrum
from settings import Settings
from windows import PanelGraph, DialogPrefs, DialogCompare, DialogAutoCal, \
    DialogSaveWarn, Statusbar


class DropTarget(wx.FileDropTarget):
    def __init__(self, window):
        wx.FileDropTarget.__init__(self)
        self.window = window

    def OnDropFiles(self, _xPos, _yPos, filenames):
        filename = filenames[0]
        if os.path.splitext(filename)[1].lower() == ".rfs":
            self.window.dirname, self.window.filename = os.path.split(filename)
            self.window.open()


class RtlSdrScanner(wx.App):
    def __init__(self, pool):
        self.pool = pool
        wx.App.__init__(self, redirect=False)


class FrameMain(wx.Frame):
    def __init__(self, title, pool):

        self.grid = True

        self.pool = pool
        self.lock = threading.Lock()
        self.threadScan = None
        self.threadPlot = None
        self.stepsTotal = 0
        self.steps = 0
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
        self.devices = get_devices(self.settings.devices)
        self.oldCal = 0

        displaySize = wx.DisplaySize()
        wx.Frame.__init__(self, None, title=title, size=(displaySize[0] / 1.5,
                                                         displaySize[1] / 2))

        self.Bind(wx.EVT_CLOSE, self.on_exit)

        self.status = Statusbar(self)
        self.SetStatusBar(self.status)

        self.create_widgets()
        self.create_menu()
        self.create_popup_menu()
        self.set_control_state(True)
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
        self.Bind(wx.EVT_SPINCTRL, self.on_spin, self.spinCtrlStart)
        self.Bind(wx.EVT_SPINCTRL, self.on_spin, self.spinCtrlStop)

        textMode = wx.StaticText(self.panel, label="Mode")
        self.choiceMode = wx.Choice(self.panel, choices=MODE[::2])
        self.choiceMode.SetToolTip(wx.ToolTip('Scanning mode'))

        textDwell = wx.StaticText(self.panel, label="Dwell")
        self.choiceDwell = wx.Choice(self.panel, choices=DWELL[::2])
        self.choiceDwell.SetToolTip(wx.ToolTip('Scan time per step'))

        textNfft = wx.StaticText(self.panel, label="FFT size")
        self.choiceNfft = wx.Choice(self.panel, choices=map(str, NFFT))
        self.choiceNfft.SetToolTip(wx.ToolTip('Higher values for greater'
                                              'precision'))
        self.set_controls()

        self.checkAuto = wx.CheckBox(self.panel, wx.ID_ANY,
                                        "Auto range")
        self.checkAuto.SetToolTip(wx.ToolTip('Scale the axes to fit all data'))
        self.checkAuto.SetValue(self.settings.autoScale)
        self.Bind(wx.EVT_CHECKBOX, self.on_check_auto, self.checkAuto)

        self.checkUpdate = wx.CheckBox(self.panel, wx.ID_ANY,
                                        "Live update")
        self.checkUpdate.SetToolTip(wx.ToolTip('Update plot with live '
                                               'samples (experimental)'))
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
        self.menuOpen = menuFile.Append(wx.ID_OPEN, "&Open...",
                                        "Open plot")
        self.menuSave = menuFile.Append(wx.ID_SAVE, "&Save As...",
                                          "Save plot")
        self.menuExport = menuFile.Append(wx.ID_ANY, "&Export...",
                                            "Export plot")
        menuExit = menuFile.Append(wx.ID_EXIT, "E&xit", "Exit the program")

        menuScan = wx.Menu()
        self.menuStart = menuScan.Append(wx.ID_ANY, "&Start", "Start scan")
        self.menuStop = menuScan.Append(wx.ID_ANY, "S&top",
                                        "Stop scan immediately")
        self.menuStopEnd = menuScan.Append(wx.ID_ANY, "Stop at &end",
                                           "Complete current sweep "
                                           "before stopping")

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
                                                      "Complete current sweep "
                                                      "before stopping")

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
            self.status.set_general("Saving")
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()
            save_plot(self.dirname, self.filename, self.settings,
                      self.spectrum)
            self.isSaved = True
            self.status.set_general("Finished")
        dlg.Destroy()

    def on_export(self, _event):
        dlg = wx.FileDialog(self, "Export a scan", self.dirname,
                            self.filename + ".csv", File.CSV, wx.SAVE)
        if dlg.ShowModal() == wx.ID_OK:
            self.status.set_general("Exporting")
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()
            export_plot(self.dirname, self.filename, self.spectrum)
            self.status.set_general("Finished")
        dlg.Destroy()

    def on_exit(self, _event):
        self.Unbind(wx.EVT_CLOSE)
        if self.save_warn(Warn.EXIT):
            self.Bind(wx.EVT_CLOSE, self.on_exit)
            return
        self.stop_scan()
        self.wait_background()
        self.get_controls()
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
        self.get_controls()
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
            self.status.set_general("Starting")
        elif status == Event.STEPS:
            self.stepsTotal = freq * 2
            self.steps = self.stepsTotal
            self.status.set_progress(0)
            self.status.show_progress()
        elif status == Event.STEP:
            self.progress()
        elif status == Event.CAL:
            self.auto_cal(Cal.DONE)
        elif status == Event.DATA:
            self.isSaved = False
            cal = self.devices[self.settings.index].calibration
            self.pool.apply_async(anaylse_data,
                                  (freq, data, cal, self.settings.nfft),
                                  callback=self.on_process_done)
        elif status == Event.STOPPED:
            self.status.hide_progress()
            self.status.set_general("Stopped")
            self.threadScan = None
            self.set_control_state(True)
            self.update_plot()
        elif status == Event.ERROR:
            self.status.hide_progress()
            self.status.set_general("Error: {0}".format(data))
            self.threadScan = None
            self.set_control_state(True)
            if self.dlgCal is not None:
                self.dlgCal.Destroy()
                self.dlgCal = None
        elif status == Event.DRAW:
            self.graph.get_axes().relim()
            self.graph.get_canvas().draw()
        elif status == Event.PLOTTED:
            self.threadPlot = None
            self.next_plot()
        elif status == Event.PLOTTED_FULL:
            self.threadPlot = None
            self.next_plot()
            if self.pendingScan:
                self.start_scan()

    def on_process_done(self, data):
        self.progress()
        freq, scan = data
        offset = self.settings.devices[self.settings.index].offset
        update_spectrum(self.settings.start, self.settings.stop, freq, scan,
                        offset, self.spectrum)
        self.progress()

        if self.settings.liveUpdate:
            self.update_plot()

    def open(self, dirname, filename):
        self.filename = filename
        self.dirname = dirname
        self.status.set_general("Opening: {0}".format(filename))

        start, stop, dwell, nfft, spectrum = open_plot(dirname, filename)

        if len(spectrum) > 0:
            self.spectrum.clear()
            self.settings.start = start
            self.settings.stop = stop
            self.settings.dwell = dwell
            self.settings.nfft = nfft
            self.spectrum = spectrum
            self.isSaved = True
            self.set_controls()
            self.set_control_state(True)
            clear_plot(self.graph.get_axes())
            self.update_plot()
            self.status.set_general("Finished")
        else:
            self.status.set_general("Open failed")

    def auto_cal(self, status):
        freq = self.dlgCal.get_freq()
        if self.dlgCal is not None:
            if status == Cal.START:
                self.spinCtrlStart.SetValue(freq - 1)
                self.spinCtrlStop.SetValue(freq + 1)
                self.oldCal = self.devices[self.settings.index].calibration
                self.devices[self.settings.index].calibration = 0
                self.get_controls()
                self.graph.get_axes().clear()
                if not self.start_scan(isCal=True):
                    self.dlgCal.reset_cal()
            elif status == Cal.DONE:
                ppm = self.calc_ppm(freq)
                self.dlgCal.set_cal(ppm)
                self.set_control_state(True)
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
        if self.settings.mode == Mode.SINGLE:
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

        if not self.threadScan or not self.threadScan.isAlive():
            self.set_control_state(False)
            samples = calc_samples(self.settings.dwell)
            self.spectrum.clear()
            self.status.set_info('')
            self.pendingScan = False

            self.threadScan = ThreadScan(self, self.settings,
                                         self.settings.index, samples, isCal)
            self.filename = "Scan {0:.1f}-{1:.1f}MHz".format(self.settings.start,
                                                            self.settings.stop)
            return True

    def stop_scan(self):
        if self.threadScan:
            self.status.set_general("Stopping")
            self.threadScan.abort()

    def progress(self):
        self.steps -= 1
        if self.steps > 0:
            self.status.set_progress((self.stepsTotal - self.steps) * 100
                    / self.stepsTotal)
            self.status.show_progress()
            self.status.set_general("Scanning")
        else:
            self.status.hide_progress()
            if self.settings.mode == Mode.SINGLE or self.stopAtEnd:
                self.status.set_general("Finished")
            self.threadScan = None
            if self.settings.mode == Mode.SINGLE:
                self.set_control_state(True)
                self.update_plot(True)
            else:
                if self.settings.mode == Mode.CONTIN and not self.stopScan:
                    if self.dlgCal is None and not self.stopAtEnd:
                        self.pendingScan = True
                    else:
                        self.stopAtEnd = False
                        self.stopScan = False
                        self.set_control_state(True)
                    self.update_plot(True)

    def set_control_state(self, state):
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

    def set_controls(self):
        self.spinCtrlStart.SetValue(self.settings.start)
        self.spinCtrlStop.SetValue(self.settings.stop)
        self.choiceMode.SetSelection(MODE[1::2].index(self.settings.mode))
        dwell = calc_real_dwell(self.settings.dwell)
        self.choiceDwell.SetSelection(DWELL[1::2].index(dwell))
        self.choiceNfft.SetSelection(NFFT.index(self.settings.nfft))

    def get_controls(self):
        self.settings.start = self.spinCtrlStart.GetValue()
        self.settings.stop = self.spinCtrlStop.GetValue()
        self.settings.mode = MODE[1::2][self.choiceMode.GetSelection()]
        self.settings.dwell = DWELL[1::2][self.choiceDwell.GetSelection()]
        self.settings.fft = NFFT[self.choiceNfft.GetSelection()]

    def plot(self, full):
        if self.threadPlot is None:
            if self.settings.mode == Mode.CONTIN:
                fade = True
            else:
                fade = False
            self.threadPlot = ThreadPlot(self, self.lock, self.graph,
                                         self.spectrum, self.settings,
                                         self.grid, full, fade)
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

    def refresh_devices(self):
        self.settings.devices = self.devices
        devices = get_devices(self.settings.devices)
        if self.settings.index > len(self.devices) - 1:
            self.settings.index = 0
        self.settings.save()
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


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
