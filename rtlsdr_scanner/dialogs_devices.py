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
import copy
from urlparse import urlparse

from wx import grid
import wx

from rtlsdr_scanner.constants import TUNER
from rtlsdr_scanner.widgets import TickCellRenderer, SatLevel
from rtlsdr_scanner.devices import DeviceRTL, DeviceGPS
from rtlsdr_scanner.dialogs_prefs import DialogOffset
from rtlsdr_scanner.events import Event
from rtlsdr_scanner.location import ThreadLocation
from rtlsdr_scanner.misc import nearest, limit, get_serial_ports


class DialogDevicesRTL(wx.Dialog):
    COLS = 10
    COL_SEL, COL_DEV, COL_TUN, COL_SER, COL_IND, \
        COL_GAIN, COL_CAL, COL_LEVOFF, COL_LO, COL_OFF = range(COLS)

    def __init__(self, parent, devices, settings):
        self.devices = copy.copy(devices)
        self.settings = settings
        self.index = None

        wx.Dialog.__init__(self, parent=parent, title="Radio Devices")

        self.gridDev = grid.Grid(self)
        self.gridDev.CreateGrid(len(self.devices), self.COLS)
        self.gridDev.SetRowLabelSize(0)
        self.gridDev.SetColLabelValue(self.COL_SEL, "Selected")
        self.gridDev.SetColLabelValue(self.COL_DEV, "Device")
        self.gridDev.SetColLabelValue(self.COL_TUN, "Tuner")
        self.gridDev.SetColLabelValue(self.COL_SER, "Serial Number")
        self.gridDev.SetColLabelValue(self.COL_IND, "Index")
        self.gridDev.SetColLabelValue(self.COL_GAIN, "Gain\n(dB)")
        self.gridDev.SetColLabelValue(self.COL_CAL, "Frequency\nCalibration\n(ppm)")
        self.gridDev.SetColLabelValue(self.COL_LEVOFF, "Level\nOffset\n(dB)")
        self.gridDev.SetColLabelValue(self.COL_LO, "LO\n(MHz)")
        self.gridDev.SetColLabelValue(self.COL_OFF, "Band Offset\n(kHz)")
        self.gridDev.SetColFormatFloat(self.COL_GAIN, -1, 1)
        self.gridDev.SetColFormatFloat(self.COL_CAL, -1, 3)
        self.gridDev.SetColFormatFloat(self.COL_LEVOFF, -1, 2)
        self.gridDev.SetColFormatFloat(self.COL_LO, -1, 3)
        self.gridDev.SetColFormatFloat(self.COL_OFF, -1, 0)

        dc = wx.ScreenDC()
        dc.SetFont(self.gridDev.GetLabelFont())
        maxHeight = 0
        for i in range(self.COLS - 1):
            _w, h, _hl = dc.GetMultiLineTextExtent(self.gridDev.GetColLabelValue(i))
            if h > maxHeight:
                maxHeight = h
        self.gridDev.SetColLabelSize(maxHeight * 1.25)

        self.__set_dev_grid()
        self.Bind(grid.EVT_GRID_CELL_LEFT_CLICK, self.__on_click)

        serverSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonAdd = wx.Button(self, wx.ID_ADD)
        self.buttonDel = wx.Button(self, wx.ID_DELETE)
        self.Bind(wx.EVT_BUTTON, self.__on_add, buttonAdd)
        self.Bind(wx.EVT_BUTTON, self.__on_del, self.buttonDel)
        serverSizer.Add(buttonAdd, 0, wx.ALL)
        serverSizer.Add(self.buttonDel, 0, wx.ALL)
        self.__set_button_state()

        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons = wx.StdDialogButtonSizer()
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

        self.devbox = wx.BoxSizer(wx.VERTICAL)
        self.devbox.Add(self.gridDev, 1, wx.ALL | wx.EXPAND, 10)
        self.devbox.Add(serverSizer, 0, wx.ALL | wx.EXPAND, 10)
        self.devbox.Add(sizerButtons, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizerAndFit(self.devbox)

    def __set_dev_grid(self):
        colourBackground = self.gridDev.GetLabelBackgroundColour()
        attributes = grid.GridCellAttr()
        attributes.SetBackgroundColour(colourBackground)
        self.gridDev.SetColAttr(self.COL_IND, attributes)

        self.gridDev.ClearGrid()

        i = 0
        for device in self.devices:
            self.gridDev.SetReadOnly(i, self.COL_SEL, True)
            self.gridDev.SetReadOnly(i, self.COL_DEV, device.isDevice)
            self.gridDev.SetReadOnly(i, self.COL_TUN, True)
            self.gridDev.SetReadOnly(i, self.COL_SER, True)
            self.gridDev.SetReadOnly(i, self.COL_IND, True)
            self.gridDev.SetCellRenderer(i, self.COL_SEL,
                                         TickCellRenderer())
            if device.isDevice:
                cell = grid.GridCellChoiceEditor(map(str, device.gains),
                                                 allowOthers=False)
                self.gridDev.SetCellEditor(i, self.COL_GAIN, cell)
            self.gridDev.SetCellEditor(i, self.COL_CAL,
                                       grid.GridCellFloatEditor(-1, 3))
            self.gridDev.SetCellEditor(i, self.COL_LEVOFF,
                                       grid.GridCellFloatEditor(-1, 3))
            self.gridDev.SetCellEditor(i, self.COL_LO,
                                       grid.GridCellFloatEditor(-1, 3))
            if device.isDevice:
                self.gridDev.SetCellValue(i, self.COL_DEV, device.name)
                self.gridDev.SetCellValue(i, self.COL_SER, str(device.serial))
                self.gridDev.SetCellValue(i, self.COL_IND, str(i))
                self.gridDev.SetCellBackgroundColour(i, self.COL_DEV,
                                                     colourBackground)
                self.gridDev.SetCellValue(i, self.COL_GAIN,
                                          str(nearest(device.gain,
                                                      device.gains)))
            else:
                self.gridDev.SetCellValue(i, self.COL_DEV,
                                          '{}:{}'.format(device.server,
                                                         device.port))
                self.gridDev.SetCellValue(i, self.COL_SER, '')
                self.gridDev.SetCellValue(i, self.COL_IND, '')
                self.gridDev.SetCellValue(i, self.COL_GAIN, str(device.gain))
            self.gridDev.SetCellBackgroundColour(i, self.COL_SER,
                                                 colourBackground)

            self.gridDev.SetCellValue(i, self.COL_TUN, TUNER[device.tuner])
            self.gridDev.SetCellValue(i, self.COL_CAL, str(device.calibration))
            self.gridDev.SetCellValue(i, self.COL_LEVOFF, str(device.levelOff))
            self.gridDev.SetCellValue(i, self.COL_LO, str(device.lo))
            self.gridDev.SetCellValue(i, self.COL_OFF, str(device.offset / 1e3))
            i += 1

        if self.settings.indexRtl >= len(self.devices):
            self.settings.indexRtl = len(self.devices) - 1
        self.__select_row(self.settings.indexRtl)
        self.index = self.settings.indexRtl

        self.gridDev.AutoSize()

    def __get_dev_grid(self):
        i = 0
        for device in self.devices:
            if not device.isDevice:
                server = self.gridDev.GetCellValue(i, self.COL_DEV)
                server = '//' + server
                url = urlparse(server)
                if url.hostname is not None:
                    device.server = url.hostname
                else:
                    device.server = 'localhost'
                if url.port is not None:
                    device.port = url.port
                else:
                    device.port = 1234
            device.gain = float(self.gridDev.GetCellValue(i, self.COL_GAIN))
            device.calibration = float(self.gridDev.GetCellValue(i, self.COL_CAL))
            device.levelOff = float(self.gridDev.GetCellValue(i, self.COL_LEVOFF))
            device.lo = float(self.gridDev.GetCellValue(i, self.COL_LO))
            device.offset = float(self.gridDev.GetCellValue(i, self.COL_OFF)) * 1e3
            i += 1

    def __set_button_state(self):
        if len(self.devices) > 0:
            self.buttonDel.Enable()
        else:
            self.buttonDel.Disable()
        if len(self.devices) == 1:
            self.__select_row(0)

    def __warn_duplicates(self):
        servers = []
        for device in self.devices:
            if not device.isDevice:
                servers.append("{}:{}".format(device.server, device.port))

        dupes = set(servers)
        if len(dupes) != len(servers):
            message = "Duplicate server found:\n'{}'".format(dupes.pop())
            dlg = wx.MessageDialog(self, message, "Warning",
                                   wx.OK | wx.ICON_WARNING)
            dlg.ShowModal()
            dlg.Destroy()
            return True

        return False

    def __on_click(self, event):
        col = event.GetCol()
        index = event.GetRow()
        if col == self.COL_SEL:
            self.index = event.GetRow()
            self.__select_row(index)
        elif col == self.COL_OFF:
            device = self.devices[index]
            dlg = DialogOffset(self, device,
                               float(self.gridDev.GetCellValue(index,
                                                               self.COL_OFF)),
                               self.settings.winFunc)
            if dlg.ShowModal() == wx.ID_OK:
                self.gridDev.SetCellValue(index, self.COL_OFF,
                                          str(dlg.get_offset()))
            dlg.Destroy()
        else:
            self.gridDev.ForceRefresh()
            event.Skip()

        self.__set_button_state()

    def __on_add(self, _event):
        device = DeviceRTL()
        device.isDevice = False
        self.devices.append(device)
        self.gridDev.AppendRows(1)
        self.__set_dev_grid()
        self.SetSizerAndFit(self.devbox)
        self.__set_button_state()

    def __on_del(self, _event):
        del self.devices[self.index]
        self.gridDev.DeleteRows(self.index)
        self.__set_dev_grid()
        self.SetSizerAndFit(self.devbox)
        self.__set_button_state()

    def __on_ok(self, _event):
        self.__get_dev_grid()
        if self.__warn_duplicates():
            return
        self.EndModal(wx.ID_OK)

    def __select_row(self, index):
        self.gridDev.ClearSelection()
        for i in range(0, len(self.devices)):
            tick = "0"
            if i == index:
                tick = "1"
            self.gridDev.SetCellValue(i, self.COL_SEL, tick)

    def get_index(self):
        return self.index

    def get_devices(self):
        return self.devices


class DialogDevicesGPS(wx.Dialog):
    COL_SEL, COL_NAME, COL_TYPE, COL_HOST, COL_TEST = range(5)

    def __init__(self, parent, settings):
        self.settings = settings
        self.index = settings.indexGps
        self.devices = copy.copy(settings.devicesGps)
        self.comboType = None

        wx.Dialog.__init__(self, parent=parent, title="GPS")

        self.checkGps = wx.CheckBox(self, wx.ID_ANY, "Enable GPS")
        self.checkGps.SetToolTipString('Record GPS locations in scans')
        self.checkGps.SetValue(settings.gps)
        self.Bind(wx.EVT_CHECKBOX, self.__on_check, self.checkGps)

        self.checkGpsRetry = wx.CheckBox(self, wx.ID_ANY, "Retry after disconnection")
        self.checkGpsRetry.SetToolTipString('Retry GPS if disconnected')
        self.checkGpsRetry.SetValue(settings.gpsRetry)
        self.checkGpsRetry.Enable(settings.gps)

        self.gridDev = grid.Grid(self)
        self.gridDev.CreateGrid(len(self.devices), 5)
        self.gridDev.SetRowLabelSize(0)
        self.gridDev.SetColLabelValue(self.COL_SEL, "Selected")
        self.gridDev.SetColLabelValue(self.COL_NAME, "Name")
        self.gridDev.SetColLabelValue(self.COL_HOST, "Host")
        self.gridDev.SetColLabelValue(self.COL_TYPE, "Type")
        self.gridDev.SetColLabelValue(self.COL_TEST, "Test")

        try:
            self.gridDev.ShowScrollbars(wx.SHOW_SB_NEVER, wx.SHOW_SB_NEVER)
        except AttributeError:
            pass

        self.__set_dev_grid()

        sizerDevice = wx.BoxSizer(wx.HORIZONTAL)
        buttonAdd = wx.Button(self, wx.ID_ADD)
        self.buttonDel = wx.Button(self, wx.ID_DELETE)
        self.Bind(wx.EVT_BUTTON, self.__on_add, buttonAdd)
        self.Bind(wx.EVT_BUTTON, self.__on_del, self.buttonDel)
        sizerDevice.Add(buttonAdd, 0, wx.ALL)
        sizerDevice.Add(self.buttonDel, 0, wx.ALL)
        self.__set_button_state()

        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons = wx.StdDialogButtonSizer()
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

        self.devbox = wx.BoxSizer(wx.VERTICAL)
        self.devbox.Add(self.checkGps, 0, wx.ALL | wx.EXPAND, 10)
        self.devbox.Add(self.checkGpsRetry, 0, wx.ALL | wx.EXPAND, 10)
        self.devbox.Add(self.gridDev, 1, wx.ALL | wx.EXPAND, 10)
        self.devbox.Add(sizerDevice, 0, wx.ALL | wx.EXPAND, 10)
        self.devbox.Add(sizerButtons, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizerAndFit(self.devbox)

    def __set_dev_grid(self):
        self.gridDev.Unbind(grid.EVT_GRID_EDITOR_CREATED)
        self.Unbind(grid.EVT_GRID_CELL_LEFT_CLICK)
        self.Unbind(grid.EVT_GRID_CELL_CHANGE)
        self.gridDev.ClearGrid()

        i = 0
        for device in self.devices:
            self.gridDev.SetReadOnly(i, self.COL_SEL, True)
            self.gridDev.SetCellRenderer(i, self.COL_SEL,
                                         TickCellRenderer())
            self.gridDev.SetCellValue(i, self.COL_NAME, device.name)
            cell = grid.GridCellChoiceEditor(sorted(DeviceGPS.TYPE),
                                             allowOthers=False)
            self.gridDev.SetCellValue(i, self.COL_TYPE,
                                      DeviceGPS.TYPE[device.type])
            self.gridDev.SetCellEditor(i, self.COL_TYPE, cell)

            if device.type == DeviceGPS.NMEA_SERIAL:
                self.gridDev.SetCellValue(i, self.COL_HOST,
                                          device.get_serial_desc())
                self.gridDev.SetReadOnly(i, self.COL_HOST, True)
            else:
                self.gridDev.SetCellValue(i, self.COL_HOST, device.resource)
                self.gridDev.SetReadOnly(i, self.COL_HOST, False)

            self.gridDev.SetCellValue(i, self.COL_TEST, '...')
            self.gridDev.SetCellAlignment(i, self.COL_SEL,
                                          wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
            i += 1

        self.index = limit(self.index, 0, len(self.devices) - 1)
        self.__select_row(self.index)
        self.index = self.index

        self.gridDev.AutoSize()
        font = self.gridDev.GetFont()
        dc = wx.WindowDC(self.gridDev)
        dc.SetFont(font)
        width, _height = dc.GetTextExtent(max(DeviceGPS.TYPE, key=len))
        self.gridDev.SetColSize(self.COL_TYPE, width * 1.5)

        self.gridDev.Bind(grid.EVT_GRID_EDITOR_CREATED, self.__on_create)
        self.Bind(grid.EVT_GRID_CELL_LEFT_CLICK, self.__on_click)
        self.Bind(grid.EVT_GRID_CELL_CHANGE, self.__on_change)

    def __set_button_state(self):
        if len(self.devices) > 0:
            self.buttonDel.Enable()
        else:
            self.buttonDel.Disable()
        if len(self.devices) == 1:
            self.__select_row(0)

    def __warn_duplicates(self):
        devices = []
        for device in self.devices:
            devices.append(device.name)

        dupes = set(devices)
        if len(dupes) != len(devices):
            message = "Duplicate name found:\n'{}'".format(dupes.pop())
            dlg = wx.MessageDialog(self, message, "Warning",
                                   wx.OK | wx.ICON_WARNING)
            dlg.ShowModal()
            dlg.Destroy()
            return True

        return False

    def __on_create(self, event):
        col = event.GetCol()
        index = event.GetRow()
        device = self.devices[index]
        if col == self.COL_TYPE:
            self.comboType = event.GetControl()
            self.comboType.Bind(wx.EVT_COMBOBOX,
                                lambda event,
                                device=device: self.__on_type(event, device))
        event.Skip()

    def __on_check(self, _event):
        self.checkGpsRetry.Enable(self.checkGps.GetValue())

    def __on_click(self, event):
        col = event.GetCol()
        index = event.GetRow()
        device = self.devices[index]
        if col == self.COL_SEL:
            self.index = event.GetRow()
            self.__select_row(index)
        elif col == self.COL_HOST:
            if device.type == DeviceGPS.NMEA_SERIAL:
                dlg = DialogGPSSerial(self, device)
                dlg.ShowModal()
                dlg.Destroy()
                self.gridDev.SetCellValue(index, self.COL_HOST,
                                          device.get_serial_desc())
            else:
                event.Skip()

        elif col == self.COL_TEST:
            dlg = DialogGPSTest(self, device)
            dlg.ShowModal()
            dlg.Destroy()
        else:
            self.gridDev.ForceRefresh()
            event.Skip()

    def __on_change(self, event):
        col = event.GetCol()
        index = event.GetRow()
        device = self.devices[index]
        if col == self.COL_NAME:
            device.name = self.gridDev.GetCellValue(index, self.COL_NAME)
        elif col == self.COL_TYPE:
            device.type = DeviceGPS.TYPE.index(self.gridDev.GetCellValue(index,
                                                                         self.COL_TYPE))
            self.__set_dev_grid()
            self.SetSizerAndFit(self.devbox)
            event.Skip()
        elif col == self.COL_HOST:
            if device.type != DeviceGPS.NMEA_SERIAL:
                device.resource = self.gridDev.GetCellValue(index,
                                                            self.COL_HOST)

    def __on_type(self, event, device):
        device.type = DeviceGPS.TYPE.index(event.GetString())
        if device.type == DeviceGPS.NMEA_SERIAL:
            device.resource = get_serial_ports()[0]
        elif device.type == DeviceGPS.NMEA_TCP:
            device.resource = 'localhost:10110'
        else:
            device.resource = 'localhost:2947'

    def __on_add(self, _event):
        device = DeviceGPS()
        self.devices.append(device)
        self.gridDev.AppendRows(1)
        self.__set_dev_grid()
        self.SetSizerAndFit(self.devbox)
        self.__set_button_state()

    def __on_del(self, _event):
        del self.devices[self.index]
        self.gridDev.DeleteRows(self.index)
        self.__set_dev_grid()
        self.SetSizerAndFit(self.devbox)
        self.__set_button_state()

    def __on_ok(self, _event):
        if self.__warn_duplicates():
            return

        self.settings.gps = self.checkGps.GetValue()
        self.settings.gpsRetry = self.checkGpsRetry.GetValue()
        self.settings.devicesGps = self.devices
        if len(self.devices) == 0:
            self.index = -1
        self.settings.indexGps = self.index
        self.EndModal(wx.ID_OK)

    def __select_row(self, index):
        self.index = index
        self.gridDev.ClearSelection()
        for i in range(0, len(self.devices)):
            tick = "0"
            if i == index:
                tick = "1"
            self.gridDev.SetCellValue(i, self.COL_SEL, tick)


class DialogGPSSerial(wx.Dialog):
    def __init__(self, parent, device):
        self.device = device
        ports = get_serial_ports()
        ports.append(device.resource)
        self.ports = list(set(ports))

        wx.Dialog.__init__(self, parent=parent, title='Serial port settings')

        textPort = wx.StaticText(self, label='Port')
        self.comboPort = wx.ComboBox(self, choices=self.ports,
                                     style=wx.TE_PROCESS_ENTER)
        self.comboPort.SetSelection(self.ports.index(device.resource))

        textBaud = wx.StaticText(self, label='Baud rate')
        self.choiceBaud = wx.Choice(self,
                                    choices=[str(baud) for baud in device.get_bauds()])
        self.choiceBaud.SetSelection(device.get_bauds().index(device.baud))
        textByte = wx.StaticText(self, label='Byte size')
        self.choiceBytes = wx.Choice(self,
                                     choices=[str(byte) for byte in DeviceGPS.BYTES])
        self.choiceBytes.SetSelection(DeviceGPS.BYTES.index(device.bytes))
        textParity = wx.StaticText(self, label='Parity')
        self.choiceParity = wx.Choice(self, choices=DeviceGPS.PARITIES)
        self.choiceParity.SetSelection(DeviceGPS.PARITIES.index(device.parity))
        textStop = wx.StaticText(self, label='Stop bits')
        self.choiceStops = wx.Choice(self,
                                     choices=[str(stop) for stop in DeviceGPS.STOPS])
        self.choiceStops.SetSelection(DeviceGPS.STOPS.index(device.stops))
        textSoft = wx.StaticText(self, label='Software flow control')
        self.checkSoft = wx.CheckBox(self)
        self.checkSoft.SetValue(device.soft)

        buttonOk = wx.Button(self, wx.ID_OK)
        buttonCancel = wx.Button(self, wx.ID_CANCEL)
        sizerButtons = wx.StdDialogButtonSizer()
        sizerButtons.AddButton(buttonOk)
        sizerButtons.AddButton(buttonCancel)
        sizerButtons.Realize()
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

        grid = wx.GridBagSizer(10, 10)
        grid.Add(textPort, pos=(0, 0), flag=wx.ALL)
        grid.Add(self.comboPort, pos=(0, 1), flag=wx.ALL)
        grid.Add(textBaud, pos=(1, 0), flag=wx.ALL)
        grid.Add(self.choiceBaud, pos=(1, 1), flag=wx.ALL)
        grid.Add(textByte, pos=(2, 0), flag=wx.ALL)
        grid.Add(self.choiceBytes, pos=(2, 1), flag=wx.ALL)
        grid.Add(textParity, pos=(3, 0), flag=wx.ALL)
        grid.Add(self.choiceParity, pos=(3, 1), flag=wx.ALL)
        grid.Add(textStop, pos=(4, 0), flag=wx.ALL)
        grid.Add(self.choiceStops, pos=(4, 1), flag=wx.ALL)
        grid.Add(textSoft, pos=(5, 0), flag=wx.ALL)
        grid.Add(self.checkSoft, pos=(5, 1), flag=wx.ALL)

        box = wx.BoxSizer(wx.VERTICAL)
        box.Add(grid, flag=wx.ALL, border=10)
        box.Add(sizerButtons, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)

        self.SetSizerAndFit(box)

    def __on_ok(self, _event):
        self.device.resource = self.comboPort.GetValue()
        self.device.baud = self.device.get_bauds()[self.choiceBaud.GetSelection()]
        self.device.bytes = DeviceGPS.BYTES[self.choiceBytes.GetSelection()]
        self.device.parity = DeviceGPS.PARITIES[self.choiceParity.GetSelection()]
        self.device.stops = DeviceGPS.STOPS[self.choiceStops.GetSelection()]
        self.device.soft = self.checkSoft.GetValue()

        self.EndModal(wx.ID_OK)


class DialogGPSTest(wx.Dialog):
    POLL = 500

    def __init__(self, parent, device):
        self.device = device
        self.threadLocation = None
        self.raw = ''

        wx.Dialog.__init__(self, parent=parent, title='GPS Test')

        textLat = wx.StaticText(self, label='Longitude')
        self.textLat = wx.TextCtrl(self, style=wx.TE_READONLY)
        textLon = wx.StaticText(self, label='Latitude')
        self.textLon = wx.TextCtrl(self, style=wx.TE_READONLY)
        textAlt = wx.StaticText(self, label='Altitude')
        self.textAlt = wx.TextCtrl(self, style=wx.TE_READONLY)
        textSats = wx.StaticText(self, label='Satellites')
        self.textSats = wx.TextCtrl(self, style=wx.TE_READONLY)
        textRaw = wx.StaticText(self, label='Raw output')
        self.textRaw = wx.TextCtrl(self,
                                   style=wx.TE_MULTILINE | wx.TE_READONLY)

        textLevel = wx.StaticText(self, label='Level')
        self.satLevel = SatLevel(self)

        self.buttonStart = wx.Button(self, label='Start')
        self.Bind(wx.EVT_BUTTON, self.__on_start, self.buttonStart)
        self.buttonStop = wx.Button(self, label='Stop')
        self.Bind(wx.EVT_BUTTON, self.__on_stop, self.buttonStop)
        self.buttonStop.Disable()

        buttonOk = wx.Button(self, wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.__on_ok, buttonOk)

        grid = wx.GridBagSizer(10, 10)

        grid.Add(textLat, pos=(0, 0), flag=wx.ALL, border=5)
        grid.Add(self.textLat, pos=(0, 1), span=(1, 2), flag=wx.ALL, border=5)
        grid.Add(textLon, pos=(1, 0), flag=wx.ALL, border=5)
        grid.Add(self.textLon, pos=(1, 1), span=(1, 2), flag=wx.ALL, border=5)
        grid.Add(textAlt, pos=(2, 0), flag=wx.ALL, border=5)
        grid.Add(self.textAlt, pos=(2, 1), span=(1, 2), flag=wx.ALL, border=5)
        grid.Add(textSats, pos=(3, 0), flag=wx.ALL, border=5)
        grid.Add(self.textSats, pos=(3, 1), span=(1, 2), flag=wx.ALL, border=5)
        grid.Add(textLevel, pos=(0, 3), flag=wx.ALL, border=5)
        grid.Add(self.satLevel, pos=(1, 3), span=(3, 2), flag=wx.ALL, border=5)
        grid.Add(textRaw, pos=(4, 0), flag=wx.ALL, border=5)
        grid.Add(self.textRaw, pos=(5, 0), span=(5, 5),
                 flag=wx.ALL | wx.EXPAND, border=5)
        grid.Add(self.buttonStart, pos=(10, 2), flag=wx.ALL, border=5)
        grid.Add(self.buttonStop, pos=(10, 3), flag=wx.ALL | wx.ALIGN_RIGHT,
                 border=5)
        grid.Add(buttonOk, pos=(11, 4), flag=wx.ALL | wx.ALIGN_RIGHT,
                 border=5)

        self.SetSizerAndFit(grid)

        self.queue = Queue.Queue()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.__on_timer, self.timer)
        self.timer.Start(self.POLL)

    def __on_start(self, _event):
        if not self.threadLocation:
            self.buttonStart.Disable()
            self.buttonStop.Enable()
            self.textRaw.SetValue('')
            self.__add_raw('Starting...')
            self.threadLocation = ThreadLocation(self.queue, self.device,
                                                 raw=True)

    def __on_stop(self, _event):
        if self.threadLocation and self.threadLocation.isAlive():
            self.__add_raw('Stopping...')
            self.threadLocation.stop()
            self.threadLocation.join()
        self.threadLocation = None
        self.satLevel.clear_sats()
        self.textLat.SetValue('')
        self.textLon.SetValue('')
        self.textAlt.SetValue('')
        self.textSats.SetValue('')
        self.buttonStart.Enable()
        self.buttonStop.Disable()

    def __on_ok(self, _event):
        self.__on_stop(None)
        self.EndModal(wx.ID_OK)

    def __on_timer(self, _event):
        self.timer.Stop()
        while not self.queue.empty():
            event = self.queue.get()
            status = event.data.get_status()
            loc = event.data.get_arg2()

            if status == Event.LOC:
                if loc[0] is not None:
                    text = '{:.5f}'.format(loc[0])
                else:
                    text = ''
                self.textLon.SetValue(text)
                if loc[1] is not None:
                    text = '{:.5f}'.format(loc[1])
                else:
                    text = ''
                self.textLat.SetValue(text)
                if loc[2] is not None:
                    text = '{:.1f}'.format(loc[2])
                else:
                    text = ''
                self.textAlt.SetValue(text)
            elif status == Event.LOC_SAT:
                self.satLevel.set_sats(loc)
                used = sum(1 for sat in loc.values() if sat[1])
                self.textSats.SetLabel('{}/{}'.format(used, len(loc)))
            elif status == Event.LOC_ERR:
                self.__on_stop(None)
                self.__add_raw('{}'.format(loc))
            elif status == Event.LOC_RAW:
                self.__add_raw(loc)
        self.timer.Start(self.POLL)

    def __add_raw(self, text):
        text = text.replace('\n', '')
        text = text.replace('\r', '')
        terminal = self.textRaw.GetValue().split('\n')
        terminal.append(text)
        while len(terminal) > 100:
            terminal.pop(0)
        self.textRaw.SetValue('\n'.join(terminal))
        self.textRaw.ScrollPages(self.textRaw.GetNumberOfLines())


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
