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

import Queue
from collections import OrderedDict
import os
import sys
from threading import Thread
import threading
import time
from urlparse import urlparse

from rtlsdr_scanner.constants import SAMPLE_RATE
from rtlsdr_scanner.devices import DeviceRTL, get_devices_rtl
from rtlsdr_scanner.events import Event
from rtlsdr_scanner.file import save_plot, export_plot, ScanInfo, File
from rtlsdr_scanner.location import ThreadLocation
from rtlsdr_scanner.misc import nearest, calc_real_dwell, next_2_to_pow, get_dwells
from rtlsdr_scanner.scan import ThreadScan, update_spectrum, ThreadProcess
from rtlsdr_scanner.settings import Settings


class Cli(object):
    def __init__(self, args):
        start = args.start
        end = args.end
        sweeps = args.sweeps
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

        self.spectrum = OrderedDict()
        self.locations = OrderedDict()
        self.settings = Settings(load=False)

        self.queueNotify = Queue.Queue()
        self.queueScan = Queue.Queue()
        self.queueLocation = Queue.Queue()

        self.threadLocation = None

        error = None

        if end <= start:
            error = "Start should be lower than end"
        elif dwell <= 0:
            error = "Dwell should be positive"
        elif dwell > max(get_dwells()[1::2]):
            error = "Dwell should equal lower than {}s".format(max(get_dwells()[1::2]))
        elif nfft <= 0:
            error = "FFT bins should be positive"
        elif ext != ".rfs" and File.get_type_index(ext) == -1:
            error = "File extension should be "
            error += File.get_type_pretty(File.Types.SAVE)
            error += File.get_type_pretty(File.Types.PLOT)
        else:
            device = DeviceRTL()
            if remote is None:
                self.settings.devicesRtl = get_devices_rtl()
                count = len(self.settings.devicesRtl)
                if index > count - 1:
                    error = "Device not found ({} devices in total):\n".format(count)
                    for device in self.settings.devicesRtl:
                        error += "\t{}: {}\n".format(device.indexRtl,
                                                     device.name)
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
                self.settings.devicesRtl.append(device)
                index = len(self.settings.devicesRtl) - 1

            if args.conf is not None:
                if os.path.exists(args.conf):
                    error = self.settings.load_conf(args.conf)
                    if error is not None:
                        error = 'GPS configuration - ' + error
                else:
                    error = 'Cannot find {}'.format(args.conf)

            if end - 1 < start:
                end = start + 1
            if remote is None:
                if len(self.settings.devicesRtl):
                    gain = nearest(gain, self.settings.devicesRtl[index].gains)
                else:
                    error = 'No devices found'

        if error is not None:
            print "Error: {}".format(error)
            exit(1)

        self.settings.start = start
        self.settings.stop = end
        self.settings.dwell = calc_real_dwell(dwell)
        self.settings.scanDelay = args.delay
        self.settings.nfft = nfft
        self.settings.devicesRtl[index].gain = gain
        self.settings.devicesRtl[index].lo = lo

        print "{} - {}MHz".format(start, end)
        print "{} Sweeps".format(sweeps)
        print "{}dB Gain".format(gain)
        print "{}s Dwell".format(self.settings.dwell)
        print "{} FFT points".format(nfft)
        print "{}MHz LO".format(lo)
        if remote is not None:
            print remote
        else:
            print self.settings.devicesRtl[index].name

        if len(self.settings.devicesGps):
            print 'Using GPS configuration \'{}\''.format(self.settings.devicesGps[0].name)
            self.threadLocation = ThreadLocation(self.queueLocation,
                                                 self.settings.devicesGps[0])
            if not self.__gps_wait():
                self.__gps_stop()
                exit(1)

        self.__scan(sweeps, self.settings, index)

        fullName = os.path.join(directory, filename)
        if ext == ".rfs":
            scanInfo = ScanInfo()
            scanInfo.set_from_settings(self.settings)

            save_plot(fullName, scanInfo, self.spectrum, self.locations)
        else:
            exportType = File.get_type_index(ext)
            export_plot(fullName, exportType, self.spectrum)

        self.__gps_stop()
        print "Done"

    def __gps_wait(self):
        print '\nWaiting for GPS fix: {}'.format(self.settings.devicesGps[0].get_desc())

        while True:
            if not self.queueLocation.empty():
                status = self.__process_event(self.queueLocation)
                if status == Event.LOC:
                    return True
                elif status == Event.LOC_ERR:
                    return False

    def __gps_stop(self):
        if self.threadLocation and self.threadLocation.isAlive():
            self.threadLocation.stop()

    def __scan(self, sweeps, settings, index):
        samples = settings.dwell * SAMPLE_RATE
        samples = next_2_to_pow(int(samples))

        for sweep in range(0, sweeps):
            print '\nSweep {}:'.format(sweep + 1)
            threadScan = ThreadScan(self.queueNotify, self.queueScan, None,
                                    settings, index, samples, False)
            while threadScan.isAlive() or self.steps > 0:
                if not self.queueNotify.empty():
                    self.__process_event(self.queueNotify)
                if not self.queueLocation.empty():
                    self.__process_event(self.queueLocation)
            if self.settings.scanDelay > 0 and sweep < sweeps - 1:
                print '\nDelaying {}s'.format(self.settings.scanDelay)
                time.sleep(self.settings.scanDelay)
            threadScan.rtl_close()
            print ""
        print ""

    def __process_event(self, queue):
        event = queue.get()
        status = event.data.get_status()
        arg1 = event.data.get_arg1()
        arg2 = event.data.get_arg2()

        if status == Event.STARTING:
            print "Starting"
        elif status == Event.STEPS:
            self.stepsTotal = (arg1 + 1) * 2
            self.steps = self.stepsTotal
        elif status == Event.INFO:
            if arg2 != -1:
                self.settings.devicesRtl[self.settings.indexRtl].tuner = arg2
        elif status == Event.DATA:
            cal = self.settings.devicesRtl[self.settings.indexRtl].calibration
            levelOff = self.settings.devicesRtl[self.settings.indexRtl].levelOff
            freq, scan = self.queueScan.get()
            process = ThreadProcess(self.queueNotify,
                                    freq, scan, cal, levelOff,
                                    self.settings.nfft,
                                    self.settings.overlap,
                                    self.settings.winFunc)
            process.start()
            self.__progress()
        elif status == Event.ERROR:
            print "Error: {}".format(arg2)
            exit(1)
        elif status == Event.PROCESSED:
            offset = self.settings.devicesRtl[self.settings.indexRtl].offset
            Thread(target=update_spectrum, name='Update',
                   args=(self.queueNotify, self.lock,
                         self.settings.start,
                         self.settings.stop,
                         arg1,
                         offset,
                         self.spectrum,
                         not self.settings.retainScans,
                         False)).start()
        elif status == Event.UPDATED:
            self.__progress()
        elif status == Event.LOC:
            if len(self.spectrum) > 0:
                self.locations[max(self.spectrum)] = (arg2[0],
                                                      arg2[1],
                                                      arg2[2])
        elif status == Event.LOC_ERR:
            print 'Error: {}'.format(arg2)
            exit(1)

        return status

    def __progress(self):
        self.steps -= 1
        comp = (self.stepsTotal - self.steps) * 100 / self.stepsTotal
        sys.stdout.write("\r{0:.1f}%".format(comp))


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
