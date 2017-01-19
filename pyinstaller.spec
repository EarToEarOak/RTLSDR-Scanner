#
# rtlsdr_scan
#
# http://eartoearoak.com/software/rtlsdr-scanner
#
# Copyright 2012, 2015 Al Brown
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
import platform
import sys

from PIL import Image
from PyInstaller import compat
from PyInstaller.utils.win32 import versioninfo
import pkg_resources


def create_version():
    search = os.path.join(os.getcwd(), 'rtlsdr_scanner')
    sys.path.append(search)
    from version import VERSION
    version = VERSION
    version.append(0)

    ffi = versioninfo.FixedFileInfo(filevers=VERSION,
                                    prodvers=VERSION)

    strings = []
    strings.append(versioninfo.StringStruct('ProductName',
                                            'RTLSDR Scanner'))
    strings.append(versioninfo.StringStruct('FileDescription',
                                            'Spectrum Analyser'))
    strings.append(versioninfo.StringStruct('LegalCopyright',
                                            'Copyright 2012 - 2017 Al Brown'))
    table = versioninfo.StringTable('040904B0', strings)
    sInfo = versioninfo.StringFileInfo([table])
    var = versioninfo.VarStruct('Translation', [2057, 1200])
    vInfo = versioninfo.VarFileInfo([var])
    vvi = versioninfo.VSVersionInfo(ffi, [sInfo, vInfo])

    f = open('version.txt', 'w')
    f.write(vvi.__unicode__())
    f.close()

    print 'Version: {}.{}.{}.{}'.format (vvi.ffi.fileVersionMS >> 16,
                                         vvi.ffi.fileVersionMS & 0xffff,
                                         vvi.ffi.fileVersionLS >> 16,
                                         vvi.ffi.fileVersionLS & 0xFFFF)

def build(version=None):
    architecture, _null = platform.architecture()
    filename = 'rtlsdr_scan-' + system + '-' + architecture.lower()

    excludes = ['PySide', 'qt', 'scipy']
    a = Analysis(['rtlsdr_scanner/__main__.py'],
                excludes=excludes)

    a.datas += Tree('rtlsdr_scanner/res', prefix='res')

    pyz = PYZ(a.pure)

    image = Image.open('rtlsdr_scanner/res/icon.png')
    image.save('icon.ico')

    exe = EXE(pyz,
              a.scripts + [('O', '', 'OPTION')],
              a.binaries,
              a.zipfiles,
              a.datas,
              name=os.path.join('dist', filename),
              icon='icon.ico',
              version=version,
              upx=True)

    os.remove('icon.ico')


system = platform.system().lower()
if system == 'windows':
    create_version()
    build('version.txt')
    os.remove('version.txt')
else:
    build()
