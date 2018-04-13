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
import cPickle
import os

from PIL import Image
from matplotlib import mlab, patheffects
import matplotlib
import matplotlib.tri
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.ticker import ScalarFormatter
import numpy
from wx import grid
import wx
from wx.grid import GridCellDateTimeRenderer
from wx.lib.masked.numctrl import NumCtrl, EVT_NUM

from rtlsdr_scanner.constants import SAMPLE_RATE, TUNER
from rtlsdr_scanner.events import Event
from rtlsdr_scanner.file import export_image, File
from rtlsdr_scanner.misc import format_time
from rtlsdr_scanner.panels import PanelColourBar
from rtlsdr_scanner.plot_line import Plotter
from rtlsdr_scanner.spectrum import Extent, count_points
from rtlsdr_scanner.utils_mpl import get_colours, create_heatmap
from rtlsdr_scanner.utils_wx import ValidatorCoord
from rtlsdr_scanner.widgets import TickCellRenderer


class DialogProperties(wx.Dialog):

    def __init__(self, parent, scanInfo):
        wx.Dialog.__init__(self, parent, title="Scan Properties")

        self.scanInfo = scanInfo

        box = wx.BoxSizer(wx.VERTICAL)

        grid = wx.GridBagSizer(0, 0)

        boxScan = wx.StaticBoxSizer(wx.StaticBox(self, wx.ID_ANY, "Scan"),
                                    wx.HORIZONTAL)

        gridScan = wx.GridBagSizer(0, 0)

        textDesc = wx.StaticText(self, label="Description")
        gridScan.Add(textDesc, (0, 0), (1, 1), wx.ALL, 5)
        self.textCtrlDesc = wx.TextCtrl(self, value=scanInfo.desc,
                                        style=wx.TE_MULTILINE)
        gridScan.Add(self.textCtrlDesc, (0, 1), (2, 2), wx.ALL | wx.EXPAND, 5)

        textStart = wx.StaticText(self, label="Start")
        gridScan.Add(textStart, (2, 0), (1, 1), wx.ALL, 5)
        textCtrlStart = wx.TextCtrl(self, value="Unknown",
                                    style=wx.TE_READONLY)
        if scanInfo.start is not None:
            textCtrlStart.SetValue(str(scanInfo.start))
        gridScan.Add(textCtrlStart, (2, 1), (1, 1), wx.ALL, 5)
        textMHz1 = wx.StaticText(self, wx.ID_ANY, label="MHz")
        gridScan.Add(textMHz1, (2, 2), (1, 1), wx.ALL, 5)

        textStop = wx.StaticText(self, label="Stop")
        gridScan.Add(textStop, (3, 0), (1, 1), wx.ALL, 5)
        textCtrlStop = wx.TextCtrl(self, value="Unknown",
                                   style=wx.TE_READONLY)
        if scanInfo.stop is not None:
            textCtrlStop.SetValue(str(scanInfo.stop))
        gridScan.Add(textCtrlStop, (3, 1), (1, 1), wx.ALL, 5)
        textMHz2 = wx.StaticText(self, label="MHz")
        gridScan.Add(textMHz2, (3, 2), (1, 1), wx.ALL, 5)

        textDwell = wx.StaticText(self, label="Dwell")
        gridScan.Add(textDwell, (4, 0), (1, 1), wx.ALL, 5)
        textCtrlDwell = wx.TextCtrl(self, value="Unknown",
                                    style=wx.TE_READONLY)
        if scanInfo.dwell is not None:
            textCtrlDwell.SetValue(str(scanInfo.dwell))
        gridScan.Add(textCtrlDwell, (4, 1), (1, 1), wx.ALL, 5)
        textSeconds = wx.StaticText(self, label="seconds")
        gridScan.Add(textSeconds, (4, 2), (1, 1), wx.ALL, 5)

        textNfft = wx.StaticText(self, label="FFT Size")
        gridScan.Add(textNfft, (5, 0), (1, 1), wx.ALL, 5)
        textCtrlNfft = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.nfft is not None:
            textCtrlNfft.SetValue(str(scanInfo.nfft))
        gridScan.Add(textCtrlNfft, (5, 1), (1, 1), wx.ALL, 5)

        textRbw = wx.StaticText(self, label="RBW")
        gridScan.Add(textRbw, (6, 0), (1, 1), wx.ALL, 5)
        rbw = ((SAMPLE_RATE / scanInfo.nfft) / 1000.0) * 2.0
        textCtrlStop = wx.TextCtrl(self, value="{0:.3f}".format(rbw),
                                   style=wx.TE_READONLY)
        gridScan.Add(textCtrlStop, (6, 1), (1, 1), wx.ALL, 5)
        textKHz = wx.StaticText(self, label="kHz")
        gridScan.Add(textKHz, (6, 2), (1, 1), wx.ALL, 5)

        textTime = wx.StaticText(self, label="First scan")
        gridScan.Add(textTime, (7, 0), (1, 1), wx.ALL, 5)
        textCtrlTime = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.timeFirst is not None:
            textCtrlTime.SetValue(format_time(scanInfo.timeFirst, True))
        gridScan.Add(textCtrlTime, (7, 1), (1, 1), wx.ALL, 5)

        textTime = wx.StaticText(self, label="Last scan")
        gridScan.Add(textTime, (8, 0), (1, 1), wx.ALL, 5)
        textCtrlTime = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.timeLast is not None:
            textCtrlTime.SetValue(format_time(scanInfo.timeLast, True))
        gridScan.Add(textCtrlTime, (8, 1), (1, 1), wx.ALL, 5)

        textLat = wx.StaticText(self, label="Latitude")
        gridScan.Add(textLat, (9, 0), (1, 1), wx.ALL, 5)
        self.textCtrlLat = wx.TextCtrl(self, value="Unknown")
        self.textCtrlLat.SetValidator(ValidatorCoord(True))
        if scanInfo.lat is not None:
            self.textCtrlLat.SetValue(str(scanInfo.lat))
        gridScan.Add(self.textCtrlLat, (9, 1), (1, 1), wx.ALL, 5)

        textLon = wx.StaticText(self, label="Longitude")
        gridScan.Add(textLon, (10, 0), (1, 1), wx.ALL, 5)
        self.textCtrlLon = wx.TextCtrl(self, value="Unknown")
        self.textCtrlLon.SetValidator(ValidatorCoord(False))
        if scanInfo.lon is not None:
            self.textCtrlLon.SetValue(str(scanInfo.lon))
        gridScan.Add(self.textCtrlLon, (10, 1), (1, 1), wx.ALL, 5)

        boxScan.Add(gridScan, 0, 0, 5)

        grid.Add(boxScan, (0, 0), (1, 1), wx.ALL | wx.EXPAND, 5)

        boxDevice = wx.StaticBoxSizer(wx.StaticBox(self, label="Device"),
                                      wx.VERTICAL)

        gridDevice = wx.GridBagSizer(0, 0)

        textName = wx.StaticText(self, label="Name")
        gridDevice.Add(textName, (0, 0), (1, 1), wx.ALL, 5)
        textCtrlName = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.name is not None:
            textCtrlName.SetValue(scanInfo.name)
        gridDevice.Add(textCtrlName, (0, 1), (1, 2), wx.ALL | wx.EXPAND, 5)

        textTuner = wx.StaticText(self, label="Tuner")
        gridDevice.Add(textTuner, (1, 0), (1, 1), wx.ALL, 5)
        textCtrlTuner = wx.TextCtrl(self, value="Unknown",
                                    style=wx.TE_READONLY)
        if scanInfo.tuner != -1:
            textCtrlTuner.SetValue(TUNER[scanInfo.tuner])
        gridDevice.Add(textCtrlTuner, (1, 1), (1, 2), wx.ALL | wx.EXPAND, 5)

        testGain = wx.StaticText(self, label="Gain")
        gridDevice.Add(testGain, (2, 0), (1, 1), wx.ALL, 5)
        textCtrlGain = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.gain is not None:
            textCtrlGain.SetValue(str(scanInfo.gain))
        gridDevice.Add(textCtrlGain, (2, 1), (1, 1), wx.ALL, 5)
        textDb = wx.StaticText(self, label="dB")
        gridDevice.Add(textDb, (2, 2), (1, 1), wx.ALL, 5)

        textLo = wx.StaticText(self, label="LO")
        gridDevice.Add(textLo, (3, 0), (1, 1), wx.ALL, 5)
        textCtrlLo = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.lo is not None:
            textCtrlLo.SetValue(str(scanInfo.lo))
        gridDevice.Add(textCtrlLo, (3, 1), (1, 1), wx.ALL, 5)
        textMHz3 = wx.StaticText(self, label="MHz")
        gridDevice.Add(textMHz3, (3, 2), (1, 1), wx.ALL, 5)

        textCal = wx.StaticText(self, label="Calibration")
        gridDevice.Add(textCal, (4, 0), (1, 1), wx.ALL, 5)
        textCtrlCal = wx.TextCtrl(self, value="Unknown", style=wx.TE_READONLY)
        if scanInfo.calibration is not None:
            textCtrlCal.SetValue(str(scanInfo.calibration))
        gridDevice.Add(textCtrlCal, (4, 1), (1, 1), wx.ALL, 5)
        testPpm = wx.StaticText(self, label="ppm")
        gridDevice.Add(testPpm, (4, 2), (1, 1), wx.ALL, 5)

        boxDevice.Add(gridDevice, 1, wx.EXPAND, 5)

        grid.Add(boxDevice, (1, 0), (1, 1), wx.ALL | wx.EXPAND, 5)

        box.Add(grid, 1, wx.ALL | wx.EXPAND, 5)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)
        box.Add(sizerButtons, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        self.SetSizerAndFit(box)

    def __on_ok(self, _event):
        self.scanInfo.desc = self.textCtrlDesc.GetValue()
        if self.Validate():
            lat = self.textCtrlLat.GetValue()
            if len(lat) == 0 or lat == "-" or lat.lower() == "unknown":
                self.scanInfo.lat = None
            else:
                self.scanInfo.lat = float(lat)

            lon = self.textCtrlLon.GetValue()
            if len(lon) == 0 or lon == "-" or lon.lower() == "unknown":
                self.scanInfo.lon = None
            else:
                self.scanInfo.lon = float(lon)

            self.EndModal(wx.ID_CLOSE)


class DialogImageSize(wx.Dialog):

    def __init__(self, parent, settings, onlyDpi=False):
        wx.Dialog.__init__(self, parent=parent, title='Image settings')

        self.settings = settings

        textWidth = wx.StaticText(self, label="Width (inches)")
        self.ctrlWidth = NumCtrl(self, integerWidth=2, fractionWidth=1)
        self.ctrlWidth.SetValue(settings.exportWidth)
        self.Bind(EVT_NUM, self.__update_size, self.ctrlWidth)

        textHeight = wx.StaticText(self, label="Height (inches)")
        self.ctrlHeight = NumCtrl(self, integerWidth=2, fractionWidth=1)
        self.ctrlHeight.SetValue(settings.exportHeight)
        self.Bind(EVT_NUM, self.__update_size, self.ctrlHeight)

        textDpi = wx.StaticText(self, label="Dots per inch")
        self.spinDpi = wx.SpinCtrl(self)
        self.spinDpi.SetRange(32, 3200)
        self.spinDpi.SetValue(settings.exportDpi)
        self.Bind(wx.EVT_SPINCTRL, self.__update_size, self.spinDpi)

        textSize = wx.StaticText(self, label='Size')
        self.textSize = wx.StaticText(self)
        self.__update_size(None)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

        sizer = wx.GridBagSizer(5, 5)
        sizer.Add(textWidth, pos=(0, 0),
                  flag=wx.ALL, border=5)
        sizer.Add(self.ctrlWidth, pos=(0, 1),
                  flag=wx.ALL, border=5)
        sizer.Add(textHeight, pos=(1, 0),
                  flag=wx.ALL, border=5)
        sizer.Add(self.ctrlHeight, pos=(1, 1),
                  flag=wx.ALL, border=5)
        sizer.Add(textDpi, pos=(2, 0),
                  flag=wx.ALL, border=5)
        sizer.Add(self.spinDpi, pos=(2, 1),
                  flag=wx.ALL, border=5)
        sizer.Add(textSize, pos=(3, 0),
                  flag=wx.ALL, border=5)
        sizer.Add(self.textSize, pos=(3, 1),
                  flag=wx.ALL, border=5)
        sizer.Add(sizerButtons, pos=(4, 0), span=(1, 2),
                  flag=wx.ALL | wx.ALIGN_RIGHT, border=5)
        sizer.SetEmptyCellSize((0, 0))

        if onlyDpi:
            textWidth.Hide()
            self.ctrlWidth.Hide()
            textHeight.Hide()
            self.ctrlHeight.Hide()
            textSize.Hide()
            self.textSize.Hide()

        self.SetSizerAndFit(sizer)

    def __update_size(self, _event):
        width = self.ctrlWidth.GetValue()
        height = self.ctrlHeight.GetValue()
        dpi = self.spinDpi.GetValue()

        self.textSize.SetLabel('{:.0f}px x {:.0f}px'.format(width * dpi,
                                                            height * dpi))

    def __on_ok(self, _event):
        self.settings.exportWidth = self.ctrlWidth.GetValue()
        self.settings.exportHeight = self.ctrlHeight.GetValue()
        self.settings.exportDpi = self.spinDpi.GetValue()

        self.EndModal(wx.ID_OK)


class DialogExportSeq(wx.Dialog):
    POLL = 250

    def __init__(self, parent, spectrum, settings):
        self.spectrum = spectrum
        self.settings = settings
        self.sweeps = None
        self.isExporting = False

        wx.Dialog.__init__(self, parent=parent, title='Export Plot Sequence')

        self.queue = Queue.Queue()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.__on_timer, self.timer)
        self.timer.Start(self.POLL)

        self.figure = matplotlib.figure.Figure(facecolor='white')
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.plot = Plotter(self.queue, self.figure, settings)

        textPlot = wx.StaticText(self, label='Plot')

        self.checkAxes = wx.CheckBox(self, label='Axes')
        self.checkAxes.SetValue(True)
        self.Bind(wx.EVT_CHECKBOX, self.__on_axes, self.checkAxes)
        self.checkGrid = wx.CheckBox(self, label='Grid')
        self.checkGrid.SetValue(True)
        self.Bind(wx.EVT_CHECKBOX, self.__on_grid, self.checkGrid)
        self.checkBar = wx.CheckBox(self, label='Bar')
        self.checkBar.SetValue(True)
        self.Bind(wx.EVT_CHECKBOX, self.__on_bar, self.checkBar)

        sizerCheck = wx.BoxSizer(wx.HORIZONTAL)
        sizerCheck.Add(self.checkAxes, flag=wx.ALL, border=5)
        sizerCheck.Add(self.checkGrid, flag=wx.ALL, border=5)
        sizerCheck.Add(self.checkBar, flag=wx.ALL, border=5)

        textRange = wx.StaticText(self, label='Range')

        self.sweepTimeStamps = sorted([timeStamp for timeStamp in spectrum.keys()])
        sweepChoices = [format_time(timeStamp, True) for timeStamp in self.sweepTimeStamps]

        textStart = wx.StaticText(self, label="Start")
        self.choiceStart = wx.Choice(self, choices=sweepChoices)
        self.choiceStart.SetSelection(0)
        self.Bind(wx.EVT_CHOICE, self.__on_choice, self.choiceStart)

        textEnd = wx.StaticText(self, label="End")
        self.choiceEnd = wx.Choice(self, choices=sweepChoices)
        self.choiceEnd.SetSelection(len(self.sweepTimeStamps) - 1)
        self.Bind(wx.EVT_CHOICE, self.__on_choice, self.choiceEnd)

        textSweeps = wx.StaticText(self, label='Sweeps')
        self.textSweeps = wx.StaticText(self, label="")

        textOutput = wx.StaticText(self, label='Output')

        self.textSize = wx.StaticText(self)
        buttonSize = wx.Button(self, label='Change...')
        buttonSize.SetToolTipString('Change exported image size')
        self.Bind(wx.EVT_BUTTON, self.__on_imagesize, buttonSize)
        self.__show_image_size()

        buttonBrowse = wx.Button(self, label='Browse...')
        self.Bind(wx.EVT_BUTTON, self.__on_browse, buttonBrowse)

        self.editDir = wx.TextCtrl(self)
        self.editDir.SetValue(settings.dirExport)

        font = textPlot.GetFont()
        fontSize = font.GetPointSize()
        font.SetPointSize(fontSize + 4)
        textPlot.SetFont(font)
        textRange.SetFont(font)
        textOutput.SetFont(font)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

        sizerGrid = wx.GridBagSizer(5, 5)
        sizerGrid.Add(self.canvas, pos=(0, 0), span=(10, 6),
                      flag=wx.EXPAND | wx.ALL, border=5)
        sizerGrid.Add(textPlot, pos=(0, 7),
                      flag=wx.TOP | wx.BOTTOM, border=5)
        sizerGrid.Add(sizerCheck, pos=(1, 7), span=(1, 2),
                      flag=wx.ALL, border=5)
        sizerGrid.Add(textRange, pos=(2, 7),
                      flag=wx.TOP | wx.BOTTOM, border=5)
        sizerGrid.Add(textStart, pos=(3, 7),
                      flag=wx.ALIGN_CENTRE_VERTICAL | wx.ALL, border=5)
        sizerGrid.Add(self.choiceStart, pos=(3, 8),
                      flag=wx.ALL, border=5)
        sizerGrid.Add(textEnd, pos=(4, 7),
                      flag=wx.ALIGN_CENTRE_VERTICAL | wx.ALL, border=5)
        sizerGrid.Add(self.choiceEnd, pos=(4, 8),
                      flag=wx.ALL, border=5)
        sizerGrid.Add(textSweeps, pos=(5, 7),
                      flag=wx.ALIGN_CENTRE_VERTICAL | wx.ALL, border=5)
        sizerGrid.Add(self.textSweeps, pos=(5, 8),
                      flag=wx.ALIGN_CENTRE_VERTICAL | wx.ALL, border=5)
        sizerGrid.Add(textOutput, pos=(6, 7),
                      flag=wx.TOP | wx.BOTTOM, border=5)
        sizerGrid.Add(self.textSize, pos=(7, 7),
                      flag=wx.ALIGN_CENTRE_VERTICAL | wx.ALL, border=5)
        sizerGrid.Add(buttonSize, pos=(7, 8),
                      flag=wx.ALL, border=5)
        sizerGrid.Add(self.editDir, pos=(8, 7), span=(1, 2),
                      flag=wx.ALL | wx.EXPAND, border=5)
        sizerGrid.Add(buttonBrowse, pos=(9, 7),
                      flag=wx.ALL, border=5)
        sizerGrid.Add(sizerButtons, pos=(10, 7), span=(1, 2),
                      flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(sizerGrid)

        self.__draw_plot()

    def __on_choice(self, event):
        start = self.choiceStart.GetSelection()
        end = self.choiceEnd.GetSelection()
        control = event.GetEventObject()

        if start > end:
            if control == self.choiceStart:
                self.choiceStart.SetSelection(end)
            else:
                self.choiceEnd.SetSelection(start)

        self.__draw_plot()

    def __on_axes(self, _event):
        self.plot.set_axes(self.checkAxes.GetValue())
        self.__draw_plot()

    def __on_grid(self, _event):
        self.plot.set_grid(self.checkGrid.GetValue())
        self.__draw_plot()

    def __on_bar(self, _event):
        self.plot.set_bar(self.checkBar.GetValue())
        self.__draw_plot()

    def __on_imagesize(self, _event):
        dlg = DialogImageSize(self, self.settings)
        dlg.ShowModal()
        self.__show_image_size()

    def __on_browse(self, _event):
        directory = self.editDir.GetValue()
        dlg = wx.DirDialog(self, 'Output directory', directory)
        if dlg.ShowModal() == wx.ID_OK:
            directory = dlg.GetPath()
            self.editDir.SetValue(directory)

    def __on_timer(self, _event):
        self.timer.Stop()
        if not self.isExporting:
            while not self.queue.empty():
                event = self.queue.get()
                status = event.data.get_status()

                if status == Event.DRAW:
                    self.canvas.draw()

        self.timer.Start(self.POLL)

    def __on_ok(self, _event):
        self.isExporting = True
        extent = Extent(self.spectrum)
        dlgProgress = wx.ProgressDialog('Exporting', '', len(self.sweeps),
                                        style=wx.PD_AUTO_HIDE | 
                                        wx.PD_CAN_ABORT | 
                                        wx.PD_REMAINING_TIME)

        try:
            count = 1
            for timeStamp, sweep in self.sweeps.items():
                name = '{0:.0f}.png'.format(timeStamp)
                directory = self.editDir.GetValue()
                filename = os.path.join(directory, name)

                thread = self.plot.set_plot({timeStamp: sweep}, extent, False)
                thread.join()
                filename = os.path.join(directory, '{}.png'.format(timeStamp))
                export_image(filename, File.ImageType.PNG,
                             self.figure,
                             self.settings)

                cont, _skip = dlgProgress.Update(count, name)
                if not cont:
                    break
                count += 1
        except IOError as error:
            wx.MessageBox(error.strerror, 'Error', wx.OK | wx.ICON_WARNING)
        finally:
            dlgProgress.Destroy()
            self.EndModal(wx.ID_OK)

    def __spectrum_range(self, start, end):
        sweeps = {}
        for timeStamp, sweep in self.spectrum.items():
            if start <= timeStamp <= end:
                sweeps[timeStamp] = sweep

        self.sweeps = sweeps

    def __draw_plot(self):
        start, end = self.__get_range()
        self.__spectrum_range(start, end)

        self.textSweeps.SetLabel(str(len(self.sweeps)))

        if len(self.sweeps) > 0:
            total = count_points(self.sweeps)
            if total > 0:
                extent = Extent(self.spectrum)
                self.plot.set_plot(self.sweeps, extent, False)
        else:
            self.plot.clear_plots()

    def __show_image_size(self):
        self.textSize.SetLabel('{}" x {}" @ {}dpi'.format(self.settings.exportWidth,
                                                          self.settings.exportHeight,
                                                          self.settings.exportDpi))

    def __get_range(self):
        start = self.sweepTimeStamps[self.choiceStart.GetSelection()]
        end = self.sweepTimeStamps[self.choiceEnd.GetSelection()]

        return start, end


class DialogExportGeo(wx.Dialog):
    IMAGE_SIZE = 500

    def __init__(self, parent, spectrum, location, settings):
        self.spectrum = spectrum
        self.location = location
        self.settings = settings
        self.directory = settings.dirExport
        self.colourMap = settings.colourMap
        self.colourHeat = settings.colourMap
        self.canvas = None
        self.extent = None
        self.xyz = None
        self.plotAxes = False
        self.plotMesh = True
        self.plotCont = True
        self.plotPoint = False
        self.plotHeat = False
        self.plot = None

        wx.Dialog.__init__(self, parent=parent, title='Export Map')

        colours = get_colours()
        freqMin = min(spectrum[min(spectrum)]) * 1000
        freqMax = max(spectrum[min(spectrum)]) * 1000
        bw = freqMax - freqMin

        self.figure = matplotlib.figure.Figure(facecolor='white')
        self.figure.set_size_inches((6, 6))
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.axes = self.figure.add_subplot(111)
        if matplotlib.__version__ >= '1.2':
            self.figure.tight_layout()
        self.figure.subplots_adjust(left=0, right=1, top=1, bottom=0)

        textPlot = wx.StaticText(self, label='Plot')
        self.checkAxes = wx.CheckBox(self, label='Axes')
        self.checkAxes.SetValue(self.plotAxes)
        self.Bind(wx.EVT_CHECKBOX, self.__on_axes, self.checkAxes)
        self.checkCont = wx.CheckBox(self, label='Contour lines')
        self.checkCont.SetValue(self.plotCont)
        self.Bind(wx.EVT_CHECKBOX, self.__on_cont, self.checkCont)
        self.checkPoint = wx.CheckBox(self, label='Locations')
        self.checkPoint.SetValue(self.plotPoint)
        self.Bind(wx.EVT_CHECKBOX, self.__on_point, self.checkPoint)
        sizerPlotCheck = wx.BoxSizer(wx.HORIZONTAL)
        sizerPlotCheck.Add(self.checkAxes, flag=wx.ALL, border=5)
        sizerPlotCheck.Add(self.checkCont, flag=wx.ALL, border=5)
        sizerPlotCheck.Add(self.checkPoint, flag=wx.ALL, border=5)
        sizerPlot = wx.BoxSizer(wx.VERTICAL)
        sizerPlot.Add(textPlot, flag=wx.ALL, border=5)
        sizerPlot.Add(sizerPlotCheck, flag=wx.ALL, border=5)

        textMesh = wx.StaticText(self, label='Mesh')
        self.checkMesh = wx.CheckBox(self, label='On')
        self.checkMesh.SetToolTipString('Signal level mesh')
        self.checkMesh.SetValue(self.plotMesh)
        self.Bind(wx.EVT_CHECKBOX, self.__on_mesh, self.checkMesh)
        self.choiceMapMesh = wx.Choice(self, choices=colours)
        self.choiceMapMesh.SetSelection(colours.index(self.colourMap))
        self.Bind(wx.EVT_CHOICE, self.__on_colour_mesh, self.choiceMapMesh)
        self.barMesh = PanelColourBar(self, self.colourMap)
        sizerMapMesh = wx.BoxSizer(wx.HORIZONTAL)
        sizerMapMesh.Add(self.choiceMapMesh, flag=wx.ALL, border=5)
        sizerMapMesh.Add(self.barMesh, flag=wx.ALL, border=5)
        sizerMesh = wx.BoxSizer(wx.VERTICAL)
        sizerMesh.Add(textMesh, flag=wx.ALL, border=5)
        sizerMesh.Add(self.checkMesh, flag=wx.ALL, border=5)
        sizerMesh.Add(sizerMapMesh, flag=wx.ALL, border=5)

        colours = get_colours()
        textHeat = wx.StaticText(self, label='Heat map')
        self.checkHeat = wx.CheckBox(self, label='On')
        self.checkHeat.SetToolTipString('GPS location heatmap')
        self.checkHeat.SetValue(self.plotHeat)
        self.Bind(wx.EVT_CHECKBOX, self.__on_heat, self.checkHeat)
        self.choiceMapHeat = wx.Choice(self, choices=colours)
        self.choiceMapHeat.SetSelection(colours.index(self.colourHeat))
        self.Bind(wx.EVT_CHOICE, self.__on_colour_heat, self.choiceMapHeat)
        self.barHeat = PanelColourBar(self, self.colourHeat)
        sizerMapHeat = wx.BoxSizer(wx.HORIZONTAL)
        sizerMapHeat.Add(self.choiceMapHeat, flag=wx.ALL, border=5)
        sizerMapHeat.Add(self.barHeat, flag=wx.ALL, border=5)
        sizerHeat = wx.BoxSizer(wx.VERTICAL)
        sizerHeat.Add(textHeat, flag=wx.ALL, border=5)
        sizerHeat.Add(self.checkHeat, flag=wx.ALL, border=5)
        sizerHeat.Add(sizerMapHeat, flag=wx.ALL, border=5)

        textRange = wx.StaticText(self, label='Range')
        textCentre = wx.StaticText(self, label='Centre')
        self.spinCentre = wx.SpinCtrl(self)
        self.spinCentre.SetToolTipString('Centre frequency (kHz)')
        self.spinCentre.SetRange(freqMin, freqMax)
        self.spinCentre.SetValue(freqMin + bw / 2)
        sizerCentre = wx.BoxSizer(wx.HORIZONTAL)
        sizerCentre.Add(textCentre, flag=wx.ALL, border=5)
        sizerCentre.Add(self.spinCentre, flag=wx.ALL, border=5)
        textBw = wx.StaticText(self, label='Bandwidth')
        self.spinBw = wx.SpinCtrl(self)
        self.spinBw.SetToolTipString('Bandwidth (kHz)')
        self.spinBw.SetRange(1, bw)
        self.spinBw.SetValue(bw / 10)
        sizerBw = wx.BoxSizer(wx.HORIZONTAL)
        sizerBw.Add(textBw, flag=wx.ALL, border=5)
        sizerBw.Add(self.spinBw, flag=wx.ALL, border=5)
        buttonUpdate = wx.Button(self, label='Update')
        self.Bind(wx.EVT_BUTTON, self.__on_update, buttonUpdate)
        sizerRange = wx.BoxSizer(wx.VERTICAL)
        sizerRange.Add(textRange, flag=wx.ALL, border=5)
        sizerRange.Add(sizerCentre, flag=wx.ALL, border=5)
        sizerRange.Add(sizerBw, flag=wx.ALL, border=5)
        sizerRange.Add(buttonUpdate, flag=wx.ALL, border=5)

        textOutput = wx.StaticText(self, label='Output')
        self.textRes = wx.StaticText(self)
        buttonRes = wx.Button(self, label='Change...')
        buttonRes.SetToolTipString('Change output resolution')
        self.Bind(wx.EVT_BUTTON, self.__on_imageres, buttonRes)
        sizerRes = wx.BoxSizer(wx.HORIZONTAL)
        sizerRes.Add(self.textRes, flag=wx.ALL, border=5)
        sizerRes.Add(buttonRes, flag=wx.ALL, border=5)
        sizerOutput = wx.BoxSizer(wx.VERTICAL)
        sizerOutput.Add(textOutput, flag=wx.ALL, border=5)
        sizerOutput.Add(sizerRes, flag=wx.ALL, border=5)

        self.__show_image_res()

        font = textPlot.GetFont()
        fontSize = font.GetPointSize()
        font.SetPointSize(fontSize + 4)
        textPlot.SetFont(font)
        textMesh.SetFont(font)
        textHeat.SetFont(font)
        textRange.SetFont(font)
        textOutput.SetFont(font)

        sizerButtons = wx.StdDialogButtonSizer()
        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

        self.__setup_plot()

        sizerGrid = wx.GridBagSizer(5, 5)
        sizerGrid.Add(self.canvas, pos=(0, 0), span=(5, 6),
                      flag=wx.EXPAND | wx.ALL, border=5)
        sizerGrid.Add(sizerPlot, pos=(0, 7),
                      flag=wx.EXPAND | wx.ALL, border=5)
        sizerGrid.Add(sizerMesh, pos=(1, 7),
                      flag=wx.EXPAND | wx.ALL, border=5)
        sizerGrid.Add(sizerHeat, pos=(2, 7),
                      flag=wx.EXPAND | wx.ALL, border=5)
        sizerGrid.Add(sizerRange, pos=(3, 7),
                      flag=wx.EXPAND | wx.ALL, border=5)
        sizerGrid.Add(sizerOutput, pos=(4, 7),
                      flag=wx.EXPAND | wx.ALL, border=5)
        sizerGrid.Add(sizerButtons, pos=(5, 7), span=(1, 2),
                      flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        self.SetSizerAndFit(sizerGrid)

        self.__draw_plot()

    def __setup_plot(self):
        self.axes.clear()

        self.choiceMapMesh.Enable(self.plotMesh)
        self.choiceMapHeat.Enable(self.plotHeat)

        self.axes.set_xlabel('Longitude ($^\circ$)')
        self.axes.set_ylabel('Latitude ($^\circ$)')
        self.axes.set_xlim(auto=True)
        self.axes.set_ylim(auto=True)
        formatter = ScalarFormatter(useOffset=False)
        self.axes.xaxis.set_major_formatter(formatter)
        self.axes.yaxis.set_major_formatter(formatter)

    def __draw_plot(self):
        freqCentre = self.spinCentre.GetValue()
        freqBw = self.spinBw.GetValue()
        freqMin = (freqCentre - freqBw) / 1000.
        freqMax = (freqCentre + freqBw) / 1000.

        coords = {}
        for timeStamp in self.spectrum:
            spectrum = self.spectrum[timeStamp]
            sweep = [yv for xv, yv in spectrum.items() if freqMin <= xv <= freqMax]
            if len(sweep):
                peak = max(sweep)
                try:
                    location = self.location[timeStamp]
                except KeyError:
                    continue

                coord = tuple(location[0:2])
                if coord not in coords:
                    coords[coord] = peak
                else:
                    coords[coord] = (coords[coord] + peak) / 2

        x = []
        y = []
        z = []

        for coord, peak in coords.iteritems():
            x.append(coord[1])
            y.append(coord[0])
            z.append(peak)

        self.extent = (min(x), max(x), min(y), max(y))
        self.xyz = (x, y, z)

        xi, yi = numpy.meshgrid(numpy.linspace(min(x), max(x), self.IMAGE_SIZE),
                                numpy.linspace(min(y), max(y), self.IMAGE_SIZE))

        if self.plotMesh or self.plotCont:
            triangle = matplotlib.tri.Triangulation(x, y)
            interp = matplotlib.tri.CubicTriInterpolator(triangle, z, kind='geom')
            zi = interp(xi, yi)
            
        if self.plotMesh:
            self.plot = self.axes.pcolormesh(xi, yi, zi, cmap=self.colourMap)
            self.plot.set_zorder(1)
 
        if self.plotCont:
            contours = self.axes.contour(xi, yi, zi, linewidths=0.5,
                                         colors='k')
            self.axes.clabel(contours, inline=1, fontsize='x-small',
                            gid='clabel', zorder=3)

        if self.plotHeat:
            image = create_heatmap(x, y,
                                   self.IMAGE_SIZE, self.IMAGE_SIZE / 10,
                                   self.colourHeat)
            heatMap = self.axes.imshow(image, aspect='auto', extent=self.extent)
            heatMap.set_zorder(2)

        if self.plotPoint:
            self.axes.plot(x, y, 'wo')
            for posX, posY, posZ in zip(x, y, z):
                points = self.axes.annotate('{0:.2f}dB'.format(posZ), xy=(posX, posY),
                                            xytext=(-5, 5), ha='right',
                                            textcoords='offset points')
                points.set_zorder(3)

        if matplotlib.__version__ >= '1.3':
            effect = patheffects.withStroke(linewidth=2, foreground="w",
                                            alpha=0.75)
            for child in self.axes.get_children():
                child.set_path_effects([effect])

        if self.plotAxes:
            self.axes.set_axis_on()
        else:
            self.axes.set_axis_off()
        self.canvas.draw()

    def __draw_warning(self):
        self.axes.text(0.5, 0.5, 'Insufficient GPS data',
                       ha='center', va='center',
                       transform=self.axes.transAxes)

    def __on_update(self, _event):
        self.__setup_plot()
        self.__draw_plot()

    def __on_imageres(self, _event):
        dlg = DialogImageSize(self, self.settings, True)
        dlg.ShowModal()
        self.__show_image_res()

    def __on_ok(self, _event):
        self.EndModal(wx.ID_OK)

    def __on_axes(self, _event):
        self.plotAxes = self.checkAxes.GetValue()
        if self.plotAxes:
            self.axes.set_axis_on()
        else:
            self.axes.set_axis_off()
        self.canvas.draw()

    def __on_mesh(self, _event):
        self.plotMesh = self.checkMesh.GetValue()
        self.__on_update(None)

    def __on_cont(self, _event):
        self.plotCont = self.checkCont.GetValue()
        self.__on_update(None)

    def __on_point(self, _event):
        self.plotPoint = self.checkPoint.GetValue()
        self.__on_update(None)

    def __on_heat(self, _event):
        self.plotHeat = self.checkHeat.GetValue()
        self.__on_update(None)

    def __on_colour_mesh(self, _event):
        self.colourMesh = self.choiceMapMesh.GetStringSelection()
        self.barMesh.set_map(self.colourMesh)
        if self.plot:
            self.plot.set_cmap(self.colourMesh)
            self.canvas.draw()

    def __on_colour_heat(self, _event):
        self.colourHeat = self.choiceMapHeat.GetStringSelection()
        self.barHeat.set_map(self.colourHeat)
        self.__on_update(None)

    def __show_image_res(self):
        self.textRes.SetLabel('{}dpi'.format(self.settings.exportDpi))

    def get_filename(self):
        return self.filename

    def get_directory(self):
        return self.directory

    def get_extent(self):
        return self.extent

    def get_image(self):
        width = self.extent[1] - self.extent[0]
        height = self.extent[3] - self.extent[2]
        self.figure.set_size_inches((6, 6. * width / height))
        self.figure.set_dpi(self.settings.exportDpi)
        self.figure.patch.set_alpha(0)
        self.axes.patch.set_alpha(0)
        canvas = FigureCanvasAgg(self.figure)
        canvas.draw()

        renderer = canvas.get_renderer()
        if matplotlib.__version__ >= '1.2':
            buf = renderer.buffer_rgba()
        else:
            buf = renderer.buffer_rgba(0, 0)
        size = canvas.get_width_height()
        image = Image.frombuffer('RGBA', size, buf, 'raw', 'RGBA', 0, 1)

        return image

    def get_xyz(self):
        return self.xyz


class DialogSaveWarn(wx.Dialog):

    def __init__(self, parent, warnType):
        self.code = -1

        wx.Dialog.__init__(self, parent=parent, title="Warning")

        prompt = ["scanning again", "opening a file",
                  "exiting", "clearing", "merging"][warnType]
        text = wx.StaticText(self,
                             label="Save plot_line before {}?".format(prompt))
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

        buttonYes.Bind(wx.EVT_BUTTON, self.__on_close)
        buttonNo.Bind(wx.EVT_BUTTON, self.__on_close)

        buttons = wx.StdDialogButtonSizer()
        buttons.AddButton(buttonYes)
        buttons.AddButton(buttonNo)
        buttons.AddButton(buttonCancel)
        buttons.Realize()

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(hbox, 1, wx.ALL | wx.EXPAND, 10)
        vbox.Add(buttons, 1, wx.ALL | wx.EXPAND, 10)

        self.SetSizerAndFit(vbox)

    def __on_close(self, event):
        self.EndModal(event.GetId())
        return

    def get_code(self):
        return self.code


class DialogRestore(wx.Dialog):
    COL_SEL, COL_TIME, COL_SIZE = range(3)

    def __init__(self, parent, backups):
        self.selected = 0
        self.backups = backups
        self.restored = None

        wx.Dialog.__init__(self, parent=parent, title='Restore backups')

        self.grid = grid.Grid(self)
        self.grid.CreateGrid(1, 3)
        self.grid.SetRowLabelSize(0)
        self.grid.SetColLabelValue(self.COL_SEL, 'Selected')
        self.grid.SetColLabelValue(self.COL_TIME, 'Time')
        self.grid.SetColLabelValue(self.COL_SIZE, 'Size (k)')
        self.grid.SetColFormatFloat(self.COL_SIZE, -1, 1)

        self.Bind(grid.EVT_GRID_CELL_LEFT_CLICK, self.__on_click)

        buttonRest = wx.Button(self, wx.ID_OPEN, 'Restore')
        buttonDel = wx.Button(self, wx.ID_DELETE, 'Delete')
        buttonDelAll = wx.Button(self, wx.ID_DELETE, 'Delete all')
        buttonCancel = wx.Button(self, wx.ID_CANCEL, 'Close')
        self._buttonsBackup = [buttonRest, buttonDel, buttonDelAll]

        buttonRest.Bind(wx.EVT_BUTTON, self.__on_restore)
        buttonDel.Bind(wx.EVT_BUTTON, self.__on_delete)
        buttonDelAll.Bind(wx.EVT_BUTTON, self.__on_delete_all)

        sizerButtons = wx.BoxSizer(wx.HORIZONTAL)
        sizerButtons.Add(buttonRest)
        sizerButtons.Add(buttonDel)
        sizerButtons.Add(buttonDelAll)
        sizerButtons.Add(buttonCancel)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.grid, flag=wx.ALL | wx.EXPAND, border=5)
        sizer.Add(sizerButtons, flag=wx.ALL, border=5)

        self.__update()

        self.SetSizerAndFit(sizer)

    def __update(self):
        if self.grid.GetNumberRows():
            self.grid.DeleteRows(0, self.grid.GetNumberRows())
        self.grid.AppendRows(len(self.backups.backups))

        i = 0
        for backup in self.backups.backups:
            self.grid.SetCellRenderer(i, self.COL_SEL, TickCellRenderer())
            self.grid.SetCellRenderer(i, self.COL_TIME,
                                      GridCellDateTimeRenderer())
            self.grid.SetReadOnly(i, self.COL_TIME, True)
            self.grid.SetReadOnly(i, self.COL_SIZE, True)

            self.grid.SetCellValue(i, self.COL_TIME,
                                   str(backup[1].replace(microsecond=0)))
            self.grid.SetCellValue(i, self.COL_SIZE, str(backup[2]))
            i += 1

        self.__select_row(0)

        self.grid.AutoSize()

        for button in self._buttonsBackup:
            button.Enable(len(self.backups.backups))

    def __on_click(self, event):
        col = event.GetCol()

        if col == self.COL_SEL:
            row = event.GetRow()
            self.selected = row
            self.__select_row(row)

    def __on_restore(self, event):
        try:
            self.restored = self.backups.load(self.selected)
        except (cPickle.UnpicklingError, AttributeError,
                EOFError, ImportError, IndexError, ValueError):
            wx.MessageBox('The file could not be restored', 'Restore failed',
                          wx.OK | wx.ICON_ERROR)
            return

        self.EndModal(event.GetId())

    def __on_delete(self, _event):
        dlg = wx.MessageDialog(self, 'Delete the selected backup?',
                               'Delete backup',
                               wx.OK | wx.CANCEL | wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_OK:
            self.backups.delete(self.selected)
            self.__update()

    def __on_delete_all(self, _event):
        dlg = wx.MessageDialog(self, 'Delete all the backups?',
                               'Delete all backups',
                               wx.OK | wx.CANCEL | wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_OK:
            for i in range(len(self.backups.backups)):
                self.backups.delete(i)
        self.__update()

    def __select_row(self, index):
        self.grid.ClearSelection()
        for i in range(0, self.grid.GetNumberRows()):
            tick = "0"
            if i == index:
                tick = "1"
            self.grid.SetCellValue(i, self.COL_SEL, tick)

    def get_restored(self):
        return self.restored


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
