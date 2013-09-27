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

from matplotlib.ticker import ScalarFormatter, AutoMinorLocator


def setup_plot(graph, settings, grid):
    axes = graph.get_axes()
    if len(settings.devices) > 0:
        gain = settings.devices[settings.index].gain
    else:
        gain = 0
    formatter = ScalarFormatter(useOffset=False)

    axes.set_title("Frequency Scan\n{0} - {1} MHz,"
                   " gain = {2}".format(settings.start,
                                        settings.stop, gain))
    axes.set_xlabel("Frequency (MHz)")
    axes.set_ylabel('Level (dB)')
    axes.xaxis.set_major_formatter(formatter)
    axes.yaxis.set_major_formatter(formatter)
    axes.xaxis.set_minor_locator(AutoMinorLocator(10))
    axes.yaxis.set_minor_locator(AutoMinorLocator(10))
    axes.grid(grid)


def scale_plot(graph, settings, updateScale=False):
    axes = graph.get_axes()
    if settings.autoScale:
        axes.set_ylim(auto=True)
        axes.set_xlim(auto=True)
        settings.yMin, settings.yMax = axes.get_ylim()
    else:
        axes.set_ylim(auto=False)
        axes.set_xlim(auto=False)
        if updateScale:
            if settings.yMin == settings.yMax:
                settings.yMax += 1
            axes.set_ylim(settings.yMin, settings.yMax)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
