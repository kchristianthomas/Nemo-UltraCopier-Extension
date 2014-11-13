#! /usr/bin/python
#  -*- coding: utf-8 -*-

from gi.repository import Gtk, Gdk, Nemo, GObject, Gio, GLib
import mimetypes
import os
import urllib
import re
import gettext
import locale

# initialize i18n
locale.setlocale(locale.LC_ALL, '')
gettext.bindtextdomain('nemo-ultracopier')
gettext.textdomain('nemo-ultracopier')
_ = gettext.gettext

FILE_ACCEL = ".config-ultracopier"
KEY_ACCEL = "<Control>U"
PATH_ACCEL = "<Actions>/UltraActions/Paste"
KEY_DEFAULT_ACCEL = "<Control>V"
PATH_DEFAULT_ACCEL = "<Actions>/DirViewActions/Paste"

class UltraCopier(GObject.GObject, Nemo.MenuProvider):
    def __init__(self):
        self.action = ""
        self.file_list = ""
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.clipboard.connect('owner-change', self.on_clipboard_change)
        self.accel_name = KEY_ACCEL
        self.accel_path = PATH_ACCEL
        self.default_accel_name = KEY_DEFAULT_ACCEL
        self.default_accel_path = PATH_DEFAULT_ACCEL
        path = os.path.join(os.path.expanduser("~"), FILE_ACCEL)
        self.accel_file = Gio.File.new_for_path(path)
        self.init_accel()
        self.source_windows = {}
        self.window_accel_group = None
        self.call_timeout = 0

    def init_accel(self):
        path = self.accel_file.get_path()
        self.accel_name = self.read_accel_from_file()
        self.monitor = self.accel_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.monitor_id = self.monitor.connect("changed", self.on_monitor_change_file)
        self.accel_group = Gtk.AccelGroup()
        key, mods = Gtk.accelerator_parse(self.accel_name)
        if Gtk.accelerator_valid(key, mods):
            self.accel_group.connect(key, mods, Gtk.AccelFlags.VISIBLE, self.callback_accel)
        else:
            self.restore_accel(KEY_ACCEL)

    def read_accel_from_file(self):
        path = self.accel_file.get_path()
        accel_name = KEY_ACCEL
        if not os.path.isfile(path):
            file = open(path, "w")
            file.write("%s" %(accel_name))
            file.close()
        else:
            file = open(path, "r")
            accel_name = file.readline().rstrip()
            file.close()
        return accel_name

    def restore_accel(self, accel):
        if self.monitor_id > 0:
            self.monitor.disconnect(self.monitor_id)
        path = self.accel_file.get_path()
        if os.path.isfile(path):
            file = open(path, "w")
            file.seek(0)
            file.write("%s" %(accel))
            file.truncate()
            file.close()
        else:
            file = open(path, "w")
            file.write("%s" %(accel))
            file.close()
        dialog = Gtk.MessageDialog(None, Gtk.DialogFlags.MODAL, Gtk.MessageType.INFO, Gtk.ButtonsType.OK)
        accel = accel.replace("<", "&lt;").replace(">", "&gt;")
        msg = _("The current shortcut key is not valid, we return to use '%s' as a shortcut key.")%(accel)
        dialog.set_markup("<b>%s</b>" % msg)
        dialog.run()
        dialog.destroy()
        self.monitor_id = self.monitor.connect("changed", self.on_monitor_change_file)

    def create_default_accel(self, window, file):
        default_accel_group = Gtk.accel_groups_from_object(window)[0]
        if (window not in self.source_windows):
            self.source_windows[window] = [file, default_accel_group, False]
            window.connect("focus_in_event", self.on_focus_in_window)
            window.connect("destroy", self.on_destroy)

    def on_destroy(self, window):
        if self.window_accel_group == window:
            self.window_accel_group.remove_accel_group(self.accel_group)
            self.window_accel_group = None
        if (window in self.source_windows):
            del self.source_windows[window]

    def on_focus_in_window(self, window, ref):
        if (self.accel_name == self.default_accel_name):
            if (not self.source_windows[window][2]):
                key, mods = Gtk.accelerator_parse(self.accel_name)
                default_accel_group = self.source_windows[window][1]
                if (default_accel_group.disconnect_key(key, mods)):
                    default_accel_group.connect_by_path(self.default_accel_path, self.callback_accel_default)
                    self.source_windows[window][2] = True
        else:
            accel_list = Gtk.accel_groups_from_object(window)
            if (self.accel_group not in accel_list):
                if self.window_accel_group:
                    self.window_accel_group.remove_accel_group(self.accel_group)
                window.add_accel_group(self.accel_group)
                self.window_accel_group = window
            if (self.source_windows[window][2]):
                key, mods = Gtk.accelerator_parse(self.accel_name)
                self.source_windows[window][1].disconnect_key(key, mods)
                self.source_windows[window][2] = False
        file = self.source_windows[window][0]
        if file:
            uri = file.get_uri()
            if (uri.startswith("x-nemo-desktop:")) or (uri.startswith("x-nautilus-desktop:")):
                uri = "file://%s" %(GLib.get_user_special_dir(GLib.USER_DIRECTORY_DESKTOP))
            src_file = Gio.File.new_for_uri(uri)
            self.src_path = src_file.get_path()

    def on_monitor_change_file(self, monitor, file, o, event):
        if self.call_timeout == 0:
            self.call_timeout = GObject.timeout_add(100, self.on_change_accel)

    def on_change_accel(self):
        if self.call_timeout > 0:
            GObject.source_remove(self.call_timeout)
            self.call_timeout = 0
        accel_name = self.read_accel_from_file()
        key, mods = Gtk.accelerator_parse(accel_name)
        if Gtk.accelerator_valid(key, mods):
            if self.accel_name == self.default_accel_name:
                dialog = Gtk.MessageDialog(None, Gtk.DialogFlags.MODAL, Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO)
                dialog.set_markup("<b>%s</b>" % _("Will be required restart Nemo to be used again the standard shortcut key."))
                dialog.format_secondary_markup(_("Do you want to restart Nemo?"))
                response = dialog.run()
                dialog.destroy()
                if response == Gtk.ResponseType.YES:
                   os.system("nemo -q &")
            else:
                self.change_accel(accel_name)
        else:
            self.restore_accel(self.accel_name)

    def change_accel(self, accel_name=""):
        if accel_name != self.accel_name: 
            if self.window_accel_group:
                self.window_accel_group.remove_accel_group(self.accel_group)
                self.window_accel_group = None
            key, mods = Gtk.accelerator_parse(self.accel_name)
            if accel_name == self.default_accel_name:
                for window in self.source_windows:
                    default_accel_group = self.source_windows[window][1]
                    if (not self.source_windows[window][2]) and (default_accel_group.disconnect_key(key, mods)):
                        default_accel_group.connect_by_path(self.default_accel_path, self.callback_accel_default)
                        self.source_windows[window][2] = True
            else:
                for window in self.source_windows:
                    if (self.source_windows[window][2]):
                        self.source_windows[window][1].disconnect_key(key, mods)
                        self.source_windows[window][2] = False
                self.accel_group.disconnect_key(key, mods)
                key, mods = Gtk.accelerator_parse(accel_name)
                self.accel_group.connect(key, mods, Gtk.AccelFlags.VISIBLE, self.callback_accel)
            self.accel_name = accel_name

    def callback_accel_default(self, *arg):
        self._menu_paste()

    def callback_accel(self, a_groups, window, key, gdk_mask):
        self._menu_paste()

    def on_clipboard_change(self, *args):
        self._update_clipboard_data()

    def get_file_items(self, window, files):
        '''Called when the user selects a file in Nautilus. We want to check
        whether those are supported files or directories with supported files.'''
        if (len(files) != 1) or (not self._valid_file(files[0])) or (not files[0].is_directory()):
            return []

        self.create_default_accel(window, files[0])

        self.pasteItem = Nemo.MenuItem(name='UltraCopier::Paste_UltraCopier_item',
                              label=_('Paste on folder with UltraCopier'),
                              tip=_('Move or copy files previously selected by a Cut or Copy command in to the current folder'),
                              icon='nemo-ultracopier',
                              sensitive=False)
        
        src_file = Gio.File.new_for_uri(files[0].get_uri())
        self.src_path = src_file.get_path()
        self.pasteItem.connect("activate", self._menu_paste)
        if (self.action not in ["copy","cut"]) or (self.file_list is ""):
            self.pasteItem.set_property("sensitive", False)
        else:
            self.pasteItem.set_property("sensitive", True)
        return self.pasteItem,

    def get_background_items(self, window, file):
        self.create_default_accel(window, file)
        self.pasteItem = Nemo.MenuItem(name='UltraCopier::Paste_UltraCopier_Folder_item',
                              label=_('Paste with UltraCopier'),
                              tip=_('Move or copy files previously selected by a Cut or Copy command'),
                              icon='nemo-ultracopier',
                              sensitive=True)
        uri = file.get_uri()
        if (uri.startswith("x-nemo-desktop:")) or (uri.startswith("x-nautilus-desktop:")):
            uri = "file://%s" %(GLib.get_user_special_dir(GLib.USER_DIRECTORY_DESKTOP))
        src_file = Gio.File.new_for_uri(uri)
        self.src_path = src_file.get_path()
        self.pasteItem.connect("activate", self._menu_paste)
        return self.pasteItem,

    def _valid_file(self, file):
        '''Tests if the file is valid comparable'''
        if file.get_uri_scheme() == 'file' and file.get_file_type() in (Gio.FileType.DIRECTORY, Gio.FileType.REGULAR, Gio.FileType.SYMBOLIC_LINK):
            return True
        else:
            return False

    def _update_clipboard_data(self):
        self.action = ""
        self.file_list = ""
        src_files = self.clipboard.wait_for_contents(Gdk.Atom.intern("x-special/gnome-copied-files", False))
        if src_files is not None:
            info = src_files.get_data().splitlines()
            self.action = info[0]
            files = info[1:]
            for file_uri in files:
                try:
                    file = Gio.File.new_for_uri(file_uri)
                    if file.query_exists():
                        self.file_list += " '" + file.get_path() + "'"
                except:
                    pass

    def _menu_paste(self, menu=None):
        '''Called when the user selects the menu.
        Launch CopyUltraCopier with the files selected.'''
        if (self.file_list is not ""):
            if self.action == "copy":
                os.system("ultracopier cp %s '%s' &" % (self.file_list, self.src_path))
            elif self.action == "cut":
                os.system("ultracopier mv %s '%s' &" % (self.file_list, self.src_path))
                self.clipboard.set_text(" ")
                self.clipboard.store()
