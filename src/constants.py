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

F_MIN = 0
F_MAX = 9999
GAIN = 0
SAMPLE_RATE = 2e6
BANDWIDTH = 500e3

THREAD_STATUS_STARTING = 0
THREAD_STATUS_SCAN = 1
THREAD_STATUS_DATA = 2
THREAD_STATUS_FINISHED = 3
THREAD_STATUS_STOPPED = 4
THREAD_STATUS_ERROR = 5
THREAD_STATUS_PROCESSED = 6
THREAD_STATUS_PLOTTED = 7

WARN_SCAN = 0
WARN_OPEN = 1
WARN_EXIT = 2

CAL_START = 0
CAL_DONE = 1
CAL_OK = 2
CAL_CANCEL = 3

FILE_RFS = "RTLSDR frequency scan (*.rfs)|*.rfs"
FILE_CSV = "CSV table (*.csv)|*.csv"
FILE_HEADER = "RTLSDR Scanner"
FILE_VERSION = 1
