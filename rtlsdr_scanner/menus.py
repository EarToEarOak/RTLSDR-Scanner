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
import wx


class MenuMain(object):
    def __init__(self, parent, settings):
        self.parent = parent
        self.settings = settings

        file = wx.Menu()
        self.new = file.Append(wx.ID_NEW, "&New",
                               "New plot_line")
        self.open = file.Append(wx.ID_OPEN, "&Open...",
                                "Open plot_line")
        self.merge = file.Append(wx.ID_ANY, "&Merge...",
                                 "Open and merge with current plot")
        self.restore = file.Append(wx.ID_ANY, "&Backups...",
                                   "Manage backups from crashes")
        recent = wx.Menu()
        settings.fileHistory.UseMenu(recent)
        settings.fileHistory.AddFilesToMenu()
        file.AppendMenu(wx.ID_ANY, "&Recent Files", recent)
        file.AppendSeparator()
        self.save = file.Append(wx.ID_SAVE, "&Save As...",
                                "Save plot_line")
        self.exportScan = file.Append(wx.ID_ANY, "Export scan...",
                                      "Export scan")
        self.exportImage = file.Append(wx.ID_ANY, "Export image...",
                                       "Export image")
        self.exportSeq = file.Append(wx.ID_ANY, "Export image sequence...",
                                     "Export sweep plots in sequence")
        self.exportGeo = file.Append(wx.ID_ANY, "Export map...",
                                     "Export maps")
        self.exportTrack = file.Append(wx.ID_ANY, "Export GPS track...",
                                       "Export GPS data")

        file.AppendSeparator()
        self.exportCont = file.Append(wx.ID_ANY, "Continuous export...",
                                      'Continually export data at the end of each sweep',
                                      kind=wx.ITEM_CHECK)

        file.AppendSeparator()
        self.page = file.Append(wx.ID_ANY, "Page setup...",
                                "Page setup")
        self.preview = file.Append(wx.ID_ANY, "Print preview...",
                                   "Print preview")
        self.printer = file.Append(wx.ID_ANY, "&Print...",
                                   "Print plot_line")
        file.AppendSeparator()
        self.properties = file.Append(wx.ID_ANY, "P&roperties...",
                                      "Show properties")
        file.AppendSeparator()
        self.close = file.Append(wx.ID_EXIT, "E&xit", "Exit the program")

        edit = wx.Menu()
        self.pref = edit.Append(wx.ID_ANY, "&Preferences...",
                                "Preferences")
        self.advPref = edit.Append(wx.ID_ANY, "&Advanced preferences...",
                                   "Advanced preferences")
        edit.AppendSeparator()
        self.formatting = edit.Append(wx.ID_ANY, "&Number formatting...",
                                      "Adjust the displayed precision of values")
        edit.AppendSeparator()
        self.devicesRtl = edit.Append(wx.ID_ANY, "&Radio Devices...",
                                      "Device selection and configuration")
        self.devicesGps = edit.Append(wx.ID_ANY, "&GPS...",
                                      "GPS selection and configuration")
        edit.AppendSeparator()
        self.reset = edit.Append(wx.ID_ANY, "&Reset settings...",
                                 "Reset setting to the default")

        view = wx.Menu()
        self.clearSelect = view.Append(wx.ID_ANY, "Clear selection",
                                       "Clear current selection")
        self.showMeasure = view.Append(wx.ID_ANY, "Show &measurements",
                                       "Show measurements window",
                                       kind=wx.ITEM_CHECK)
        self.showMeasure.Check(settings.showMeasure)
        view.AppendSeparator()
        self.fullScreen = view.Append(wx.ID_ANY, "Full screen\tF11",
                                      "Toggle full screen",
                                      kind=wx.ITEM_CHECK)

        scan = wx.Menu()
        self.start = scan.Append(wx.ID_ANY, "&Start",
                                 "Start scan")
        self.cont = scan.Append(wx.ID_ANY, "&Continue",
                                "Continue scan")
        self.stop = scan.Append(wx.ID_ANY, "S&top",
                                "Stop scan immediately")
        self.stopEnd = scan.Append(wx.ID_ANY, "Stop at &end",
                                   "Complete current sweep before stopping")
        scan.AppendSeparator()
        self.sweepClear = scan.Append(wx.ID_ANY, "Clear all sweeps",
                                      "Clear all sweeps")
        self.sweepRemain = scan.Append(wx.ID_ANY, "Clear all but first sweep",
                                       "Clear all but first sweep")
        scan.AppendSeparator()
        self.sweepDelay = scan.Append(wx.ID_ANY, "Delay...",
                                      "Delay between sweeps")

        tools = wx.Menu()
        self.compare = tools.Append(wx.ID_ANY, "&Compare...",
                                    "Compare plots")
        tools.AppendSeparator()
        self.smooth = tools.Append(wx.ID_ANY, "&Smooth...",
                                   "Smooth scans")
        tools.AppendSeparator()
        self.cal = tools.Append(wx.ID_ANY, "&Auto Calibration...",
                                "Automatically calibrate to a known frequency")
        tools.AppendSeparator()
        self.gearth = tools.Append(wx.ID_ANY, "Track in Google &Earth",
                                   "Display recorded points in Google Earth")
        self.gmaps = tools.Append(wx.ID_ANY, "Track in Google &Maps",
                                  "Display recorded points in Google Maps")
        self.sats = tools.Append(wx.ID_ANY, "&GPS Satellites...",
                                 "Show satellite signal levels")
        tools.AppendSeparator()
        self.locClear = tools.Append(wx.ID_ANY, "&Clear location data...",
                                     "Remove GPS data from scan")
        tools.AppendSeparator()
        self.log = tools.Append(wx.ID_ANY, "&Log...",
                                "Program log")

        help = wx.Menu()
        self.helpLink = help.Append(wx.ID_HELP, "&Help...",
                                    "Link to help")
        help.AppendSeparator()
        self.sys = help.Append(wx.ID_ANY, "&System information...",
                               "Displays system information")
        help.AppendSeparator()
        self.about = help.Append(wx.ID_ABOUT, "&About...",
                                 "Information about this program")

        menuBar = wx.MenuBar()
        menuBar.Append(file, "&File")
        menuBar.Append(edit, "&Edit")
        menuBar.Append(view, "&View")
        menuBar.Append(scan, "&Scan")
        menuBar.Append(tools, "&Tools")
        menuBar.Append(help, "&Help")
        self.menuBar = menuBar

    def set_state(self, state, spectrum, locations):
        self.new.Enable(state)
        self.open.Enable(state)
        self.merge.Enable(state and len(spectrum))
        self.restore.Enable(state)
        self.exportScan.Enable(state and len(spectrum))
        self.exportImage.Enable(state)
        self.exportSeq.Enable(state and len(spectrum))
        self.exportGeo.Enable(state and len(spectrum) and len(locations) > 4)
        self.exportTrack.Enable(state and len(locations))
        self.exportCont.Enable(state)
        self.page.Enable(state)
        self.preview.Enable(state)
        self.printer.Enable(state)
        self.properties.Enable(len(spectrum))
        self.start.Enable(state)
        self.cont.Enable(state and len(spectrum))
        self.stop.Enable(not state)
        self.pref.Enable(state)
        self.advPref.Enable(state)
        self.devicesRtl.Enable(state)
        self.devicesGps.Enable(state)
        self.reset.Enable(state)
        self.smooth.Enable(state and len(spectrum))
        self.cal.Enable(state)
        self.locClear.Enable(state and len(locations))
        self.stopEnd.Enable(not state)
        self.sweepClear.Enable(state and len(spectrum))
        self.sweepRemain.Enable(state and len(spectrum))


class PopMenuMain(object):
    def __init__(self, settings):
        self.settings = settings

        self.menu = wx.Menu()

        self.start = self.menu.Append(wx.ID_ANY, "&Start",
                                      "Start scan")
        self.cont = self.menu.Append(wx.ID_ANY, "&Continue",
                                     "Continue scan")
        self.stop = self.menu.Append(wx.ID_ANY, "S&top",
                                     "Stop scan immediately")
        self.stopEnd = self.menu.Append(wx.ID_ANY, "Stop at &end",
                                        "Complete current sweep "
                                        "before stopping")
        self.menu.AppendSeparator()
        self.sweepDelay = self.menu.Append(wx.ID_ANY, "Delay...",
                                           "Delay between sweeps")
        self.menu.AppendSeparator()
        self.rangeLim = self.menu.Append(wx.ID_ANY,
                                         "Set range to current zoom",
                                         "Set scanning range to the "
                                         "current zoom")
        self.menu.AppendSeparator()
        self.pointsLim = self.menu.Append(wx.ID_ANY,
                                          "Limit points",
                                          "Limit points to "
                                          "increase plot_line speed",
                                          kind=wx.ITEM_CHECK)
        self.pointsLim.Check(settings.pointsLimit)

        self.menu.AppendSeparator()
        self.clearSelect = self.menu.Append(wx.ID_ANY, "Clear selection",
                                            "Clear current selection")
        self.showMeasure = self.menu.Append(wx.ID_ANY,
                                            "Show &measurements",
                                            "Show measurements window",
                                            kind=wx.ITEM_CHECK)
        self.showMeasure.Check(settings.showMeasure)

        self.menu.AppendSeparator()
        self.fullScreen = self.menu.Append(wx.ID_ANY, "Full screen\tF11",
                                           "Toggle full screen",
                                           kind=wx.ITEM_CHECK)

    def set_state(self, state, spectrum):
        self.start.Enable(state)
        self.cont.Enable(state and len(spectrum))
        self.stop.Enable(not state)
        self.stopEnd.Enable(not state)
        self.rangeLim.Enable(state)


if __name__ == '__main__':
    print 'Please run rtlsdr_scan.py'
    exit(1)
