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

from collections import OrderedDict
import itertools
import math
import threading
import time

import matplotlib
import rtlsdr

from rtlsdr_scanner.constants import SAMPLE_RATE, BANDWIDTH, WINFUNC
from rtlsdr_scanner.events import EventThread, Event, post_event
from rtlsdr_scanner.rtltcp import RtlTcp


class ThreadScan(threading.Thread):
    def __init__(self, notify, queue, sdr, settings, device, samples, isCal):
        threading.Thread.__init__(self)
        self.name = 'Scan'
        self.notify = notify
        self.queue = queue
        self.sdr = sdr
        self.fstart = settings.start * 1e6
        self.fstop = settings.stop * 1e6
        self.samples = int(samples)
        self.isCal = isCal
        self.indexRtl = settings.indexRtl
        self.isDevice = settings.devicesRtl[device].isDevice
        self.server = settings.devicesRtl[device].server
        self.port = settings.devicesRtl[device].port
        self.gain = settings.devicesRtl[device].gain
        self.lo = settings.devicesRtl[device].lo * 1e6
        self.offset = settings.devicesRtl[device].offset
        self.cancel = False

        post_event(self.notify, EventThread(Event.STARTING))
        steps = int((self.__f_stop() - self.__f_start()) / self.__f_step())
        post_event(self.notify, EventThread(Event.STEPS, steps))
        self.start()

    def __f_start(self):
        return self.fstart - self.offset - BANDWIDTH

    def __f_stop(self):
        return self.fstop + self.offset + BANDWIDTH * 2

    def __f_step(self):
        return BANDWIDTH / 2

    def __rtl_setup(self):

        if self.sdr is not None:
            return

        tuner = 0

        if self.isDevice:
            try:
                self.sdr = rtlsdr.RtlSdr(self.indexRtl)
                self.sdr.set_sample_rate(SAMPLE_RATE)
                self.sdr.set_gain(self.gain)
                tuner = self.sdr.get_tuner_type()
            except IOError as error:
                post_event(self.notify, EventThread(Event.ERROR,
                                                    0, error.message))
        else:
            try:
                self.sdr = RtlTcp(self.server, self.port, self.notify)
                self.sdr.set_sample_rate(SAMPLE_RATE)
                self.sdr.set_gain(self.gain)
                tuner = self.sdr.get_tuner_type()
            except IOError as error:
                post_event(self.notify, EventThread(Event.ERROR,
                                                    0, error))

        return tuner

    def run(self):
        tuner = self.__rtl_setup()
        if self.sdr is None:
            return
        post_event(self.notify, EventThread(Event.INFO, None, tuner))

        freq = self.__f_start()
        timeStamp = math.floor(time.time())
        while freq <= self.__f_stop():
            if self.cancel:
                post_event(self.notify, EventThread(Event.STOPPED))
                self.rtl_close()
                return
            try:
                scan = self.rtl_scan(freq)
                if len(scan):
                    self.queue.put([freq, (timeStamp, scan)])
                    post_event(self.notify, EventThread(Event.DATA))
                else:
                    post_event(self.notify, EventThread(Event.ERROR, 0,
                                                        'No samples returned'))
                    return
            except (AttributeError, MemoryError, TypeError) as error:
                post_event(self.notify, EventThread(Event.ERROR,
                                                    0, error.message))
                return
            except (IOError, OSError) as error:
                if self.sdr is not None:
                    self.rtl_close()
                post_event(self.notify, EventThread(Event.ERROR,
                                                    0, error.message))
                return

            freq += self.__f_step()

        post_event(self.notify, EventThread(Event.FINISHED, 0, None))

        if self.isCal:
            post_event(self.notify, EventThread(Event.CAL))

    def abort(self):
        self.cancel = True

    def rtl_scan(self, freq):
        self.sdr.set_center_freq(freq + self.lo)
        capture = self.sdr.read_samples(self.samples)

        return capture

    def rtl_close(self):
        self.sdr.close()

    def get_sdr(self):
        return self.sdr


class ThreadProcess(threading.Thread):
    def __init__(self, notify, freq, scan, cal, levelOff, nfft, overlap, winFunc):
        threading.Thread.__init__(self)
        self.name = 'ThreadProcess'
        self.notify = notify
        self.freq = freq
        self.scan = scan
        self.cal = cal
        self.levelOff = math.pow(10, levelOff / 10.0)
        self.nfft = nfft
        self.overlap = overlap
        self.winFunc = winFunc
        self.window = matplotlib.numpy.hamming(nfft)

    def run(self):
        spectrum = {}
        timeStamp = self.scan[0]
        samples = self.scan[1]
        pos = WINFUNC[::2].index(self.winFunc)
        function = WINFUNC[1::2][pos]

        powers, freqs = matplotlib.mlab.psd(samples,
                                            NFFT=self.nfft,
                                            Fs=SAMPLE_RATE / 1e6,
                                            window=function(self.nfft))
        for freqPsd, pwr in itertools.izip(freqs, powers):
            xr = freqPsd + (self.freq / 1e6)
            xr = xr + (xr * self.cal / 1e6)
            spectrum[xr] = pwr * self.levelOff
        post_event(self.notify, EventThread(Event.PROCESSED,
                                            (timeStamp, self.freq, spectrum)))


def update_spectrum(notify, lock, start, stop, data, offset,
                    spectrum, average, alertLevel=None):
    with lock:
        updated = False
        if average:
            if len(spectrum) > 0:
                timeStamp = min(spectrum)
            else:
                timeStamp = data[0]
        else:
            timeStamp = data[0]

        freqCentre = data[1]
        scan = data[2]

        upperStart = freqCentre + offset
        upperEnd = freqCentre + offset + BANDWIDTH / 2
        lowerStart = freqCentre - offset - BANDWIDTH / 2
        lowerEnd = freqCentre - offset

        if timeStamp not in spectrum:
            spectrum[timeStamp] = OrderedDict()

        for freq in scan:
            if start <= freq < stop:
                power = 10 * math.log10(scan[freq])
                if upperStart <= freq * 1e6 <= upperEnd or \
                   lowerStart <= freq * 1e6 <= lowerEnd:
                    if freq in spectrum[timeStamp]:
                        spectrum[timeStamp][freq] = \
                            (spectrum[timeStamp][freq] + power) / 2
                        if alertLevel is not None and (spectrum[timeStamp][freq] >
                                                       alertLevel):
                            post_event(notify, EventThread(Event.LEVEL))
                        updated = True
                    else:
                        spectrum[timeStamp][freq] = power
                        updated = True

        if updated:
            spectrum[timeStamp] = OrderedDict(sorted(spectrum[timeStamp].items()))

    post_event(notify, EventThread(Event.UPDATED, None, updated))


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
