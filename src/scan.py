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

import itertools
import math
import threading

import matplotlib
import rtlsdr

from constants import SAMPLE_RATE, BANDWIDTH
from events import EventThreadStatus, Event, post_event
import rtltcp


class ThreadScan(threading.Thread):
    def __init__(self, notify, settings, device, samples, isCal):
        threading.Thread.__init__(self)
        self.name = 'ThreadScan'
        self.notify = notify
        self.fstart = settings.start * 1e6
        self.fstop = settings.stop * 1e6
        self.samples = samples
        self.isCal = isCal
        self.index = settings.index
        self.isDevice = settings.devices[device].isDevice
        self.server = settings.devices[device].server
        self.port = settings.devices[device].port
        self.gain = settings.devices[device].gain
        self.lo = settings.devices[device].lo * 1e6
        self.offset = settings.devices[device].offset
        self.cancel = False
        post_event(self.notify, EventThreadStatus(Event.STARTING))
        self.start()

    def run(self):
        sdr = self.rtl_setup()
        if sdr is None:
            return

        freq = self.fstart - self.offset - BANDWIDTH
        while freq <= self.fstop + self.offset:
            if self.cancel:
                post_event(self.notify,
                           EventThreadStatus(Event.STOPPED))
                self.rtl_close(sdr)
                return
            try:
                progress = ((freq - self.fstart + self.offset + BANDWIDTH) /
                             (self.fstop - self.fstart + (self.offset * 2) + BANDWIDTH)) * 100
                post_event(self.notify,
                           EventThreadStatus(Event.SCAN,
                                               0, progress))
                scan = self.rtl_scan(sdr, freq)
                post_event(self.notify,
                           EventThreadStatus(Event.DATA, freq,
                                               scan))
            except (IOError, WindowsError):
                if sdr is not None:
                    self.rtl_close(sdr)
                sdr = self.rtl_setup()
            except (TypeError, AttributeError) as error:
                if self.notify:
                    post_event(self.notify,
                               EventThreadStatus(Event.ERROR,
                                                 0, error.message))
                return

            freq += BANDWIDTH / 2

        self.rtl_close(sdr)
        post_event(self.notify, EventThreadStatus(Event.FINISHED,
                                                  0, self.isCal))

    def abort(self):
        self.cancel = True

    def rtl_setup(self):
        sdr = None

        if self.isDevice:
            try:
                sdr = rtlsdr.RtlSdr(self.index)
                sdr.set_sample_rate(SAMPLE_RATE)
                sdr.set_gain(self.gain)
            except IOError as error:
                post_event(self.notify, EventThreadStatus(Event.ERROR,
                                                          0, error.message))
        else:
            try:
                sdr = rtltcp.RtlTcp(self.server, self.port)
                sdr.set_sample_rate(SAMPLE_RATE)
                sdr.set_gain(self.gain)
            except IOError as error:
                post_event(self.notify, EventThreadStatus(Event.ERROR,
                                                          0, error))

        return sdr

    def rtl_scan(self, sdr, freq):
        sdr.set_center_freq(freq + self.lo)
        capture = sdr.read_samples(self.samples)

        return capture

    def rtl_close(self, sdr):
        sdr.close()


def anaylse_data(freq, data, cal, nfft):
    rtl_scan = {}
    window = matplotlib.numpy.hamming(nfft)
    powers, freqs = matplotlib.mlab.psd(data,
                     NFFT=nfft,
                     Fs=SAMPLE_RATE / 1e6,
                     window=window)
    for freqPsd, pwr in itertools.izip(freqs, powers):
        xr = freqPsd + (freq / 1e6)
        xr = xr + (xr * cal / 1e6)
        xr = int((xr * 5e4) + 0.5) / 5e4
        rtl_scan[xr] = pwr

    return (freq, rtl_scan)


def update_spectrum(start, stop, freqCentre, scan, offset, spectrum):
        upperStart = freqCentre + offset
        upperEnd = freqCentre + offset + BANDWIDTH / 2
        lowerStart = freqCentre - offset - BANDWIDTH / 2
        lowerEnd = freqCentre - offset

        for freq in scan:
            if start < freq < stop:
                power = 10 * math.log10(scan[freq])
                if upperStart < freq * 1e6 < upperEnd:
                    spectrum[freq] = power
                if lowerStart < freq * 1e6 < lowerEnd:
                    if freq in spectrum:
                        spectrum[freq] = (spectrum[freq] + power) / 2
                    else:
                        spectrum[freq] = power


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
