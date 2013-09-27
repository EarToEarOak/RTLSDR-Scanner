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

import itertools

import matplotlib

from constants import SAMPLE_RATE


def process_data(freq, data, cal, nfft):
    scan = {}
    window = matplotlib.numpy.hamming(nfft)
    powers, freqs = matplotlib.mlab.psd(data,
                     NFFT=nfft,
                     Fs=SAMPLE_RATE / 1e6,
                     window=window)
    for freqPsd, pwr in itertools.izip(freqs, powers):
        xr = freqPsd + (freq / 1e6)
        xr = xr + (xr * cal / 1e6)
        xr = int((xr * 5e4) + 0.5) / 5e4
        scan[xr] = pwr

    return (freq, scan)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
