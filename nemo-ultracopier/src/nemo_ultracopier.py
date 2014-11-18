#! /usr/bin/python
#  -*- coding: utf-8 -*-

# Nemo-UltraCopier-Extension
#==========================
#
# An utility to integrate UltraCopier in the Nemo file manager.
#
# Author: Lester Carballo Pérez(lestcape@gmail.com)

from gi.repository import Gtk, Gdk, Nemo, GObject, Gio, GLib
import os
import gettext
import locale

# initialize i18n
locale.setlocale(locale.LC_ALL, '')
gettext.bindtextdomain('nemo-ultracopier')
gettext.textdomain('nemo-ultracopier')
_ = gettext.gettext

FILE_ACCEL = ".config/ultracopier-keybind.conf"
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
        '''Called one time to Init the keybindings'''
        self.accel_group = Gtk.AccelGroup()
        path = self.accel_file.get_path()
        accel_name = self.read_accel_from_file()
        if accel_name == "":
            self.restore_accel(KEY_ACCEL)
        else:
            key, mods = Gtk.accelerator_parse(accel_name)
            if Gtk.accelerator_valid(key, mods):
                self.accel_group.connect(key, mods, Gtk.AccelFlags.VISIBLE, self.callback_accel)
            else:
                self.restore_accel(KEY_ACCEL)
        self.accel_name = accel_name
        self.monitor = self.accel_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.monitor_id = self.monitor.connect("changed", self.on_monitor_change_file)

    def read_accel_from_file(self):
        '''Called when the file of keybindings change'''
        path = self.accel_file.get_path()
        accel_name = KEY_ACCEL
        if not os.path.isfile(path):
            accel_qt = self.accel_to_qt(accel_name)
            file = open(path, "w")
            file.write("%s" %(accel_qt))
            file.close()
        else:
            file = open(path, "r")
            accel_qt = file.readline().rstrip()
            file.close()
            accel_name = self.accel_to_gtk(accel_qt)
        return accel_name

    def restore_accel(self, accel):
        '''Called when the user select a wrong keybindings'''
        accel = self.accel_to_qt(accel)
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
        '''Called when the user enter in a new background'''
        default_accel_group = Gtk.accel_groups_from_object(window)[0]
        if (window not in self.source_windows):
            self.source_windows[window] = [file, default_accel_group, False]
            window.connect("focus_in_event", self.on_focus_in_window)
            window.connect("destroy", self.on_destroy)
        else:
            self.source_windows[window][0] = file

        if file:
            uri = file.get_uri()
            if (uri.startswith("x-nemo-desktop:")) or (uri.startswith("x-nautilus-desktop:")):
                uri = "file://%s" %(GLib.get_user_special_dir(GLib.USER_DIRECTORY_DESKTOP))
            src_file = Gio.File.new_for_uri(uri)
            self.src_path = src_file.get_path()

    def accel_to_gtk(self, accel_name):
        '''Called to translate QT accel to Gtk'''
        translate_accel = ""
        list_accel = accel_name.split(",")
        if (len(list_accel) > 0):
            list_keys = list_accel[0].split("+")
            number_keys = len(list_keys)
            for pos, val in enumerate(list_keys):
               if val == "Ctrl":
                   val = "Control"
               if val == "Meta":
                   val = "Super"
               if(pos != number_keys - 1):
                   translate_accel += "<" + val + ">"
               else:
                   translate_accel += val
        return translate_accel

    def accel_to_qt(self, accel_name):
        '''Called to translate Gtk accel to QT'''
        translate_accel = ""
        list_accel = accel_name.split(">")
        number_keys = len(list_accel)
        if (number_keys > 0):
            for pos, val in enumerate(list_accel):
               if val[0] == "<":
                   val = val[1:]
               if val == "Control":
                   val = "Ctrl"
               if val == "Super":
                   val = "Meta"
               if pos != number_keys - 1:
                   translate_accel += val + "+"
               else:
                   translate_accel += val
        return translate_accel

    def on_destroy(self, window):
        '''Called when the user close a windows'''
        if self.window_accel_group == window:
            self.window_accel_group.remove_accel_group(self.accel_group)
            self.window_accel_group = None
        if (window in self.source_windows):
            del self.source_windows[window]

    def on_focus_in_window(self, window, ref):
        '''Called when the user select a new windows'''
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
        '''Called when the user modify the file of keybining'''
        if self.call_timeout == 0:
            self.call_timeout = GObject.timeout_add(100, self.on_change_accel)

    def on_change_accel(self):
        '''Called when the user swap the keybining'''
        if self.call_timeout > 0:
            GObject.source_remove(self.call_timeout)
            self.call_timeout = 0
        accel_name = self.read_accel_from_file()
        if accel_name == "":
            self.restore_accel(self.accel_name)
        else:
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
        '''Called when the user swap to a valid the keybining'''
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
        '''Called when the user use Control+V'''
        self._menu_paste()

    def callback_accel(self, a_groups, window, key, gdk_mask):
        '''Called when the user don't use Control+V'''
        self._menu_paste()

    def on_clipboard_change(self, *args):
        '''Called when the user add new values to the clipboard'''
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

    def get_file_items(self, window, files):
        '''Called when the user selects a file in Nemo. We want to check
        whether those are supported files or directories with supported files.'''
        if (len(files) != 1) or (not self._valid_file(files[0])) or (not files[0].is_directory()):
            return []

        self.pasteItem = Nemo.MenuItem(name='UltraCopier::Paste_UltraCopier_item',
                              label=_('Paste on folder with UltraCopier'),
                              tip=_('Move or copy files previously selected by a Cut or Copy command in to the current folder'),
                              icon='nemo-ultracopier',
                              sensitive=False)
        
        src_file = Gio.File.new_for_uri(files[0].get_uri())
        self.pasteItem.connect("activate", self._menu_paste_on_folder, src_file.get_path())
        if (self.action not in ["copy","cut"]) or (self.file_list is ""):
            self.pasteItem.set_property("sensitive", False)
        else:
            self.pasteItem.set_property("sensitive", True)
        return self.pasteItem,

    def get_background_items(self, window, file):
        '''Called when the user selects the background in Nemo. We want to check
        whether those are supported files or directories with supported files.'''
        self.create_default_accel(window, file)
        self.pasteItem = Nemo.MenuItem(name='UltraCopier::Paste_UltraCopier_Folder_item',
                              label=_('Paste with UltraCopier'),
                              tip=_('Move or copy files previously selected by a Cut or Copy command'),
                              icon='nemo-ultracopier',
                              sensitive=True)
        self.settingItem = Nemo.MenuItem(name='UltraCopier::Setting_UltraCopier_Folder_item',
                              label=_('UltraCopier Settings'),
                              tip=_('Configure the ultracopier settings'),
                              icon='gtk-preferences',
                              sensitive=True)
        list_items = [self.pasteItem,] 
        uri = file.get_uri()
        if (uri.startswith("x-nemo-desktop:")) or (uri.startswith("x-nautilus-desktop:")):
            uri = "file://%s" %(GLib.get_user_special_dir(GLib.USER_DIRECTORY_DESKTOP))
            list_items.append(self.settingItem)
        src_file = Gio.File.new_for_uri(uri)
        self.src_path = src_file.get_path()
        self.pasteItem.connect("activate", self._menu_paste)
        self.settingItem.connect("activate", self._menu_settings, window)
        return list_items

    def _valid_file(self, file):
        '''Tests if the file is valid comparable'''
        if file.get_uri_scheme() == 'file' and file.get_file_type() in (Gio.FileType.DIRECTORY, Gio.FileType.REGULAR, Gio.FileType.SYMBOLIC_LINK):
            return True
        else:
            return False

    def _menu_paste_on_folder(self, menu, folder):
        '''Called when the user selects the menu.
        Launch CopyUltraCopier with the files selected.'''
        if (self.file_list is not ""):
            if self.action == "copy":
                os.system("ultracopier cp %s '%s' &" % (self.file_list, folder))
            elif self.action == "cut":
                os.system("ultracopier mv %s '%s' &" % (self.file_list, folder))
                self.clipboard.set_text(" ")
                self.clipboard.store()

    def _menu_paste(self, menu=None):
        '''Called when the user selects the backgroud menu or used
        keyboard instead. Launch CopyUltraCopier with the files selected.'''
        self._menu_paste_on_folder(menu, self.src_path)

    def _menu_settings(self, menu, window):
        AccelChanger(window)

SPECIAL_MODS = (["Super_L", "<Super>"],
                ["Super_R", "<Super>"],
                ["Alt_L", "<Alt>"],
                ["Alt_R", "<Alt>"],
                ["Control_L", "<Primary>"],
                ["Control_R", "<Primary>"],
                ["Shift_L", "<Shift>"],
                ["Shift_R", "<Shift>"])

class AccelChanger:
    def __init__(self, window):
        self.teaching = False
        self.dialog = Gtk.Dialog(title=_("UltraCopier Accel Changer"), parent=window, flags=Gtk.DialogFlags.MODAL)
        theme = Gtk.IconTheme.get_default()
        windowicon = theme.load_icon('nemo-ultracopier', 48, 0)
        self.dialog.connect("destroy", self.on_destroy)

        accel_box = Gtk.VBox.new(homogeneous=False, spacing=0)
        accel_box.set_hexpand(True)

        style_c = accel_box.get_style_context()
        style_c.add_class(Gtk.STYLE_CLASS_LINKED)
        self.dialog.get_content_area().add(accel_box)

        self.label = Gtk.Label(_("UltraCopier accel changer for the Paste action..."))
        self.entry = Gtk.Entry()
        self.entry.set_editable(False)
        self.entry.set_tooltip_text(_("Click to set a new accelerator key.\nPress Escape or click again to cancel the operation."))
        self.dialog.set_size_request(400, 50)
        self.entry.set_hexpand(True)
        accel_box.pack_start(self.label, False, False, 0)
        accel_box.pack_start(self.entry, False, False, 1)

        self.dialog.show_all()

        self.call_timeout = 0
        path = os.path.join(os.path.expanduser("~"), FILE_ACCEL)
        self.accel_file = Gio.File.new_for_path(path)
        self.monitor = self.accel_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.monitor_id = self.monitor.connect("changed", self.on_monitor_change_file)

        self.accel_name = self.accel_to_qt(KEY_ACCEL)
        if os.path.isfile(path):
            self.try_to_show()
        else:
            self.restore_accel(KEY_ACCEL)

        self.entry.connect("button-press-event", self.on_entry_focus)

    def on_entry_focus(self, widget, event, data=None):
        self.teach_button = widget
        if not self.teaching:
            device = Gtk.get_current_event_device()
            if device.get_source() == Gdk.InputSource.KEYBOARD:
                self.keyboard = device
            else:
                self.keyboard = device.get_associated_device()

            self.keyboard.grab(self.get_window(), Gdk.GrabOwnership.WINDOW, False,
                               Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.KEY_RELEASE_MASK,
                               None, Gdk.CURRENT_TIME)
            self.entry.set_text(_("Pick an accelerator..."))
            self.event_id = self.dialog.connect("key-release-event", self.on_key_release)
            self.teaching = True
        else:
            if self.event_id:
                self.dialog.disconnect(self.event_id)
            self.ungrab()
            self.set_button_text()
            self.teaching = False
            self.teach_button = None

    def on_key_release(self, widget, event):
        self.dialog.disconnect(self.event_id)
        self.ungrab()
        self.event_id = None
        if event.keyval == Gdk.KEY_Escape:
            self.set_button_text()
            self.teaching = False
            self.teach_button = None
            return True
        accel_string = Gtk.accelerator_name(event.keyval, event.state)
        accel_string = self.sanitize(accel_string)
        accel_string = self.accel_to_qt(accel_string)
        if(accel_string[len(accel_string) - 1] == "+"):
           accel_string = self.accel_name
        if self.accel_name != accel_string:
           self.accel_name = accel_string
           self.write_accel_to_file()
        self.set_button_text()
        self.teaching = False
        self.teach_button = None
        return True

    def get_window(self):
        return self.dialog.get_window();

    def set_button_text(self):
        self.entry.set_text(self.accel_name)

    def ungrab(self):
        self.keyboard.ungrab(Gdk.CURRENT_TIME)

    def sanitize(self, string):
        accel_string = string.replace("<Mod2>", "")
        accel_string = accel_string.replace("<Mod4>", "")
        for single, mod in SPECIAL_MODS:
            if single in accel_string and mod in accel_string:
                accel_string = accel_string.replace(mod, "")
            if single in accel_string:
                accel_string = accel_string.replace(single, mod)
        return accel_string

    def try_to_show(self):
        accel_name = self.read_accel_from_file()
        if accel_name != "":
            key, mods = Gtk.accelerator_parse(accel_name)
            if Gtk.accelerator_valid(key, mods):
                self.accel_name = self.accel_to_qt(accel_name)
                self.entry.set_text(self.accel_name)

    def on_monitor_change_file(self, monitor, file, o, event):
        if self.call_timeout == 0:
            self.call_timeout = GObject.timeout_add(100, self.on_change_key)

    def on_change_key(self):
        if self.call_timeout > 0:
            GObject.source_remove(self.call_timeout)
            self.call_timeout = 0
        self.try_to_show()

    def read_accel_from_file(self):
        '''Called when the file of keybindings change'''
        path = self.accel_file.get_path()
        accel_name = KEY_ACCEL
        if not os.path.isfile(path):
            accel_qt = self.accel_to_qt(accel_name)
            file = open(path, "w")
            file.write("%s" %(accel_qt))
            file.close()
        else:
            file = open(path, "r")
            accel_qt = file.readline().rstrip()
            file.close()
            accel_name = self.accel_to_gtk(accel_qt)
        return accel_name

    def write_accel_to_file(self):
        '''Called when the file of keybindings change'''
        if self.monitor_id > 0:
            self.monitor.disconnect(self.monitor_id)
        path = self.accel_file.get_path()
        file = open(path, "w")
        file.seek(0)
        file.write("%s" %(self.accel_name))
        file.truncate()
        file.close()
        self.monitor_id = self.monitor.connect("changed", self.on_monitor_change_file)

    def restore_accel(self, accel):
        '''Called when the user select a wrong keybindings'''
        accel = self.accel_to_qt(accel)
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
        msg = "The current shortcut key is not valid, we return to use '%s' as a shortcut key."%(accel)
        dialog.set_markup("<b>%s</b>" % msg)
        dialog.run()
        dialog.destroy()
        self.monitor_id = self.monitor.connect("changed", self.on_monitor_change_file)

    def accel_to_upper(self, accel_name):
        translate_accel = ""
        list_accel = accel_name.split(">")
        number_keys = len(list_accel)
        if (number_keys > 0):
            for pos, val in enumerate(list_accel):
               if val[0] != "<":
                   val = val.upper()
               if pos != number_keys - 1:
                   translate_accel += val + "+"
               else:
                   translate_accel += val
        return translate_accel

    def accel_to_gtk(self, accel_name):
        translate_accel = ""
        list_accel = accel_name.split(",")
        if (len(list_accel) > 0):
            list_keys = list_accel[0].split("+")
            number_keys = len(list_keys)
            for pos, val in enumerate(list_keys):
               if(pos != number_keys - 1):
                   translate_accel += "<" + val + ">"
               else:
                   translate_accel += val
        return translate_accel

    def accel_to_qt(self, accel_name):
        translate_accel = ""
        list_accel = accel_name.split(">")
        number_keys = len(list_accel)
        if (number_keys > 0):
            for pos, val in enumerate(list_accel):
                if (len(val) > 0):
                    if (val[0] == "<"):
                        val = val[1:]
                    else:
                        val = val.upper()
                if (val == "Control") or (val == "Primary"):
                    val = "Ctrl"
                if (val == "Super"):
                    val = "Meta"
                if pos != number_keys - 1:
                    translate_accel += val + "+"
                else:
                    translate_accel += val
        return translate_accel

    def on_destroy(self, *arg):
        if self.call_timeout > 0:
            GObject.source_remove(self.call_timeout)
            self.call_timeout = 0
