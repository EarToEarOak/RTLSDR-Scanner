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

import wx

from main_window import FrameMain


class RtlsdrScanner(wx.App):
    def __init__(self, pool):
        self.pool = pool
        wx.App.__init__(self, redirect=False)


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="update_plot filename", nargs='?')
    args = parser.parse_args()

    filename = None
    directory = None
    if args.file != None:
        directory, filename = os.path.split(args.file)

    return directory, filename


if __name__ == '__main__':
    multiprocessing.freeze_support()
    pool = multiprocessing.Pool()
    app = RtlsdrScanner(pool)
    frame = FrameMain("RTLSDR Scanner", pool)
    directory, filename = arguments()

    if filename != None:
        frame.open(directory, filename)
    app.MainLoop()
