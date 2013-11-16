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

import Queue
import os
import sys
from urlparse import urlparse

from constants import SAMPLE_RATE
from devices import Device, get_devices
from events import Event
from misc import next_2_to_pow, nearest, calc_real_dwell
from plot import save_plot, export_plot
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

        self.stepsTotal = 0
        self.steps = 0

        self.spectrum = {}
        self.settings = Settings(load=False)

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
        self.settings.dwell = calc_real_dwell(dwell)
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
            save_plot(directory, filename, self.settings, self.spectrum)
        else:
            export_plot(directory, filename, self.spectrum)

        print "Done"

    def scan(self, settings, index, pool):
        queue = Queue.Queue()
        samples = settings.dwell * SAMPLE_RATE
        samples = next_2_to_pow(int(samples))
        threadScan = ThreadScan(queue, settings, index, samples, False)
        while threadScan.isAlive():
            if not queue.empty():
                self.process_event(queue, pool)
        print ""

    def process_event(self, queue, pool):
        event = queue.get()
        status = event.data.get_status()
        freq = event.data.get_freq()
        data = event.data.get_data()

        if status == Event.STARTING:
            print "Starting"
        elif status == Event.STEPS:
            self.stepsTotal = freq * 2
            self.steps = self.stepsTotal
        elif status == Event.DATA:
            pool.apply_async(anaylse_data, (freq, data, 0, self.settings.nfft),
                             callback=self.on_process_done)
            self.progress()
        elif status == Event.ERROR:
            print "Error: {0}".format(data)
            exit(1)

    def on_process_done(self, data):
        freq, scan = data
        offset = self.settings.devices[self.settings.index].offset
        update_spectrum(self.settings.start, self.settings.stop, freq, scan,
                        offset, self.spectrum)
        self.progress()

    def progress(self):
        self.steps -= 1
        comp = (self.stepsTotal - self.steps) * 100 / self.stepsTotal
        sys.stdout.write("\r{0:.1f}%".format(comp))


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
