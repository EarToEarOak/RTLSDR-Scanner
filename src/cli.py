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

import os
import sys
from threading import Thread
import threading
from urlparse import urlparse

from devices import Device, get_devices
from events import *
from misc import ScanInfo, save_plot, export_plot, nearest
from scan import ThreadScan, anaylse_data, update_spectrum
from settings import Settings


class Cli():
    def __init__(self, pool, args):
        start = args.start
        end = args.end
        gain = args.gain
        dwell = args.dwell
        nfft = args.fft
        lo = args.lo
        index = args.index
        remote = args.remote
        directory, filename = os.path.split(args.file)
        _null, ext = os.path.splitext(args.file)

        self.lock = threading.Lock()

        self.stepsTotal = 0
        self.steps = 0

        self.spectrum = {}
        self.settings = Settings(load=False)

        self.queue = Queue.Queue()

        error = None

        if end <= start:
            error = "Start should be lower than end"
        elif dwell <= 0:
            error = "Dwell should be positive"
        elif nfft <= 0:
            error = "FFT bins should be positive"
        elif ext != ".rfs" and ext != ".csv":
            error = "File extension should be .rfs or .csv"
        else:
            device = Device()
            if remote is None:
                self.settings.devices = get_devices()
                count = len(self.settings.devices)
                if index > count - 1:
                    error = "Device not found ({0} devices in total):\n".format(count)
                    for device in self.settings.devices:
                        error += "\t{0}: {1}\n".format(device.index, device.name)
            else:
                device.isDevice = False
                url = urlparse('//' + remote)
                if url.hostname is not None:
                        device.server = url.hostname
                else:
                    error = "Invalid hostname"
                if url.port is not None:
                    device.port = url.port
                else:
                    device.port = 1234
                self.settings.devices.append(device)
                index = len(self.settings.devices) - 1

        if error is not None:
            print "Error: {0}".format(error)
            exit(1)

        if end - 1 < start:
            end = start + 1
        if remote is None:
            gain = nearest(gain, self.settings.devices[index].gains)

        self.settings.start = start
        self.settings.stop = end
        self.settings.dwell = dwell
        self.settings.nfft = nfft
        self.settings.devices[index].gain = gain
        self.settings.devices[index].lo = lo

        print "{0} - {1}MHz".format(start, end)
        print "{0}dB Gain".format(gain)
        print "{0}s Dwell".format(self.settings.dwell)
        print "{0} FFT points".format(nfft)
        print "{0}MHz LO".format(lo)
        if remote is not None:
            print remote
        else:
            print self.settings.devices[index].name

        self.scan(self.settings, index, pool)

        if ext == ".rfs":
            scanInfo = ScanInfo()
            scanInfo.setFromSettings(self.settings)
            save_plot(directory, filename, scanInfo, self.spectrum)
        else:
            export_plot(directory, filename, self.spectrum)

        print "Done"

    def scan(self, settings, index, pool):
        rate = settings.devices[settings.index].rate
        samples = settings.dwell * rate
        threadScan = ThreadScan(self.queue, None, settings, index, samples,
                                False)
        while threadScan.isAlive() or self.steps > 0:
            if not self.queue.empty():
                self.process_event(self.queue, pool)
        print ""

    def process_event(self, queue, pool):
        event = queue.get()
        status = event.data.get_status()
        freq = event.data.get_freq()
        data = event.data.get_data()

        if status == Event.STARTING:
            print "Starting"
        elif status == Event.STEPS:
            self.stepsTotal = (freq+1) * 2
            self.steps = self.stepsTotal
        elif status == Event.INFO:
            if data != -1:
                self.settings.devices[self.settings.index].tuner = data
        elif status == Event.DATA:
            cal = self.settings.devices[self.settings.index].calibration
            pool.apply_async(anaylse_data, (freq, data, cal,
                                            self.settings.nfft,
                                            self.settings.devices[self.settings.index].rate,
                                            "Hamming"),
                             callback=self.on_process_done)
            self.progress()
        elif status == Event.ERROR:
            print "Error: {0}".format(data)
            exit(1)
        elif status == Event.PROCESSED:
            bandwidth = self.settings.devices[self.settings.index].bandwidth
            offset = self.settings.devices[self.settings.index].offset
            Thread(target=update_spectrum, name='Update',
                   args=(queue, self.lock, self.settings.start,
                         self.settings.stop, freq,
                         data, bandwidth, offset, self.spectrum, False,)).start()
        elif status == Event.UPDATED:
            self.progress()

    def on_process_done(self, data):
        timeStamp, freq, scan = data
        post_event(self.queue, EventThreadStatus(Event.PROCESSED, freq,
                                                 (timeStamp, scan)))

    def progress(self):
        self.steps -= 1
        comp = (self.stepsTotal - self.steps) * 100 / self.stepsTotal
        sys.stdout.write("\r{0:.1f}%".format(comp))


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
