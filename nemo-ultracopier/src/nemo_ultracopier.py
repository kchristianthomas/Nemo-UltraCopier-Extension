#! /usr/bin/python
#  -*- coding: utf-8 -*-

from gi.repository import Gtk, Gdk, Nemo, GObject, Gio
import mimetypes
import os
import urllib
import gettext
import locale

# initialize i18n
locale.setlocale(locale.LC_ALL, '')
gettext.bindtextdomain('nemo-ultracopier')
gettext.textdomain('nemo-ultracopier')
_ = gettext.gettext

class UltraCopier(GObject.GObject, Nemo.MenuProvider):
    def __init__(self):
        pass

    def get_file_items(self, window, files):
        '''Called when the user selects a file in Nautilus. We want to check
        whether those are supported files or directories with supported files.'''

        if (len(files) != 1) or (not self._valid_file(files[0])) or (not files[0].is_directory()):
            return []

        [action, fileList] = self._clipboard_data()
        if (action not in ["copy","cut"]) or (fileList is ""):
            return []

        pasteItem = Nemo.MenuItem(name='UltraCopier::Paste_UltraCopier_item',
                              label=_('Paste on folder with UltraCopier'),
                              tip=_('Move or copy files previously selected by a Cut or Copy command in to the current folder'),
                              icon='nemo-ultracopier')
        pasteItem.connect("activate", self._menu_paste, urllib.unquote(files[0].get_uri()[7:]), fileList, action)

        return pasteItem,

    def get_background_items(self, window, file):
        [action, fileList] = self._clipboard_data()
        if (action not in ["copy","cut"]) or (fileList is ""):
            return []

        pasteItem = Nemo.MenuItem(name='UltraCopier::Paste_UltraCopier_Folder_item',
                              label=_('Paste with UltraCopier'),
                              tip=_('Move or copy files previously selected by a Cut or Copy command'),
                              icon='nemo-ultracopier')
        pasteItem.connect("activate", self._menu_paste, urllib.unquote(file.get_uri()[7:]), fileList, action)
        return pasteItem,

    def _valid_file(self, file):
        '''Tests if the file is valid comparable'''
        if file.get_uri_scheme() == 'file' and file.get_file_type() in (Gio.FileType.DIRECTORY, Gio.FileType.REGULAR, Gio.FileType.SYMBOLIC_LINK):
            return True
        else:
            return False

    def _clipboard_data(self):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        src_files = clipboard.wait_for_contents(Gdk.Atom.intern("x-special/gnome-copied-files", False))
        if src_files is not None:
            info = src_files.get_data().splitlines()
            action = info[0]
            files = info[1:]
            fileList = ""
            for file in files:
                if file.index("file://") == 0:
                   fileList += " '" + urllib.unquote(file[7:]) + "'"
            return [action, fileList]
        return ["", ""]

    def _menu_paste(self, menu, out_folder, src_files, action):
        '''Called when the user selects the menu.
        Launch CopyUltraCopier with the files selected.'''
        if action == "copy":
            os.system("ultracopier cp %s '%s' &" % (src_files, out_folder))
        elif action == "cut":
            os.system("ultracopier mv %s '%s' &" % (src_files, out_folder))
