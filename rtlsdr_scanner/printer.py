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

from PIL import Image
import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg
import wx


class PrintOut(wx.Printout):
    def __init__(self, graph, filename, pageConfig):
        wx.Printout.__init__(self, title=filename)
        self.figure = graph.get_figure()
        margins = (pageConfig.GetMarginTopLeft().Get()[0],
                   pageConfig.GetMarginTopLeft().Get()[1],
                   pageConfig.GetMarginBottomRight().Get()[0],
                   pageConfig.GetMarginBottomRight().Get()[1])
        self.margins = [v / 25.4 for v in margins]

    def __draw_image(self, sizeInches, ppi):
        oldSize = self.figure.get_size_inches()
        oldDpi = self.figure.get_dpi()
        self.figure.set_size_inches(sizeInches)
        self.figure.set_dpi(ppi)

        canvas = FigureCanvasAgg(self.figure)
        canvas.draw()
        renderer = canvas.get_renderer()
        if matplotlib.__version__ >= '1.2':
            buf = renderer.buffer_rgba()
        else:
            buf = renderer.buffer_rgba(0, 0)
        size = canvas.get_width_height()
        image = Image.frombuffer('RGBA', size, buf, 'raw', 'RGBA', 0, 1)

        self.figure.set_size_inches(oldSize)
        self.figure.set_dpi(oldDpi)

        imageWx = wx.EmptyImage(image.size[0], image.size[1])
        imageWx.SetData(image.convert('RGB').tostring())

        return imageWx

    def GetPageInfo(self):
        return 1, 1, 1, 1

    def HasPage(self, page):
        return page == 1

    def OnPrintPage(self, _page):
        dc = self.GetDC()
        if self.IsPreview():
            ppi = max(self.GetPPIScreen())
            sizePixels = dc.GetSize()
        else:
            ppi = max(self.GetPPIPrinter())
            sizePixels = self.GetPageSizePixels()
        width = (sizePixels[0] / ppi) - self.margins[1] - self.margins[3]
        height = (sizePixels[1] / ppi) - self.margins[0] - self.margins[2]
        sizeInches = (width, height)

        image = self.__draw_image(sizeInches, ppi)
        dc.DrawBitmap(image.ConvertToBitmap(),
                      self.margins[0] * ppi,
                      self.margins[1] * ppi)

        return True
