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

import datetime
import json
from math import radians, sin, cos, asin, sqrt
import math
import os
import pkg_resources
import socket
import sys
from threading import Thread
import time

import serial.tools.list_ports

from rtlsdr_scanner.constants import SAMPLE_RATE


class RemoteControl(object):
    def __init__(self):
        self.connected = False
        self.socket = None

    def __connect(self):
        if not self.connected:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(1)
                self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.socket.connect(('localhost', 3382))
                self.connected = True
            except socket.error:
                self.connected = False

    def __thread(self, command):
        self.__connect()
        if self.connected:
            try:
                self.socket.send(json.dumps(command))
                self.socket.send('\r\n')
            except socket.error:
                self.socket.close()
                self.connected = False

    def __send(self, command):
        thread = Thread(target=self.__thread, args=(command,))
        thread.daemon = True
        thread.start()

    def tune(self, frequency):
        command = {'Command': 'Set',
                   'Method': 'Frequency',
                   'Value': frequency}
        self.__send(command)


def get_resource(resource):
    if not hasattr(sys, 'frozen'):
        return pkg_resources.resource_filename('rtlsdr_scanner.res',
                                               resource)
    else:
        return os.path.join(sys._MEIPASS, 'res', resource)


def limit(value, minimum, maximum):
    return max(min(maximum, value), minimum)


def level_to_db(level):
    return 10 * math.log10(level)


def db_to_level(dB):
    return math.pow(10, dB / 10.0)


def next_2_to_pow(val):
    val -= 1
    val |= val >> 1
    val |= val >> 2
    val |= val >> 4
    val |= val >> 8
    val |= val >> 16
    return val + 1


def calc_samples(dwell):
    samples = dwell * SAMPLE_RATE
    samples = next_2_to_pow(int(samples))
    return samples


def get_dwells():
    dwells = ["8 ms", 0.008,
              "16 ms", 0.016,
              "32 ms", 0.032,
              "65 ms", 0.065,
              "131 ms", 0.131,
              "262 ms", 0.262,
              "524 ms", 0.524,
              "1 s", 1.048,
              "2 s", 2.097,
              "4 s", 4.194,
              "8 s", 8.388]

    if sys.platform == 'linux' or sys.platform == "linux2":
        del dwells[-4:]

    return dwells


def calc_real_dwell(dwell):
    samples = calc_samples(dwell)
    dwellReal = samples / SAMPLE_RATE
    return (int)(dwellReal * 1000.0) / 1000.0


def nearest(value, values):
    offset = [abs(value - v) for v in values]
    return values[offset.index(min(offset))]


def haversine(lat1, lat2, lon1, lon2):
    lat1, lat2, lon1, lon2 = map(radians, [lat1, lat2, lon1, lon2])

    dlon = lon1 - lon2
    dlat = lat1 - lat2
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    b = asin(sqrt(a))

    return 2 * b * 6371000


def format_precision(settings, freq=None, level=None,
                     units=True, fancyUnits=False):
    textFreq = None
    textLevel = None

    if freq is not None:
        prec = settings.precisionFreq
        width = 4 + prec
        textFreq = '{:{width}.{prec}f}'.format(freq, width=width, prec=prec)
        if units or fancyUnits:
            textFreq += " MHz"
    if level is not None:
        prec = settings.precisionLevel
        width = 4 + prec
        textLevel = '{:{width}.{prec}f}'.format(level, width=width, prec=prec)
        if fancyUnits:
            textLevel += r" dB/Hz"
        elif units:
            textLevel += " dB/Hz"

    if textFreq and textLevel:
        return (textFreq, textLevel)
    if textFreq:
        return textFreq
    if textLevel:
        return textLevel

    return None


def format_time(timeStamp, withDate=False):
    if timeStamp <= 1:
        return 'Unknown'

    if withDate:
        return time.strftime('%c', time.localtime(timeStamp))

    return time.strftime('%H:%M:%S', time.localtime(timeStamp))


def format_iso_time(timeStamp):
    dt = datetime.datetime.utcfromtimestamp(timeStamp)
    return dt.isoformat() + 'Z'


def get_serial_ports():
    ports = [port[0] for port in serial.tools.list_ports.comports()]
    if len(ports) == 0:
        if os.name == 'nt':
            ports.append('COM1')
        else:
            ports.append('/dev/ttyS0')

    return ports


def limit_to_ascii(text):
    return ''.join([i if ord(i) < 128 else '' for i in text])


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
