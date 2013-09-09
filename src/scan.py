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
import threading

import matplotlib
import rtlsdr
import wx

from constants import *


EVT_THREAD_STATUS = wx.NewId()


class Status():
    def __init__(self, status, freq, data):
        self.status = status
        self.freq = freq
        self.data = data

    def get_status(self):
        return self.status

    def get_freq(self):
        return self.freq

    def get_data(self):
        return self.data


class EventThreadStatus(wx.PyEvent):
    def __init__(self, status, freq, data):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_THREAD_STATUS)
        self.data = Status(status, freq, data)


class ThreadScan(threading.Thread):
    def __init__(self, notify, settings, devices, samples, isCal):
        threading.Thread.__init__(self)
        self.notify = notify
        self.index = settings.index
        self.fstart = settings.start * 1e6
        self.fstop = settings.stop * 1e6
        self.samples = samples
        self.isCal = isCal
        self.gain = devices[self.index].gain
        self.lo = devices[self.index].lo * 1e6
        self.offset = devices[self.index].offset
        self.cancel = False
        wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_STARTING,
                                                    None, None))
        self.start()

    def run(self):
        sdr = self.rtl_setup()
        if sdr is None:
            return

        freq = self.fstart - self.offset
        while freq <= self.fstop + self.offset:
            if self.cancel:
                wx.PostEvent(self.notify,
                             EventThreadStatus(THREAD_STATUS_STOPPED,
                                               None, None))
                sdr.close()
                return
            try:
                progress = ((freq - self.fstart + self.offset) /
                             (self.fstop - self.fstart + BANDWIDTH)) * 100
                wx.PostEvent(self.notify,
                             EventThreadStatus(THREAD_STATUS_SCAN,
                                               None, progress))
                scan = self.scan(sdr, freq)
                wx.PostEvent(self.notify,
                             EventThreadStatus(THREAD_STATUS_DATA, freq,
                                               scan))
            except (IOError, WindowsError):
                if sdr is not None:
                    sdr.close()
                sdr = self.rtl_setup()
            except (TypeError, AttributeError) as error:
                if self.notify:
                    wx.PostEvent(self.notify,
                             EventThreadStatus(THREAD_STATUS_ERROR,
                                               None, error.message))
                return

            freq += BANDWIDTH / 2

        sdr.close()
        wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_FINISHED,
                                                    None, self.isCal))

    def abort(self):
        self.cancel = True

    def rtl_setup(self):
        sdr = None
        try:
            sdr = rtlsdr.RtlSdr(self.index)
            sdr.set_sample_rate(SAMPLE_RATE)
            sdr.set_gain(self.gain)
        except IOError as error:
            wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_ERROR,
                                                        None, error.message))

        return sdr

    def scan(self, sdr, freq):
        sdr.set_center_freq(freq + self.lo)
        capture = sdr.read_samples(self.samples)

        return capture


class ThreadProcess(threading.Thread):
    def __init__(self, notify, freq, data, settings, devices, nfft):
        threading.Thread.__init__(self)
        self.notify = notify
        self.freq = freq
        self.data = data
        self.cal = devices[settings.index].calibration
        self.nfft = nfft
        self.window = matplotlib.numpy.hamming(nfft)

        self.start()

    def run(self):
        scan = {}
        powers, freqs = matplotlib.mlab.psd(self.data,
                         NFFT=self.nfft,
                         Fs=SAMPLE_RATE / 1e6,
                         window=self.window)
        for freq, pwr in itertools.izip(freqs, powers):
            xr = freq + (self.freq / 1e6)
            xr = xr + (xr * self.cal / 1e6)
            xr = int((xr * 5e4) + 0.5) / 5e4
            scan[xr] = pwr
        wx.PostEvent(self.notify, EventThreadStatus(THREAD_STATUS_PROCESSED,
                                                            self.freq, scan))
