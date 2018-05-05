;
; rtlsdr_scan
;
; http://eartoearoak.com/software/rtlsdr-scanner
;
; Copyright 2012 - 2017 Al Brown
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
!include "WinVer.nsh"
!include "include\nsDialogs_createTextMultiline.nsh"
!include "include\EnvVarUpdate.nsh"
!include "include\fileassoc.nsh"

!define INSTALLER_VERSION "24"

!define PRODUCT_NAME "RTLSDR Scanner"
!define PRODUCT_PUBLISHER "Ear to Ear Oak"
!define PRODUCT_WEB_SITE "https://eartoearoak.com/software/rtlsdr-scanner"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

!define SETTINGS_KEY "Software\rtlsdr-scanner"
!define SETTINGS_INSTDIR "InstDir"
!define SETTINGS_INSTVER "InstVer"

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
https://github.com/EarToEarOak/RTLSDR-Scanner/releases $\r$\n$\r$\n\
Updating is highly recommended"'
!define INFO '"This will install RTLSDR Scanner and its dependencies $\r$\n$\r$\n\
You can update to the latest versions of RTLSDR-Scanner, $\r$\n\
the rtlsdr driver and dependencies by running this installer again"'

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

Var ErrorLog
Var ErrorMessage

Var PythonPath

Var UriPath
Var UriFile
Var Switches


Section "RTLSDR Scanner (Required)" SEC_SCAN
SectionEnd

SectionGroup "/e" "Dependencies" SEC_DEP
	Section "RTLSDR Driver" SEC_RTLSDR
		Call install_rtlsdr
	SectionEnd
	Section "MSVC 2010 Runtime" SEC_MSVC
		File vcredist_x86.exe
		ExecWait 'vcredist_x86.exe /quiet /norestart'
	SectionEnd
	SectionGroup "/e" "Python 2.7" SEC_PYDEP
		Section "Python 2.7.12" SEC_PYTHON
			StrCpy $UriPath "http://www.python.org/ftp/python/2.7.14"
			StrCpy $UriFile "python-2.7.14.msi"
            StrCpy $Switches "/qb ALLUSERS=1"
			Call install_msi
		SectionEnd
		Section "wxPython 3" SEC_WX
			StrCpy $UriPath "http://downloads.sourceforge.net/wxpython/3.0.2.0"
			StrCpy $UriFile "wxPython3.0-win32-3.0.2.0-py27.exe"
            StrCpy $Switches "/silent"
			Call install_exe
		SectionEnd
	SectionGroupEnd
SectionGroupEnd

Section -Install
    SetOutPath "$INSTDIR"
    SetOverwrite ifnewer
    File "rtlsdr_scan.ico"
    File "..\doc\Manual.pdf"
    File "..\doc\BBCR2.rfs"
    File "license.txt"
    Call install_rtlsdr_scanner
    CopyFiles "$ExePath" "$InstDir\"
    CreateDirectory "$SMPROGRAMS\RTLSDR Scanner"
    CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\Setup.lnk" "$INSTDIR\$EXEFILE"
    
    ${If} ${IsWinXP}
        StrCpy $UriFile "pyserial==2.7"
        Call install_pip
    ${EndIf}
SectionEnd

Section -AdditionalIcons
	SetOutPath "$INSTDIR"
	WriteIniStr "$INSTDIR\${PRODUCT_NAME}.url" "InternetShortcut" "URL" "${PRODUCT_WEB_SITE}"
	
	CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\Website.lnk" "$INSTDIR\${PRODUCT_NAME}.url"
	CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\Uninstall.lnk" "$INSTDIR\uninst.exe"
	CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\Manual.lnk" "$INSTDIR\Manual.pdf"
	CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\Example.lnk" "$INSTDIR\BBCR2.rfs"
SectionEnd

Section -Post
	WriteRegStr HKCU "${SETTINGS_KEY}" "${SETTINGS_INSTDIR}" "$INSTDIR"
    WriteRegDWORD HKCU "${SETTINGS_KEY}" "${SETTINGS_INSTVER}" ${INSTALLER_VERSION}

	WriteUninstaller "$INSTDIR\uninst.exe"
	WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
	WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
	WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
	WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
	WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\rtlsdr_scan.ico"
SectionEnd

Section Uninstall
	!insertmacro APP_UNASSOCIATE "${FILE_TYPE}" "${FILE_CLASS}"
    
    StrCpy $UriFile "rtlsdr-scanner"
    Call un.install_pip

	Delete "$INSTDIR\rtlsdr_scan.ico"
    Delete "$INSTDIR\Manual.pdf"
	Delete "$INSTDIR\BBCR2.rfs"
    Delete "$INSTDIR\license.txt"
    Delete "$INSTDIR\${PRODUCT_NAME}.url"
    Delete "$INSTDIR\*.dll"
    Delete "$INSTDIR\uninst.exe"
    RMDir "$INSTDIR"

	DeleteRegKey HKCU "${SETTINGS_KEY}/${SETTINGS_INSTDIR}"

	Delete "$SMPROGRAMS\RTLSDR Scanner\Uninstall.lnk"
	Delete "$SMPROGRAMS\RTLSDR Scanner\Website.lnk"
	Delete "$SMPROGRAMS\RTLSDR Scanner\Setup.lnk"
	Delete "$SMPROGRAMS\RTLSDR Scanner\RTLSDR Scanner.lnk"
    Delete "$SMPROGRAMS\RTLSDR Scanner\RTLSDR Example.lnk"

	RMDir "$SMPROGRAMS\RTLSDR Scanner"

	DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
    
    ${un.EnvVarUpdate} $0 "PATH" "R" "HKLM" "$INSTDIR"
    
	SetAutoClose true
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
!insertmacro MUI_DESCRIPTION_TEXT ${SEC_SCAN} "RTLSDR Scanner"
!insertmacro MUI_DESCRIPTION_TEXT ${SEC_RTLSDR} "Latest rtlsdr driver"
!insertmacro MUI_DESCRIPTION_TEXT ${SEC_MSVC} "Microsoft Visual C++ Redistributable"
!insertmacro MUI_DESCRIPTION_TEXT ${SEC_DEP} "Dependencies"
!insertmacro MUI_DESCRIPTION_TEXT ${SEC_PYDEP} "Python dependencies"
!insertmacro MUI_FUNCTION_DESCRIPTION_END


Function .onInit
    ReadRegStr $0 HKCU "${SETTINGS_KEY}" "${SETTINGS_INSTDIR}"
    ReadRegDWORD $1 HKCU "${SETTINGS_KEY}" "${SETTINGS_INSTVER}"
    ${IfNot} $0 == ""    
    ${AndIf} $1 == ""
        MessageBox MB_ICONEXCLAMATION|MB_OKCANCEL "The previous version needs to be uninstalled first.$\r$\nCancelling this will exit the installer." IDOK ok IDCANCEL cancel
        cancel:
            abort
        ok:
            Call uninstall
    ${EndIf}

	ReadRegStr $0 HKCU "${SETTINGS_KEY}" "${SETTINGS_INSTDIR}"
	${If} $0 == ""
    	StrCpy $Type ${TYPE_FULL}
	${EndIf}
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
	${NSD_CreateLabel} 20% 50% 100% 10u "Update the scanner and dependencies."
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
	${EndIf}

    IntOp $0 ${SF_SELECTED} | ${SF_RO}
    IntOp $0 $0 | ${SF_BOLD}
    SectionSetFlags ${SEC_SCAN} $0
    
    Call has_python
    ${If} $0 == ""
        IntOp $0 ${SF_SELECTED} | ${SF_RO}
        SectionSetFlags ${SEC_PYTHON} $0
        SectionSetFlags ${SEC_WX} $0
    ${EndIf}
FunctionEnd

Function page_error
	${If} $ErrorLog != ""
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
		${EndIf}
FunctionEnd

Function page_error_end
	${If} $ErrorLog != ""
		Quit
	${EndIf}
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
				ExecShell "open" "https://github.com/EarToEarOak/RTLSDR-Scanner/releases/latest"
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
	${IfNot} ${FileExists} "$TEMP\$UriFile"
		inetc::get "$UriPath/$UriFile" "$TEMP\$UriFile"  /end
		Pop $R0
		${If} $R0 != "OK"
			StrCpy $ErrorMessage "$UriFile download failed: $R0"
			Call error
			Return
		${EndIf}
	${EndIf}
	ClearErrors
	ExecWait '"msiexec" /i "$TEMP\$UriFile"  $Switches'
	${If} ${Errors}
		StrCpy $ErrorMessage "Failed to install $UriFile"
		Call error
	${EndIf}
FunctionEnd

Function install_exe
    ${IfNot} ${FileExists} "$TEMP\$UriFile"
	    inetc::get "$UriPath/$UriFile" "$TEMP\$UriFile"  /end
	    Pop $R0
	    ${If} $R0 != "OK"
			StrCpy $ErrorMessage "$UriFile download failed: $R0"
			Call error
			Return
	    ${EndIf}
	${EndIf}
	ClearErrors
	ExecWait "$TEMP\$UriFile  $Switches"
	${If} ${Errors}
		StrCpy $ErrorMessage "Failed to install $UriFile"
		Call error
	${EndIf}
FunctionEnd

Function install_pip
	Call get_python_path
	ClearErrors
	ExecWait '"$PythonPath\python.exe" -m pip install -U "$UriFile"'
	${If} ${Errors}
		StrCpy $ErrorMessage "Failed to install $UriFile"
		Call error
	${EndIf}
FunctionEnd

Function install_rtlsdr_scanner
    StrCpy $UriFile "rtlsdr-scanner"
    Call install_pip
    ${IfNot} ${Errors}
        Call get_python_path
        CreateShortCut "$SMPROGRAMS\RTLSDR Scanner\RTLSDR Scanner.lnk" '"$PythonPath\python.exe"' '-m rtlsdr_scanner' "$INSTDIR\rtlsdr_scan.ico" 0
        ${EnvVarUpdate} $0 "PATH" "A" "HKLM" "$INSTDIR"
        Call get_python_path
        !insertmacro APP_ASSOCIATE "${FILE_TYPE}" "${FILE_CLASS}" "${FILE_DESC}" "$INSTDIR\rtlsdr_scan.ico,0" "Open with RTLSDR Scanner" '"$PythonPath\python.exe" -m rtlsdr_scanner "%1"'
    ${EndIf}
FunctionEnd

Function install_rtlsdr
	inetc::get "http://osmocom.org/attachments/download/2242/RelWithDebInfo.zip" "$TEMP\rtlsdr.zip" /end
	Pop $R0
	${If} $R0 != "OK"
		StrCpy $ErrorMessage "rtlsdr download failed: $R0"
		Call error
	${Else}
		ZipDLL::extractall "$TEMP\rtlsdr.zip" "$TEMP"
		CopyFiles "$TEMP\rtl-sdr-release\x32\*.dll" "$INSTDIR"
		RmDir /r "$TEMP\rtl-sdr-release"
	${EndIf}
FunctionEnd

Function has_python
    ClearErrors
    ReadRegStr $R0 HKLM Software\Python\PythonCore\2.7\InstallPath ""
    ${IfNot} ${Errors}
        ${If} ${FileExists} "$R0\python.exe"
            StrCpy $0 $R0
        ${Else}
            StrCpy $0 ""
        ${EndIf}
    ${Else}
        StrCpy $0 ""
    ${Endif}
FunctionEnd

Function get_python_path
	ClearErrors
	ReadRegStr $R0 HKLM Software\Python\PythonCore\2.7\InstallPath ""
	${If} ${Errors}
		StrCpy $ErrorMessage "Cannot find Python 2.7 - aborting"
		MessageBox MB_OK|MB_ICONEXCLAMATION $ErrorMessage
		Abort $ErrorMessage"
	${Else}
		StrCpy $PythonPath $R0
	${EndIf}"
FunctionEnd

Function error
	StrCpy $ErrorLog "$ErrorLog$\r$\n$ErrorMessage"
FunctionEnd

Function uninstall
    ReadRegStr $0 ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString"
    ${If} $0 != ""
        DetailPrint "Removing previous version"
        ExecWait '"$0" _?=$INSTDIR'
    ${EndIf}
FunctionEnd

Function un.onInit
	MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 "Are you sure you want to completely uninstall $(^Name)?" IDYES end
	Abort
	end:
FunctionEnd

Function un.install_pip
    Call un.get_python_path
    ClearErrors
    ExecWait '"$PythonPath\python.exe" -m pip uninstall -y "$UriFile"'
FunctionEnd

Function un.get_python_path
    ClearErrors
    ReadRegStr $R0 HKLM Software\Python\PythonCore\2.7\InstallPath ""
    ${If} ${Errors}
        StrCpy $ErrorMessage "Cannot find Python 2.7 - aborting"
        MessageBox MB_OK|MB_ICONEXCLAMATION $ErrorMessage
        Abort $ErrorMessage"
    ${Else}
        StrCpy $PythonPath $R0
    ${EndIf}"
FunctionEnd

Function un.onUninstSuccess
	HideWindow
	MessageBox MB_ICONINFORMATION|MB_OK "$(^Name) was successfully uninstalled from your computer."
FunctionEnd
