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

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
import json
import mimetypes
import os
import select
import socket
import threading
import time
import urllib
from urlparse import urlparse

import serial
from serial.serialutil import SerialException

from rtlsdr_scanner.constants import LOCATION_PORT, APP_NAME
from rtlsdr_scanner.devices import DeviceGPS
from rtlsdr_scanner.events import post_event, EventThread, Event, Log
from rtlsdr_scanner.misc import format_iso_time, haversine, format_time, \
    limit_to_ascii, limit, get_resource


TIMEOUT = 15


class ThreadLocation(threading.Thread):
    def __init__(self, notify, device, raw=False):
        threading.Thread.__init__(self)
        self.name = 'Location'
        self._notify = notify
        self._device = device
        self._raw = raw
        self._cancel = False
        self._comm = None
        self._timeout = None
        self._sats = {}
        self._send = None

        self.start()

    def __tcp_connect(self, defaultPort):
        self._comm = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._comm.settimeout(5)
        self._comm.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        url = urlparse('//' + self._device.resource)
        if url.hostname is not None:
            host = url.hostname
        else:
            host = 'localhost'
        if url.port is not None:
            port = url.port
        else:
            port = defaultPort
        if self._raw:
            text = 'Opening "{}"'.format(self._device.resource)
            post_event(self._notify, EventThread(Event.LOC_RAW, 0, text))
        try:
            self._comm.connect((host, port))
        except socket.error as error:
            post_event(self._notify, EventThread(Event.LOC_ERR,
                                                 0, error))
            return False

        return True

    def __tcp_read(self, isGpsd=False):
        buf = ''
        data = True

        while data and not self._cancel:
            reads, writes, errors = select.select([self._comm],
                                                  [self._comm],
                                                  [self._comm],
                                                  0.1)
            for read in reads:
                data = read.recv(64)
                buf += data
                while buf.find('\n') != -1:
                    line, buf = buf.split('\n', 1)
                    if not isGpsd:
                        pos = line.find('$')
                        if pos != -1 and pos + 1 < len(line):
                            yield line[pos + 1:].rstrip('\r\n')
                    else:
                        yield line
                    if self._raw:
                        line = limit_to_ascii(line)
                        post_event(self._notify, EventThread(Event.LOC_RAW,
                                                             0, line))

            for write in writes:
                if self._send is not None:
                    write.sendall(self._send)
                    self._send = None

            for _error in errors:
                post_event(self._notify, EventThread(Event.LOC_ERR,
                                                     0,
                                                     'Connection dropped'))
        return

    def __serial_timeout(self):
        self.stop()
        post_event(self._notify, EventThread(Event.LOC_ERR,
                                             0, 'GPS timed out'))

    def __serial_connect(self):
        self._timeout = Timeout(self.__serial_timeout)
        if self._raw:
            text = 'Opening "{}"'.format(self._device.resource)
            post_event(self._notify, EventThread(Event.LOC_RAW, 0, text))
        try:
            self._comm = serial.Serial(self._device.resource,
                                       baudrate=self._device.baud,
                                       bytesize=self._device.bytes,
                                       parity=self._device.parity,
                                       stopbits=self._device.stops,
                                       xonxoff=self._device.soft,
                                       timeout=0)

        except SerialException as error:
            post_event(self._notify, EventThread(Event.LOC_ERR,
                                                 0, error.message))
            return False
        except OSError as error:
            post_event(self._notify, EventThread(Event.LOC_ERR,
                                                 0, error))
            return False
        except ValueError as error:
            post_event(self._notify, EventThread(Event.LOC_ERR,
                                                 0, error))
            return False

        return True

    def __serial_read(self):
        isSentence = False
        sentence = ''
        while not self._cancel:
            data = self._comm.read(1)
            if data:
                self._timeout.reset()
                if data == '$':
                    isSentence = True
                    continue
                if data == '\r' or data == '\n':
                    isSentence = False
                    if sentence:
                        yield sentence
                        if self._raw:
                            line = limit_to_ascii(sentence)
                            post_event(self._notify, EventThread(Event.LOC_RAW,
                                                                 0, line))
                        sentence = ''
                if isSentence:
                    sentence += data
            else:
                time.sleep(0.1)

    def __gpsd_open(self):
        if not self.__tcp_connect(2947):
            return False

        try:
            if self._device.type == DeviceGPS.GPSD:
                self._send = '?WATCH={"enable": true,"json": true}\n'
            else:
                self._send = 'w'

        except IOError as error:
            post_event(self._notify, EventThread(Event.LOC_ERR,
                                                 0, error))
            self._comm.close()
            return False

        return True

    def __gpsd_read(self):
        for resp in self.__tcp_read(True):
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
                    self.__post_location(lat, lon, alt)
            elif data['class'] == 'SKY':
                self.__gpsd_sats(data['satellites'])

    def __gpsd_old_read(self):
        for resp in self.__tcp_read(True):
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

                self.__post_location(lat, lon, alt)

    def __gpsd_close(self):
        if self._device.type == DeviceGPS.GPSD:
            self._send = '?WATCH={"enable": false}\n'
        else:
            self._send = 'W'
        if self._comm is not None:
            self._comm.close()

    def __gpsd_sats(self, satData):
        sats = {}
        for sat in satData:
            sats[sat['PRN']] = [sat['ss'], sat['used']]

        post_event(self._notify,
                   EventThread(Event.LOC_SAT, None, sats))

    def __nmea_open(self):
        if self._device.type == DeviceGPS.NMEA_SERIAL:
            return self.__serial_connect()
        else:
            return self.__tcp_connect(10110)

    def __nmea_read(self):
        if self._device.type == DeviceGPS.NMEA_SERIAL:
            comm = self.__serial_read()
        else:
            comm = self.__tcp_read()

        for resp in comm:
            nmea = resp.split('*')
            if len(nmea) == 2:
                data = nmea[0].split(',')
                if data[0] in ['GPGGA', 'GPGSV']:
                    checksum = self.__nmea_checksum(nmea[0])
                    if checksum == nmea[1]:
                        if data[0] == 'GPGGA':
                            self.__nmea_global_fix(data)
                        elif data[0] == 'GPGSV':
                            self.__nmea_sats(data)
                    else:
                        error = 'Invalid checksum {}, should be {}'.format(resp[1],
                                                                           checksum)
                        post_event(self._notify, EventThread(Event.LOC_WARN,
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

            self.__post_location(lat, lon, alt)

    def __nmea_sats(self, data):
        message = int(data[1])
        messages = int(data[1])
        viewed = int(data[3])

        if message == 1:
            self._sats.clear()

        blocks = (len(data) - 4) / 4
        for i in range(0, blocks):
            sat = int(data[4 + i * 4])
            level = data[7 + i * 4]
            used = True
            if level == '':
                level = None
                used = False
            else:
                level = int(level)
            self._sats[sat] = [level, used]

        if message == messages and len(self._sats) == viewed:
            post_event(self._notify,
                       EventThread(Event.LOC_SAT, None, self._sats))

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

    def __nmea_close(self):
        if self._timeout is not None:
            self._timeout.cancel()
        if self._comm is not None:
            self._comm.close()

    def __post_location(self, lat, lon, alt):
        utc = time.time()
        post_event(self._notify,
                   EventThread(Event.LOC, 0, [lat, lon, alt, utc]))

    def run(self):
        conn = True

        if self._device.type in [DeviceGPS.NMEA_SERIAL, DeviceGPS.NMEA_TCP]:
            if not self.__nmea_open():
                self.__nmea_close()
                conn = False
        else:
            if not self.__gpsd_open():
                conn = False

        if conn:
            if self._device.type in [DeviceGPS.NMEA_SERIAL, DeviceGPS.NMEA_TCP]:
                self.__nmea_read()
            elif self._device.type == DeviceGPS.GPSD:
                self.__gpsd_read()
            elif self._device.type == DeviceGPS.GPSD_OLD:
                self.__gpsd_old_read()

            if self._device.type in [DeviceGPS.NMEA_SERIAL, DeviceGPS.NMEA_TCP]:
                self.__nmea_close()
            else:
                self.__gpsd_close()

        if self._raw:
            post_event(self._notify, EventThread(Event.LOC_RAW, 0, 'Stopped'))

    def stop(self):
        self._cancel = True
        if self._raw:
            self._notify.queue.clear()


class LocationServer(object):
    def __init__(self, locations, currentLoc, lock, log):
        self.server = HTTPServer(('127.0.0.1', LOCATION_PORT),
                                 LocationServerHandler)
        self.server.locations = locations
        self.server.currentLoc = currentLoc
        self.server.lock = lock
        self.server.log = log
        self.thread = threading.Thread(target=self.__serve, name='Location')
        self.thread.start()

    def __serve(self):
        self.server.serve_forever()

    def close(self):
        self.server.shutdown()


class LocationServerHandler(BaseHTTPRequestHandler):
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
        dist = haversine(latMin, latMax, lonMin, lonMax)
        dist = limit(dist, 100, 50000)

        lookAt = ('\t\t<LookAt>\n'
                  '\t\t\t<latitude>{}</latitude>\n'
                  '\t\t\t<longitude>{}</longitude>\n'
                  '\t\t\t<altitudeMode>clampToGround</altitudeMode>\n'
                  '\t\t\t<range>{}</range>\n'
                  '\t\t\t<gx:TimeSpan>\n'
                  '\t\t\t\t<begin>{}</begin>\n'
                  '\t\t\t\t<end>{}</end>\n'
                  '\t\t\t</gx:TimeSpan>\n'
                  '\t\t</LookAt>\n').\
            format(latCen, lonCen, dist * 2, begin, end)

        return lookAt

    def __create_last(self):
        loc = self.server.currentLoc
        if loc[0] is None:
            return ''

        last = ('\t\t<Placemark>\n'
                '\t\t\t<name>Last Location</name>\n'
                '\t\t\t<description>{}</description>\n'
                '\t\t\t<styleUrl>#last</styleUrl>\n'
                '\t\t\t<altitudeMode>clampToGround</altitudeMode>\n'
                '\t\t\t<Point>\n').format(format_time(loc[3]))

        if loc[2] is None:
            last += '\t\t\t\t<coordinates>{},{}</coordinates>\n'.\
                format(loc[1], loc[0])
        else:
            last += '\t\t\t\t<coordinates>{},{},{}</coordinates>\n'.\
                format(loc[1], loc[0], loc[2])

        last += ('\t\t\t</Point>\n'
                 '\t\t</Placemark>\n')

        return last

    def __create_track(self):
        if not len(self.server.locations):
            return ''

        track = ('\t\t<Placemark>\n'
                 '\t\t\t<name>Track</name>\n'
                 '\t\t\t<description>{} locations</description>\n'
                 '\t\t\t<styleUrl>#track</styleUrl>\n'
                 '\t\t\t<gx:Track>\n'
                 '\t\t\t\t<altitudeMode>clampToGround</altitudeMode>\n').\
            format(len(self.server.locations))

        with self.server.lock:
            for timeStamp in sorted(self.server.locations):
                lat, lon, alt = self.server.locations[timeStamp]
                timeStr = format_iso_time(timeStamp)
                if alt is None:
                    track += '\t\t\t\t<gx:coord>{} {}</gx:coord>\n'.\
                        format(lon, lat)

                else:
                    track += '\t\t\t\t<gx:coord>{} {} {}</gx:coord>\n'.\
                        format(lon, lat, alt)
                track += '\t\t\t\t<when>{}</when>\n'.format(timeStr)

        track += ('\t\t\t</gx:Track>\n'
                  '\t\t</Placemark>\n')

        return track

    def __send_kml(self):
        self.send_response(200)
        self.send_header('Content-type',
                         'application/vnd.google-earth.kml+xml')
        self.end_headers()

        self.wfile.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                         '<kml xmlns="http://www.opengis.net/kml/2.2" '
                         'xmlns:gx="http://www.google.com/kml/ext/2.2">\n')

        self.wfile.write(('\t<Document>\n'
                          '\t\t<name>{}</name>\n').format(APP_NAME))

        self.wfile.write(self.__create_lookat())

        self.wfile.write(('\t\t<Style id="last">\n'
                          '\t\t\t<IconStyle>\n'
                          '\t\t\t\t<Icon>\n'
                          '\t\t\t\t\t<href>http://localhost:{}/crosshair.png</href>\n'
                          '\t\t\t\t</Icon>\n'
                          '\t\t\t\t<hotSpot x="0.5" y="0.5" xunits="fraction" yunits="fraction"/>\n'
                          '\t\t\t\t<scale>2</scale>\n'
                          '\t\t\t</IconStyle>\n'
                          '\t\t</Style>\n').format(LOCATION_PORT))

        self.wfile.write('\t\t<Style id="track">\n'
                         '\t\t\t<LineStyle>\n'
                         '\t\t\t\t<color>7f0000ff</color>\n'
                         '\t\t\t\t<width>4</width>\n'
                         '\t\t\t</LineStyle>\n'
                         '\t\t\t<IconStyle>\n'
                         '\t\t\t\t<scale>0</scale>\n'
                         '\t\t\t</IconStyle>\n'
                         '\t\t\t<LabelStyle>\n'
                         '\t\t\t\t<scale>0</scale>\n'
                         '\t\t\t</LabelStyle>\n'
                         '\t\t</Style>\n')

        self.wfile.write(self.__create_last())
        self.wfile.write(self.__create_track())

        self.wfile.write('\t</Document>\n'
                         '</kml>\n')

    def __send_geojson(self):
        self.send_response(200)
        self.send_header('Content-type',
                         'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        features = []
        with self.server.lock:
            for location in self.server.locations.values():
                geometry = {'type': 'Point',
                            'coordinates': location}
                feature = {'type': 'Feature',
                           'geometry': geometry}
                features.append(feature)

        location = self.server.currentLoc
        if location[0] is not None:
            geometry = {'type': 'Point',
                        'coordinates': location}
            feature = {'type': 'Feature',
                       'geometry': geometry,
                       'properties': {'isLast': True}}
            features.append(feature)

        data = {'Type': 'FeatureCollection',
                'features': features}

        self.wfile.write(json.dumps(data, indent=4))

    def __send_file(self):
        url = urlparse(self.path)
        _dir, filename = os.path.split(url.path)
        localFile = get_resource(filename)
        if os.path.isdir(localFile) or not os.path.exists(localFile):
            self.send_error(404)
            self.server.log.add('File not found: {}'.format(self.path),
                                Log.WARN)
            return

        urlFile = urllib.pathname2url(localFile)
        self.send_response(200)
        self.send_header('Content-type', mimetypes.guess_type(urlFile)[0])
        self.end_headers()

        f = open(localFile, 'rb')
        self.wfile.write(f.read())
        f.close()

    def do_GET(self):
        if self.path == '/kml':
            self.__send_kml()
        elif self.path == '/gjson':
            self.__send_geojson()
        else:
            self.__send_file()

    def log_message(self, *args, **kwargs):
        pass


class Timeout(threading.Thread):
    def __init__(self, callback):
        threading.Thread.__init__(self)
        self.name = 'GPS Timeout'

        self._callback = callback
        self._done = threading.Event()
        self._reset = True

        self.start()

    def run(self):
        while self._reset:
            self._reset = False
            self._done.wait(TIMEOUT)

        if not self._done.isSet():
            self._callback()

    def reset(self):
        self._reset = True
        self._done.clear()

    def cancel(self):
        self._done.set()


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
