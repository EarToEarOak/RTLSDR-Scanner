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
from collections import OrderedDict

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

import datetime
import os.path
import threading
import webbrowser

from constants import *
from devices import get_devices
from events import EVT_THREAD_STATUS, Event, EventThreadStatus
from misc import ScanInfo, calc_samples, calc_real_dwell, open_plot, save_plot, \
    export_plot
from plot import Plotter
from scan import ThreadScan, anaylse_data, update_spectrum
from settings import Settings
from spectrogram import Spectrogram
from windows import PanelGraph, DialogPrefs, DialogCompare, DialogAutoCal, \
    DialogSaveWarn, Statusbar, DialogProperties


class DropTarget(wx.FileDropTarget):
    def __init__(self, window):
        wx.FileDropTarget.__init__(self)
        self.window = window

    def OnDropFiles(self, _xPos, _yPos, filenames):
        filename = filenames[0]
        if os.path.splitext(filename)[1].lower() == ".rfs":
            dirname, filename = os.path.split(filename)
            self.window.open(dirname, filename)


class RtlSdrScanner(wx.App):
    def __init__(self, pool):
        self.pool = pool
        wx.App.__init__(self, redirect=False)


class FrameMain(wx.Frame):
    def __init__(self, title, pool):

        self.grid = True

        self.pool = pool
        self.lock = threading.Lock()

        self.sdr = None
        self.threadScan = None

        self.plot = None

        self.stopAtEnd = False
        self.stopScan = False

        self.dlgCal = None

        self.menuOpen = None
        self.menuSave = None
        self.menuExport = None
        self.menuProperties = None
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

        self.spectrum = OrderedDict()
        self.scanInfo = ScanInfo()
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

        self.create_plot()

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
        self.Bind(wx.EVT_CHOICE, self.on_choice, self.choiceMode)

        textDwell = wx.StaticText(self.panel, label="Dwell")
        self.choiceDwell = wx.Choice(self.panel, choices=DWELL[::2])
        self.choiceDwell.SetToolTip(wx.ToolTip('Scan time per step'))

        textNfft = wx.StaticText(self.panel, label="FFT size")
        self.choiceNfft = wx.Choice(self.panel, choices=map(str, NFFT))
        self.choiceNfft.SetToolTip(wx.ToolTip('Higher values for greater'
                                              'precision'))

        textDisplay = wx.StaticText(self.panel, label="Display")
        self.choiceDisplay = wx.Choice(self.panel, choices=DISPLAY[::2])
        self.Bind(wx.EVT_CHOICE, self.on_choice, self.choiceDisplay)

        self.set_controls()

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

        grid.Add(textDisplay, pos=(0, 12), flag=wx.ALIGN_CENTER)
        grid.Add(self.choiceDisplay, pos=(1, 12), flag=wx.ALIGN_CENTER)

        self.panel.SetSizer(grid)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.graph, 1, wx.EXPAND)
        sizer.Add(self.panel, 0, wx.ALIGN_CENTER)
        panel.SetSizer(sizer)

    def create_menu(self):
        menuFile = wx.Menu()
        self.menuOpen = menuFile.Append(wx.ID_OPEN, "&Open...",
                                        "Open polot")
        recent = wx.Menu()
        self.settings.fileHistory.UseMenu(recent)
        self.settings.fileHistory.AddFilesToMenu()
        menuFile.AppendMenu(wx.ID_ANY, "&Recent Files", recent)
        menuFile.AppendSeparator()
        self.menuSave = menuFile.Append(wx.ID_SAVE, "&Save As...",
                                          "Save polot")
        self.menuExport = menuFile.Append(wx.ID_ANY, "&Export...",
                                            "Export polot")
        menuFile.AppendSeparator()
        self.menuProperties = menuFile.Append(wx.ID_ANY, "&Properties...",
                                            "Show properties")
        menuFile.AppendSeparator()
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
        self.Bind(wx.EVT_MENU_RANGE, self.on_file_history, id=wx.ID_FILE1,
                  id2=wx.ID_FILE9)
        self.Bind(wx.EVT_MENU, self.on_save, self.menuSave)
        self.Bind(wx.EVT_MENU, self.on_export, self.menuExport)
        self.Bind(wx.EVT_MENU, self.on_properties, self.menuProperties)
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

    def create_plot(self):
        if self.plot is not None:
            self.plot.close()

        if self.settings.display == Display.PLOT:
            self.plot = Plotter(self, self.graph, self.settings, self.grid,
                                self.lock)
        else:
            self.plot = Spectrogram(self, self.graph, self.settings, self.grid, self.lock)

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

    def on_file_history(self, event):
        selection = event.GetId() - wx.ID_FILE1
        path = self.settings.fileHistory.GetHistoryFile(selection)
        self.settings.fileHistory.AddFileToHistory(path)
        dirname, filename = os.path.split(path)
        self.open(dirname, filename)

    def on_save(self, _event):
        dlg = wx.FileDialog(self, "Save a scan", self.dirname,
                            self.filename, File.RFS,
                            wx.SAVE | wx.OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            self.status.set_general("Saving")
            self.filename = dlg.GetFilename()
            self.dirname = dlg.GetDirectory()
            save_plot(self.dirname, self.filename, self.scanInfo,
                      self.spectrum)
            self.isSaved = True
            self.status.set_general("Finished")
            self.settings.fileHistory.AddFileToHistory(os.path.join(self.dirname,
                                                                    self.filename))
        dlg.Destroy()

    def on_export(self, _event):
        dlg = wx.FileDialog(self, "Export a scan", self.dirname,
                            self.filename + ".csv", File.CSV,
                            wx.SAVE | wx.OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            self.status.set_general("Exporting")
            export_plot(self.dirname, self.filename, self.spectrum)
            self.status.set_general("Finished")
        dlg.Destroy()

    def on_properties(self, _event):
        dlg = DialogProperties(self, self.scanInfo)
        dlg.ShowModal()
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

    def on_choice(self, event):
        control = event.GetEventObject()
        if control == self.choiceMode:
            if self.choiceMode.GetSelection() == Display.PLOT:
                self.choiceDisplay.Enable(False)
                self.choiceDisplay
            else:
                self.choiceDisplay.Enable(True)
        elif control == self.choiceDisplay:
            self.get_controls()
            self.create_plot()

    def on_start(self, _event):
        if self.settings.start >= self.settings.stop:
            wx.MessageBox('Stop frequency must be greater that start',
                          'Warning', wx.OK | wx.ICON_WARNING)
            return

        self.get_controls()
        self.plot.clear_plots()

        self.devices = self.refresh_devices()
        if(len(self.devices) == 0):
            wx.MessageBox('No devices found',
                          'Error', wx.OK | wx.ICON_ERROR)
        else:
            self.spectrum.clear()
            self.start_scan()

    def on_stop(self, _event):
        self.stopScan = True
        self.stopAtEnd = False
        self.stop_scan()

    def on_stop_end(self, _event):
        self.stopAtEnd = True

    def on_event(self, event):
        status = event.data.get_status()
        freq = event.data.get_freq()
        data = event.data.get_data()
        if status == Event.STARTING:
            self.status.set_general("Starting")
        elif status == Event.STEPS:
            self.stepsTotal = (freq * 2) - 1
            self.steps = self.stepsTotal
            self.status.set_progress(0)
            self.status.show_progress()
        elif status == Event.CAL:
            self.auto_cal(Cal.DONE)
        elif status == Event.INFO:
            self.sdr = self.threadScan.get_sdr()
            if data is not None:
                self.devices[self.settings.index].tuner = data
                self.scanInfo.tuner = data
        elif status == Event.DATA:
            self.isSaved = False
            cal = self.devices[self.settings.index].calibration
            self.pool.apply_async(anaylse_data,
                                  (freq, data, cal, self.settings.nfft),
                                  callback=self.on_process_done)
            self.progress()
        elif status == Event.STOPPED:
            self.cleanup()
            self.status.set_general("Stopped")
        elif status == Event.FINISHED:
            self.threadScan = None
        elif status == Event.ERROR:
            self.cleanup()
            self.status.set_general("Error: {0}".format(data))
            if self.dlgCal is not None:
                self.dlgCal.Destroy()
                self.dlgCal = None
        elif status == Event.PROCESSED:
            offset = self.settings.devices[self.settings.index].offset
            with self.lock:
                updated = update_spectrum(self.settings.start,
                                          self.settings.stop, freq,
                                          data, offset, self.spectrum)
            if updated and self.settings.liveUpdate:
                self.plot.set_plot(self.spectrum,
                                   self.settings.annotate and \
                                   self.settings.mode == Mode.CONTIN)
            self.progress()
        elif status == Event.DRAW:
            self.graph.get_canvas().draw()

        wx.YieldIfNeeded()

    def on_process_done(self, data):
        timeStamp, freq, scan = data
        wx.PostEvent(self, EventThreadStatus(Event.PROCESSED, freq,
                                             (timeStamp, scan)))

    def open(self, dirname, filename):
        if not os.path.exists(os.path.join(dirname, filename)):
                wx.MessageBox('File not found',
                              'Error', wx.OK | wx.ICON_ERROR)

        self.filename = filename
        self.dirname = dirname
        self.status.set_general("Opening: {0}".format(filename))

        self.scanInfo, spectrum = open_plot(dirname, filename)

        if len(spectrum) > 0:
            self.spectrum.clear()
            self.scanInfo.setToSettings(self.settings)
            self.spectrum = spectrum
            self.isSaved = True
            self.set_controls()
            self.set_control_state(True)
            self.plot.clear_plots()
            self.plot.set_plot(spectrum, self.settings.annotate)
            self.status.set_general("Finished")
            self.settings.fileHistory.AddFileToHistory(os.path.join(dirname,
                                                                    filename))
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
                self.spectrum.clear()
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
        with self.lock:
            timeStamp = max(self.spectrum)
            spectrum = self.spectrum[timeStamp].copy()

            for x, y in spectrum.iteritems():
                spectrum[x] = (((x - freq) * (x - freq)) + 1) * y
                peak = max(spectrum, key=spectrum.get)

        return ((freq - peak) / freq) * 1e6

    def start_scan(self, isCal=False):
        if self.settings.mode == Mode.SINGLE:
            if self.save_warn(Warn.SCAN):
                return False

        if not self.threadScan:
            self.set_control_state(False)
            samples = calc_samples(self.settings.dwell)
            self.status.set_info('')
            self.scanInfo.setFromSettings(self.settings)
            time = datetime.datetime.utcnow().replace(microsecond=0)
            self.scanInfo.time = time.isoformat() + "Z"
            self.scanInfo.lat = None
            self.scanInfo.lon = None
            self.stopAtEnd = False
            self.stopScan = False
            self.threadScan = ThreadScan(self, self.sdr, self.settings,
                                         self.settings.index, samples, isCal)
            self.filename = "Scan {0:.1f}-{1:.1f}MHz".format(self.settings.start,
                                                            self.settings.stop)
            return True

    def stop_scan(self):
        if self.threadScan:
            self.status.set_general("Stopping")
            self.threadScan.abort()
            self.threadScan.join()
        if self.sdr is not None:
            self.sdr.close()
        self.set_control_state(True)

    def progress(self):
        self.steps -= 1
        if self.steps > -1 and not self.stopScan:
            self.status.set_progress((self.stepsTotal - self.steps) * 100
                    / self.stepsTotal)
            self.status.show_progress()
            self.status.set_general("Scanning")
        else:
            self.status.hide_progress()
            self.plot.set_plot(self.spectrum, self.settings.annotate)
            if self.stopScan:
                self.status.set_general("Stopped")
                self.cleanup()
            elif self.settings.mode == Mode.SINGLE:
                self.status.set_general("Finished")
                self.cleanup()
            else:
                if self.settings.mode == Mode.CONTIN:
                    if self.dlgCal is None and not self.stopAtEnd:
                        self.limit_spectrum()
                        self.start_scan()
                    else:
                        self.status.set_general("Stopped")
                        self.cleanup()

    def cleanup(self):
        if self.sdr is not None:
            self.sdr.close()
            self.sdr = None
        self.status.hide_progress()
        self.steps = 0
        self.threadScan = None
        self.set_control_state(True)
        self.stopAtEnd = False
        self.stopScan = True

    def limit_spectrum(self):
        with self.lock:
            while len(self.spectrum) >= self.settings.retainMax:
                timeStamp = min(self.spectrum)
                del self.spectrum[timeStamp]

    def set_control_state(self, state):
        self.spinCtrlStart.Enable(state)
        self.spinCtrlStop.Enable(state)
        self.choiceMode.Enable(state)
        self.choiceDwell.Enable(state)
        self.choiceNfft.Enable(state)
        self.buttonStart.Enable(state)
        self.buttonStop.Enable(not state)
        self.menuOpen.Enable(state)
        self.menuSave.Enable(state and len(self.spectrum) > 0)
        self.menuExport.Enable(state and len(self.spectrum) > 0)
        self.menuStart.Enable(state)
        self.menuStop.Enable(not state)
        self.menuPref.Enable(state)
        self.menuCal.Enable(state)
        self.popupMenuStop.Enable(not state)
        self.popupMenuStart.Enable(state)
        if self.settings.mode == Mode.CONTIN:
            self.menuStopEnd.Enable(not state)
            self.popupMenuStopEnd.Enable(not state)
            self.choiceDisplay.Enable(True)
        else:
            self.menuStopEnd.Enable(False)
            self.popupMenuStopEnd.Enable(False)
            self.choiceDisplay.Enable(False)

    def set_controls(self):
        self.spinCtrlStart.SetValue(self.settings.start)
        self.spinCtrlStop.SetValue(self.settings.stop)
        self.choiceMode.SetSelection(MODE[1::2].index(self.settings.mode))
        dwell = calc_real_dwell(self.settings.dwell)
        self.choiceDwell.SetSelection(DWELL[1::2].index(dwell))
        self.choiceNfft.SetSelection(NFFT.index(self.settings.nfft))
        self.choiceDisplay.SetSelection(DISPLAY[1::2].index(self.settings.display))

    def get_controls(self):
        self.settings.start = self.spinCtrlStart.GetValue()
        self.settings.stop = self.spinCtrlStop.GetValue()
        self.settings.mode = MODE[1::2][self.choiceMode.GetSelection()]
        self.settings.dwell = DWELL[1::2][self.choiceDwell.GetSelection()]
        self.settings.nfft = NFFT[self.choiceNfft.GetSelection()]
        self.settings.display = DISPLAY[1::2][self.choiceDisplay.GetSelection()]

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
        self.settings.devices = get_devices(self.devices)
        if self.settings.index > len(self.devices) - 1:
            self.settings.index = 0
        self.settings.save()
        return self.settings.devices

    def wait_background(self):
        self.Disconnect(-1, -1, EVT_THREAD_STATUS, self.on_event)
        if self.threadScan:
            self.threadScan.abort()
            self.threadScan.join()
            self.threadScan = None
        self.pool.close()
        self.pool.join()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
