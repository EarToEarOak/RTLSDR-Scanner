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
import time

import wx


EVENT_THREAD = wx.NewId()


class Event(object):
    STARTING, STEPS, INFO, DATA, STOPPED, ERROR, FINISHED, PROCESSED, \
        CAL, LEVEL, UPDATED, DRAW, \
        DELAY_COUNT, DELAY_START, \
        LOC, LOC_RAW, LOC_WARN, LOC_ERR, LOC_SAT = range(19)


class Status(object):
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


class EventTimer(wx.Timer):
    def __init__(self, parent, delay,
                 eventCount=Event.DELAY_COUNT, eventStart=Event.DELAY_START):
        wx.Timer.__init__(self)
        self.parent = parent
        self.delay = delay
        self.count = delay
        self.eventCount = eventCount
        self.eventStart = eventStart

        self.Start(1000)
        post_event(parent,
                   EventThread(self.eventCount, self.delay, self.count))

    def Notify(self):
        self.count -= 1
        post_event(self.parent,
                   EventThread(self.eventCount, self.delay, self.count))
        if self.count == 0:
            self.Stop()
            post_event(self.parent,
                       EventThread(self.eventStart))


class Log(object):
    MAX_ENTRIES = 50

    INFO, WARN, ERROR = range(3)
    TEXT_LEVEL = ['Info', 'Warn', 'Error']

    def __init__(self):
        self.log = []

    def add(self, text, level=None):
        if level is None:
            return
        entry = [time.time(), level, text]
        self.log.append(entry)

        while len(self.log) > self.MAX_ENTRIES:
            self.log.pop(0)

    def get(self, level):
        if level is None:
            return self.log

        filtered = []
        for entry in self.log:
            if entry[1] == level:
                filtered.append(entry)

        return filtered


def post_event(destination, status):
    if isinstance(destination, Queue.Queue):
        destination.put(status)
    elif isinstance(destination, wx.EvtHandler):
        wx.PostEvent(destination, status)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
