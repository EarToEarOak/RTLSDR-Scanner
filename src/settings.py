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

from constants import Display, Mode
from devices import Device, format_device_name


class Settings():
    def __init__(self, load=True):
        self.cfg = None

        self.saveWarn = True
        self.fileHistory = wx.FileHistory(5)

        self.display = Display.PLOT

        self.annotate = True

        self.retainScans = True
        self.retainMax = 20
        self.fadeScans = True
        self.lineWidth = 0.4
        self.colourMap = 'jet'
        self.wireframe = False
        self.average = False

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

        self.alert = False
        self.alertLevel = -20

        self.devices = []
        self.index = 0

        if load:
            self.load()

    def clear_servers(self):
        self.cfg.SetPath("/Devices")
        group = self.cfg.GetFirstGroup()
        while group[0]:
            key = "/Devices/" + group[1]
            self.cfg.SetPath(key)
            if not self.cfg.ReadBool('isDevice', True):
                self.cfg.DeleteGroup(key)
            self.cfg.SetPath("/Devices")
            group = self.cfg.GetNextGroup(group[2])

    def load(self):
        self.cfg = wx.Config('rtlsdr-scanner')
        self.display = self.cfg.ReadInt('display', self.display)
        self.saveWarn = self.cfg.ReadBool('saveWarn', self.saveWarn)
        self.fileHistory.Load(self.cfg)
        self.annotate = self.cfg.ReadBool('annotate', self.annotate)
        self.retainScans = self.cfg.ReadBool('retainScans', self.retainScans)
        self.fadeScans = self.cfg.ReadBool('fadeScans', self.fadeScans)
        self.lineWidth = self.cfg.ReadFloat('lineWidth', self.lineWidth)
        self.retainMax = self.cfg.ReadInt('retainMax', self.retainMax)
        self.colourMap = self.cfg.Read('colourMap', self.colourMap)
        self.wireframe = self.cfg.ReadBool('wireframe', self.wireframe)
        self.average = self.cfg.ReadBool('average', self.average)
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
        self.alert = self.cfg.ReadBool('alert', self.alert)
        self.alertLevel = self.cfg.ReadFloat('alertLevel', self.alertLevel)
        self.index = self.cfg.ReadInt('index', self.index)
        self.cfg.SetPath("/Devices")
        group = self.cfg.GetFirstGroup()
        while group[0]:
            self.cfg.SetPath("/Devices/" + group[1])
            device = Device()
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
            self.devices.append(device)
            self.cfg.SetPath("/Devices")
            group = self.cfg.GetNextGroup(group[2])

    def save(self):
        self.cfg.SetPath("/")
        self.cfg.WriteInt('display', self.display)
        self.cfg.WriteBool('saveWarn', self.saveWarn)
        self.fileHistory.Save(self.cfg)
        self.cfg.WriteBool('annotate', self.annotate)
        self.cfg.WriteBool('retainScans', self.retainScans)
        self.cfg.WriteBool('fadeScans', self.fadeScans)
        self.cfg.WriteFloat('lineWidth', self.lineWidth)
        self.cfg.WriteInt('retainMax', self.retainMax)
        self.cfg.Write('colourMap', self.colourMap)
        self.cfg.WriteBool('wireframe', self.wireframe)
        self.cfg.WriteBool('average', self.average)
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
        self.cfg.WriteBool('alert', self.alert)
        self.cfg.WriteFloat('alertLevel', self.alertLevel)
        self.cfg.WriteInt('index', self.index)
        self.clear_servers()
        if self.devices:
            for device in self.devices:
                if device.isDevice:
                    name = device.name
                else:
                    name = "{0}:{1}".format(device.server, device.port)
                self.cfg.SetPath("/Devices/" + format_device_name(name))
                self.cfg.Write('serial', device.serial)
                self.cfg.WriteBool('isDevice', device.isDevice)
                self.cfg.Write('server', device.server)
                self.cfg.WriteInt('port', device.port)
                self.cfg.WriteFloat('gain', device.gain)
                self.cfg.WriteFloat('lo', device.lo)
                self.cfg.WriteFloat('calibration', device.calibration)
                self.cfg.WriteFloat('offset', device.offset)
                self.cfg.WriteInt('tuner', device.tuner)

        self.cfg.DeleteEntry('autoScale')
        self.cfg.DeleteEntry('yMax')
        self.cfg.DeleteEntry('yMin')


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
