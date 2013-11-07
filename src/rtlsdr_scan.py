#! /usr/bin/env python
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


import argparse
import multiprocessing
import os.path

from cli import Cli
from main_window import FrameMain, RtlSdrScanner


def arguments():
    parser = argparse.ArgumentParser(prog="rtlsdr_scan.py",
                                     description='''
                                        Scan a range of frequencies and
                                        save the results to a file''')
    parser.add_argument("-s", "--start", help="Start frequency (MHz)",
                        type=int)
    parser.add_argument("-e", "--end", help="End frequency (MHz)", type=int)
    parser.add_argument("-g", "--gain", help="Gain (dB)", type=int, default=0)
    parser.add_argument("-d", "--dwell", help="Dwell time (seconds)",
                        type=float, default=0.1)
    parser.add_argument("-f", "--fft", help="FFT bins", type=int, default=1024)
    parser.add_argument("-l", "--lo", help="Local oscillator offset", type=int,
                        default=0)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-i", "--index", help="Device index (from 0)", type=int,
                       default=0)
    group.add_argument("-r", "--remote", help="Server IP and port", type=str)
    parser.add_argument("file", help="Input file (.rfs) or output file (.rfs or .cvs) when scanning",
                        nargs='?')
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
        print "Error: {0}".format(error)
        parser.exit(1)

    return isGui, (args)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    pool = multiprocessing.Pool()
    print "RTLSDR Scanner\n"
    isGui, args = arguments()
    if isGui:
        app = RtlSdrScanner(pool)
        frame = FrameMain("RTLSDR Scanner", pool)
        if args.file is not None:
            frame.open(args.dirname, args.filename)
        app.MainLoop()
    else:
        Cli(pool, args)
