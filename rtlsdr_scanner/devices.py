#
# rtlsdr_scan
#
# http://eartoearoak.com/software/rtlsdr-scanner
#
# Copyright 2012 -2015 Al Brown
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
from ctypes import c_ubyte, string_at

import rtlsdr
import serial


class DeviceGPS(object):
    NMEA_SERIAL, GPSD, GPSD_OLD, NMEA_TCP = range(4)
    TYPE = ['NMEA (Serial)', 'GPSd', 'GPSd (Legacy)', 'NMEA (Server)']
    BYTES = [serial.FIVEBITS, serial.SIXBITS, serial.SEVENBITS,
             serial.EIGHTBITS]
    PARITIES = [serial.PARITY_NONE, serial.PARITY_EVEN, serial.PARITY_ODD,
                serial.PARITY_MARK, serial.PARITY_SPACE]
    STOPS = [serial.STOPBITS_ONE, serial.STOPBITS_ONE_POINT_FIVE,
             serial.STOPBITS_TWO]

    def __init__(self):
        self.name = 'GPS'
        self.type = self.GPSD
        self.resource = 'localhost:2947'
        self.baud = 115200
        self.bytes = serial.EIGHTBITS
        self.parity = serial.PARITY_NONE
        self.stops = serial.STOPBITS_ONE
        self.soft = False

    def get_bauds(self):
        if self.type == DeviceGPS.NMEA_SERIAL:
            return serial.Serial.BAUDRATES

        return None

    def get_serial_desc(self):
        port = self.resource.split('/')
        return '{} {}-{}{}{:g}'.format(port[0], self.baud, self.bytes,
                                       self.parity, self.stops)

    def get_desc(self):
        if self.type == DeviceGPS.NMEA_SERIAL:
            return self.get_serial_desc()

        return self.resource


class DeviceRTL(object):
    def __init__(self):
        self.isDevice = True
        self.indexRtl = None
        self.name = None
        self.serial = ''
        self.server = 'localhost'
        self.port = 1234
        self.gains = []
        self.gain = 0
        self.calibration = 0
        self.lo = 0
        self.offset = 250e3
        self.tuner = 0
        self.levelOff = 0

    def set(self, device):
        self.gain = device.gain
        self.calibration = device.calibration
        self.lo = device.lo
        self.offset = device.offset
        self.tuner = device.tuner
        self.levelOff = device.levelOff

    def get_gains_str(self):
        gainsStr = []
        for gain in self.gains:
            gainsStr.append(str(gain))

        return gainsStr

    def get_closest_gain_str(self, desired):
        gain = min(self.gains, key=lambda n: abs(n - desired))

        return str(gain)


def get_devices_rtl(currentDevices=None, statusBar=None):
    if statusBar is not None:
        statusBar.set_general("Refreshing device list...")

    if currentDevices is None:
        currentDevices = []

    devices = []
    count = rtlsdr.librtlsdr.rtlsdr_get_device_count()

    for dev in range(0, count):
        device = DeviceRTL()
        device.indexRtl = dev
        device.name = format_device_rtl_name(rtlsdr.librtlsdr.rtlsdr_get_device_name(dev))
        buffer1 = (c_ubyte * 256)()
        buffer2 = (c_ubyte * 256)()
        serial = (c_ubyte * 256)()
        rtlsdr.librtlsdr.rtlsdr_get_device_usb_strings(dev, buffer1, buffer2,
                                                       serial)
        device.serial = string_at(serial)
        try:
            sdr = rtlsdr.RtlSdr(dev)
        except IOError:
            continue
        device.gains = sdr.valid_gains_db
        device.calibration = 0.0
        device.lo = 0.0
        for conf in currentDevices:
            if conf.isDevice and device.name == conf.name and device.serial == conf.serial:
                device.set(conf)

        devices.append(device)

    for conf in currentDevices:
        if not conf.isDevice:
            devices.append(conf)

    if statusBar is not None:
        statusBar.set_general("")

    return devices


def format_device_rtl_name(name):
    remove = ["/", "\\"]
    for char in remove:
        name = name.replace(char, " ")

    return name


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
