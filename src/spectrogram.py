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


class Spectrogram:
    def __init__(self, notify, graph, settings, lock):
        self.notify = notify
        self.settings = settings
        self.graph = graph
        self.lock = lock
        self.setup_plot()

    def setup_plot(self):
#         TODO:
        pass

    def scale_plot(self):
        pass

    def redraw(self):
#         TODO:
        pass

    def set_plot(self, plot):
#         TODO:
        pass

    def new_plot(self):
#         TODO:
        pass

    def annotate_plot(self):
        pass

    def clear_plots(self):
#         TODO:
        pass

    def set_grid(self, on):
        pass


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
