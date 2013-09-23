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

import wx

from misc import format_device_name


class Device():
    def __init__(self):
        self.index = None
        self.name = None
        self.gain = 0
        self.calibration = None
        self.lo = None
        self.offset = 250e3


class Settings():
    def __init__(self):
        self.cfg = None

        self.saveWarn = True

        self.annotate = True

        self.retainScans = False
        self.fadeScans = True
        self.maxScans = 5

        self.start = None
        self.stop = None
        self.mode = 0
        self.dwell = 0.0
        self.nfft = 0
        self.liveUpdate = False
        self.calFreq = None
        self.yAuto = True
        self.yMax = 1
        self.yMin = 0

        self.devices = []
        self.index = None

        self.load()

    def load(self):
        self.cfg = wx.Config('rtlsdr-scanner')
        self.saveWarn = self.cfg.ReadBool('saveWarn', True)
        self.annotate = self.cfg.ReadBool('annotate', True)
        self.retainScans = self.cfg.ReadBool('retainScans', False)
        self.fadeScans = self.cfg.ReadBool('fadeScans', True)
        self.maxScans = self.cfg.ReadInt('maxScans', 5)
        self.start = self.cfg.ReadInt('start', 87)
        self.stop = self.cfg.ReadInt('stop', 108)
        self.mode = self.cfg.ReadInt('mode', 0)
        self.dwell = self.cfg.ReadFloat('dwell', 0.1)
        self.nfft = int(self.cfg.Read('nfft', '1024'))
        self.liveUpdate = self.cfg.ReadBool('liveUpdate', False)
        self.calFreq = self.cfg.ReadFloat('calFreq', 1575.42)
        self.index = self.cfg.ReadInt('index', 0)
        self.cfg.SetPath("/Devices")
        group = self.cfg.GetFirstGroup()
        while group[0]:
            self.cfg.SetPath("/Devices/" + group[1])
            device = Device()
            device.name = group[1]
            device.gain = self.cfg.ReadFloat('gain', 0)
            device.calibration = self.cfg.ReadFloat('calibration', 0)
            device.lo = self.cfg.ReadFloat('lo', 0)
            device.offset = self.cfg.ReadFloat('offset', 250e3)
            self.devices.append(device)
            self.cfg.SetPath("/Devices")
            group = self.cfg.GetNextGroup(group[2])

    def save(self):
        self.cfg.SetPath("/")
        self.cfg.WriteBool('saveWarn', self.saveWarn)
        self.cfg.WriteBool('annotate', self.annotate)
        self.cfg.WriteBool('retainScans', self.retainScans)
        self.cfg.WriteBool('fadeScans', self.fadeScans)
        self.cfg.WriteInt('maxScans', self.maxScans)
        self.cfg.WriteInt('start', self.start)
        self.cfg.WriteInt('stop', self.stop)
        self.cfg.WriteInt('mode', self.mode)
        self.cfg.WriteFloat('dwell', self.dwell)
        self.cfg.Write('nfft', str(self.nfft))
        self.cfg.WriteBool('liveUpdate', self.liveUpdate)
        self.cfg.WriteFloat('calFreq', self.calFreq)
        self.cfg.WriteInt('index', self.index)
        if self.devices:
            for device in self.devices:
                self.cfg.SetPath("/Devices/" + format_device_name(device.name))
                self.cfg.WriteFloat('gain', device.gain)
                self.cfg.WriteFloat('lo', device.lo)
                self.cfg.WriteFloat('calibration', device.calibration)
                self.cfg.WriteFloat('offset', device.offset)
