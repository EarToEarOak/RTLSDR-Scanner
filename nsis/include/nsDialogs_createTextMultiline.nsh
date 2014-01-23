/*

nsDialogs_createTextMultiline.nsh
Header file for creating Edit (Text) controls with multiline support.
Multiline is a style that cannot be added after the control has been created.

Usage:
  ${NSD_CreateTextMultiline} x y width height text
	; Creates the multi-line Edit (Text) control
	
*/

!ifndef NSDIALOGS_createTextMultiline_INCLUDED
	!define NSDIALOGS_createTextMultiline_INCLUDED
	!verbose push
	!verbose 3

	!include LogicLib.nsh
	!include WinMessages.nsh

	!define __NSD_TextMultiline_CLASS EDIT
	!define __NSD_TextMultiline_STYLE ${DEFAULT_STYLES}|${WS_VSCROLL}|${WS_TABSTOP}|${ES_AUTOHSCROLL}|${ES_MULTILINE}|${ES_WANTRETURN}
	!define __NSD_TextMultiline_EXSTYLE ${WS_EX_WINDOWEDGE}|${WS_EX_CLIENTEDGE}
	!insertmacro __NSD_DefineControl TextMultiline

	!verbose pop
!endif
