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

import platform

import PyInstaller.utils.versioninfo


def create_version():
    f = open('src/version-timestamp', 'r')
    timeStamp = int(f.read())
    f.close()

    version = (1, 0, 0, 0)
    ffi = versioninfo.FixedFileInfo(filevers=version,
                                    prodvers=version,
                                    date=(0, timeStamp))
    ffi.fileVersionLS = timeStamp
    ffi.productVersionLS = timeStamp

    strings = []
    strings.append(versioninfo.StringStruct('ProductName',
                                            'RTLSDR Scanner'))
    strings.append(versioninfo.StringStruct('FileDescription',
                                            'Spectrum Analyser'))
    strings.append(versioninfo.StringStruct('LegalCopyright',
                                            'Copyright 2012 - 2015 Al Brown'))
    table = versioninfo.StringTable('040904B0', strings)
    sInfo = versioninfo.StringFileInfo([table])
    var = versioninfo.VarStruct('Translation', [2057, 1200])
    vInfo = versioninfo.VarFileInfo([var])
    vvi = versioninfo.VSVersionInfo(ffi, [sInfo, vInfo])

    f = open('version.txt', 'w')
    f.write(vvi.__unicode__())
    f.close()


def build():
    excludes = ['pyside', 'qt', 'scipy']
    extension = ''
    system = platform.system().lower()
    architecture, _null = platform.architecture()
    if system == 'windows':
        extension = '.exe'
    filename = 'rtlsdr_scan-' + system + '-' + architecture.lower() + extension

    a = Analysis(['src/rtlsdr_scan.py'])
    for exclude in excludes:
        a.binaries = [x for x in a.binaries
                      if not x[0].lower().startswith(exclude)]
    a.datas += Tree('res', prefix='res')
    a.datas += [('version-timestamp', 'src/version-timestamp', 'DATA')]
    a.datas += [('rtlsdr_scan.ico', 'rtlsdr_scan.ico', 'DATA')]

    pyz = PYZ(a.pure)

    exe = EXE(pyz,
              a.scripts + [('O', '', 'OPTION')],
              a.binaries,
              a.zipfiles,
              a.datas,
              name=os.path.join('dist', filename),
              icon='rtlsdr_scan.ico',
              version='version.txt',
              upx=True)


create_version()
build()
os.remove('version.txt')
