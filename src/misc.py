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

import cPickle
import os

from matplotlib.ticker import AutoMinorLocator
import wx

from constants import FILE_HEADER


def setup_plot(graph, settings, grid):
        axes = graph.get_axes()
        gain = settings.devices[settings.index].gain

        axes.set_title("Frequency Scan\n{0} - {1} MHz,"
                       " gain = {2}".format(settings.start,
                                            settings.stop, gain))
        axes.set_xlabel("Frequency (MHz)")
        axes.set_ylabel('Level (dB)')
        axes.xaxis.set_minor_locator(AutoMinorLocator(10))
        axes.yaxis.set_minor_locator(AutoMinorLocator(10))
        axes.grid(grid)


def scale_plot(graph, settings):
        axes = graph.get_axes()
        axes.set_xlim(settings.start, settings.stop)
        if(settings.yAuto):
            axes.set_ylim(auto=True)
            settings.yMin, settings.yMax = axes.get_ylim()
        else:
            axes.set_ylim(settings.yMin, settings.yMax)


def open_plot(dirname, filename):
    try:
        handle = open(os.path.join(dirname, filename), 'rb')
        header = cPickle.load(handle)
        if header != FILE_HEADER:
            wx.MessageBox('Invalid or corrupted file', 'Warning',
                      wx.OK | wx.ICON_WARNING)
            return
        _version = cPickle.load(handle)
        start = cPickle.load(handle)
        stop = cPickle.load(handle)
        spectrum = cPickle.load(handle)
    except:
        wx.MessageBox('File could not be opened', 'Warning',
                      wx.OK | wx.ICON_WARNING)

    return start, stop, spectrum


def split_spectrum(spectrum):
    freqs = spectrum.keys()
    freqs.sort()
    powers = map(spectrum.get, freqs)

    return freqs, powers


def format_device_name(name):
    remove = ["/", "\\"]
    for char in remove:
        name = name.replace(char, " ")

    return name
