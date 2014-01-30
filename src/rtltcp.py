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

import array
import socket
import struct
import threading

import numpy


class RtlTcpCmd():
    SET_FREQ = 0x1
    SET_SAMPLE_RATE = 0x2
    SET_GAIN_MODE = 0x3
    SET_GAIN = 0x4


class RtlTcp():
    def __init__(self, host, port):
        self.host = host
        self.port = port

        self.threadBuffer = None
        self.tuner = 0
        self.rate = 0

        self.setup()

    def setup(self):
        self.threadBuffer = ThreadBuffer(self.host, self.port)
        self.get_header()

    def get_header(self):
        header = self.threadBuffer.get_header()
        if len(header) == 12:
            if header.startswith('RTL'):
                self.tuner = (ord(header[4]) << 24) | \
                             (ord(header[5]) << 16) | \
                             (ord(header[6]) << 8) | \
                             ord(header[7])

    def send_command(self, command, data):
        send = array.array('c', '\0' * 5)

        struct.pack_into('>l', send, 1, data)
        send[0] = struct.pack('<b', command)

        self.threadBuffer.sendall(send)

    def read_raw(self, samples):
        return self.threadBuffer.recv(samples)

    def raw_to_iq(self, raw):
        iq = numpy.empty(len(raw) / 2, 'complex')
        iq.real, iq.imag = raw[::2], raw[1::2]
        iq /= (255 / 2)
        iq -= 1

        return iq

    def set_sample_rate(self, rate):
        self.send_command(RtlTcpCmd.SET_SAMPLE_RATE, rate)
        self.rate = rate

    def set_gain_mode(self, mode):
        self.send_command(RtlTcpCmd.SET_GAIN_MODE, mode)

    def set_gain(self, gain):
        self.send_command(RtlTcpCmd.SET_GAIN, gain * 10)

    def set_center_freq(self, freq):
        self.send_command(RtlTcpCmd.SET_FREQ, freq)
        self.read_raw(int(self.rate * 2 * 0.1))

    def get_tuner_type(self):
        return self.tuner

    def read_samples(self, samples):

        raw = self.read_raw(samples)
        return self.raw_to_iq(raw)

    def close(self):
        self.threadBuffer.abort()
        self.threadBuffer.join()


class ThreadBuffer(threading.Thread):
    name = 'Buffer'
    buffer = ""
    cancel = False
    readLen = 0
    read = 0
    done = False
    READ_SIZE = 4096

    def __init__(self, host, port):
        threading.Thread.__init__(self)

        self.condition = threading.Condition()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(5)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.socket.connect((host, port))
        self.header = self.socket.recv(12)
        self.start()

    def run(self):
        while(not self.cancel):
            if self.readLen > 0:
                self.read_stream()
            else:
                self.skip_stream()

        self.socket.close()
        self.doNotify()

    def doWait(self):
        self.condition.acquire()
        while not self.done:
            self.condition.wait(2)
        self.done = False
        self.condition.release()

    def doNotify(self):
        self.condition.acquire()
        self.done = True
        self.condition.notify()
        self.condition.release()

    def read_stream(self):
        data = []
        recv = ""

        self.buffer = ""
        while self.readLen > 0:
            recv = self.socket.recv(self.readLen)
            if len(recv) == 0:
                break
            data.append(recv)
            self.readLen -= len(recv)

        self.buffer = bytearray(''.join(data))
        self.doNotify()

    def skip_stream(self):
        total = self.READ_SIZE
        while total > 0:
            recv = self.socket.recv(total)
            if len(recv) == 0:
                break
            total -= len(recv)

    def get_header(self):
        return self.header

    def recv(self, length):
        self.readLen = length
        self.doWait()
        return self.buffer

    def sendall(self, data):
        self.socket.sendall(data)

    def abort(self):
        self.cancel = True
