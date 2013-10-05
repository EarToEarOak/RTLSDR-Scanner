;
; rtlsdr_scan
;
; http://eartoearoak.com/software/rtlsdr-scanner
;
; Copyright 2012, 2013 Al Brown
;
; A frequency scanning GUI for the OsmoSDR rtl-sdr library at
; http://sdr.osmocom.org/trac/wiki/rtl-sdr
;
;
; This program is free software: you can redistribute it and/or modify
; it under the terms of the GNU General Public License as published by
; the Free Software Foundation, or (at your option)
; any later version.
;
; This program is distributed in the hope that it will be useful,
; but WITHOUT ANY WARRANTY; without even the implied warranty of
; MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
; GNU General Public License for more details.
;
; You should have received a copy of the GNU General Public License
; along with this program.  If not, see <http://www.gnu.org/licenses/>.
;

!include "EnvVarUpdate.nsh"
!include "LogicLib.nsh"
!include "MUI.nsh"
!include "nsDialogs.nsh"
!include "nsDialogs_createTextMultiline.nsh"

!define PRODUCT_NAME "RTLSDR Scanner"
!define PRODUCT_VERSION ""
!define PRODUCT_PUBLISHER "Ear to Ear Oak"
!define PRODUCT_WEB_SITE "http://eartoearoak.com/software/rtlsdr-scanner"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

!define MUI_ABORTWARNING
!define MUI_ICON "rtlsdr_scan.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"
!insertmacro MUI_PAGE_WELCOME
Page custom page_info
!insertmacro MUI_PAGE_LICENSE "license.txt"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

!define INFO '"This will install RTLSDR Scanner and its Python dependencies $\r$\n$\r$\n \
It will add the new installation of Python to the path, potentially causing problems $\r$\n \
to previous Python installs $\r$\n$\r$\n \
You can update to the latest versions of RTLSDR-Scanner, $\r$\n \
the rtlsdr driver and pyrtlsdr by running this installer again"'


Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "rtlsdr_scanner-setup-win32.exe"
RequestExecutionLevel admin
InstallDir "$PROGRAMFILES\RTLSDR Scanner"
ShowInstDetails show
ShowUnInstDetails show


Section "RTLSDR Scanner (Required)" SECTION1
    SetOutPath "$INSTDIR"
    SetOverwrite ifnewer
    File "license.txt"
    Call get_rtlsdr_scanner
    CreateShortCut "$STARTMENU.lnk" "$INSTDIR\rtlsdr_scan.py"
    CreateShortCut "$DESKTOP.lnk" "$INSTDIR\rtlsdr_scan.py"
SectionEnd


SectionGroup "Dependencies" SECTION2
    Section "RTLSDR Driver" SECTION3
        Call get_rtlsdr
    SectionEnd
    SectionGroup "Python"
        Section "Python 2.7.5"
           Call get_python
           Call set_installer_path
        SectionEnd
        Section "Add Python to PATH"
           Call set_python_path
        SectionEnd
        Section "wxPython 2.8.12.1"
            Call get_wxpython
        SectionEnd
        Section "matplotlib 1.3.0"
            Call get_matplotlib
        SectionEnd
        Section "numpy 1.7.1"
            Call get_numpy
        SectionEnd
        Section "pyparsing 2.0.1"
            Call get_pyparsing
        SectionEnd
        Section "setuptools 1.1.6"
            Call get_setuptools
        SectionEnd
        Section "dateutils 2.1"
            Call get_dateutil
        SectionEnd
        Section "pyrtlsdr" SECTION4
            Call get_pyrtlsdr
        SectionEnd
    SectionGroupEnd
SectionGroupEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
!insertmacro MUI_DESCRIPTION_TEXT ${SECTION1} "RTLSDR Scanner"
!insertmacro MUI_DESCRIPTION_TEXT ${SECTION2} "Dependencies"
!insertmacro MUI_DESCRIPTION_TEXT ${SECTION3} "Latest rtlsdr driver"
!insertmacro MUI_DESCRIPTION_TEXT ${SECTION4} "Latest Python wrapper for the rtlsdr driver"
!insertmacro MUI_FUNCTION_DESCRIPTION_END


Section -AdditionalIcons
    SetOutPath "$INSTDIR"
    WriteIniStr "$INSTDIR\${PRODUCT_NAME}.url" "InternetShortcut" "URL" "${PRODUCT_WEB_SITE}"
    CreateDirectory "$SMPROGRAMS\RTLSDR Scanner"
    CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\RTLSDR Scanner.lnk" "python" '"$INSTDIR\rtlsdr_scan.py"' "$INSTDIR\rtlsdr_scan.ico" 0
    CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\Website.lnk" "$INSTDIR\${PRODUCT_NAME}.url"
    CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\Uninstall.lnk" "$INSTDIR\uninst.exe"
SectionEnd


Section -Post
    WriteUninstaller "$INSTDIR\uninst.exe"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
SectionEnd


Section Uninstall
    Delete "$INSTDIR\${PRODUCT_NAME}.url"
    Delete "$INSTDIR\rtlsdr_scan.ico"
    Delete "$INSTDIR\uninst.exe"
    Delete "$INSTDIR\license.txt"
    Delete "$INSTDIR\windows.py"
    Delete "$INSTDIR\threads.py"
    Delete "$INSTDIR\settings.py"
    Delete "$INSTDIR\scan.py"
    Delete "$INSTDIR\rtltcp.py"
    Delete "$INSTDIR\rtlsdr_scan_diag.py"
    Delete "$INSTDIR\rtlsdr_scan.py"
    Delete "$INSTDIR\plot.py"
    Delete "$INSTDIR\misc.py"
    Delete "$INSTDIR\events.py"
    Delete "$INSTDIR\constants.py"

    Delete "$SMPROGRAMS\RTLSDR Scanner\Uninstall.lnk"
    Delete "$SMPROGRAMS\RTLSDR Scanner\Website.lnk"
    Delete "$SMPROGRAMS\RTLSDR Scanner\RTLSDR Scanner.lnk"

    RMDir "$SMPROGRAMS\RTLSDR Scanner"
    RMDir "$INSTDIR"

    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
    SetAutoClose true
SectionEnd


Var Page
Var Text

Function .onInit
    IntOp $0 ${SF_SELECTED} | ${SF_RO}
    IntOp $0 $0 | ${SF_BOLD}
    SectionSetFlags ${SECTION1} $0
FunctionEnd

Function page_info
    !insertmacro MUI_HEADER_TEXT "Information" "Please read before continuing"
    nsDialogs::Create 1018
    Pop $Page
    ${If} $Page == error
        Abort
    ${EndIf}
    ${NSD_CreateTextMultiline} 0 0% 100% 100% ${INFO}
    Pop $Text
    SendMessage $Text ${EM_SETREADONLY} 1 0
    nsDialogs::Show
FunctionEnd

Function get_rtlsdr_scanner
    inetc::get "https://github.com/EarToEarOak/RTLSDR-Scanner/archive/master.zip" "$TEMP\rtlsdr_scanner.zip" /end
    Pop $R0
    StrCmp $R0 "OK" exists
    MessageBox MB_OK "RTLSDR Scanner download failed: $R0"
    return
    exists:
    ZipDLL::extractall "$TEMP\rtlsdr_scanner.zip" "$TEMP"
    CopyFiles "$TEMP\RTLSDR-Scanner-master\src\*.py" "$INSTDIR"
    CopyFiles "$TEMP\RTLSDR-Scanner-master\*.ico" "$INSTDIR"
    ;Delete "$TEMP\pyrtlsdr.zip"
    RmDir /r "$TEMP\RTLSDR-Scanner-master"
FunctionEnd

Function get_rtlsdr
    inetc::get "http://sdr.osmocom.org/trac/raw-attachment/wiki/rtl-sdr/RelWithDebInfo.zip" "$TEMP\rtlsdr.zip" /end
    Pop $R0
    StrCmp $R0 "OK" exists
    MessageBox MB_OK "rtlsdr download failed: $R0"
    return
    exists:
    ZipDLL::extractall "$TEMP\rtlsdr.zip" "$TEMP"
    CopyFiles "$TEMP\rtl-sdr-release\x32\*.dll" "$INSTDIR"
    ;Delete "$TEMP\rtlsdr.zip"
    RmDir /r "$TEMP\rtl-sdr-release"
FunctionEnd

Function get_python
    IfFileExists "$TEMP\python.msi" exists download
    download:
    inetc::get "http://www.python.org/ftp/python/2.7.5/python-2.7.5.msi" "$TEMP\python.msi"  /end
    Pop $R0
    StrCmp $R0 "OK" exists
    MessageBox MB_OK "Python download failed: $R0"
    return
    exists:
    ExecWait '"msiexec" /i "$TEMP\python.msi"'
    ;Delete "$TEMP\python.msi"
FunctionEnd

Function get_wxpython
    IfFileExists "$TEMP\wxPython2.8-win32-unicode-2.8.12.1-py27.exe" exists download
    download:
    inetc::get "http://downloads.sourceforge.net/wxpython/wxPython2.8-win32-unicode-2.8.12.1-py27.exe" "$TEMP\wxPython2.8-win32-unicode-2.8.12.1-py27.exe" /end
    Pop $R0
    StrCmp $R0 "OK" exists
    MessageBox MB_OK "wxPython download failed: $R0"
    return
    exists:
    ExecWait "$TEMP\wxPython2.8-win32-unicode-2.8.12.1-py27.exe"
    ;Delete "$TEMP\wxPython2.8-win32-unicode-2.8.12.1-py27.exe"
FunctionEnd

Function get_matplotlib
    IfFileExists "$TEMP\matplotlib-1.3.0.win32-py2.7.exe" exists download
    download:
    inetc::get "http://downloads.sourceforge.net/project/matplotlib/matplotlib/matplotlib-1.3.0/matplotlib-1.3.0.win32-py2.7.exe" "$TEMP\matplotlib-1.3.0.win32-py2.7.exe"  /end
    Pop $R0
    StrCmp $R0 "OK" exists
    MessageBox MB_OK "matplotlib download failed: $R0"
    return
    exists:
    ExecWait "$TEMP\matplotlib-1.3.0.win32-py2.7.exe"
    ;Delete "$TEMP\matplotlib-1.3.0.win32-py2.7.exe"
FunctionEnd

Function get_numpy
    IfFileExists "$TEMP\numpy-1.7.1.win32-py2.7.exe" exists download
    download:
    inetc::get "https://pypi.python.org/packages/2.7/n/numpy/numpy-1.7.1.win32-py2.7.exe" "$TEMP\numpy-1.7.1.win32-py2.7.exe"  /end
    Pop $R0
    StrCmp $R0 "OK" exists
    MessageBox MB_OK "NumPy download failed: $R0"
    return
    exists:
    ExecWait "$TEMP\numpy-1.7.1.win32-py2.7.exe"
    ;Delete "$TEMP\numpy-1.7.1.win32-py2.7.exe"
FunctionEnd

Function get_pyparsing
    IfFileExists "$TEMP\pyparsing-2.0.1.win32-py2.7.exe" exists download
    download:
    inetc::get "http://downloads.sourceforge.net/project/pyparsing/pyparsing/pyparsing-2.0.1/pyparsing-2.0.1.win32-py2.7.exe" "$TEMP\pyparsing-2.0.1.win32-py2.7.exe"  /end
    Pop $R0
    StrCmp $R0 "OK" exists
    MessageBox MB_OK "pyparsing download failed: $R0"
    return
    exists:
    ExecWait "$TEMP\pyparsing-2.0.1.win32-py2.7.exe"
    ;Delete "$TEMP\pyparsing-2.0.1.win32-py2.7.exe"
FunctionEnd

Function get_setuptools
    IfFileExists "$TEMP\setuptools-1.1.6.tar.gz" exists download
    download:
    inetc::get "http://pypi.python.org/packages/source/s/setuptools/setuptools-1.1.6.tar.gz" "$TEMP\setuptools-1.1.6.tar.gz"  /end
    Pop $R0
    StrCmp $R0 "OK" exists
    MessageBox MB_OK "setuptools download failed: $R0"
    return
    exists:
    untgz::extract "-d" "$TEMP" "$TEMP\setuptools-1.1.6.tar.gz"
    SetOutPath "$TEMP\setuptools-1.1.6"
    ExecWait "python $TEMP\setuptools-1.1.6\setup.py install"
    ;Delete "$TEMP\setuptools-1.1.6.tar.gz"
    RmDir /r "$TEMP\setuptools-1.1.6"
FunctionEnd

Function get_dateutil
    IfFileExists "$TEMP\python-dateutil-2.1.tar.gz" exists download
    download:
    inetc::get "http://pypi.python.org/packages/source/p/python-dateutil/python-dateutil-2.1.tar.gz" "$TEMP\python-dateutil-2.1.tar.gz" /end
    Pop $R0
    StrCmp $R0 "OK" exists
    MessageBox MB_OK "dateutil download failed: $R0"
    return
    exists:
    untgz::extract "-d" "$TEMP" "$TEMP\python-dateutil-2.1.tar.gz"
    SetOutPath "$TEMP\python-dateutil-2.1"
    ExecWait "python $TEMP\python-dateutil-2.1\setup.py install"
    ;Delete "$TEMP\python-dateutil-2.1.tar.gz"
    RmDir /r "$TEMP\python-dateutil-2.1.tar.gz"
FunctionEnd

Function get_pyrtlsdr
    inetc::get "https://github.com/roger-/pyrtlsdr/archive/master.zip" "$TEMP\pyrtlsdr.zip" /end
    Pop $R0
    StrCmp $R0 "OK" exists
    MessageBox MB_OK "pyrtlsdr download failed: $R0"
    return
    exists:
    ZipDLL::extractall "$TEMP\pyrtlsdr.zip" "$TEMP"
    SetOutPath "$TEMP\pyrtlsdr-master"
    ExecWait "python $TEMP\pyrtlsdr-master\setup.py install"
    ;Delete "$TEMP\pyrtlsdr.zip"
    RmDir /r "$TEMP\pyrtlsdr-master"
FunctionEnd

Function set_installer_path
    ReadEnvStr $R0 "PATH"
    ReadRegStr $R1 HKLM Software\Python\PythonCore\2.7\InstallPath ""
    StrCpy $R0 "$R0;$R1"
    SetEnv::SetEnvVar "PATH" $R0
FunctionEnd

Function set_python_path
    ReadRegStr $0 HKLM Software\Python\PythonCore\2.7\InstallPath ""
    ${EnvVarUpdate} $0 "PATH" "A" "HKLM" $0
FunctionEnd

Function un.onUninstSuccess
    HideWindow
    MessageBox MB_ICONINFORMATION|MB_OK "$(^Name) was successfully uninstalled from your computer."
FunctionEnd

Function un.onInit
    MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 "Are you sure you want to completely uninstall $(^Name)?" IDYES end
    Abort
    end:
FunctionEnd