;
; rtlsdr_scan
;
; http://eartoearoak.com/software/rtlsdr-scanner
;
; Copyright 2012 - 2014 Al Brown
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

!include "FileFunc.nsh"
!include "LogicLib.nsh"
!include "Sections.nsh"
!include "MUI.nsh"
!include "nsDialogs.nsh"
!include "include\nsDialogs_createTextMultiline.nsh"
!include "include\EnvVarUpdate.nsh"
!include "include\fileassoc.nsh"

!define INSTALLER_VERSION "10"

!define PRODUCT_NAME "RTLSDR Scanner"
!define PRODUCT_PUBLISHER "Ear to Ear Oak"
!define PRODUCT_WEB_SITE "http://eartoearoak.com/software/rtlsdr-scanner"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

!define SETTINGS_KEY "Software\rtlsdr-scanner"
!define SETTINGS_INSTDIR "InstDir"

!define MUI_ABORTWARNING
!define MUI_ICON "rtlsdr_scan.ico"
!define MUI_UNICON "rtlsdr_scan.ico"
!define MUI_FINISHPAGE_NOAUTOCLOSE

!insertmacro MUI_PAGE_WELCOME
Page custom page_update
Page custom page_info
!insertmacro MUI_PAGE_LICENSE "license.txt"
Page custom page_type page_type_end
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
Page custom page_error page_error_end
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

!define TYPE_FULL "Full"
!define TYPE_UPDATE "Update"
!define UPDATE_CHECK '"Checking for updates..."'
!define UPDATE_PROBLEM '"There was a problem checking for an updated installer"'
!define UPDATE_NONE '"You are using an up to date installer"'
!define UPDATE_FOUND '"An updated installer is available at: $\r$\n$\r$\n\
http://sourceforge.net/projects/rtlsdrscanner/files/latest/download $\r$\n$\r$\n\
Updating is highly recommended"'
!define INFO '"This will install RTLSDR Scanner and its Python dependencies $\r$\n$\r$\n\
When asked it is recommended to use the default options for all software $\r$\n$\r$\n\
It will add the new installation of Python to the path, potentially causing problems $\r$\n\
to previous Python installs $\r$\n$\r$\n\
You can update to the latest versions of RTLSDR-Scanner, $\r$\n\
the rtlsdr driver and pyrtlsdr by running this installer again"'

!define FILE_CLASS "RTLSDRScanner.Scan"
!define FILE_TYPE "rfs"
!define FILE_DESC "RTLSDR Scan"

Name "${PRODUCT_NAME}"
OutFile "rtlsdr_scanner-setup-win32.exe"
RequestExecutionLevel admin
InstallDir "$PROGRAMFILES\RTLSDR Scanner"
ShowInstDetails show
ShowUnInstDetails show

Var Version
Var Type
Var Page
Var Text
Var Radio1
Var Radio2
Var UpdateText
Var UpdateNext
Var InstSize

Var ErrorLog
Var ErrorMessage

Var PythonPath

Var UriPath
Var UriFile

Section "RTLSDR Scanner (Required)" SEC_SCAN
    SetOutPath "$INSTDIR"
    SetOverwrite ifnewer
    File "license.txt"
    Call install_rtlsdr_scanner
    !insertmacro APP_ASSOCIATE "${FILE_TYPE}" "${FILE_CLASS}" "${FILE_DESC}" "$INSTDIR\rtlsdr_scan.ico,0" "Open with RTLSDR Scanner" "python $\"$INSTDIR\rtlsdr_scan.py$\" $\"%1$\""
    CopyFiles "$ExePath" "$InstDir\"
    CreateDirectory "$SMPROGRAMS\RTLSDR Scanner"
    CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\RTLSDR Scanner.lnk" "python" '"$INSTDIR\rtlsdr_scan.py"' "$INSTDIR\rtlsdr_scan.ico" 0
    CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\Setup.lnk" "$INSTDIR\$EXEFILE"

    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
 	IntFmt $InstSize "0x%08X" $0
SectionEnd


SectionGroup "/e" "Dependencies" SEC_DEP
    Section "RTLSDR Driver" SEC_RTLSDR
        Call install_rtlsdr
    SectionEnd
    Section "MSVC 2010 Runtime" SEC_MSVC
        File vcredist_x86.exe
        ExecWait 'vcredist_x86.exe /quiet /norestart'
    SectionEnd
    SectionGroup "/e" "Python" SEC_PYDEP
        Section "Python 2.7.8" SEC_PYTHON
        	StrCpy $UriPath "http://www.python.org/ftp/python/2.7.8"
        	StrCpy $UriFile "python-2.7.8.msi"
			Call install_msi
			Call set_installer_path
			Call install_setuptools
        SectionEnd
        Section "Add Python to PATH"
           Call set_python_path
        SectionEnd
        Section "dateutil"
        	StrCpy $UriFile "python-dateutil"
            Call install_easy
        SectionEnd
        Section "matplotlib 1.3.1"
            StrCpy $UriPath "http://downloads.sourceforge.net/project/matplotlib/matplotlib/matplotlib-1.3.1"
        	StrCpy $UriFile "matplotlib-1.3.1.win32-py2.7.exe"
			Call install_exe
        SectionEnd
        Section "numpy 1.8.1"
            StrCpy $UriPath "http://downloads.sourceforge.net/project/numpy/NumPy/1.8.1"
        	StrCpy $UriFile "numpy-1.8.1-win32-superpack-python2.7.exe"
			Call install_exe
        SectionEnd
        Section "Pillow"
            StrCpy $UriFile "Pillow"
            Call install_easy
        SectionEnd
        Section "pyparsing"
            StrCpy $UriFile "pyparsing"
            Call install_easy
        SectionEnd
        Section "pyrtlsdr" SEC_PYRTLSDR
            Call get_pyrtlsdr
        SectionEnd
        Section "PySerial"
        	StrCpy $UriFile "pyserial"
            Call install_easy
        SectionEnd
       	Section "wxPython 3"
            StrCpy $UriPath "http://downloads.sourceforge.net/wxpython/3.0.0.0"
        	StrCpy $UriFile "wxPython3.0-win32-3.0.0.0-py27.exe"
			Call install_exe
        SectionEnd
    SectionGroupEnd
SectionGroupEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
!insertmacro MUI_DESCRIPTION_TEXT ${SEC_SCAN} "RTLSDR Scanner"
!insertmacro MUI_DESCRIPTION_TEXT ${SEC_RTLSDR} "Latest rtlsdr driver"
!insertmacro MUI_DESCRIPTION_TEXT ${SEC_MSVC} "Microsoft Visual C++ Redistributable"
!insertmacro MUI_DESCRIPTION_TEXT ${SEC_DEP} "Dependencies"
!insertmacro MUI_DESCRIPTION_TEXT ${SEC_PYDEP} "Python dependencies"
!insertmacro MUI_DESCRIPTION_TEXT ${SEC_PYRTLSDR} "Latest Python wrapper for the rtlsdr driver"
!insertmacro MUI_FUNCTION_DESCRIPTION_END


Section -AdditionalIcons
    SetOutPath "$INSTDIR"
    WriteIniStr "$INSTDIR\${PRODUCT_NAME}.url" "InternetShortcut" "URL" "${PRODUCT_WEB_SITE}"
    CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\Website.lnk" "$INSTDIR\${PRODUCT_NAME}.url"
    CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\Uninstall.lnk" "$INSTDIR\uninst.exe"
    CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\Manual.lnk" "$INSTDIR\doc\Manual.pdf"
    CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\Example.lnk" "$INSTDIR\doc\BBCR2.rfs"
SectionEnd


Section -Post
    WriteRegStr HKCU "${SETTINGS_KEY}" "${SETTINGS_INSTDIR}" "$INSTDIR"
    WriteUninstaller "$INSTDIR\uninst.exe"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\rtlsdr_scan.ico"
    WriteRegDWORD ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "EstimatedSize" "$InstSize"
SectionEnd


Section Uninstall

    !insertmacro APP_UNASSOCIATE "${FILE_TYPE}" "${FILE_CLASS}"

    Delete "$INSTDIR\${PRODUCT_NAME}.url"
    Delete "$INSTDIR\rtlsdr_scan.ico"
    Delete "$INSTDIR\uninst.exe"
    Delete "$INSTDIR\license.txt"
    Delete "$INSTDIR\windows.py"
    Delete "$INSTDIR\toolbars.py"
    Delete "$INSTDIR\spectrum.py"
    Delete "$INSTDIR\spectrogram.py"
    Delete "$INSTDIR\settings.py"
    Delete "$INSTDIR\scan.py"
    Delete "$INSTDIR\rtltcp.py"
    Delete "$INSTDIR\rtlsdr_scan.py"
    Delete "$INSTDIR\rtlsdr_scan_diag.py"
    Delete "$INSTDIR\printer.py"
    Delete "$INSTDIR\plot3d.py"
    Delete "$INSTDIR\plot.py"
    Delete "$INSTDIR\plot_controls.py"
    Delete "$INSTDIR\misc.py"
    Delete "$INSTDIR\main_window.py"
    Delete "$INSTDIR\file.py"
    Delete "$INSTDIR\events.py"
    Delete "$INSTDIR\dialogs.py"
    Delete "$INSTDIR\devices.py"
    Delete "$INSTDIR\constants.py"
    Delete "$INSTDIR\cli.py"
    Delete "$INSTDIR\version-timestamp"
    Delete "$INSTDIR\res\wireframe.png"
    Delete "$INSTDIR\res\variance.png"
    Delete "$INSTDIR\res\spacer.png"
    Delete "$INSTDIR\res\peak.png"
    Delete "$INSTDIR\res\min.png"
    Delete "$INSTDIR\res\max.png"
    Delete "$INSTDIR\res\icon.png"
    Delete "$INSTDIR\res\grid.png"
    Delete "$INSTDIR\res\fade.png"
    Delete "$INSTDIR\res\colurmap.png"
    Delete "$INSTDIR\res\average.png"
    Delete "$INSTDIR\res\auto_refresh.png"
    Delete "$INSTDIR\res\auto_t.png"
    Delete "$INSTDIR\res\auto_l.png"
    Delete "$INSTDIR\res\auto_f.png"
    Delete "$INSTDIR\res\icon.png"
    Delete "$INSTDIR\doc\Manual.pdf"
    Delete "$INSTDIR\doc\BBCR2.rfs"
    Delete "$INSTDIR\*.pyc"
    Delete "$INSTDIR\libusb-1.0.dll"
    Delete "$INSTDIR\pthreadVC2-w32.dll"
    Delete "$INSTDIR\rtlsdr.dll"

    ; Obsolete
    Delete "$INSTDIR\threads.py"
    Delete "$INSTDIR\res\auto_range.png"
    Delete "$INSTDIR\res\range.png"

    DeleteRegKey HKCU "${SETTINGS_KEY}/${SETTINGS_INSTDIR}"

    Delete "$SMPROGRAMS\RTLSDR Scanner\Uninstall.lnk"
    Delete "$SMPROGRAMS\RTLSDR Scanner\Website.lnk"
    Delete "$SMPROGRAMS\RTLSDR Scanner\Setup.lnk"
    Delete "$SMPROGRAMS\RTLSDR Scanner\RTLSDR Scanner.lnk"

    RMDir "$SMPROGRAMS\RTLSDR Scanner"

    RMDir "$INSTDIR\res"
    RMDir "$INSTDIR\doc"
    RMDir "$INSTDIR"

    DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
    SetAutoClose true
SectionEnd


Function .onInit
    ReadRegStr $0 HKCU "${SETTINGS_KEY}" "${SETTINGS_INSTDIR}"
    ${If} $0 == ""
        StrCpy $Type ${TYPE_FULL}
    ${EndIf}
    IntOp $0 ${SF_SELECTED} | ${SF_RO}
    IntOp $0 $0 | ${SF_BOLD}
    SectionSetFlags ${SEC_SCAN} $0
FunctionEnd

Function page_update
    !insertmacro MUI_HEADER_TEXT "Updates" "Checking for installer updates"
    nsDialogs::Create 1018
    Pop $Page
    ${If} $Page == error
        Abort
    ${EndIf}
    ${NSD_CreateTextMultiline} 0 0% 100% 100% ${UPDATE_CHECK}
    Pop $UpdateText
	SendMessage $Text ${EM_SETREADONLY} 1 0
    GetDlgItem $UpdateNext $HWNDPARENT 1
    EnableWindow $UpdateNext 0
    ${NSD_CreateTimer} update_check 1000
    nsDialogs::Show
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

Function page_type
    !insertmacro MUI_HEADER_TEXT "Installation type" "Please select an install type"
    nsDialogs::Create 1018
    Pop $Page
    ${If} $Page == error
        Abort
    ${EndIf}
    ${NSD_CreateRadioButton} 20% 10% 100% 10u ${TYPE_FULL}
    Pop $Radio1
    ${NSD_CreateLabel} 20% 20% 100% 10u "Full installation."
    Pop $0
    ${NSD_CreateRadioButton} 20% 40% 100% 10u ${TYPE_UPDATE}
    Pop $Radio2
    ${NSD_CreateLabel} 20% 50% 100% 10u "Update the scanner, the rtlsdr library and pyrtlsdr wrapper."
    Pop $0
    ${NSD_CreateLabel} 20% 60% 100% 10u "Select this if the dependencies are already installed."
    Pop $0
    ${If} $Type == ${TYPE_FULL}
        ${NSD_SetState} $Radio1 ${BST_CHECKED}
    ${Else}
        ${NSD_SetState} $Radio2 ${BST_CHECKED}
    ${EndIf}
    nsDialogs::Show
FunctionEnd

Function page_type_end
    ${NSD_GetState} $Radio1 $0
    ${If} $0 == ${BST_CHECKED}
        StrCpy $Type ${TYPE_FULL}
        !insertmacro SelectSection ${SEC_DEP}
        !insertmacro SelectSection ${SEC_MSVC}
    ${Else}
        StrCpy $Type ${TYPE_UPDATE}
        !insertmacro UnselectSection ${SEC_DEP}
        !insertmacro SelectSection ${SEC_RTLSDR}
        !insertmacro SelectSection ${SEC_PYRTLSDR}
    ${EndIf}
FunctionEnd

Function page_error
	StrCmp $ErrorLog "" noerrors
	!insertmacro MUI_HEADER_TEXT "Installation failed" "Errors occurred"
    nsDialogs::Create 1018
    Pop $Page
    ${If} $Page == error
        Abort
    ${EndIf}
    ${NSD_CreateTextMultiline} 0 0% 100% 100% $ErrorLog
    SendMessage $Text ${EM_SETREADONLY} 1 0
    GetDlgItem $R0 $HWNDPARENT 1
	SendMessage $R0 ${WM_SETTEXT} 0 "STR:Close"
	GetDlgItem $R0 $HWNDPARENT 2
	EnableWindow $R0 0
    nsDialogs::Show
    noerrors:
FunctionEnd

Function page_error_end
	StrCmp $ErrorLog "" noerrors
	Quit
	noerrors:
FunctionEnd

Function update_check
    ${NSD_KillTimer} update_check
    inetc::get "https://raw.github.com/EarToEarOak/RTLSDR-Scanner/master/nsis/_version" "$TEMP\_version" /end
    ${If} ${FileExists} "$TEMP\_version"
        FileOpen $0 "$TEMP\_version" r
        FileRead $0 $Version
        FileClose $0
        Delete "$TEMP\_version"
        ${If} $Version > ${INSTALLER_VERSION}
            ${NSD_SetText} $UpdateText ${UPDATE_FOUND}
            MessageBox MB_YESNO|MB_ICONQUESTION "Installer update found, download now (recommended)?" IDYES download IDNO skip
            download:
                ExecShell "open" "http://sourceforge.net/projects/rtlsdrscanner/files/latest/download"
                SendMessage $HWNDPARENT ${WM_CLOSE} 0 0
                Quit
            skip:
        ${Else}
            ${NSD_SetText} $UpdateText ${UPDATE_NONE}
        ${EndIf}
    ${Else}
        ${NSD_SetText} $UpdateText ${UPDATE_PROBLEM}
    ${EndIf}
    EnableWindow $UpdateNext 1
FunctionEnd

Function install_msi
    IfFileExists "$TEMP\$UriFile" exists download
    download:
	    inetc::get "$UriPath/$UriFile" "$TEMP\$UriFile"  /end
	    Pop $R0
	    StrCmp $R0 "OK" exists
	    StrCpy $ErrorMessage "$UriFile download failed: $R0"
	    Call error
	    Return
    exists:
    	ExecWait '"msiexec" /i "$TEMP\$UriFile"'
    	IfErrors error
    	Return
    	error:
    		StrCpy $ErrorMessage "Failed to install $UriFile"
	    	Call error
FunctionEnd

Function install_exe
    IfFileExists "$TEMP\$UriFile" exists download
    download:
	    inetc::get "$UriPath/$UriFile" "$TEMP\$UriFile"  /end
	    Pop $R0
	    StrCmp $R0 "OK" exists
	    StrCpy $ErrorMessage "$UriFile download failed: $R0"
	    Call error
	    Return
    exists:
    	ExecWait "$TEMP\$UriFile"
    	IfErrors error
    	Return
    	error:
    		StrCpy $ErrorMessage "Failed to install $UriFile"
	    	Call error
FunctionEnd

Function install_setuptools
    inetc::get "https://bootstrap.pypa.io/ez_setup.py" "$TEMP\ez_setup.py"  /end
    Pop $R0
    StrCmp $R0 "OK" exists
    StrCpy $ErrorMessage "setuptools download failed: $R0"
	Call error
    Return
    exists:
	    ExecWait "python $TEMP\ez_setup.py"
		IfErrors error
    	Return
    	error:
    		StrCpy $ErrorMessage "Failed to install setuptools"
			Call error
FunctionEnd

Function install_easy
	Call get_python_path
	ExecWait "$PythonPath\Scripts\easy_install $UriFile"
	IfErrors error
    	Return
    	error:
    		StrCpy $ErrorMessage "Failed to install $UriFile"
			Call error
FunctionEnd

Function install_rtlsdr_scanner
    inetc::get "https://github.com/EarToEarOak/RTLSDR-Scanner/archive/master.zip" "$TEMP\rtlsdr_scanner.zip" /end
    Pop $R0
    StrCmp $R0 "OK" exists
    StrCpy $ErrorMessage "RTLSDR Scanner download failed: $R0"
	Call error
    Return
    exists:
	    ZipDLL::extractall "$TEMP\rtlsdr_scanner.zip" "$TEMP"
	    CopyFiles "$TEMP\RTLSDR-Scanner-master\src\*.py" "$INSTDIR"
	    CopyFiles "$TEMP\RTLSDR-Scanner-master\src\version-timestamp" "$INSTDIR"
	    CreateDirectory "$INSTDIR\res"
	    CopyFiles "$TEMP\RTLSDR-Scanner-master\res\*.png" "$INSTDIR\res"
	    CreateDirectory "$INSTDIR\doc"
	    CopyFiles "$TEMP\RTLSDR-Scanner-master\doc\*.pdf" "$INSTDIR\doc"
	    CopyFiles "$TEMP\RTLSDR-Scanner-master\doc\*.rfs" "$INSTDIR\doc"
	    CopyFiles "$TEMP\RTLSDR-Scanner-master\*.ico" "$INSTDIR"
	    RmDir /r "$TEMP\RTLSDR-Scanner-master"
	    ${EnvVarUpdate} $0 "PATH" "A" "HKLM" "$INSTDIR"
FunctionEnd

Function install_rtlsdr
    inetc::get "http://sdr.osmocom.org/trac/raw-attachment/wiki/rtl-sdr/RelWithDebInfo.zip" "$TEMP\rtlsdr.zip" /end
    Pop $R0
    StrCmp $R0 "OK" exists
    StrCpy $ErrorMessage "rtlsdr download failed: $R0"
	Call error
    Return
    exists:
	    ZipDLL::extractall "$TEMP\rtlsdr.zip" "$TEMP"
	    CopyFiles "$TEMP\rtl-sdr-release\x32\*.dll" "$INSTDIR"
	    RmDir /r "$TEMP\rtl-sdr-release"
FunctionEnd

Function get_pyrtlsdr
    inetc::get "https://github.com/roger-/pyrtlsdr/archive/master.zip" "$TEMP\pyrtlsdr.zip" /end
    Pop $R0
    StrCmp $R0 "OK" exists
    StrCpy $ErrorMessage "pyrtlsdr download failed: $R0"
    Call error
    Return
    exists:
	    ZipDLL::extractall "$TEMP\pyrtlsdr.zip" "$TEMP"
	    SetOutPath "$TEMP\pyrtlsdr-master"
	    ExecWait "python $TEMP\pyrtlsdr-master\setup.py install"
	    RmDir /r "$TEMP\pyrtlsdr-master"
FunctionEnd

Function get_python_path
	ReadRegStr $R0 HKLM Software\Python\PythonCore\2.7\InstallPath ""
	IfErrors error
		StrCpy $PythonPath $R0
	Return
	error:
		StrCpy $ErrorMessage "Cannot find Python - aborting"
		MessageBox MB_OK|MB_ICONEXCLAMATION $ErrorMessage
		Abort $ErrorMessage"
FunctionEnd

Function set_installer_path
	Call get_python_path
    ReadEnvStr $R0 "PATH"
    StrCpy $R0 "$R0;$PythonPath"
    SetEnv::SetEnvVar "PATH" $R0
FunctionEnd

Function set_python_path
	Call get_python_path
    ${EnvVarUpdate} $PythonPath "PATH" "A" "HKLM" $PythonPath
FunctionEnd

Function error
	StrCpy $ErrorLog "$ErrorLog$\r$\n$ErrorMessage"
FunctionEnd

Function un.onInit
    MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 "Are you sure you want to completely uninstall $(^Name)?" IDYES end
    Abort
    end:
FunctionEnd

Function un.onUninstSuccess
    HideWindow
    MessageBox MB_ICONINFORMATION|MB_OK "$(^Name) was successfully uninstalled from your computer."
FunctionEnd
