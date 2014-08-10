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
import datetime
import time

from matplotlib import cm
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.dates import date2num, AutoDateLocator, AutoDateFormatter, \
    DateFormatter, MinuteLocator, num2date, DayLocator


def add_colours():
    r = {'red':     ((0.0, 1.0, 1.0),
                     (1.0, 1.0, 1.0)),
         'green':   ((0.0, 0.0, 0.0),
                     (1.0, 0.0, 0.0)),
         'blue':   ((0.0, 0.0, 0.0),
                    (1.0, 0.0, 0.0))}
    g = {'red':     ((0.0, 0.0, 0.0),
                     (1.0, 0.0, 0.0)),
         'green':   ((0.0, 1.0, 1.0),
                     (1.0, 1.0, 1.0)),
         'blue':    ((0.0, 0.0, 0.0),
                     (1.0, 0.0, 0.0))}
    b = {'red':     ((0.0, 0.0, 0.0),
                     (1.0, 0.0, 0.0)),
         'green':   ((0.0, 0.0, 0.0),
                     (1.0, 0.0, 0.0)),
         'blue':    ((0.0, 1.0, 1.0),
                     (1.0, 1.0, 1.0))}

    rMap = LinearSegmentedColormap('red_map', r)
    gMap = LinearSegmentedColormap('red_map', g)
    bMap = LinearSegmentedColormap('red_map', b)
    cm.register_cmap(name=' Pure Red', cmap=rMap)
    cm.register_cmap(name=' Pure Green', cmap=gMap)
    cm.register_cmap(name=' Pure Blue', cmap=bMap)


def get_colours():
    colours = [colour for colour in cm.cmap_d]
    colours.sort()

    return colours


def find_artists(figure, gid):
    return figure.findobj(lambda x: x.get_gid() == gid)


def set_table_colour(table, colour):
    for _loc, cell in table.get_celld().items():
        cell.set_edgecolor(colour)


def utc_to_mpl(utc):
    local = time.mktime(time.localtime(utc))
    dt = datetime.datetime.fromtimestamp(local)
    return date2num(dt)


def set_date_ticks(axis, auto=True):
    axis.axis_date()
    if auto:
        timeLocator = AutoDateLocator()
        timeFormatter = AutoDateFormatter(timeLocator)
        timeFormatter.scaled[1. / (24. * 60.)] = '%H:%M:%S'
        timeFormatter.scaled[1. / (24. * 60. * 1000.)] = '%H:%M:%S.%f'
    else:
        timeFormatter = DateFormatter("%H:%M:%S")
        timeLocator = MinuteLocator()

    axis.set_major_locator(timeLocator)
    axis.set_major_formatter(timeFormatter)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
