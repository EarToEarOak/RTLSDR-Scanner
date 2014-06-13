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

import Queue

import wx


EVENT_THREAD = wx.NewId()


class Event:
    STARTING, STEPS, INFO, DATA, CAL, STOPPED, ERROR, FINISHED, PROCESSED, \
    LEVEL, UPDATED, DRAW, PLOTTED, PLOTTED_FULL, VER_UPD, VER_NOUPD, \
    VER_UPDFAIL, LOC, LOC_RAW, LOC_WARN, LOC_ERR, LOC_SAT = range(22)


class Status():
    def __init__(self, status, arg1, arg2):
        self.status = status
        self.arg1 = arg1
        self.arg2 = arg2

    def get_status(self):
        return self.status

    def get_arg1(self):
        return self.arg1

    def get_arg2(self):
        return self.arg2


class EventThread(wx.PyEvent):
    def __init__(self, status, arg1=None, arg2=None):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVENT_THREAD)
        self.data = Status(status, arg1, arg2)


def post_event(destination, status):
    if isinstance(destination, Queue.Queue):
        destination.put(status)
    elif isinstance(destination, wx.EvtHandler):
        wx.PostEvent(destination, status)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
