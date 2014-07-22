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

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
import json
from math import radians, sin, cos, asin, sqrt
import socket
import threading
from urlparse import urlparse

import serial
from serial.serialutil import SerialException

from devices import DeviceGPS
from events import post_event, EventThread, Event
from misc import format_iso_time


class ThreadLocation(threading.Thread):
    def __init__(self, notify, device, raw=False):
        threading.Thread.__init__(self)
        self.name = 'Location'
        self.notify = notify
        self.device = device
        self.raw = raw
        self.cancel = False
        self.comm = None
        self.sats = {}
        self.start()

    def __tcp_connect(self, defaultPort):
        self.comm = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.comm.settimeout(5)
        self.comm.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        url = urlparse('//' + self.device.resource)
        if url.hostname is not None:
            host = url.hostname
        else:
            host = 'localhost'
        if url.port is not None:
            port = url.port
        else:
            port = defaultPort
        if self.raw:
            text = 'Opening "{0}"'.format(self.device.resource)
            post_event(self.notify, EventThread(Event.LOC_RAW, 0, text))
        try:
            self.comm.connect((host, port))
        except socket.error as error:
            post_event(self.notify, EventThread(Event.LOC_ERR,
                                                0, error))

    def __tcp_read(self):
        buf = ''
        data = True
        while data and not self.cancel:
            try:
                data = self.comm.recv(1024)
            except socket.timeout as error:
                post_event(self.notify, EventThread(Event.LOC_ERR,
                                                    0, error))
                return
            buf += data
            while buf.find('\n') != -1:
                line, buf = buf.split('\n', 1)
                yield line
                if self.raw:
                    post_event(self.notify, EventThread(Event.LOC_RAW,
                                                        0, line))
        return

    def __serial_connect(self):
        if self.raw:
            text = 'Opening "{0}"'.format(self.device.resource)
            post_event(self.notify, EventThread(Event.LOC_RAW, 0, text))
        try:
            self.comm = serial.Serial(self.device.resource,
                                      baudrate=self.device.baud,
                                      bytesize=self.device.bytes,
                                      parity=self.device.parity,
                                      stopbits=self.device.stops,
                                      xonxoff=self.device.soft,
                                      timeout=1)
        except SerialException as error:
            post_event(self.notify, EventThread(Event.LOC_ERR,
                                                0, error.message))
            return False
        except OSError as error:
            post_event(self.notify, EventThread(Event.LOC_ERR,
                                                0, error))
            return False
        return True

    def __serial_read(self):
        data = True
        while data and not self.cancel:
            data = self.comm.readline()
            yield data
            if self.raw:
                post_event(self.notify, EventThread(Event.LOC_RAW,
                                                    0, data))
        return

    def __gpsd_open(self):
        self.__tcp_connect(2947)

        try:
            if self.device.type == DeviceGPS.GPSD:
                self.comm.sendall('?WATCH={"enable": true,"json": true}')
            else:
                self.comm.sendall('w')

        except IOError as error:
            post_event(self.notify, EventThread(Event.LOC_ERR,
                                                0, error))
            self.comm.close()
            return False

        return True

    def __gpsd_read(self):
        for resp in self.__tcp_read():
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
                               EventThread(Event.LOC, 0,
                                           (lat, lon, alt)))

    def __gpsd_old_read(self):
        for resp in self.__tcp_read():
            data = resp.split(' ')
            if len(data) == 15 and data[0] == 'GPSD,O=GGA':
                try:
                    lat = float(data[4])
                    lon = float(data[3])
                except ValueError:
                    return
                try:
                    alt = float(data[5])
                except ValueError:
                    alt = None
                post_event(self.notify,
                           EventThread(Event.LOC, 0,
                                       (lat, lon, alt)))

    def __gpsd_close(self):
        if self.device.type == DeviceGPS.GPSD:
            self.comm.sendall('?WATCH={"enable": false}')
        else:
            self.comm.sendall('W')
        self.comm.close()

    def __nmea_open(self):
        if self.device.type == DeviceGPS.NMEA_SERIAL:
            return self.__serial_connect()
        else:
            self.__tcp_connect(10110)
            return True

    def __nmea_read(self):
        if self.device.type == DeviceGPS.NMEA_SERIAL:
            comm = self.__serial_read()
        else:
            comm = self.__tcp_read()

        for resp in comm:
            resp = resp.replace('\n', '')
            resp = resp.replace('\r', '')
            resp = resp[1::]
            resp = resp.split('*')
            if len(resp) == 2:
                checksum = self.__nmea_checksum(resp[0])
                if checksum == resp[1]:
                    data = resp[0].split(',')
                    if data[0] == 'GPGGA':
                        self.__nmea_global_fix(data)
                    elif data[0] == 'GPGSV':
                        self.__nmea_sats(data)
                else:
                    error = 'Invalid checksum {0}, should be {1}'.format(resp[1],
                                                                         checksum)
                    post_event(self.notify, EventThread(Event.LOC_WARN,
                                                        0, error))

    def __nmea_checksum(self, data):
        checksum = 0
        for char in data:
            checksum ^= ord(char)
        return "{0:02X}".format(checksum)

    def __nmea_global_fix(self, data):
        if data[6] in ['1', '2']:
            lat = self.__nmea_coord(data[2], data[3])
            lon = self.__nmea_coord(data[4], data[5])
            try:
                alt = float(data[9])
            except ValueError:
                alt = None
            post_event(self.notify,
                       EventThread(Event.LOC, 0, (lat, lon, alt)))

    def __nmea_sats(self, data):
        message = int(data[1])
        messages = int(data[1])
        viewed = int(data[3])

        if message == 1:
            self.sats.clear()

        blocks = (len(data) - 4) / 4
        for i in range(0, blocks):
            sat = int(data[4 + i * 4])
            used = False if data[5 + i * 4] == '' else True
            self.sats[sat] = used

        if message == messages and len(self.sats) == viewed:
            post_event(self.notify,
                       EventThread(Event.LOC_SAT,
                                   sum(self.sats.values()), viewed))

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
        self.comm.close()

    def run(self):
        if self.device.type in [DeviceGPS.NMEA_SERIAL, DeviceGPS.NMEA_TCP]:
            if not self.__nmea_open():
                return
        else:
            if not self.__gpsd_open():
                return

        if self.device.type in [DeviceGPS.NMEA_SERIAL, DeviceGPS.NMEA_TCP]:
            self.__nmea_read()
        elif self.device.type == DeviceGPS.GPSD:
            self.__gpsd_read()
        elif self.device.type == DeviceGPS.GPSD_OLD:
            self.__gpsd_old_read()

        if self.device.type in [DeviceGPS.NMEA_SERIAL, DeviceGPS.NMEA_TCP]:
            self.___nmea_close()
        else:
            self.__gpsd_close()

    def stop(self):
        self.cancel = True
        if self.raw:
            self.notify.queue.clear()


class KmlServer(object):
    def __init__(self, locations, lock):
        self.server = HTTPServer(('127.0.0.1', 12345), KmlServerHandler)
        self.server.locations = locations
        self.server.lock = lock
        self.thread = threading.Thread(target=self.__serve_kml)
        self.thread.start()

    def __serve_kml(self):
        self.server.serve_forever()

    def close(self):
        self.server.shutdown()


class KmlServerHandler(BaseHTTPRequestHandler):
    def __haversine(self, lat1, lat2, lon1, lon2):
        lat1, lat2, lon1, lon2 = map(radians, [lat1, lat2, lon1, lon2])

        dlon = lon1 - lon2
        dlat = lat1 - lat2
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        b = asin(sqrt(a))

        return 2 * b * 6371000

    def __create_lookat(self):
        if not len(self.server.locations):
            return ''

        begin = format_iso_time(min(self.server.locations))
        end = format_iso_time(max(self.server.locations))

        lat = [y for y, _x, _z in self.server.locations.itervalues()]
        lon = [x for _y, x, _z in self.server.locations.itervalues()]
        latMin = min(lat)
        latMax = max(lat)
        lonMin = min(lon)
        lonMax = max(lon)
        latCen = (latMax + latMin) / 2
        lonCen = (lonMax + lonMin) / 2
        dist = self.__haversine(latMin, latMax, lonMin, lonMax)
        dist = max(min(50000, dist), 100)

        lookAt = ('\t\t<LookAt>\n'
                  '\t\t\t<latitude>{}</latitude>\n'
                  '\t\t\t<longitude>{}</longitude>\n'
                  '\t\t\t<altitudeMode>clampToGround</altitudeMode>\n'
                  '\t\t\t<range>{}</range>\n'
                  '\t\t\t<gx:TimeSpan>\n'
                  '\t\t\t\t<begin>{}</begin>\n'
                  '\t\t\t\t<end>{}</end>\n'
                  '\t\t\t</gx:TimeSpan>\n'
                  '\t\t</LookAt>\n').format(latCen, lonCen, dist * 2, begin, end)

        return lookAt

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/vnd.google-earth.kml+xml')
        self.end_headers()

        self.wfile.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        self.wfile.write('<kml xmlns="http://www.opengis.net/kml/2.2" '
                         'xmlns:gx="http://www.google.com/kml/ext/2.2">\n')

        self.wfile.write('\t<Document>\n')
        self.wfile.write('\t\t<name>RTLSDR Scanner</name>\n')

        self.wfile.write(self.__create_lookat())

        self.wfile.write('\t\t<Style id="track">\n')
        self.wfile.write('\t\t\t<LineStyle>\n')
        self.wfile.write('\t\t\t\t<color>7f0000ff</color>\n')
        self.wfile.write('\t\t\t\t<width>4</width>\n')
        self.wfile.write('\t\t\t</LineStyle>\n')
        self.wfile.write('\t\t</Style>\n')

        self.wfile.write('\t\t<Placemark>\n')
        self.wfile.write('\t\t\t<name>Track</name>\n')
        self.wfile.write('\t\t\t<description>{} locations</description>\n'.
                         format(len(self.server.locations)))
        self.wfile.write('\t\t\t<styleUrl>#track</styleUrl>\n')

        self.wfile.write('\t\t\t<gx:Track>\n')
        self.wfile.write('\t\t\t\t<altitudeMode>clampToGround</altitudeMode>\n')

        with self.server.lock:
            for timeStamp in sorted(self.server.locations):
                lat, lon, alt = self.server.locations[timeStamp]
                timeStr = format_iso_time(timeStamp)
                self.wfile.write('\t\t\t\t<gx:coord>{} {} {}</gx:coord>\n'.
                                 format(lon, lat, alt))
                self.wfile.write('\t\t\t\t<when>{}</when>\n'.format(timeStr))

        self.wfile.write('\t\t\t</gx:Track>\n')
        self.wfile.write('\t\t</Placemark>\n')
        self.wfile.write('\t</Document>\n')
        self.wfile.write('</kml>\n')

    def log_message(self, *args, **kwargs):
        pass


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
