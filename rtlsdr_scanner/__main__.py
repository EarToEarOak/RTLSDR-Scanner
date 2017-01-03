#! /usr/bin/env python
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

try:
    input = raw_input
except:
    pass

try:
    import matplotlib
    matplotlib.interactive(True)
    matplotlib.use('WXAgg')
    import rtlsdr  # @UnusedImport
    import wx  # @UnusedImport
except ImportError as error:
    print 'Import error: {}'.format(error)
    input('\nError importing libraries\nPress [Return] to exit')
    exit(1)

import argparse
import os.path
import signal
import sys

from rtlsdr_scanner.cli import Cli
from rtlsdr_scanner.constants import APP_NAME
from rtlsdr_scanner.file import File
from rtlsdr_scanner.main_window import FrameMain, RtlSdrScanner

if not hasattr(sys, 'frozen'):
    try:
        import visvis as vv
        vv.use('wx')
    except ImportError:
        pass


def __init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def __arguments():
    parser = argparse.ArgumentParser(prog="rtlsdr_scan.py",
                                     description='''
                                        Scan a range of frequencies and
                                        save the results to a file''')
    parser.add_argument("-s", "--start", help="Start frequency (MHz)",
                        type=int)
    parser.add_argument("-e", "--end", help="End frequency (MHz)", type=int)
    parser.add_argument("-w", "--sweeps", help="Number of sweeps", type=int,
                        default=1)
    parser.add_argument("-p", "--delay", help="Delay between sweeps (s)",
                        type=int, default=0)
    parser.add_argument("-g", "--gain", help="Gain (dB)", type=float, default=0)
    parser.add_argument("-d", "--dwell", help="Dwell time (seconds)",
                        type=float, default=0.1)
    parser.add_argument("-f", "--fft", help="FFT bins", type=int, default=1024)
    parser.add_argument("-l", "--lo", help="Local oscillator offset",
                        type=int, default=0)
    parser.add_argument("-c", "--conf", help="Load a config file",
                        default=None)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-i", "--index", help="Device index (from 0)", type=int,
                       default=0)
    group.add_argument("-r", "--remote", help="Server IP and port", type=str)
    types = File.get_type_pretty(File.Types.SAVE)
    types += File.get_type_pretty(File.Types.PLOT)
    help = 'Output file (' + types + ')'
    parser.add_argument("file", help=help, nargs='?')
    args = parser.parse_args()

    error = None
    isGui = True
    if args.start is not None or args.end is not None:
        if args.start is not None:
            if args.end is not None:
                if args.file is not None:
                    isGui = False
                else:
                    error = "No filename specified"
            else:
                error = "No end frequency specified"
        else:
            error = "No start frequency specified"
    elif args.file is not None:
        args.dirname, args.filename = os.path.split(args.file)

    if error is not None:
        print "Error: {}".format(error)
        parser.exit(1)

    return isGui, (args)


if __name__ == '__main__':
    print APP_NAME + "\n"

    isGui, args = __arguments()
    if isGui:
        app = RtlSdrScanner()
        app.SetClassName(APP_NAME)
        wx.Locale().Init2()
        frame = FrameMain(APP_NAME)
        if args.file is not None:
            frame.open(os.path.abspath(args.dirname), args.filename)
        app.MainLoop()
    else:
        try:
            Cli(args)
        except KeyboardInterrupt:
            print '\nAborted'
            exit(1)
