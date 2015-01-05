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


import os
import re

from pip._vendor import requests


def __load_nsis():
    files = [f for f in os.listdir('.') if os.path.isfile(f)]
    files = [f for f in files if os.path.splitext(f)[1] == '.nsi' ]

    return files[0]


def __find_urls(nsis):
    rePath = re.compile('StrCpy \$UriPath \"(http[s]{0,1}.*?)\".*?StrCpy \$UriFile \"(.*?)\"',
                        re.DOTALL | re.MULTILINE)
    reInetc = re.compile('inetc::get \"(http[s]{0,1}.+?)\"', re.MULTILINE)

    f = open(nsis, 'r')
    data = f.read()
    matchPath = rePath.findall(data)
    urlsPath = [f + '/' + p for f, p in matchPath]
    urlsInetc = reInetc.findall(data)
    urlsPath.extend(urlsInetc)

    return urlsPath


def __test_urls(urls):
    ok = True

    for url in urls:
        request = requests.head(url)
        ok &= request.ok
        print '{} - {} - {}'.format(request.ok,
                                    url,
                                    request.status_code)

    if ok:
        print 'Passed'
    else:
        print 'Failed'


if __name__ == '__main__':
    print 'Testing installer URLs\n'

    nsis = __load_nsis()
    urls = __find_urls(nsis)
    __test_urls(urls)
