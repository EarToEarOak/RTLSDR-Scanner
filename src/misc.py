import cPickle
import os
import wx

from constants import FILE_HEADER


def open_plot(dirname, filename):
    try:
        handle = open(os.path.join(dirname, filename), 'rb')
        header = cPickle.load(handle)
        if header != FILE_HEADER:
            wx.MessageBox('Invalid or corrupted file', 'Warning',
                      wx.OK | wx.ICON_WARNING)
            return
        _version = cPickle.load(handle)
        start = cPickle.load(handle)
        stop = cPickle.load(handle)
        spectrum = cPickle.load(handle)
    except:
        wx.MessageBox('File could not be opened', 'Warning',
                      wx.OK | wx.ICON_WARNING)

    return start, stop, spectrum


def split_spectrum(spectrum):
    freqs = spectrum.keys()
    freqs.sort()
    powers = map(spectrum.get, freqs)

    return freqs, powers


def format_device_name(name):
    remove = ["/", "\\"]
    for char in remove:
        name = name.replace(char, " ")

    return name
