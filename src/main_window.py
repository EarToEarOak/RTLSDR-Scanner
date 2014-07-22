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


import datetime
import math
import os.path
import tempfile
from threading import Thread
import threading
import time
import webbrowser

from matplotlib.dates import num2epoch
import wx
from wx.lib.masked import NumCtrl

from constants import F_MIN, F_MAX, MODE, DWELL, NFFT, DISPLAY, Warn, \
    Display, Cal, Mode
from controls import MultiButton
from devices import get_devices_rtl
from dialogs import DialogProperties, DialogPrefs, DialogAdvPrefs, \
    DialogDevicesRTL, DialogCompare, DialogAutoCal, DialogAbout, \
    DialogSaveWarn, DialogDevicesGPS, DialogGeo, DialogSeq, DialogImageSize, \
    DialogFormatting, DialogLog
from events import EVENT_THREAD, Event, EventThread, post_event, Log
from file import save_plot, export_plot, open_plot, ScanInfo, export_image, \
    export_map, extension_add, File, run_file, export_gpx
from location import ThreadLocation, KmlServer
from misc import RemoteControl, format_precision, calc_samples, calc_real_dwell, \
    get_version_timestamp, get_version_timestamp_repo
from panels import PanelGraph
from printer import PrintOut
from scan import ThreadScan, anaylse_data, update_spectrum
from settings import Settings
from spectrum import count_points, sort_spectrum, Extent
from toolbars import Statusbar
from utils_mpl import add_colours


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
        self.threadUpdate = None
        self.threadLocation = None

        self.serverKml = None

        self.isNewScan = True
        self.isScanning = False

        self.stopAtEnd = False
        self.stopScan = False

        self.dlgCal = None
        self.dlgLog = None

        self.menuNew = None
        self.menuOpen = None
        self.menuSave = None
        self.menuExportScan = None
        self.menuExportImage = None
        self.menuExportSeq = None
        self.menuExportGeo = None
        self.menuExportTrack = None
        self.menuPreview = None
        self.menuPage = None
        self.menuPrint = None
        self.menuProperties = None
        self.menuPref = None
        self.menuAdvPref = None
        self.menuFormatting = None
        self.menuDevicesRtl = None
        self.menuDevicesGps = None
        self.menuReset = None
        self.menuClearSelect = None
        self.menuShowMeasure = None
        self.menuStart = None
        self.menuStop = None
        self.menuStopEnd = None
        self.menuCompare = None
        self.menuCal = None
        self.menuKml = None
        self.menuLocClear = None
        self.menuLog = None
        self.menuHelpLink = None
        self.menuUpdate = None
        self.menuAbout = None

        self.popupMenu = None
        self.popupMenuStart = None
        self.popupMenuStop = None
        self.popupMenuStopEnd = None
        self.popupMenuRangeLim = None
        self.popupMenuPointsLim = None
        self.popupMenuClearSelect = None
        self.popupMenuShowMeasure = None

        self.graph = None
        self.toolbar = None
        self.canvas = None
        self.mouseZoom = None
        self.mouseSelect = None

        self.buttonStart = None
        self.buttonStop = None
        self.controlGain = None
        self.choiceMode = None
        self.choiceDwell = None
        self.choiceNfft = None
        self.spinCtrlStart = None
        self.spinCtrlStop = None
        self.checkUpdate = None
        self.checkGrid = None
        self.choiceDisplay = None

        self.spectrum = {}
        self.scanInfo = ScanInfo()
        self.location = {}
        self.isSaved = True

        self.settings = Settings()
        self.devicesRtl = get_devices_rtl(self.settings.devicesRtl)
        self.filename = ""
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

        wx.Frame.__init__(self, None, title=title)

        self.timerGpsRetry = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.__on_gps_retry, self.timerGpsRetry)

        self.Bind(wx.EVT_CLOSE, self.__on_exit)

        self.status = Statusbar(self, self.log)
        self.status.set_info(title)
        self.SetStatusBar(self.status)

        add_colours()
        self.__create_widgets()
        self.__create_menu()
        self.__create_popup_menu()
        self.__set_control_state(True)
        self.Show()

        displaySize = wx.DisplaySize()
        toolbarSize = self.toolbar.GetBestSize()
        self.SetClientSize((toolbarSize[0] + 10, displaySize[1] / 2))
        self.SetMinSize((displaySize[0] / 4, displaySize[1] / 4))

        self.Connect(-1, -1, EVENT_THREAD, self.__on_event)

        self.SetDropTarget(DropTarget(self))

        self.steps = 0
        self.stepsTotal = 0

        self.__start_gps()
        self.__start_kml()

    def __create_widgets(self):
        panel = wx.Panel(self)

        self.remoteControl = RemoteControl()

        self.graph = PanelGraph(panel, self, self.settings, self.__on_motion,
                                self.remoteControl)
        self.toolbar = wx.Panel(panel)

        self.buttonStart = MultiButton(self.toolbar,
                                       ['Start', 'Continue'],
                                       ['Start new scan', 'Continue scanning'])
        self.buttonStart.SetSelected(self.settings.startOption)
        self.buttonStop = MultiButton(self.toolbar,
                                      ['Stop', 'Stop at end'],
                                      ['Stop scan', 'Stop scan at end'])
        self.buttonStop.SetSelected(self.settings.stopOption)
        self.Bind(wx.EVT_BUTTON, self.__on_start, self.buttonStart)
        self.Bind(wx.EVT_BUTTON, self.__on_stop, self.buttonStop)

        textRange = wx.StaticText(self.toolbar, label="Range (MHz)",
                                  style=wx.ALIGN_CENTER)
        textStart = wx.StaticText(self.toolbar, label="Start")
        textStop = wx.StaticText(self.toolbar, label="Stop")

        self.spinCtrlStart = wx.SpinCtrl(self.toolbar)
        self.spinCtrlStop = wx.SpinCtrl(self.toolbar)
        self.spinCtrlStart.SetToolTip(wx.ToolTip('Start frequency'))
        self.spinCtrlStop.SetToolTip(wx.ToolTip('Stop frequency'))
        self.spinCtrlStart.SetRange(F_MIN, F_MAX - 1)
        self.spinCtrlStop.SetRange(F_MIN + 1, F_MAX)
        self.Bind(wx.EVT_SPINCTRL, self.__on_spin, self.spinCtrlStart)
        self.Bind(wx.EVT_SPINCTRL, self.__on_spin, self.spinCtrlStop)

        textGain = wx.StaticText(self.toolbar, label="Gain (dB)")
        self.controlGain = wx.Choice(self.toolbar, choices=[''])

        textMode = wx.StaticText(self.toolbar, label="Mode")
        self.choiceMode = wx.Choice(self.toolbar, choices=MODE[::2])
        self.choiceMode.SetToolTip(wx.ToolTip('Scanning mode'))

        textDwell = wx.StaticText(self.toolbar, label="Dwell")
        self.choiceDwell = wx.Choice(self.toolbar, choices=DWELL[::2])
        self.choiceDwell.SetToolTip(wx.ToolTip('Scan time per step'))

        textNfft = wx.StaticText(self.toolbar, label="FFT size")
        self.choiceNfft = wx.Choice(self.toolbar, choices=map(str, NFFT))
        self.choiceNfft.SetToolTip(wx.ToolTip('Higher values for greater'
                                              'precision'))

        textDisplay = wx.StaticText(self.toolbar, label="Display")
        self.choiceDisplay = wx.Choice(self.toolbar, choices=DISPLAY[::2])
        self.Bind(wx.EVT_CHOICE, self.__on_choice, self.choiceDisplay)
        self.choiceDisplay.SetToolTip(wx.ToolTip('Spectrogram available in'
                                                 'continuous mode'))

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
        grid.Add(textGain, pos=(0, 7), flag=wx.ALIGN_CENTER)
        grid.Add(self.controlGain, pos=(1, 7), flag=wx.ALIGN_CENTER)
        grid.Add((20, 1), pos=(0, 8))
        grid.Add(textMode, pos=(0, 9), flag=wx.ALIGN_CENTER)
        grid.Add(self.choiceMode, pos=(1, 9), flag=wx.ALIGN_CENTER)
        grid.Add(textDwell, pos=(0, 10), flag=wx.ALIGN_CENTER)
        grid.Add(self.choiceDwell, pos=(1, 10), flag=wx.ALIGN_CENTER)
        grid.Add(textNfft, pos=(0, 11), flag=wx.ALIGN_CENTER)
        grid.Add(self.choiceNfft, pos=(1, 11), flag=wx.ALIGN_CENTER)
        grid.Add((20, 1), pos=(0, 12))
        grid.Add(textDisplay, pos=(0, 13), flag=wx.ALIGN_CENTER)
        grid.Add(self.choiceDisplay, pos=(1, 13), flag=wx.ALIGN_CENTER)

        self.__set_controls()
        self.__set_gain_control()

        self.toolbar.SetSizer(grid)
        self.toolbar.Layout()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.graph, 1, wx.EXPAND)
        sizer.Add(self.toolbar, 0, wx.EXPAND)
        panel.SetSizer(sizer)
        panel.Layout()

    def __create_menu(self):
        menuFile = wx.Menu()
        self.menuNew = menuFile.Append(wx.ID_NEW, "&New",
                                       "New plot")
        self.menuOpen = menuFile.Append(wx.ID_OPEN, "&Open...",
                                        "Open plot")
        recent = wx.Menu()
        self.settings.fileHistory.UseMenu(recent)
        self.settings.fileHistory.AddFilesToMenu()
        menuFile.AppendMenu(wx.ID_ANY, "&Recent Files", recent)
        menuFile.AppendSeparator()
        self.menuSave = menuFile.Append(wx.ID_SAVE, "&Save As...",
                                        "Save plot")
        self.menuExportScan = menuFile.Append(wx.ID_ANY, "Export scan...",
                                              "Export scan")
        self.menuExportImage = menuFile.Append(wx.ID_ANY, "Export image...",
                                               "Export image")
        self.menuExportSeq = menuFile.Append(wx.ID_ANY, "Export image sequence...",
                                             "Export sweep plots in sequence")
        self.menuExportGeo = menuFile.Append(wx.ID_ANY, "Export map...",
                                             "Export maps")
        self.menuExportTrack = menuFile.Append(wx.ID_ANY, "Export GPS track...",
                                               "Export GPS data")
        menuFile.AppendSeparator()
        self.menuPage = menuFile.Append(wx.ID_ANY, "Page setup...",
                                        "Page setup")
        self.menuPreview = menuFile.Append(wx.ID_ANY, "Print preview...",
                                           "Print preview")
        self.menuPrint = menuFile.Append(wx.ID_ANY, "&Print...",
                                         "Print plot")
        menuFile.AppendSeparator()
        self.menuProperties = menuFile.Append(wx.ID_ANY, "P&roperties...",
                                              "Show properties")
        menuFile.AppendSeparator()
        menuExit = menuFile.Append(wx.ID_EXIT, "E&xit", "Exit the program")

        menuEdit = wx.Menu()
        self.menuPref = menuEdit.Append(wx.ID_ANY, "&Preferences...",
                                        "Preferences")
        self.menuAdvPref = menuEdit.Append(wx.ID_ANY, "&Advanced preferences...",
                                           "Advanced preferences")
        menuEdit.AppendSeparator()
        self.menuFormatting = menuEdit.Append(wx.ID_ANY, "&Number formatting...",
                                              "Adjust the displayed precision of values")
        menuEdit.AppendSeparator()
        self.menuDevicesRtl = menuEdit.Append(wx.ID_ANY, "&Radio Devices...",
                                              "Device selection and configuration")
        self.menuDevicesGps = menuEdit.Append(wx.ID_ANY, "&GPS Devices...",
                                              "GPS selection and configuration")
        menuEdit.AppendSeparator()
        self.menuReset = menuEdit.Append(wx.ID_ANY, "&Reset settings...",
                                         "Reset setting to the default")

        menuView = wx.Menu()
        self.menuClearSelect = menuView.Append(wx.ID_ANY, "Clear selection",
                                               "Clear current selection")
        self.graph.add_menu_clear_select(self.menuClearSelect)
        self.menuShowMeasure = menuView.Append(wx.ID_ANY, "Show &measurements",
                                               "Show measurements window",
                                               kind=wx.ITEM_CHECK)
        self.menuShowMeasure.Check(self.settings.showMeasure)

        menuScan = wx.Menu()
        self.menuStart = menuScan.Append(wx.ID_ANY, "&Start", "Start scan")
        self.menuStop = menuScan.Append(wx.ID_ANY, "S&top",
                                        "Stop scan immediately")
        self.menuStopEnd = menuScan.Append(wx.ID_ANY, "Stop at &end",
                                           "Complete current sweep "
                                           "before stopping")

        menuTools = wx.Menu()
        self.menuCompare = menuTools.Append(wx.ID_ANY, "&Compare...",
                                            "Compare plots")
        self.menuCal = menuTools.Append(wx.ID_ANY, "&Auto Calibration...",
                                        "Automatically calibrate to a known frequency")
        menuTools.AppendSeparator()
        self.menuKml = menuTools.Append(wx.ID_ANY, "&Track in Google Earth",
                                        "Display recorded points in Google Earth")
        menuTools.AppendSeparator()
        self.menuLocClear = menuTools.Append(wx.ID_ANY, "&Clear location data...",
                                             "Remove GPS data from scan")
        menuTools.AppendSeparator()
        menuLog = menuTools.Append(wx.ID_ANY, "&Log...",
                                   "Program log")

        menuHelp = wx.Menu()
        menuHelpLink = menuHelp.Append(wx.ID_HELP, "&Help...",
                                       "Link to help")
        menuHelp.AppendSeparator()
        menuUpdate = menuHelp.Append(wx.ID_ANY, "&Check for updates...",
                                     "Check for updates to the program")
        menuHelp.AppendSeparator()
        menuAbout = menuHelp.Append(wx.ID_ABOUT, "&About...",
                                    "Information about this program")

        menuBar = wx.MenuBar()
        menuBar.Append(menuFile, "&File")
        menuBar.Append(menuEdit, "&Edit")
        menuBar.Append(menuView, "&View")
        menuBar.Append(menuScan, "&Scan")
        menuBar.Append(menuTools, "&Tools")
        menuBar.Append(menuHelp, "&Help")
        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.__on_new, self.menuNew)
        self.Bind(wx.EVT_MENU, self.__on_open, self.menuOpen)
        self.Bind(wx.EVT_MENU_RANGE, self.__on_file_history, id=wx.ID_FILE1,
                  id2=wx.ID_FILE9)
        self.Bind(wx.EVT_MENU, self.__on_save, self.menuSave)
        self.Bind(wx.EVT_MENU, self.__on_export_scan, self.menuExportScan)
        self.Bind(wx.EVT_MENU, self.__on_export_image, self.menuExportImage)
        self.Bind(wx.EVT_MENU, self.__on_export_image_seq, self.menuExportSeq)
        self.Bind(wx.EVT_MENU, self.__on_export_geo, self.menuExportGeo)
        self.Bind(wx.EVT_MENU, self.__on_export_track, self.menuExportTrack)
        self.Bind(wx.EVT_MENU, self.__on_page, self.menuPage)
        self.Bind(wx.EVT_MENU, self.__on_preview, self.menuPreview)
        self.Bind(wx.EVT_MENU, self.__on_print, self.menuPrint)
        self.Bind(wx.EVT_MENU, self.__on_properties, self.menuProperties)
        self.Bind(wx.EVT_MENU, self.__on_exit, menuExit)
        self.Bind(wx.EVT_MENU, self.__on_pref, self.menuPref)
        self.Bind(wx.EVT_MENU, self.__on_adv_pref, self.menuAdvPref)
        self.Bind(wx.EVT_MENU, self.__on_formatting, self.menuFormatting)
        self.Bind(wx.EVT_MENU, self.__on_devices_rtl, self.menuDevicesRtl)
        self.Bind(wx.EVT_MENU, self.__on_devices_gps, self.menuDevicesGps)
        self.Bind(wx.EVT_MENU, self.__on_reset, self.menuReset)
        self.Bind(wx.EVT_MENU, self.__on_clear_select, self.menuClearSelect)
        self.Bind(wx.EVT_MENU, self.__on_show_measure, self.menuShowMeasure)
        self.Bind(wx.EVT_MENU, self.__on_start, self.menuStart)
        self.Bind(wx.EVT_MENU, self.__on_stop, self.menuStop)
        self.Bind(wx.EVT_MENU, self.__on_stop_end, self.menuStopEnd)
        self.Bind(wx.EVT_MENU, self.__on_compare, self.menuCompare)
        self.Bind(wx.EVT_MENU, self.__on_cal, self.menuCal)
        self.Bind(wx.EVT_MENU, self.__on_kml, self.menuKml)
        self.Bind(wx.EVT_MENU, self.__on_loc_clear, self.menuLocClear)
        self.Bind(wx.EVT_MENU, self.__on_log, menuLog)
        self.Bind(wx.EVT_MENU, self.__on_help, menuHelpLink)
        self.Bind(wx.EVT_MENU, self.__on_update, menuUpdate)
        self.Bind(wx.EVT_MENU, self.__on_about, menuAbout)

        idF1 = wx.wx.NewId()
        self.Bind(wx.EVT_MENU, self.__on_help, id=idF1)
        accelTable = wx.AcceleratorTable([(wx.ACCEL_NORMAL, wx.WXK_F1, idF1)])
        self.SetAcceleratorTable(accelTable)

        self.Bind(wx.EVT_MENU_HIGHLIGHT, self.__on_menu_highlight)

    def __create_popup_menu(self):
        self.popupMenu = wx.Menu()
        self.popupMenuStart = self.popupMenu.Append(wx.ID_ANY, "&Start",
                                                    "Start scan")
        self.popupMenuStop = self.popupMenu.Append(wx.ID_ANY, "S&top",
                                                   "Stop scan immediately")
        self.popupMenuStopEnd = self.popupMenu.Append(wx.ID_ANY, "Stop at &end",
                                                      "Complete current sweep "
                                                      "before stopping")
        self.popupMenu.AppendSeparator()
        self.popupMenuRangeLim = self.popupMenu.Append(wx.ID_ANY,
                                                       "Set range to current zoom",
                                                       "Set scanning range to the "
                                                       "current zoom")
        self.popupMenu.AppendSeparator()
        self.popupMenuPointsLim = self.popupMenu.Append(wx.ID_ANY,
                                                        "Limit points",
                                                        "Limit points to "
                                                        "increase plot speed",
                                                        kind=wx.ITEM_CHECK)
        self.popupMenuPointsLim.Check(self.settings.pointsLimit)

        self.popupMenu.AppendSeparator()
        self.popupMenuClearSelect = self.popupMenu.Append(wx.ID_ANY, "Clear selection",
                                                          "Clear current selection")
        self.graph.add_menu_clear_select(self.popupMenuClearSelect)
        self.popupMenuShowMeasure = self.popupMenu.Append(wx.ID_ANY,
                                                          "Show &measurements",
                                                          "Show measurements window",
                                                          kind=wx.ITEM_CHECK)
        self.popupMenuShowMeasure.Check(self.settings.showMeasure)

        self.Bind(wx.EVT_MENU, self.__on_start, self.popupMenuStart)
        self.Bind(wx.EVT_MENU, self.__on_stop, self.popupMenuStop)
        self.Bind(wx.EVT_MENU, self.__on_stop_end, self.popupMenuStopEnd)
        self.Bind(wx.EVT_MENU, self.__on_range_lim, self.popupMenuRangeLim)
        self.Bind(wx.EVT_MENU, self.__on_points_lim, self.popupMenuPointsLim)
        self.Bind(wx.EVT_MENU, self.__on_clear_select, self.popupMenuClearSelect)
        self.Bind(wx.EVT_MENU, self.__on_show_measure, self.popupMenuShowMeasure)

        self.Bind(wx.EVT_CONTEXT_MENU, self.__on_popup_menu)

    def __on_menu_highlight(self, event):
        item = self.GetMenuBar().FindItemById(event.GetId())
        if item is not None:
            help = item.GetHelp()
        else:
            help = ''

        self.status.set_general(help, level=None)

    def __on_popup_menu(self, event):
        pos = event.GetPosition()
        pos = self.ScreenToClient(pos)
        self.PopupMenu(self.popupMenu, pos)

    def __on_new(self, _event):
        if self.__save_warn(Warn.NEW):
            return
        self.spectrum.clear()
        self.location.clear()
        self.__saved(True)
        self.__set_plot(self.spectrum, False)

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
            save_plot(fullName, self.scanInfo, self.spectrum, self.location)
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
        dlgSeq = DialogSeq(self, self.spectrum, self.settings)
        dlgSeq.ShowModal()
        dlgSeq.Destroy()

    def __on_export_geo(self, _event):
        dlgGeo = DialogGeo(self, self.spectrum, self.location, self.settings)
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
            export_gpx(fullName, self.location, self.GetName())
            self.status.set_general("Finished")
        dlg.Destroy()

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
        if self.__save_warn(Warn.EXIT):
            self.Bind(wx.EVT_CLOSE, self.__on_exit)
            return
        self.__scan_stop()
        self.__stop_gps()
        self.__stop_kml()
        self.__wait_background()
        self.__get_controls()
        self.graph.close()
        self.settings.dwell = DWELL[1::2][self.choiceDwell.GetSelection()]
        self.settings.nfft = NFFT[self.choiceNfft.GetSelection()]
        self.settings.devicesRtl = self.devicesRtl
        self.settings.save()
        self.Close(True)

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
            self.settings.reset()
            self.__set_controls()
            self.graph.create_plot()
        dlg.Destroy()

    def __on_compare(self, _event):
        dlg = DialogCompare(self, self.settings, self.filename)
        dlg.Show()

    def __on_clear_select(self, _event):
        self.graph.clear_selection()

    def __on_show_measure(self, event):
        show = event.Checked()
        self.menuShowMeasure.Check(show)
        self.popupMenuShowMeasure.Check(show)
        self.settings.showMeasure = show
        self.graph.show_measure_table(show)
        self.Layout()

    def __on_cal(self, _event):
        self.dlgCal = DialogAutoCal(self, self.settings.calFreq, self.__auto_cal)
        self.dlgCal.ShowModal()

    def __on_kml(self, _event):
        tempPath = tempfile.mkdtemp()
        tempFile = os.path.join(tempPath, 'RTLSDRScannerLink.kml')
        handle = open(tempFile, 'wb')
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        handle.write('<kml xmlns="http://www.opengis.net/kml/2.2">\n')
        handle.write('\t<NetworkLink>\n')
        handle.write('\t\t<flyToView>1</flyToView>\n')
        handle.write('\t\t<name>RTLSDR Scanner</name>\n')
        handle.write('\t\t<Link>\n')
        handle.write('\t\t\t<href>http://localhost:12345</href>\n')
        handle.write('\t\t\t<refreshMode>onInterval</refreshMode>\n')
        handle.write('\t\t\t<refreshInterval>10</refreshInterval>\n')
        handle.write('\t\t</Link>\n')
        handle.write('\t</NetworkLink>\n')
        handle.write('</kml>\n')
        handle.close()

        if not run_file(tempFile):
            wx.MessageBox('Error starting Google Earth', 'Error',
                          wx.OK | wx.ICON_ERROR)

    def __on_loc_clear(self, _event):
        result = wx.MessageBox('Remove {} locations from scan?'.format(len(self.location)),
                               'Clear location data',
                               wx.YES_NO, self)
        if result == wx.YES:
            self.location.clear()
            self.__set_control_state(True)

    def __on_log(self, _event):
        if self.dlgLog is None:
            self.dlgLog = DialogLog(self, self.log)
            self.dlgLog.Show()

    def __on_help(self, _event):
        webbrowser.open("http://eartoearoak.com/software/rtlsdr-scanner")

    def __on_update(self, _event):
        if self.threadUpdate is None:
            self.status.set_general("Checking for updates", level=None)
            self.threadUpdate = Thread(target=self.__update_check)
            self.threadUpdate.start()

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
        if self.settings.start >= self.settings.stop:
            wx.MessageBox('Stop frequency must be greater that start',
                          'Warning', wx.OK | wx.ICON_WARNING)
            return

        self.__get_controls()

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
        self.settings.pointsLimit = self.popupMenuPointsLim.IsChecked()
        self.__set_plot(self.spectrum, self.settings.annotate)

    def __on_gps_retry(self, _event):
        self.timerGpsRetry.Stop()
        self.__stop_gps()
        self.__start_gps()

    def __on_motion(self, event):
        xpos = event.xdata
        ypos = event.ydata
        text = ""
        if xpos is None or ypos is None or len(self.spectrum) == 0:
            return

        if self.settings.display == Display.PLOT:
            timeStamp = max(self.spectrum)
            spectrum = self.spectrum[timeStamp]
        elif self.settings.display == Display.SPECT:
            timeStamp = num2epoch(ypos)
            if timeStamp in self.spectrum:
                spectrum = self.spectrum[timeStamp]
            else:
                nearest = min(self.spectrum.keys(),
                              key=lambda k: abs(k - timeStamp))
                spectrum = self.spectrum[nearest]
        else:
            spectrum = None

        if spectrum is not None and len(spectrum) > 0:
            x = min(spectrum.keys(), key=lambda freq: abs(freq - xpos))
            if min(spectrum.keys(), key=float) <= xpos <= max(spectrum.keys(), key=float):
                y = spectrum[x]
                text = "{}, {}".format(*format_precision(self.settings, x, y))
            else:
                text = format_precision(self.settings, xpos)

        self.status.set_info(text, level=None)

    def __on_event(self, event):
        status = event.data.get_status()
        freq = event.data.get_arg1()
        data = event.data.get_arg2()
        if status == Event.STARTING:
            self.status.set_general("Starting")
            self.isScanning = True
        elif status == Event.STEPS:
            self.stepsTotal = (freq + 1) * 2
            self.steps = self.stepsTotal
            self.status.set_progress(0)
            self.status.show_progress()
        elif status == Event.CAL:
            self.__auto_cal(Cal.DONE)
        elif status == Event.INFO:
            if self.threadScan is not None:
                self.sdr = self.threadScan.get_sdr()
                if data is not None:
                    self.devicesRtl[self.settings.indexRtl].tuner = data
                    self.scanInfo.tuner = data
        elif status == Event.DATA:
            self.__saved(False)
            cal = self.devicesRtl[self.settings.indexRtl].calibration
            self.pool.apply_async(anaylse_data,
                                  (freq, data, cal,
                                   self.settings.nfft,
                                   self.settings.overlap,
                                   self.settings.winFunc),
                                  callback=self.__on_process_done)
            self.__progress()
        elif status == Event.STOPPED:
            self.__cleanup()
            self.status.set_general("Stopped")
        elif status == Event.FINISHED:
            self.threadScan = None
        elif status == Event.ERROR:
            self.__cleanup()
            self.status.set_general("Error: {0}".format(data), level=Log.ERROR)
            if self.dlgCal is not None:
                self.dlgCal.Destroy()
                self.dlgCal = None
        elif status == Event.PROCESSED:
            offset = self.settings.devicesRtl[self.settings.indexRtl].offset
            if self.settings.alert:
                alert = self.settings.alertLevel
            else:
                alert = None
            Thread(target=update_spectrum, name='Update',
                   args=(self, self.lock, self.settings.start,
                         self.settings.stop, freq,
                         data, offset, self.spectrum,
                         not self.settings.retainScans,
                         alert)).start()
        elif status == Event.LEVEL:
            wx.Bell()
        elif status == Event.UPDATED:
            if data and self.settings.liveUpdate:
                self.__set_plot(self.spectrum,
                                self.settings.annotate and
                                self.settings.retainScans and
                                self.settings.mode == Mode.CONTIN)
            self.__progress()
        elif status == Event.DRAW:
            self.graph.draw()
        elif status == Event.VER_UPD:
            self.__update_checked(True, freq, data)
        elif status == Event.VER_NOUPD:
            self.__update_checked(False)
        elif status == Event.VER_UPDFAIL:
            self.__update_checked(failed=True)
        elif status == Event.LOC_WARN:
            self.status.set_gps("{0}".format(data), level=Log.WARN)
            self.status.warn_gps()
        elif status == Event.LOC_ERR:
            self.status.set_gps("{0}".format(data), level=Log.ERROR)
            self.status.error_gps()
            self.threadLocation = None
            if not self.timerGpsRetry.IsRunning():
                self.timerGpsRetry.Start(5000, True)
        elif status == Event.LOC:
            self.__update_location(data)

        wx.YieldIfNeeded()

    def __on_process_done(self, data):
        timeStamp, freq, scan = data
        post_event(self, EventThread(Event.PROCESSED, freq,
                                     (timeStamp, scan)))

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
                self.location.clear()
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

    def __scan_start(self, isCal=False):
        if self.isNewScan and self.__save_warn(Warn.SCAN):
            return False

        if not self.threadScan:
            self.__set_control_state(False)
            samples = calc_samples(self.settings.dwell)
            if self.isNewScan:
                self.spectrum.clear()
                self.location.clear()
                self.graph.clear_plots()

                self.isNewScan = False
                self.status.set_info('', level=None)
                self.scanInfo.set_from_settings(self.settings)
                time = datetime.datetime.utcnow().replace(microsecond=0)
                self.scanInfo.time = time.isoformat() + "Z"
                self.scanInfo.lat = None
                self.scanInfo.lon = None
                self.scanInfo.desc = ''

            self.stopAtEnd = False
            self.stopScan = False
            self.threadScan = ThreadScan(self, self.sdr, self.settings,
                                         self.settings.indexRtl, samples, isCal)
            self.filename = "Scan {0:.1f}-{1:.1f}MHz".format(self.settings.start,
                                                             self.settings.stop)
            self.graph.set_plot_title()

            self.__start_gps()

            return True

    def __scan_stop(self):
        if self.threadScan:
            self.status.set_general("Stopping")
            self.threadScan.abort()
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
            self.status.show_progress()
        else:
            self.status.hide_progress()
            self.__set_plot(self.spectrum, self.settings.annotate)
            if self.stopScan:
                self.status.set_general("Stopped")
                self.__cleanup()
            elif self.settings.mode == Mode.SINGLE:
                self.status.set_general("Finished")
                self.__cleanup()
            else:
                if self.settings.mode == Mode.CONTIN:
                    if self.dlgCal is None and not self.stopAtEnd:
                        self.__limit_spectrum()
                        self.__scan_start()
                    else:
                        self.status.set_general("Stopped")
                        self.__cleanup()

    def __cleanup(self):
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

    def __remove_last(self, data):
        while len(data) >= self.settings.retainMax:
            timeStamp = min(data)
            del data[timeStamp]

    def __limit_spectrum(self):
        with self.lock:
            self.__remove_last(self.spectrum)
            self.__remove_last(self.location)

    def __start_gps(self):
        if self.settings.gps and len(self.settings.devicesGps):
            if self.threadLocation is None:
                device = self.settings.devicesGps[self.settings.indexGps]
                self.threadLocation = ThreadLocation(self, device)

    def __stop_gps(self):
        if self.threadLocation and self.threadLocation.isAlive():
            self.threadLocation.stop()
            self.threadLocation.join()
        self.threadLocation = None

    def __start_kml(self):
        self.serverKml = KmlServer(self.location, self.lock)

    def __stop_kml(self):
        if self.serverKml:
            self.serverKml.close()

    def __update_location(self, data):
        self.status.pulse_gps()
        self.status.set_gps('{:.5f}, {:.5f}'.format(data[0],
                                                    data[1]),
                            level=None)

        if not self.isScanning:
            return

        if self.scanInfo is not None:
            if data[0] and data[1]:
                self.scanInfo.lat = str(data[0])
                self.scanInfo.lon = str(data[1])

        with self.lock:
            if len(self.spectrum) > 0:
                self.location[max(self.spectrum)] = (data[0],
                                                     data[1],
                                                     data[2])

    def __saved(self, isSaved):
        self.isSaved = isSaved
        title = "RTLSDR Scanner - " + self.filename
        if not isSaved:
            title += "*"
        self.SetTitle(title)

    def __set_plot(self, spectrum, annotate):
        if len(spectrum) > 0:
            total = count_points(spectrum)
            if total > 0:
                spectrum = sort_spectrum(spectrum)
                extent = Extent(spectrum)
                self.graph.set_plot(spectrum,
                                    self.settings.pointsLimit,
                                    self.settings.pointsMax,
                                    extent, annotate)
        else:
            self.graph.clear_plots()

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
        self.menuNew.Enable(state)
        self.menuOpen.Enable(state)
        self.menuSave.Enable(state and len(self.spectrum) > 0)
        self.menuExportScan.Enable(state and len(self.spectrum) > 0)
        self.menuExportImage.Enable(state)
        self.menuExportSeq.Enable(state and len(self.spectrum) > 0)
        self.menuExportGeo.Enable(state and len(self.spectrum) > 0 and
                                  len(self.location) > 0)
        self.menuExportGeo.Enable(state and len(self.location))
        self.menuPage.Enable(state)
        self.menuPreview.Enable(state)
        self.menuPrint.Enable(state)
        self.menuStart.Enable(state)
        self.menuStop.Enable(not state)
        self.menuPref.Enable(state)
        self.menuAdvPref.Enable(state)
        self.menuDevicesRtl.Enable(state)
        self.menuDevicesGps.Enable(state)
        self.menuReset.Enable(state)
        self.menuCal.Enable(state)
        self.menuLocClear.Enable(state and len(self.location))
        self.popupMenuStop.Enable(not state)
        self.popupMenuStart.Enable(state)
        if self.settings.mode == Mode.CONTIN:
            self.menuStopEnd.Enable(not state)
            self.popupMenuStopEnd.Enable(not state)
        else:
            self.menuStopEnd.Enable(False)
            self.popupMenuStopEnd.Enable(False)
        self.popupMenuRangeLim.Enable(state)

    def __set_controls(self):
        self.spinCtrlStart.SetValue(self.settings.start)
        self.spinCtrlStop.SetValue(self.settings.stop)
        self.choiceMode.SetSelection(MODE[1::2].index(self.settings.mode))
        dwell = calc_real_dwell(self.settings.dwell)
        try:
            sel = DWELL[1::2].index(dwell)
        except ValueError:
            sel = DWELL[1::2][len(DWELL) / 4]
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
                self.controlGain = wx.Choice(self.toolbar,
                                             choices=gains)
                gain = device.get_closest_gain_str(device.gain)
                self.controlGain.SetStringSelection(gain)
            else:
                self.controlGain = NumCtrl(self.toolbar, integerWidth=3,
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
        self.settings.dwell = DWELL[1::2][self.choiceDwell.GetSelection()]
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

    def __update_check(self):
        local = get_version_timestamp(True)
        try:
            remote = get_version_timestamp_repo()
        except IOError:
            post_event(self, EventThread(Event.VER_UPDFAIL))
            return

        if remote > local:
            post_event(self, EventThread(Event.VER_UPD, local, remote))
        else:
            post_event(self, EventThread(Event.VER_NOUPD))

    def __update_checked(self, updateFound=False, local=None, remote=None,
                         failed=False):
        self.threadUpdate = None
        self.status.set_general("", level=None)
        if failed:
            icon = wx.ICON_ERROR
            message = "Update check failed"
        else:
            icon = wx.ICON_INFORMATION
            if updateFound:
                message = "Update found\n\n"
                message += "Local: " + time.strftime('%c',
                                                     time.localtime(local))
                message += "\nRemote: " + time.strftime('%c',
                                                        time.localtime(remote))
            else:
                message = "No updates found"

        dlg = wx.MessageDialog(self, message, "Update",
                               wx.OK | icon)
        dlg.ShowModal()
        dlg.Destroy()

    def __refresh_devices(self):
        self.settings.devicesRtl = get_devices_rtl(self.devicesRtl, self.status)
        if self.settings.indexRtl > len(self.devicesRtl) - 1:
            self.settings.indexRtl = 0
        self.settings.save()
        return self.settings.devicesRtl

    def __wait_background(self):
        self.Disconnect(-1, -1, EVENT_THREAD, self.__on_event)
        if self.threadScan:
            self.threadScan.abort()
            self.threadScan.join()
            self.threadScan = None
        self.pool.close()
        self.pool.join()

    def open(self, dirname, filename):
        if not os.path.exists(os.path.join(dirname, filename)):
            wx.MessageBox('File not found',
                          'Error', wx.OK | wx.ICON_ERROR)
            return

        self.__on_new(None)
        self.graph.get_canvas().draw()

        self.filename = os.path.splitext(filename)[0]
        self.settings.dirScans = dirname
        self.status.set_general("Opening: {0}".format(filename))

        self.scanInfo, spectrum, location = open_plot(dirname, filename)

        if len(spectrum) > 0:
            self.scanInfo.set_to_settings(self.settings)
            self.spectrum = spectrum
            self.location.clear()
            self.location.update(location)
            self.__saved(True)
            self.__set_controls()
            self.__set_control_state(True)
            self.__set_plot(spectrum, self.settings.annotate)
            self.graph.scale_plot(True)
            self.status.set_general("Finished")
            self.settings.fileHistory.AddFileToHistory(os.path.join(dirname,
                                                                    filename))
        else:
            self.status.set_general("Open failed", level=Log.ERROR)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
