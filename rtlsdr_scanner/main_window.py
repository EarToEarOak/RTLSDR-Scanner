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

import Queue
from collections import OrderedDict
import math
import os.path
import tempfile
import thread
from threading import Thread
import threading
import time
import webbrowser

import wx
from wx.lib.agw import aui
from wx.lib.masked.numctrl import NumCtrl

from location import ThreadLocation, LocationServer
from menus import MenuMain, PopMenuMain
from misc import RemoteControl, calc_samples, get_dwells, calc_real_dwell, \
    format_iso_time, limit
from rtlsdr_scanner.constants import F_MIN, F_MAX, MODE, NFFT, DISPLAY, Warn, \
    Cal, Mode, APP_NAME, LOCATION_PORT
from rtlsdr_scanner.devices import get_devices_rtl
from rtlsdr_scanner.dialogs_devices import DialogDevicesRTL, DialogDevicesGPS
from rtlsdr_scanner.dialogs_file import DialogImageSize, DialogExportSeq, DialogExportGeo, \
    DialogProperties, DialogSaveWarn, DialogRestore
from rtlsdr_scanner.dialogs_help import DialogSysInfo, DialogAbout
from rtlsdr_scanner.dialogs_prefs import DialogPrefs, DialogAdvPrefs, DialogFormatting
from rtlsdr_scanner.dialogs_scan import DialogScanDelay
from rtlsdr_scanner.dialogs_tools import DialogCompare, DialogAutoCal, DialogSats, DialogSmooth, \
    DialogLog
from rtlsdr_scanner.events import EVENT_THREAD, Event, Log, EventTimer
from rtlsdr_scanner.file import save_plot, export_plot, export_cont, open_plot, ScanInfo, export_image, \
    export_map, extension_add, File, run_file, export_gpx, Backups
from rtlsdr_scanner.panels import PanelGraph
from rtlsdr_scanner.printer import PrintOut
from rtlsdr_scanner.scan import ThreadScan, update_spectrum, ThreadProcess
from rtlsdr_scanner.settings import Settings
from rtlsdr_scanner.spectrum import count_points, Extent
from rtlsdr_scanner.toolbars import Statusbar, NavigationToolbar
from rtlsdr_scanner.utils_google import create_gearth
from rtlsdr_scanner.utils_mpl import add_colours
from rtlsdr_scanner.utils_wx import load_icon
from rtlsdr_scanner.widgets import MultiButton


class DropTarget(wx.FileDropTarget):
    def __init__(self, window):
        wx.FileDropTarget.__init__(self)
        self.window = window

    def OnDropFiles(self, _xPos, _yPos, filenames):
        if self.window.isScanning:
            return
        filename = filenames[0]
        if os.path.splitext(filename)[1].lower() == ".rfs":
            dirname, filename = os.path.split(filename)
            self.window.open(dirname, filename)


class RtlSdrScanner(wx.App):
    def __init__(self):
        try:
            wx.Dialog.EnableLayoutAdaptation(True)
        except AttributeError:
            pass
        wx.App.__init__(self, redirect=False)


class FrameMain(wx.Frame):
    def __init__(self, title):
        wx.Frame.__init__(self, None, title=title)
        self.lock = threading.Lock()

        self.sdr = None
        self.threadScan = None
        self.threadLocation = None

        self.queueScan = Queue.Queue()

        self.serverLocation = None

        self.isNewScan = True
        self.isScanning = False

        self.stopAtEnd = False
        self.stopScan = False

        self.scanDelayTimer = None

        self.dlgCal = None
        self.dlgSats = None
        self.dlgLog = None

        self.menuMain = None
        self.menuPopup = None

        self._mgr = None
        self.graph = None
        self.toolbar1 = None
        self.toolbar2 = None
        self.canvas = None

        self.buttonStart = None
        self.buttonStop = None
        self.controlGain = None
        self.choiceMode = None
        self.choiceDwell = None
        self.choiceNfft = None
        self.spinCtrlStart = None
        self.spinCtrlStop = None
        self.choiceDisplay = None

        self.spectrum = OrderedDict()
        self.scanInfo = ScanInfo()
        self.locations = OrderedDict()
        self.lastLocation = [None] * 4
        self.backups = Backups()

        self.isSaved = True

        self.settings = Settings()
        self.devicesRtl = get_devices_rtl(self.settings.devicesRtl)
        self.settings.indexRtl = limit(self.settings.indexRtl,
                                       0, len(self.devicesRtl) - 1)
        self.filename = ""
        self.exportCont = None

        self.oldCal = 0

        self.remoteControl = None

        self.log = Log()

        self.pageConfig = wx.PageSetupDialogData()
        self.pageConfig.GetPrintData().SetOrientation(wx.LANDSCAPE)
        self.pageConfig.SetMarginTopLeft((20, 20))
        self.pageConfig.SetMarginBottomRight((20, 20))
        self.printConfig = wx.PrintDialogData(self.pageConfig.GetPrintData())
        self.printConfig.EnableSelection(False)
        self.printConfig.EnablePageNumbers(False)

        self.timerGpsRetry = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.__on_gps_retry, self.timerGpsRetry)

        self.Bind(wx.EVT_CLOSE, self.__on_exit)

        self.status = Statusbar(self, self.log)
        self.status.set_info(title)
        self.SetStatusBar(self.status)

        add_colours()
        self.__create_toolbars()
        self.__create_menu()
        self.__create_popup_menu()
        self.__set_control_state(True)
        self.__set_size()
        self.Show()

        self.Connect(-1, -1, EVENT_THREAD, self.__on_event)

        self.SetDropTarget(DropTarget(self))

        self.SetIcon(load_icon('icon'))

        self.steps = 0
        self.stepsTotal = 0

        self.__start_gps()
        self.__start_location_server()

    def __create_toolbars(self):
        self.remoteControl = RemoteControl()

        self.graph = PanelGraph(self, self,
                                self.settings, self.status,
                                self.remoteControl)

        self.toolbar1 = wx.Panel(self)

        self.buttonStart = MultiButton(self.toolbar1,
                                       ['Start', 'Continue'],
                                       ['Start new scan', 'Continue scanning'])
        self.buttonStart.SetSelected(self.settings.startOption)
        self.buttonStop = MultiButton(self.toolbar1,
                                      ['Stop', 'Stop at end'],
                                      ['Stop scan', 'Stop scan at end'])
        self.buttonStop.SetSelected(self.settings.stopOption)
        self.Bind(wx.EVT_BUTTON, self.__on_start, self.buttonStart)
        self.Bind(wx.EVT_BUTTON, self.__on_stop, self.buttonStop)

        textRange = wx.StaticText(self.toolbar1, label="Range (MHz)",
                                  style=wx.ALIGN_CENTER)
        textStart = wx.StaticText(self.toolbar1, label="Start")
        textStop = wx.StaticText(self.toolbar1, label="Stop")

        self.spinCtrlStart = wx.SpinCtrl(self.toolbar1)
        self.spinCtrlStop = wx.SpinCtrl(self.toolbar1)
        self.spinCtrlStart.SetToolTipString('Start frequency')
        self.spinCtrlStop.SetToolTipString('Stop frequency')
        self.spinCtrlStart.SetRange(F_MIN, F_MAX - 1)
        self.spinCtrlStop.SetRange(F_MIN + 1, F_MAX)
        self.Bind(wx.EVT_SPINCTRL, self.__on_spin, self.spinCtrlStart)
        self.Bind(wx.EVT_SPINCTRL, self.__on_spin, self.spinCtrlStop)

        textGain = wx.StaticText(self.toolbar1, label="Gain (dB)")
        self.controlGain = wx.Choice(self.toolbar1, choices=[''])

        grid1 = wx.GridBagSizer(5, 5)
        grid1.Add(self.buttonStart, pos=(0, 0), span=(3, 1),
                  flag=wx.ALIGN_CENTER)
        grid1.Add(self.buttonStop, pos=(0, 1), span=(3, 1),
                  flag=wx.ALIGN_CENTER)
        grid1.Add((20, 1), pos=(0, 2))
        grid1.Add(textRange, pos=(0, 3), span=(1, 4), flag=wx.ALIGN_CENTER)
        grid1.Add(textStart, pos=(1, 3), flag=wx.ALIGN_CENTER)
        grid1.Add(self.spinCtrlStart, pos=(1, 4))
        grid1.Add(textStop, pos=(1, 5), flag=wx.ALIGN_CENTER)
        grid1.Add(self.spinCtrlStop, pos=(1, 6))
        grid1.Add(textGain, pos=(0, 7), flag=wx.ALIGN_CENTER)
        grid1.Add(self.controlGain, pos=(1, 7), flag=wx.ALIGN_CENTER)
        grid1.Add((5, 1), pos=(0, 8))
        grid1.AddGrowableCol(2)

        self.toolbar2 = wx.Window(self)

        textMode = wx.StaticText(self.toolbar2, label="Mode")
        self.choiceMode = wx.Choice(self.toolbar2, choices=MODE[::2])
        self.choiceMode.SetToolTipString('Scanning mode')

        textDwell = wx.StaticText(self.toolbar2, label="Dwell")
        self.choiceDwell = wx.Choice(self.toolbar2, choices=get_dwells()[::2])
        self.choiceDwell.SetToolTipString('Scan time per step')

        textNfft = wx.StaticText(self.toolbar2, label="FFT size")
        self.choiceNfft = wx.Choice(self.toolbar2, choices=map(str, NFFT))
        self.choiceNfft.SetToolTipString('Higher values for greater'
                                         'precision')

        textDisplay = wx.StaticText(self.toolbar2, label="Display")
        self.choiceDisplay = wx.Choice(self.toolbar2, choices=DISPLAY[::2])
        self.Bind(wx.EVT_CHOICE, self.__on_choice, self.choiceDisplay)
        self.choiceDisplay.SetToolTipString('Spectrogram available in'
                                            'continuous mode')

        grid2 = wx.GridBagSizer(5, 5)
        grid2.Add(textMode, pos=(0, 0), flag=wx.ALIGN_CENTER)
        grid2.Add(self.choiceMode, pos=(1, 0), flag=wx.ALIGN_CENTER)
        grid2.Add(textDwell, pos=(0, 1), flag=wx.ALIGN_CENTER)
        grid2.Add(self.choiceDwell, pos=(1, 1), flag=wx.ALIGN_CENTER)
        grid2.Add(textNfft, pos=(0, 2), flag=wx.ALIGN_CENTER)
        grid2.Add(self.choiceNfft, pos=(1, 2), flag=wx.ALIGN_CENTER)
        grid2.Add((20, 1), pos=(0, 3))
        grid2.Add(textDisplay, pos=(0, 4), flag=wx.ALIGN_CENTER)
        grid2.Add(self.choiceDisplay, pos=(1, 4), flag=wx.ALIGN_CENTER)
        grid2.Add((5, 1), pos=(0, 5))
        grid2.AddGrowableCol(3)

        self.toolbar1.SetSizerAndFit(grid1)
        self.toolbar1.Layout()
        toolSize1 = self.toolbar1.GetMinSize()
        self.toolbar2.SetSizerAndFit(grid2)
        self.toolbar2.Layout()
        toolSize2 = self.toolbar2.GetMinSize()

        self.__set_controls()
        self.__set_gain_control()

        self._mgr = aui.AuiManager(self)
        self._mgr.AddPane(self.graph, aui.AuiPaneInfo().
                          Centre().
                          CentrePane())
        self._mgr.AddPane(self.toolbar1, aui.AuiPaneInfo().
                          ToolbarPane().
                          Bottom().
                          Layer(1).
                          LeftDockable(False).
                          RightDockable(False).
                          NotebookDockable(False).
                          Gripper().
                          Caption('Scan').
                          CaptionVisible(left=True).
                          CloseButton(False).
                          MinimizeButton(True).
                          MinSize(toolSize1))
        self._mgr.AddPane(self.toolbar2, aui.AuiPaneInfo().
                          ToolbarPane().
                          Bottom().
                          Layer(2).
                          LeftDockable(False).
                          RightDockable(False).
                          NotebookDockable(False).
                          Gripper().
                          Caption('Analysis').
                          CaptionVisible(left=True).
                          CloseButton(False).
                          MinimizeButton(True).
                          MinSize(toolSize2))
        self._mgr.Update()

    def __create_menu(self):
        self.menuMain = MenuMain(self, self.settings)

        self.Bind(wx.EVT_MENU, self.__on_new, self.menuMain.new)
        self.Bind(wx.EVT_MENU, self.__on_open, self.menuMain.open)
        self.Bind(wx.EVT_MENU, self.__on_merge, self.menuMain.merge)
        self.Bind(wx.EVT_MENU, self.__on_backups, self.menuMain.restore)
        self.Bind(wx.EVT_MENU_RANGE, self.__on_file_history,
                  id=wx.ID_FILE1, id2=wx.ID_FILE9)
        self.Bind(wx.EVT_MENU, self.__on_save, self.menuMain.save)
        self.Bind(wx.EVT_MENU, self.__on_export_scan, self.menuMain.exportScan)
        self.Bind(wx.EVT_MENU, self.__on_export_image, self.menuMain.exportImage)
        self.Bind(wx.EVT_MENU, self.__on_export_image_seq, self.menuMain.exportSeq)
        self.Bind(wx.EVT_MENU, self.__on_export_geo, self.menuMain.exportGeo)
        self.Bind(wx.EVT_MENU, self.__on_export_track, self.menuMain.exportTrack)
        self.Bind(wx.EVT_MENU, self.__on_export_cont, self.menuMain.exportCont)
        self.Bind(wx.EVT_MENU, self.__on_page, self.menuMain.page)
        self.Bind(wx.EVT_MENU, self.__on_preview, self.menuMain.preview)
        self.Bind(wx.EVT_MENU, self.__on_print, self.menuMain.printer)
        self.Bind(wx.EVT_MENU, self.__on_properties, self.menuMain.properties)
        self.Bind(wx.EVT_MENU, self.__on_exit, self.menuMain.close)
        self.Bind(wx.EVT_MENU, self.__on_pref, self.menuMain.pref)
        self.Bind(wx.EVT_MENU, self.__on_adv_pref, self.menuMain.advPref)
        self.Bind(wx.EVT_MENU, self.__on_formatting, self.menuMain.formatting)
        self.Bind(wx.EVT_MENU, self.__on_devices_rtl, self.menuMain.devicesRtl)
        self.Bind(wx.EVT_MENU, self.__on_devices_gps, self.menuMain.devicesGps)
        self.Bind(wx.EVT_MENU, self.__on_reset, self.menuMain.reset)
        self.Bind(wx.EVT_MENU, self.__on_clear_select, self.menuMain.clearSelect)
        self.Bind(wx.EVT_MENU, self.__on_show_measure, self.menuMain.showMeasure)
        self.Bind(wx.EVT_MENU, self.__on_fullscreen, self.menuMain.fullScreen)
        self.Bind(wx.EVT_MENU, self.__on_start, self.menuMain.start)
        self.Bind(wx.EVT_MENU, self.__on_continue, self.menuMain.cont)
        self.Bind(wx.EVT_MENU, self.__on_stop, self.menuMain.stop)
        self.Bind(wx.EVT_MENU, self.__on_stop_end, self.menuMain.stopEnd)
        self.Bind(wx.EVT_MENU, self.__on_new, self.menuMain.sweepClear)
        self.Bind(wx.EVT_MENU, self.__on_sweep_remain, self.menuMain.sweepRemain)
        self.Bind(wx.EVT_MENU, self.__on_scan_delay, self.menuMain.sweepDelay)
        self.Bind(wx.EVT_MENU, self.__on_compare, self.menuMain.compare)
        self.Bind(wx.EVT_MENU, self.__on_smooth, self.menuMain.smooth)
        self.Bind(wx.EVT_MENU, self.__on_cal, self.menuMain.cal)
        self.Bind(wx.EVT_MENU, self.__on_gearth, self.menuMain.gearth)
        self.Bind(wx.EVT_MENU, self.__on_gmaps, self.menuMain.gmaps)
        self.Bind(wx.EVT_MENU, self.__on_sats, self.menuMain.sats)
        self.Bind(wx.EVT_MENU, self.__on_loc_clear, self.menuMain.locClear)
        self.Bind(wx.EVT_MENU, self.__on_log, self.menuMain.log)
        self.Bind(wx.EVT_MENU, self.__on_help, self.menuMain.helpLink)
        self.Bind(wx.EVT_MENU, self.__on_sys_info, self.menuMain.sys)
        self.Bind(wx.EVT_MENU, self.__on_about, self.menuMain.about)

        idF1 = wx.wx.NewId()
        self.Bind(wx.EVT_MENU, self.__on_help, id=idF1)
        accelTable = wx.AcceleratorTable([(wx.ACCEL_NORMAL, wx.WXK_F1, idF1)])
        self.SetAcceleratorTable(accelTable)

        self.Bind(wx.EVT_MENU_HIGHLIGHT, self.__on_menu_highlight)

        self.SetMenuBar(self.menuMain.menuBar)

    def __create_popup_menu(self):
        self.menuPopup = PopMenuMain(self.settings)

        self.Bind(wx.EVT_MENU, self.__on_start, self.menuPopup.start)
        self.Bind(wx.EVT_MENU, self.__on_continue, self.menuPopup.cont)
        self.Bind(wx.EVT_MENU, self.__on_stop, self.menuPopup.stop)
        self.Bind(wx.EVT_MENU, self.__on_stop_end, self.menuPopup.stopEnd)
        self.Bind(wx.EVT_MENU, self.__on_scan_delay, self.menuPopup.sweepDelay)
        self.Bind(wx.EVT_MENU, self.__on_range_lim, self.menuPopup.rangeLim)
        self.Bind(wx.EVT_MENU, self.__on_points_lim, self.menuPopup.pointsLim)
        self.Bind(wx.EVT_MENU, self.__on_clear_select, self.menuPopup.clearSelect)
        self.Bind(wx.EVT_MENU, self.__on_show_measure, self.menuPopup.showMeasure)
        self.Bind(wx.EVT_MENU, self.__on_fullscreen, self.menuPopup.fullScreen)

        self.Bind(wx.EVT_CONTEXT_MENU, self.__on_popup_menu)

    def __on_menu_highlight(self, event):
        item = self.GetMenuBar().FindItemById(event.GetId())
        if item is not None:
            help = item.GetHelp()
        else:
            help = ''

        self.status.set_general(help, level=None)

    def __on_popup_menu(self, event):
        if not isinstance(event.GetEventObject(), NavigationToolbar):
            pos = event.GetPosition()
            pos = self.ScreenToClient(pos)
            self.PopupMenu(self.menuPopup.menu, pos)

    def __on_new(self, _event):
        if self.__save_warn(Warn.NEW):
            return True
        self.spectrum.clear()
        self.locations.clear()
        self.__saved(True)
        self.__set_plot(self.spectrum, False)
        self.graph.clear_selection()
        self.__set_control_state(True)
        return False

    def __on_open(self, _event):
        if self.__save_warn(Warn.OPEN):
            return

        dlg = wx.FileDialog(self, "Open a scan", self.settings.dirScans,
                            self.filename,
                            File.get_type_filters(File.Types.SAVE),
                            wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.open(dlg.GetDirectory(), dlg.GetFilename())
        dlg.Destroy()

    def __on_merge(self, _event):
        if self.__save_warn(Warn.MERGE):
            return

        dlg = wx.FileDialog(self, "Merge a scan", self.settings.dirScans,
                            self.filename,
                            File.get_type_filters(File.Types.SAVE),
                            wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.__merge(dlg.GetDirectory(), dlg.GetFilename())
        dlg.Destroy()

    def __on_backups(self, _event):
        dlg = DialogRestore(self, self.backups)
        if dlg.ShowModal() == wx.ID_OPEN:
            if self.__save_warn(Warn.OPEN):
                return
            data = dlg.get_restored()
            self.scanInfo, spectrum, locations = data
            self.spectrum.clear()
            self.locations.clear()
            self.spectrum.update(OrderedDict(sorted(spectrum.items())))
            self.locations.update(OrderedDict(sorted(locations.items())))
            self.__set_plot(self.spectrum, self.settings.annotate)
            self.graph.scale_plot(True)
            self.status.set_general("Finished")

    def __on_file_history(self, event):
        selection = event.GetId() - wx.ID_FILE1
        path = self.settings.fileHistory.GetHistoryFile(selection)
        self.settings.fileHistory.AddFileToHistory(path)
        dirname, filename = os.path.split(path)
        self.open(dirname, filename)

    def __on_save(self, _event):
        dlg = wx.FileDialog(self, "Save a scan", self.settings.dirScans,
                            self.filename,
                            File.get_type_filters(File.Types.SAVE),
                            wx.SAVE | wx.OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            self.status.set_general("Saving...")
            fileName = dlg.GetFilename()
            dirName = dlg.GetDirectory()
            self.filename = os.path.splitext(fileName)[0]
            self.settings.dirScans = dirName
            fileName = extension_add(fileName, dlg.GetFilterIndex(),
                                     File.Types.SAVE)
            fullName = os.path.join(dirName, fileName)
            save_plot(fullName, self.scanInfo, self.spectrum, self.locations)
            self.__saved(True)
            self.status.set_general("Finished")
            self.settings.fileHistory.AddFileToHistory(fullName)
        dlg.Destroy()

    def __on_export_scan(self, _event):
        dlg = wx.FileDialog(self, "Export a scan", self.settings.dirExport,
                            self.filename, File.get_type_filters(),
                            wx.SAVE | wx.OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            self.status.set_general("Exporting...")
            fileName = dlg.GetFilename()
            dirName = dlg.GetDirectory()
            self.settings.dirExport = dirName
            fileName = extension_add(fileName, dlg.GetFilterIndex(),
                                     File.Types.PLOT)
            fullName = os.path.join(dirName, fileName)
            export_plot(fullName, dlg.GetFilterIndex(), self.spectrum)
            self.status.set_general("Finished")
        dlg.Destroy()

    def __on_export_image(self, _event):
        dlgFile = wx.FileDialog(self, "Export image to file",
                                self.settings.dirExport,
                                self.filename,
                                File.get_type_filters(File.Types.IMAGE),
                                wx.SAVE | wx.OVERWRITE_PROMPT)
        dlgFile.SetFilterIndex(File.ImageType.PNG)
        if dlgFile.ShowModal() == wx.ID_OK:
            dlgImg = DialogImageSize(self, self.settings)
            if dlgImg.ShowModal() != wx.ID_OK:
                dlgFile.Destroy()
                return

            self.status.set_general("Exporting...")
            fileName = dlgFile.GetFilename()
            dirName = dlgFile.GetDirectory()
            self.settings.dirExport = dirName
            fileName = extension_add(fileName, dlgFile.GetFilterIndex(),
                                     File.Types.IMAGE)
            fullName = os.path.join(dirName, fileName)
            exportType = dlgFile.GetFilterIndex()
            export_image(fullName, exportType,
                         self.graph.get_figure(),
                         self.settings)
            self.status.set_general("Finished")
        dlgFile.Destroy()

    def __on_export_image_seq(self, _event):
        dlgSeq = DialogExportSeq(self, self.spectrum, self.settings)
        dlgSeq.ShowModal()
        dlgSeq.Destroy()

    def __on_export_geo(self, _event):
        dlgGeo = DialogExportGeo(self, self.spectrum, self.locations, self.settings)
        if dlgGeo.ShowModal() == wx.ID_OK:
            self.status.set_general("Exporting...")
            extent = dlgGeo.get_extent()
            dlgFile = wx.FileDialog(self, "Export map to file",
                                    self.settings.dirExport,
                                    self.filename,
                                    File.get_type_filters(File.Types.GEO),
                                    wx.SAVE | wx.OVERWRITE_PROMPT)
            dlgFile.SetFilterIndex(File.GeoType.KMZ)
            if dlgFile.ShowModal() == wx.ID_OK:
                fileName = dlgFile.GetFilename()
                dirName = dlgFile.GetDirectory()
                self.settings.dirExport = dirName
                fileName = extension_add(fileName, dlgFile.GetFilterIndex(),
                                         File.Types.GEO)
                fullName = os.path.join(dirName, fileName)
                exportType = dlgFile.GetFilterIndex()
                image = None
                xyz = None
                if exportType == File.GeoType.CSV:
                    xyz = dlgGeo.get_xyz()
                else:
                    image = dlgGeo.get_image()
                export_map(fullName, exportType, extent, image, xyz)
            self.status.set_general("Finished")
            dlgFile.Destroy()
        dlgGeo.Destroy()

    def __on_export_track(self, _event):
        dlg = wx.FileDialog(self, "Export GPS to file",
                            self.settings.dirExport,
                            self.filename,
                            File.get_type_filters(File.Types.TRACK),
                            wx.SAVE | wx.OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            self.status.set_general("Exporting...")
            fileName = dlg.GetFilename()
            dirName = dlg.GetDirectory()
            self.settings.dirExport = dirName
            fileName = extension_add(fileName, dlg.GetFilterIndex(),
                                     File.Types.TRACK)
            fullName = os.path.join(dirName, fileName)
            export_gpx(fullName, self.locations, self.GetName())
            self.status.set_general("Finished")
        dlg.Destroy()

    def __on_export_cont(self, _event):
        if self.exportCont is None:
            dlg = wx.FileDialog(self, 'Continuous export',
                                self.settings.dirExport, '',
                                File.get_type_filters(File.Types.CONT),
                                wx.SAVE | wx.OVERWRITE_PROMPT)
            if dlg.ShowModal() == wx.ID_OK:
                fileName = dlg.GetFilename()
                dirName = dlg.GetDirectory()
                self.settings.dirExport = dirName
                fileName = extension_add(fileName, dlg.GetFilterIndex(),
                                         File.Types.CONT)
                fullName = os.path.join(dirName, fileName)
                self.exportCont = export_cont(self.exportCont, fullName, None)
                self.status.set_general('Continuous export started')
            dlg.Destroy()
        else:
            self.exportCont.close()
            self.exportCont = None
            self.status.set_general('Continuous export stopped')

    def __on_page(self, _event):
        dlg = wx.PageSetupDialog(self, self.pageConfig)
        if dlg.ShowModal() == wx.ID_OK:
            self.pageConfig = wx.PageSetupDialogData(dlg.GetPageSetupDialogData())
            self.printConfig.SetPrintData(self.pageConfig.GetPrintData())
        dlg.Destroy()

    def __on_preview(self, _event):
        printout = PrintOut(self.graph, self.filename, self.pageConfig)
        printoutPrinting = PrintOut(self.graph, self.filename, self.pageConfig)
        preview = wx.PrintPreview(printout, printoutPrinting, self.printConfig)
        frame = wx.PreviewFrame(preview, self, 'Print Preview')
        frame.Initialize()
        frame.SetSize(self.GetSize())
        frame.Show(True)

    def __on_print(self, _event):
        printer = wx.Printer(self.printConfig)
        printout = PrintOut(self.graph, self.filename, self.pageConfig)
        if printer.Print(self, printout, True):
            self.printConfig = wx.PrintDialogData(printer.GetPrintDialogData())
            self.pageConfig.SetPrintData(self.printConfig.GetPrintData())

    def __on_properties(self, _event):
        if len(self.spectrum) > 0:
            self.scanInfo.timeFirst = min(self.spectrum)
            self.scanInfo.timeLast = max(self.spectrum)

        dlg = DialogProperties(self, self.scanInfo)
        dlg.ShowModal()
        dlg.Destroy()

    def __on_exit(self, _event):
        self.Unbind(wx.EVT_CLOSE)
        self.backups.close()
        if self.__save_warn(Warn.EXIT):
            self.Bind(wx.EVT_CLOSE, self.__on_exit)
            return
        self.__scan_stop(False)
        self.__stop_gps(False)
        self.__stop_location_server()
        self.__get_controls()
        self.settings.devicesRtl = self.devicesRtl
        self.settings.save()
        self.graph.close()
        self.Destroy()

    def __on_pref(self, _event):
        self.__get_controls()
        dlg = DialogPrefs(self, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            self.graph.create_plot()
            self.__set_control_state(True)
            self.__set_controls()
        dlg.Destroy()

    def __on_adv_pref(self, _event):
        dlg = DialogAdvPrefs(self, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            self.__set_control_state(True)
        dlg.Destroy()

    def __on_formatting(self, _event):
        dlg = DialogFormatting(self, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            self.__set_control_state(True)
            self.graph.update_measure()
            self.graph.redraw_plot()
        dlg.Destroy()

    def __on_devices_rtl(self, _event):
        self.__get_controls()
        self.devicesRtl = self.__refresh_devices()
        dlg = DialogDevicesRTL(self, self.devicesRtl, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            self.devicesRtl = dlg.get_devices()
            self.settings.indexRtl = dlg.get_index()
            self.__set_gain_control()
            self.__set_control_state(True)
            self.__set_controls()
        dlg.Destroy()

    def __on_devices_gps(self, _event):
        self.__stop_gps()
        self.status.set_gps('GPS Stopped')
        dlg = DialogDevicesGPS(self, self.settings)
        dlg.ShowModal()
        dlg.Destroy()
        self.__start_gps()

    def __on_reset(self, _event):
        dlg = wx.MessageDialog(self,
                               'Reset all settings to the default values\n'
                               '(cannot be undone)?',
                               'Reset Settings',
                               wx.YES_NO | wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_YES:
            self.devicesRtl = []
            self.settings.reset()
            self.__set_controls()
            self.graph.create_plot()
        dlg.Destroy()

    def __on_compare(self, _event):
        dlg = DialogCompare(self, self.settings, self.filename)
        dlg.Show()

    def __on_smooth(self, _event):
        dlg = DialogSmooth(self, self.spectrum, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            saved = self.isSaved
            self.isSaved = False
            if not self.__on_new(None):
                self.spectrum.clear()
                spectrum = dlg.get_spectrum()
                self.spectrum.update(spectrum.items())
                self.__set_plot(self.spectrum, False)
                self.graph.update_measure()
                self.graph.redraw_plot()
                self.filename += ' - smoothed'
                self.__saved(False)
            else:
                self.__saved(saved)

    def __on_clear_select(self, _event):
        self.graph.clear_selection()

    def __on_show_measure(self, event):
        show = event.Checked()
        self.menuMain.showMeasure.Check(show)
        self.menuPopup.showMeasure.Check(show)
        self.settings.showMeasure = show
        self.graph.show_measure_table(show)
        self.Layout()

    def __on_fullscreen(self, _event):
        full = not self.IsFullScreen()

        self.menuMain.fullScreen = full
        self.menuPopup.fullScreen = full

        self._mgr.GetPane(self.toolbar1).Show(not full)
        self._mgr.GetPane(self.toolbar2).Show(not full)
        self._mgr.Update()
        self.graph.hide_toolbar(full)
        self.graph.show_measure_table(not full)
        self.ShowFullScreen(full)
        self.Layout()

    def __on_cal(self, _event):
        self.dlgCal = DialogAutoCal(self, self.settings.calFreq, self.__auto_cal)
        self.dlgCal.ShowModal()

    def __on_gearth(self, _event):
        tempPath = tempfile.mkdtemp()
        tempFile = os.path.join(tempPath, 'RTLSDRScannerLink.kml')
        handle = open(tempFile, 'wb')
        create_gearth(handle)
        handle.close()

        if not run_file(tempFile):
            wx.MessageBox('Error starting Google Earth', 'Error',
                          wx.OK | wx.ICON_ERROR)

    def __on_gmaps(self, _event):
        url = 'http://localhost:{}/rtlsdr_scan.html'.format(LOCATION_PORT)
        webbrowser.open_new(url)

    def __on_sats(self, _event):
        if self.dlgSats is None:
            self.dlgSats = DialogSats(self)
            self.dlgSats.Show()

    def __on_loc_clear(self, _event):
        result = wx.MessageBox('Remove {} locations from scan?'.format(len(self.locations)),
                               'Clear location data',
                               wx.YES_NO, self)
        if result == wx.YES:
            self.locations.clear()
            self.__set_control_state(True)

    def __on_log(self, _event):
        if self.dlgLog is None:
            self.dlgLog = DialogLog(self, self.log)
            self.dlgLog.Show()

    def __on_help(self, _event):
        webbrowser.open("http://eartoearoak.com/software/rtlsdr-scanner")

    def __on_sys_info(self, _event):
        dlg = DialogSysInfo(self)
        dlg.ShowModal()
        dlg.Destroy()

    def __on_about(self, _event):
        dlg = DialogAbout(self)
        dlg.ShowModal()
        dlg.Destroy()

    def __on_spin(self, event):
        control = event.GetEventObject()
        if control == self.spinCtrlStart:
            self.spinCtrlStop.SetRange(self.spinCtrlStart.GetValue() + 1,
                                       F_MAX)

    def __on_choice(self, _event):
        self.__get_controls()
        self.graph.create_plot()

    def __on_start(self, event):
        self.__get_controls()

        if self.settings.start >= self.settings.stop:
            wx.MessageBox('Stop frequency must be greater that start',
                          'Warning', wx.OK | wx.ICON_WARNING)
            return

        self.devicesRtl = self.__refresh_devices()
        if len(self.devicesRtl) == 0:
            wx.MessageBox('No devices found',
                          'Error', wx.OK | wx.ICON_ERROR)
        else:
            if event.GetInt() == 0:
                self.isNewScan = True
            else:
                self.isNewScan = False
            self.__scan_start()
            if not self.settings.retainScans:
                self.status.set_info('Warning: Averaging is enabled in preferences',
                                     level=Log.WARN)

    def __on_continue(self, event):
        event.SetInt(1)
        self.__on_start(event)

    def __on_stop(self, event):
        if event.GetInt() == 0:
            self.stopScan = True
            self.stopAtEnd = False
            self.__scan_stop()
        else:
            self.stopScan = False
            self.stopAtEnd = True

    def __on_stop_end(self, _event):
        self.stopAtEnd = True

    def __on_sweep_remain(self, _event):
        if self.__save_warn(Warn.NEW):
            return True

        with self.lock:
            self.__remove_last(self.spectrum)
            self.__remove_last(self.locations)

        self.__saved(False)
        self.__set_plot(self.spectrum, False)
        self.__set_control_state(True)

    def __on_scan_delay(self, _event):
        dlg = DialogScanDelay(self, self.settings)
        dlg.ShowModal()
        dlg.Destroy()

    def __on_range_lim(self, _event):
        xmin, xmax = self.graph.get_axes().get_xlim()
        xmin = int(xmin)
        xmax = math.ceil(xmax)
        if xmax < xmin + 1:
            xmax = xmin + 1
        self.settings.start = xmin
        self.settings.stop = xmax
        self.__set_controls()

    def __on_points_lim(self, _event):
        self.settings.pointsLimit = self.menuPopup.pointsLim.IsChecked()
        self.__set_plot(self.spectrum, self.settings.annotate)

    def __on_gps_retry(self, _event):
        self.timerGpsRetry.Stop()
        self.__stop_gps()
        self.__start_gps()

    def __on_event(self, event):
        status = event.data.get_status()
        arg1 = event.data.get_arg1()
        arg2 = event.data.get_arg2()
        if status == Event.STARTING:
            self.status.set_general("Starting")
            self.isScanning = True
        elif status == Event.STEPS:
            self.stepsTotal = (arg1 + 1) * 2
            self.steps = self.stepsTotal
            self.status.set_progress(0)
            self.status.show_progress()
        elif status == Event.CAL:
            self.__auto_cal(Cal.DONE)
        elif status == Event.INFO:
            if self.threadScan is not None:
                self.sdr = self.threadScan.get_sdr()
                if arg2 is not None:
                    self.devicesRtl[self.settings.indexRtl].tuner = arg2
                    self.scanInfo.tuner = arg2
        elif status == Event.DATA:
            self.__saved(False)
            cal = self.devicesRtl[self.settings.indexRtl].calibration
            levelOff = self.devicesRtl[self.settings.indexRtl].levelOff
            freq, scan = self.queueScan.get()
            process = ThreadProcess(self, freq, scan, cal, levelOff,
                                    self.settings.nfft,
                                    self.settings.overlap,
                                    self.settings.winFunc)
            process.start()
            self.__progress()
        elif status == Event.STOPPED:
            self.__cleanup()
            self.status.set_general("Stopped")
        elif status == Event.FINISHED:
            self.threadScan = None
        elif status == Event.ERROR:
            self.__cleanup()
            self.status.set_general("Error: {}".format(arg2), level=Log.ERROR)
            if self.dlgCal is not None:
                self.dlgCal.Destroy()
                self.dlgCal = None
            wx.MessageBox(arg2, 'Error',
                          wx.OK | wx.ICON_ERROR)
        elif status == Event.PROCESSED:
            offset = self.settings.devicesRtl[self.settings.indexRtl].offset
            if self.settings.alert:
                alert = self.settings.alertLevel
            else:
                alert = None
            try:
                Thread(target=update_spectrum, name='Update',
                       args=(self, self.lock,
                             self.settings.start,
                             self.settings.stop,
                             arg1,
                             offset,
                             self.spectrum,
                             not self.settings.retainScans,
                             alert)).start()
            except thread.error:
                self.__cleanup()
                self.__scan_stop(False)
                wx.MessageBox('Out of memory', 'Error',
                              wx.OK | wx.ICON_ERROR)
        elif status == Event.LEVEL:
            wx.Bell()
        elif status == Event.UPDATED:
            if arg2 and self.settings.liveUpdate:
                self.__set_plot(self.spectrum,
                                self.settings.annotate and
                                self.settings.retainScans and
                                self.settings.mode == Mode.CONTIN)
            self.__progress()
        elif status == Event.DRAW:
            self.graph.draw()
        elif status == Event.DELAY_COUNT:
            self.status.set_general('Delaying sweep', Log.INFO)
            progress = (float(arg1 - arg2) / arg1) * 100.
            self.status.set_progress(progress)
            self.status.show_progress()
        elif status == Event.DELAY_START:
            self.status.hide_progress()
            self.__scan_start()
        elif status == Event.LOC_WARN:
            self.status.set_gps("{}".format(arg2), level=Log.WARN)
            self.status.warn_gps()
        elif status == Event.LOC_ERR:
            self.status.set_gps("{}".format(arg2), level=Log.ERROR)
            self.status.error_gps()
            self.threadLocation = None
            if self.settings.gpsRetry:
                if not self.timerGpsRetry.IsRunning():
                    self.timerGpsRetry.Start(20000, True)
        elif status == Event.LOC:
            self.__update_location(arg2)
        elif status == Event.LOC_SAT:
            if self.dlgSats is not None:
                self.dlgSats.set_sats(arg2)

        wx.YieldIfNeeded()

    def __auto_cal(self, status):
        freq = self.dlgCal.get_arg1()
        if self.dlgCal is not None:
            if status == Cal.START:
                self.spinCtrlStart.SetValue(int(freq))
                self.spinCtrlStop.SetValue(math.ceil(freq))
                self.oldCal = self.devicesRtl[self.settings.indexRtl].calibration
                self.devicesRtl[self.settings.indexRtl].calibration = 0
                self.__get_controls()
                self.spectrum.clear()
                self.locations.clear()
                if not self.__scan_start(isCal=True):
                    self.dlgCal.reset_cal()
            elif status == Cal.DONE:
                ppm = self.__calc_ppm(freq)
                self.dlgCal.set_cal(ppm)
                self.__set_control_state(True)
            elif status == Cal.OK:
                self.devicesRtl[self.settings.indexRtl].calibration = self.dlgCal.get_cal()
                self.settings.calFreq = freq
                self.dlgCal = None
            elif status == Cal.CANCEL:
                self.dlgCal = None
                if len(self.devicesRtl) > 0:
                    self.devicesRtl[self.settings.indexRtl].calibration = self.oldCal

    def __calc_ppm(self, freq):
        with self.lock:
            timeStamp = max(self.spectrum)
            spectrum = self.spectrum[timeStamp].copy()

            for x, y in spectrum.iteritems():
                spectrum[x] = (((x - freq) * (x - freq)) + 1) * y
                peak = max(spectrum, key=spectrum.get)

        return ((freq - peak) / freq) * 1e6

    def __scan_delay(self):
        if self.settings.scanDelay == 0:
            self.__scan_start()
        else:
            if self.scanDelayTimer is not None:
                self.scanDelayTimer.Stop()
            self.scanDelayTimer = EventTimer(self, self.settings.scanDelay)

    def __scan_start(self, isCal=False):
        if self.isNewScan and self.__save_warn(Warn.SCAN):
            return False

        if not self.threadScan:
            if self.scanDelayTimer is not None:
                self.scanDelayTimer.Stop()
                self.scanDelayTimer = None
            self.__set_control_state(False)
            samples = calc_samples(self.settings.dwell)
            self.scanInfo.set_from_settings(self.settings)
            if self.isNewScan:
                self.spectrum.clear()
                self.locations.clear()
                self.graph.clear_plots()

                self.isNewScan = False
                self.status.set_info('', level=None)
                self.scanInfo.time = format_iso_time(time.time())
                self.scanInfo.lat = None
                self.scanInfo.lon = None
                self.scanInfo.desc = ''

            self.stopAtEnd = False
            self.stopScan = False
            self.threadScan = ThreadScan(self, self.queueScan, self.sdr, self.settings,
                                         self.settings.indexRtl, samples, isCal)
            self.filename = "Scan {0:.1f}-{1:.1f}MHz".format(self.settings.start,
                                                             self.settings.stop)
            self.graph.set_plot_title()

            self.__start_gps()

            return True

    def __scan_stop(self, join=True):
        if self.threadScan:
            self.status.set_general("Stopping")
            self.threadScan.abort()
            if join:
                self.threadScan.join()
        self.threadScan = None
        if self.sdr is not None:
            self.sdr.close()
        self.__set_control_state(True)

    def __progress(self):
        if self.steps == self.stepsTotal:
            self.status.set_general("Scanning ({} sweeps)".format(len(self.spectrum)))
        self.steps -= 1
        if self.steps > 0 and not self.stopScan:
            self.status.set_progress((self.stepsTotal - self.steps) * 100.0
                                     / (self.stepsTotal - 1))
            self.__limit_spectrum()
            self.status.show_progress()
        else:
            if self.settings.backup:
                self.backups.save(self.scanInfo, self.spectrum, self.locations)
            self.status.hide_progress()
            self.__set_plot(self.spectrum, self.settings.annotate)
            if self.exportCont is not None:
                last = next(reversed(self.spectrum))
                sweep = OrderedDict({last: self.spectrum[last]})
                export_cont(self.exportCont, None, sweep)

            if self.stopScan:
                self.status.set_general("Stopped")
                self.__cleanup()
            elif self.settings.mode == Mode.SINGLE:
                self.status.set_general("Finished")
                self.__cleanup()
            elif self.settings.mode == Mode.CONTIN:
                self.__progress_next()
            elif self.settings.mode == Mode.MAX:
                if len(self.spectrum) < self.settings.retainMax:
                    self.__progress_next()
                else:
                    self.status.set_general("Finished")
                    self.__cleanup()

    def __progress_next(self):
        if self.dlgCal is None and not self.stopAtEnd:
            self.__scan_delay()
        else:
            self.status.set_general("Stopped")
            self.__cleanup()

    def __cleanup(self):
        if self.scanDelayTimer is not None:
            self.scanDelayTimer.Stop()
            self.scanDelayTimer = None

        if self.sdr is not None:
            self.sdr.close()
            self.sdr = None

        self.status.hide_progress()
        self.steps = 0
        self.threadScan = None
        self.__set_control_state(True)
        self.stopAtEnd = False
        self.stopScan = True
        self.isScanning = False

    def __remove_first(self, data):
        while len(data) > self.settings.retainMax:
            timeStamp = min(data)
            del data[timeStamp]

    def __remove_last(self, data):
        while len(data) > 1:
            timeStamp = max(data)
            del data[timeStamp]

    def __limit_spectrum(self):
        with self.lock:
            self.__remove_first(self.spectrum)
            self.__remove_first(self.locations)

    def __start_gps(self):
        if self.settings.gps and len(self.settings.devicesGps):
            self.status.enable_gps()
            if self.threadLocation is None:
                device = self.settings.devicesGps[self.settings.indexGps]
                self.threadLocation = ThreadLocation(self, device)
        else:
            self.status.disable_gps()

    def __stop_gps(self, join=True):
        if self.threadLocation and self.threadLocation.isAlive():
            self.threadLocation.stop()
            if join:
                self.threadLocation.join()
        self.threadLocation = None

    def __start_location_server(self):
        self.serverLocation = LocationServer(self.locations, self.lastLocation,
                                             self.lock, self.log)

    def __stop_location_server(self):
        if self.serverLocation:
            self.serverLocation.close()

    def __update_location(self, data):
        i = 0
        for loc in data:
            self.lastLocation[i] = loc
            i += 1
        self.status.pulse_gps()
        if data[2] is None:
            gpsStatus = '{:.5f}, {:.5f}'.format(data[0], data[1])
        else:
            gpsStatus = '{:.5f}, {:.5f}, {:.1f}m'.format(data[0], data[1], data[2])

        self.status.set_gps(gpsStatus, level=None)

        if not self.isScanning:
            return

        if self.scanInfo is not None:
            if data[0] and data[1]:
                self.scanInfo.lat = str(data[0])
                self.scanInfo.lon = str(data[1])

        with self.lock:
            if len(self.spectrum) > 0:
                self.locations[max(self.spectrum)] = (data[0],
                                                      data[1],
                                                      data[2])

    def __saved(self, isSaved):
        self.isSaved = isSaved
        title = APP_NAME + " - " + self.filename
        if not isSaved:
            title += "*"
        self.SetTitle(title)

    def __set_plot(self, spectrum, annotate):
        if len(spectrum) > 0:
            total = count_points(spectrum)
            if total > 0:
                extent = Extent(spectrum)
                self.graph.set_plot(spectrum,
                                    self.settings.pointsLimit,
                                    self.settings.pointsMax,
                                    extent, annotate)
        else:
            self.graph.clear_plots()

    def __set_size(self):
        width, height = wx.DisplaySize()
        widthFrame = wx.SystemSettings.GetMetric(wx.SYS_FRAMESIZE_X)

        art = self._mgr.GetArtProvider()
        widthBorder = (art.GetMetric(aui.AUI_DOCKART_SASH_SIZE) +
                       art.GetMetric(aui.AUI_DOCKART_CAPTION_SIZE) +
                       art.GetMetric(aui.AUI_DOCKART_GRIPPER_SIZE) +
                       art.GetMetric(aui.AUI_DOCKART_PANE_BORDER_SIZE))

        toolSize1 = self.toolbar1.GetMinSize()
        toolSize2 = self.toolbar2.GetMinSize()

        paneTool1 = self._mgr.GetPane(self.toolbar1)
        paneTool2 = self._mgr.GetPane(self.toolbar2)
        if width >= (toolSize1[0] + toolSize2[0] +
                     (widthBorder * 2) +
                     (widthFrame * 2)):
            paneTool1.ToolbarPane()
            paneTool2.ToolbarPane()
            paneTool2.Layer(1)
        self._mgr.Update()

        minWidth = max(toolSize1[0], toolSize2[0]) + widthBorder
        minWidth = max(minWidth, 640)
        minHeight = 400

        try:
            self.SetMinClientSize((minWidth, minHeight))
        except AttributeError:
            self.SetMinSize((minWidth + (widthFrame * 2),
                             minHeight + (widthFrame * 2)))
        self.SetSize((max(minWidth + (widthFrame * 2), width / 1.5),
                      max(minHeight + (widthFrame * 2), height / 1.5)))

    def __set_control_state(self, state):
        hasDevices = len(self.devicesRtl) > 0

        self.spinCtrlStart.Enable(state)
        self.spinCtrlStop.Enable(state)
        self.controlGain.Enable(state)
        self.choiceMode.Enable(state)
        self.choiceDwell.Enable(state)
        self.choiceNfft.Enable(state)
        self.buttonStart.Enable(state and hasDevices)
        self.buttonStop.Enable(not state and hasDevices)

        self.menuMain.set_state(state, self.spectrum, self.locations)
        self.menuPopup.set_state(state, self.spectrum)

    def __set_controls(self):
        self.spinCtrlStart.SetValue(self.settings.start)
        self.spinCtrlStop.SetValue(self.settings.stop)
        self.choiceMode.SetSelection(MODE[1::2].index(self.settings.mode))
        dwell = calc_real_dwell(self.settings.dwell)
        dwells = get_dwells()
        try:
            sel = dwells[1::2].index(dwell)
        except ValueError:
            sel = dwells[1::2][len(dwells) / 4]
        self.choiceDwell.SetSelection(sel)
        self.choiceNfft.SetSelection(NFFT.index(self.settings.nfft))
        self.choiceDisplay.SetSelection(DISPLAY[1::2].index(self.settings.display))

    def __set_gain_control(self):
        grid = self.controlGain.GetContainingSizer()
        if len(self.devicesRtl) > 0:
            self.controlGain.Destroy()
            device = self.devicesRtl[self.settings.indexRtl]
            if device.isDevice:
                gains = device.get_gains_str()
                self.controlGain = wx.Choice(self.toolbar1,
                                             choices=gains)
                gain = device.get_closest_gain_str(device.gain)
                self.controlGain.SetStringSelection(gain)
            else:
                self.controlGain = NumCtrl(self.toolbar1, integerWidth=3,
                                           fractionWidth=1)
                font = self.controlGain.GetFont()
                dc = wx.WindowDC(self.controlGain)
                dc.SetFont(font)
                size = dc.GetTextExtent('####.#')
                self.controlGain.SetMinSize((size[0] * 1.2, -1))
                self.controlGain.SetValue(device.gain)

            grid.Add(self.controlGain, pos=(1, 7), flag=wx.ALIGN_CENTER)
            grid.Layout()

    def __get_controls(self):
        self.settings.start = self.spinCtrlStart.GetValue()
        self.settings.stop = self.spinCtrlStop.GetValue()
        self.settings.startOption = self.buttonStart.GetSelected()
        self.settings.stopOption = self.buttonStop.GetSelected()
        self.settings.mode = MODE[1::2][self.choiceMode.GetSelection()]
        self.settings.dwell = get_dwells()[1::2][self.choiceDwell.GetSelection()]
        self.settings.nfft = NFFT[self.choiceNfft.GetSelection()]
        self.settings.display = DISPLAY[1::2][self.choiceDisplay.GetSelection()]

        if len(self.devicesRtl) > 0:
            device = self.devicesRtl[self.settings.indexRtl]
            try:
                if device.isDevice:
                    device.gain = float(self.controlGain.GetStringSelection())
                else:
                    device.gain = self.controlGain.GetValue()
            except ValueError:
                device.gain = 0

    def __save_warn(self, warnType):
        if self.settings.saveWarn and not self.isSaved:
            dlg = DialogSaveWarn(self, warnType)
            code = dlg.ShowModal()
            if code == wx.ID_YES:
                self.__on_save(None)
                if self.isSaved:
                    return False
                else:
                    return True
            elif code == wx.ID_NO:
                return False
            else:
                return True

        return False

    def __refresh_devices(self):
        self.settings.devicesRtl = get_devices_rtl(self.devicesRtl, self.status)
        self.settings.indexRtl = limit(self.settings.indexRtl,
                                       0, len(self.devicesRtl) - 1)
        self.settings.save()
        return self.settings.devicesRtl

    def __merge(self, dirname, filename):
        if not os.path.exists(os.path.join(dirname, filename)):
            wx.MessageBox('File not found',
                          'Error', wx.OK | wx.ICON_ERROR)
            return

        self.filename = os.path.splitext(filename)[0]
        self.settings.dirScans = dirname
        self.status.set_general("Merging: {}".format(filename))

        _scanInfo, spectrum, locations = open_plot(dirname, filename)

        if len(spectrum) > 0:
            self.spectrum.clear()
            self.locations.clear()
            self.spectrum.update(OrderedDict(sorted(spectrum.items())))
            self.locations.update(OrderedDict(sorted(locations.items())))
            self.__set_plot(self.spectrum, self.settings.annotate)
            self.graph.scale_plot(True)
            self.status.set_general("Finished")
            self.settings.fileHistory.AddFileToHistory(os.path.join(dirname,
                                                                    filename))
        else:
            self.status.set_general("Merge failed", level=Log.ERROR)

    def open(self, dirname, filename):
        if not os.path.exists(os.path.join(dirname, filename)):
            wx.MessageBox('File not found',
                          'Error', wx.OK | wx.ICON_ERROR)
            return

        self.__on_new(None)
        self.graph.get_canvas().draw()

        self.filename = os.path.splitext(filename)[0]
        self.settings.dirScans = dirname
        self.status.set_general("Opening: {}".format(filename))

        self.scanInfo, spectrum, location = open_plot(dirname, filename)

        if len(spectrum) > 0:
            self.scanInfo.set_to_settings(self.settings)
            self.spectrum = spectrum
            self.locations.clear()
            self.locations.update(location)
            self.__saved(True)
            self.__set_controls()
            self.__set_control_state(True)
            self.__set_plot(spectrum, self.settings.annotate)
            self.graph.set_plot_title()
            self.graph.scale_plot(True)
            self.status.set_general("Finished")
            self.settings.fileHistory.AddFileToHistory(os.path.join(dirname,
                                                                    filename))
        else:
            self.status.set_general("Open failed", level=Log.ERROR)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
