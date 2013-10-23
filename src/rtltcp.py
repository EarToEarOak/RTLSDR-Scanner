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

import array
import socket
import struct
import threading

import numpy


class RtlTcpCmd():
    SET_FREQ = 0x1
    SET_SAMPLE_RATE = 0x2
    SET_GAIN = 0x4


class RtlTcp():
    def __init__(self, host, port):
        self.host = host
        self.port = port

        self.threadBucket = None
        self.socket = None
        self.tuner = None
        self.rate = 0

        self.setup()

    def setup(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        self.threadBucket = ThreadBucket(self.socket)
        self.tuner = self.get_header()
        self.threadBucket.bucket(True)

    def get_header(self):
        recv = self.socket.recv(4096)
        tuner = None
        if len(recv) == 12:
            if recv.startswith('RTL'):
                tuner = (ord(recv[4]) << 24) | \
                (ord(recv[5]) << 16) | \
                (ord(recv[6]) << 8) | \
                ord(recv[7])

        return tuner

    def send_command(self, command, data):
        recv = array.array('c', '\0' * 5)

        struct.pack_into('>l', recv, 1, data)
        recv[0] = struct.pack('<b', command)

        self.socket.sendall(recv)

    def read_raw(self, samples):
        total = 0
        data = []

        recv = ""
        self.threadBucket.bucket(False)
        while total < samples * 2:
            recv = self.socket.recv((samples * 2) - total)
            data.append(recv)
            total += len(recv)

        self.threadBucket.bucket(True)
        return bytearray(''.join(data))

    def raw_to_iq(self, raw):
        iq = numpy.empty(len(raw) / 2, 'complex')
        iq.real, iq.imag = raw[::2], raw[1::2]
        iq /= (255 / 2)

        return iq

    def set_sample_rate(self, rate):
        self.send_command(RtlTcpCmd.SET_SAMPLE_RATE, rate)
        self.rate = rate

    def set_gain(self, gain):
        self.send_command(RtlTcpCmd.SET_GAIN, gain)

    def set_center_freq(self, freq):
        self.send_command(RtlTcpCmd.SET_FREQ, freq)
        self.read_raw(int(self.rate * 2 * 0.1))

    def read_samples(self, samples):

        raw = self.read_raw(samples)
        return self.raw_to_iq(raw)

    def close(self):
        self.threadBucket.abort()
        self.threadBucket.join()
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()


class ThreadBucket(threading.Thread):
    def __init__(self, socket):
        threading.Thread.__init__(self)
        self.name = 'ThreadBucket'
        self.cancel = False
        self.socket = socket
        self.state = False

        self.start()

    def run(self):
        while(not self.cancel):
            if self.bucket:
                self.socket.recv(4096)

    def bucket(self, state):
        self.state = state

    def abort(self):
        self.cancel = True
