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
import rtlsdr


class Device():
    def __init__(self):
        self.isDevice = True
        self.index = None
        self.name = None
        self.server = 'localhost'
        self.port = 1234
        self.gain = 0
        self.calibration = 0
        self.lo = 0
        self.offset = 250e3

    def set(self, device):
        self.gain = device.gain
        self.calibration = device.calibration
        self.lo = device.lo
        self.offset = device.offset


def get_devices(currentDevices=[]):
    devices = []
    count = rtlsdr.librtlsdr.rtlsdr_get_device_count()

    for dev in range(0, count):
        device = Device()
        device.index = dev
        device.name = format_device_name(rtlsdr.librtlsdr.rtlsdr_get_device_name(dev))
        device.calibration = 0.0
        device.lo = 0.0
        for conf in currentDevices:
            # TODO: better matching than just name?
            if conf.isDevice and device.name == conf.name:
                device.set(conf)

        devices.append(device)

    for conf in currentDevices:
        if not conf.isDevice:
            devices.append(conf)

    return devices


def format_device_name(name):
    remove = ["/", "\\"]
    for char in remove:
        name = name.replace(char, " ")

    return name


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
