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

import json
import socket
import threading
from urlparse import urlparse

import serial
from serial.serialutil import SerialException

from devices import DeviceGPS
from events import post_event, EventThreadStatus, Event


class ThreadLocation(threading.Thread):
    def __init__(self, notify, settings):
        threading.Thread.__init__(self)
        self.name = 'Location'
        self.notify = notify
        self.device = settings.devicesGps[settings.indexGps]
        self.cancel = False
        self.socket = None
        self.serial = None

        if self.device.type == DeviceGPS.NMEA:
            if self.__nmea_open():
                self.start()
        else:
            if self.__gpsd_open():
                self.start()

    def __gpsd_open(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            url = urlparse('//' + self.device.resource)
            if url.hostname is not None:
                    host = url.hostname
            else:
                    host = 'localhost'
            if url.port is not None:
                port = url.port
            else:
                port = 2947
            self.socket.connect((host, port))

            if self.device.type == DeviceGPS.GPSD:
                self.socket.sendall('?WATCH={"enable": true,"json": true}')
            else:
                self.socket.sendall('w')

        except IOError as error:
            post_event(self.notify, EventThreadStatus(Event.LOC_WARN,
                                                      0, error))
            self.socket.close()
            return False

        return True

    def __gpsd_read(self):
        buf = ''
        data = True
        while data and not self.cancel:
            data = self.socket.recv(64)
            buf += data
            while buf.find('\n') != -1:
                line, buf = buf.split('\n', 1)
                yield line
        return

    def __gpsd_parse(self):
        for resp in self.__gpsd_read():
            data = json.loads(resp)
            if data['class'] == 'TPV':
                if data['mode'] in [2, 3]:
                    try:
                        lat = data['lat']
                        lon = data['lon']
                    except KeyError:
                        return
                    try:
                        alt = data['alt']
                    except KeyError:
                        alt = None
                    post_event(self.notify,
                               EventThreadStatus(Event.LOC, 0,
                                                 (lat, lon, alt)))

    def __gpsd_old_parse(self):
        for resp in self.__gpsd_read():
            data = resp.split(' ')
            if len(data) == 15 and data[0] == 'GPSD,O=GLL':
                try:
                    lat = float(data[4])
                    lon = float(data[3])
                except ValueError:
                        return
                try:
                    alt = float(data[6])
                except ValueError:
                    alt = None
                post_event(self.notify,
                           EventThreadStatus(Event.LOC, 0,
                                             (lat, lon, alt)))

    def __gpsd_close(self):
        if self.device.type == DeviceGPS.GPSD:
            self.socket.sendall('?WATCH={"enable": false}')
        else:
            self.socket.sendall('W')
        self.socket.close()

    def __nmea_open(self):
        try:
            self.serial = serial.Serial(self.device.resource,
                                        baudrate=self.device.baud,
                                        bytesize=self.device.bytes,
                                        parity=self.device.parity,
                                        stopbits=self.device.stops,
                                        xonxoff=self.device.soft,
                                        timeout=1)
        except SerialException as error:
            post_event(self.notify, EventThreadStatus(Event.LOC_WARN,
                                                      0, error.message))
            return False
        return True

    def __nmea_parse(self):
        while not self.cancel:
            resp = self.serial.readline()
            resp = resp.replace('\n', '')
            resp = resp.replace('\r', '')
            resp = resp[1::]
            resp = resp.split('*')
            if len(resp) == 2:
                checksum = self.__nmea_checksum(resp[0])
                if checksum == resp[1]:
                    data = resp[0].split(',')
                    if data[0] == 'GPGGA':
                        if data[6] in ['1', '2']:
                            lat = self.__nmea_coord(data[2], data[3])
                            lon = self.__nmea_coord(data[4], data[5])
                            try:
                                alt = float(data[9])
                            except ValueError:
                                alt = None
                            post_event(self.notify,
                                       EventThreadStatus(Event.LOC, 0,
                                                         (lat, lon, alt)))

    def __nmea_checksum(self, data):
        checksum = 0
        for char in data:
            checksum ^= ord(char)
        return "{0:X}".format(checksum)

    def __nmea_coord(self, coord, orient):
        pos = None

        if '.' in coord:
            if coord.index('.') == 4:
                try:
                    degrees = int(coord[:2])
                    minutes = float(coord[2:])
                    pos = degrees + minutes / 60.
                    if orient == 'S':
                        pos = -pos
                except ValueError:
                    pass
            elif coord.index('.') == 5:
                try:
                    degrees = int(coord[:3])
                    minutes = float(coord[3:])
                    pos = degrees + minutes / 60.
                    if orient == 'W':
                        pos = -pos
                except ValueError:
                    pass

        return pos

    def ___nmea_close(self):
        self.serial.close()

    def run(self):
        if self.device.type == DeviceGPS.NMEA:
            self.__nmea_parse()
        elif self.device.type == DeviceGPS.GPSD:
            self.__gpsd_parse()
        elif self.device.type == DeviceGPS.GPSD_OLD:
            self.__gpsd_old_parse()

        if self.device.type == DeviceGPS.NMEA:
            self.___nmea_close()
        else:
            self.__gpsd_close()

    def stop(self):
        self.cancel = True


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
