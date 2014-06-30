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

from constants import Display, Mode, PlotFunc
from devices import DeviceRTL, format_device_rtl_name, DeviceGPS


class Settings(object):
    def __init__(self, load=True):
        self.cfg = None

        self.saveWarn = True
        self.fileHistory = wx.FileHistory(5)

        self.dirScans = "."
        self.dirExport = "."

        self.display = Display.PLOT

        self.annotate = True

        self.retainScans = True
        self.retainMax = 20
        self.fadeScans = True
        self.lineWidth = 0.4
        self.colourMapUse = True
        self.colourMap = 'jet'
        self.background = '#f0f0f0'
        self.wireframe = False
        self.pointsLimit = False
        self.pointsMax = 5000
        self.grid = True
        self.plotFunc = PlotFunc.NONE

        self.clickTune = True

        self.compareOne = True
        self.compareTwo = True
        self.compareDiff = True

        self.start = 87
        self.stop = 108
        self.mode = Mode.SINGLE
        self.dwell = 0.1
        self.nfft = 1024
        self.overlap = 0.0
        self.winFunc = "Hamming"

        self.liveUpdate = False
        self.calFreq = 1575.42
        self.autoF = True
        self.autoL = True
        self.autoT = True

        self.showMeasure = True

        self.alert = False
        self.alertLevel = -20

        self.gps = False

        self.exportDpi = 600

        self.devicesRtl = []
        self.indexRtl = 0
        self.devicesGps = []
        self.indexGps = 0

        if load:
            self.__load()

    def __clear_servers(self):
        self.cfg.SetPath("/DevicesRTL")
        group = self.cfg.GetFirstGroup()
        while group[0]:
            key = "/DevicesRTL/" + group[1]
            self.cfg.SetPath(key)
            if not self.cfg.ReadBool('isDevice', True):
                self.cfg.DeleteGroup(key)
            self.cfg.SetPath("/DevicesRTL")
            group = self.cfg.GetNextGroup(group[2])

    def __load_devices_rtl(self):
        self.cfg.SetPath("/DevicesRTL")
        group = self.cfg.GetFirstGroup()
        while group[0]:
            self.cfg.SetPath("/DevicesRTL/" + group[1])
            device = DeviceRTL()
            device.name = group[1]
            device.serial = self.cfg.Read('serial', '')
            device.isDevice = self.cfg.ReadBool('isDevice', True)
            device.server = self.cfg.Read('server', 'localhost')
            device.port = self.cfg.ReadInt('port', 1234)
            device.gain = self.cfg.ReadFloat('gain', 0)
            device.calibration = self.cfg.ReadFloat('calibration', 0)
            device.lo = self.cfg.ReadFloat('lo', 0)
            device.offset = self.cfg.ReadFloat('offset', 250e3)
            device.tuner = self.cfg.ReadInt('tuner', 0)
            self.devicesRtl.append(device)
            self.cfg.SetPath("/DevicesRTL")
            group = self.cfg.GetNextGroup(group[2])

    def __load_devices_gps(self):
        self.devicesGps = []
        self.cfg.SetPath("/DevicesGPS")
        group = self.cfg.GetFirstGroup()
        while group[0]:
            self.cfg.SetPath("/DevicesGPS/" + group[1])
            device = DeviceGPS()
            device.name = group[1]
            device.type = self.cfg.ReadInt('type', device.type)
            device.resource = self.cfg.Read('resource', device.resource)
            device.baud = self.cfg.ReadInt('baud', device.baud)
            device.bytes = self.cfg.ReadInt('bytes', device.bytes)
            device.parity = self.cfg.Read('parity', device.parity)
            device.stops = self.cfg.ReadInt('stops', device.stops)
            device.soft = self.cfg.ReadBool('soft', device.soft)
            self.devicesGps.append(device)
            self.cfg.SetPath("/DevicesGPS")
            group = self.cfg.GetNextGroup(group[2])

    def __save_devices_rtl(self):
        self.__clear_servers()

        if self.devicesRtl:
            for device in self.devicesRtl:
                if device.isDevice:
                    name = device.name
                else:
                    name = "{0}:{1}".format(device.server, device.port)
                self.cfg.SetPath("/DevicesRTL/" + format_device_rtl_name(name))
                self.cfg.Write('serial', device.serial)
                self.cfg.WriteBool('isDevice', device.isDevice)
                self.cfg.Write('server', device.server)
                self.cfg.WriteInt('port', device.port)
                self.cfg.WriteFloat('gain', device.gain)
                self.cfg.WriteFloat('lo', device.lo)
                self.cfg.WriteFloat('calibration', device.calibration)
                self.cfg.WriteFloat('offset', device.offset)
                self.cfg.WriteInt('tuner', device.tuner)

    def __save_devices_gps(self):
        self.cfg.DeleteGroup('/DevicesGPS')
        for device in self.devicesGps:
            self.cfg.SetPath("/DevicesGPS/" + device.name)
            self.cfg.WriteInt('type', device.type)
            self.cfg.Write('resource', device.resource)
            self.cfg.WriteInt('baud', device.baud)
            self.cfg.WriteInt('bytes', device.bytes)
            self.cfg.Write('parity', device.parity)
            self.cfg.WriteInt('stops', device.stops)
            self.cfg.WriteBool('soft', device.soft)

    def __load(self):
        self.cfg = wx.Config('rtlsdr-scanner')

        self.cfg.RenameGroup('Devices', 'DevicesRTL')

        self.display = self.cfg.ReadInt('display', self.display)
        self.saveWarn = self.cfg.ReadBool('saveWarn', self.saveWarn)
        self.fileHistory.Load(self.cfg)
        self.dirScans = self.cfg.Read('dirScans', self.dirScans)
        self.dirExport = self.cfg.Read('dirExport', self.dirExport)
        self.annotate = self.cfg.ReadBool('annotate', self.annotate)
        self.retainScans = self.cfg.ReadBool('retainScans', self.retainScans)
        self.fadeScans = self.cfg.ReadBool('fadeScans', self.fadeScans)
        self.lineWidth = self.cfg.ReadFloat('lineWidth', self.lineWidth)
        self.retainMax = self.cfg.ReadInt('retainMax', self.retainMax)
        self.colourMapUse = self.cfg.ReadBool('colourMapUse', self.colourMapUse)
        self.colourMap = self.cfg.Read('colourMap', self.colourMap)
        self.background = self.cfg.Read('background', self.background)
        self.wireframe = self.cfg.ReadBool('wireframe', self.wireframe)
        self.pointsLimit = self.cfg.ReadBool('pointsLimit', self.pointsLimit)
        self.pointsMax = self.cfg.ReadInt('pointsMax', self.pointsMax)
        self.grid = self.cfg.ReadBool('grid', self.grid)
        self.plotFunc = self.cfg.ReadInt('plotFunc', self.plotFunc)
        self.clickTune = self.cfg.ReadBool('clickTune', self.clickTune)
        self.compareOne = self.cfg.ReadBool('compareOne', self.compareOne)
        self.compareTwo = self.cfg.ReadBool('compareTwo', self.compareTwo)
        self.compareDiff = self.cfg.ReadBool('compareDiff', self.compareDiff)
        self.start = self.cfg.ReadInt('start', self.start)
        self.stop = self.cfg.ReadInt('stop', self.stop)
        self.mode = self.cfg.ReadInt('mode', self.mode)
        self.dwell = self.cfg.ReadFloat('dwell', self.dwell)
        self.nfft = self.cfg.ReadInt('nfft', self.nfft)
        self.overlap = self.cfg.ReadFloat('overlap', self.overlap)
        self.winFunc = self.cfg.Read('winFunc', self.winFunc)
        self.liveUpdate = self.cfg.ReadBool('liveUpdate', self.liveUpdate)
        self.calFreq = self.cfg.ReadFloat('calFreq', self.calFreq)
        self.autoF = self.cfg.ReadBool('autoF', self.autoF)
        self.autoL = self.cfg.ReadBool('autoL', self.autoL)
        self.autoT = self.cfg.ReadBool('autoT', self.autoT)
        self.showMeasure = self.cfg.ReadBool('showMeasure', self.showMeasure)
        self.alert = self.cfg.ReadBool('alert', self.alert)
        self.alertLevel = self.cfg.ReadFloat('alertLevel', self.alertLevel)
        self.gps = self.cfg.ReadBool('gps', self.gps)
        self.exportDpi = self.cfg.ReadInt('exportDpi', self.exportDpi)
        self.indexRtl = self.cfg.ReadInt('index', self.indexRtl)
        self.indexRtl = self.cfg.ReadInt('indexRtl', self.indexRtl)
        self.indexGps = self.cfg.ReadInt('indexGps', self.indexGps)
        self.__load_devices_rtl()
        self.__load_devices_gps()

    def save(self):
        self.cfg.SetPath("/")
        self.cfg.WriteInt('display', self.display)
        self.cfg.WriteBool('saveWarn', self.saveWarn)
        self.fileHistory.Save(self.cfg)
        self.cfg.Write('dirScans', self.dirScans)
        self.cfg.Write('dirExport', self.dirExport)
        self.cfg.WriteBool('annotate', self.annotate)
        self.cfg.WriteBool('retainScans', self.retainScans)
        self.cfg.WriteBool('fadeScans', self.fadeScans)
        self.cfg.WriteFloat('lineWidth', self.lineWidth)
        self.cfg.WriteInt('retainMax', self.retainMax)
        self.cfg.WriteBool('colourMapUse', self.colourMapUse)
        self.cfg.Write('colourMap', self.colourMap)
        self.cfg.Write('background', self.background)
        self.cfg.WriteBool('wireframe', self.wireframe)
        self.cfg.WriteBool('pointsLimit', self.pointsLimit)
        self.cfg.WriteInt('pointsMax', self.pointsMax)
        self.cfg.WriteBool('grid', self.grid)
        self.cfg.WriteInt('plotFunc', self.plotFunc)
        self.cfg.WriteBool('clickTune', self.clickTune)
        self.cfg.WriteBool('compareOne', self.compareOne)
        self.cfg.WriteBool('compareTwo', self.compareTwo)
        self.cfg.WriteBool('compareDiff', self.compareDiff)
        self.cfg.WriteInt('start', self.start)
        self.cfg.WriteInt('stop', self.stop)
        self.cfg.WriteInt('mode', self.mode)
        self.cfg.WriteFloat('dwell', self.dwell)
        self.cfg.WriteInt('nfft', self.nfft)
        self.cfg.WriteFloat('overlap', self.overlap)
        self.cfg.Write("winFunc", self.winFunc)
        self.cfg.WriteBool('liveUpdate', self.liveUpdate)
        self.cfg.WriteFloat('calFreq', self.calFreq)
        self.cfg.WriteBool('autoF', self.autoF)
        self.cfg.WriteBool('autoL', self.autoL)
        self.cfg.WriteBool('autoT', self.autoT)
        self.cfg.WriteBool('showMeasure', self.showMeasure)
        self.cfg.WriteBool('alert', self.alert)
        self.cfg.WriteFloat('alertLevel', self.alertLevel)
        self.cfg.WriteBool('gps', self.gps)
        self.cfg.WriteInt('exportDpi', self.exportDpi)
        self.cfg.WriteInt('indexRtl', self.indexRtl)
        self.cfg.WriteInt('indexGps', self.indexGps)
        self.__save_devices_rtl()
        self.__save_devices_gps()

        self.cfg.DeleteEntry('autoScale')
        self.cfg.DeleteEntry('yMax')
        self.cfg.DeleteEntry('yMin')
        self.cfg.DeleteEntry('average')
        self.cfg.DeleteEntry('index')

    def reset(self):
        self.cfg.SetPath("/")
        self.cfg.DeleteAll()
        self.__init__()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
