#! /usr/bin/python3
# -*- coding:utf-8 -*-
#
# Copyright 2012-2013 "Korora Project" <dev@kororaproject.org>
# Copyright 2013 "Manjaro Linux" <support@manjaro.org>
# Copyright 2014 Antergos
#
# Antergos Welcome is free software: you can redistribute it and/or modify
# it under the temms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Antergos Welcome is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Antergos Welcome. If not, see <http://www.gnu.org/licenses/>.
#

""" Welcome screen for Antergos """

import inspect
import os
import signal
import subprocess
import sys
import urllib.request
import urllib.error
import webbrowser

from simplejson import dumps as to_json

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
from gi.repository import Gtk, GLib, WebKit2


class WelcomeConfig(object):
    """ Manages Welcome configuration """

    def __init__(self):
        # store our base architecture
        if os.uname()[4] == 'x86_64':
            self._arch = '64-bit'
        else:
            self._arch = '32-bit'

        # store we are a live CD session
        self._live = os.path.exists('/bootmnt/antergos')

        # store full path to our binary
        self._welcome_bin_path = os.path.abspath(inspect.getfile(inspect.currentframe()))

        # store directory to our welcome configuration
        self._config_dir = os.path.expanduser('~/.config/antergos/welcome/')

        # store full path to our autostart symlink
        self._autostart_path = os.path.expanduser('~/.config/autostart/antergos-welcome.desktop')

        # ensure our config directory exists
        if not os.path.exists(self._config_dir):
            try:
                os.makedirs(self._config_dir)
            except OSError:
                pass
        # does autostart symlink exist
        self._autostart = os.path.exists(self._autostart_path)

    @property
    def arch(self):
        return self._arch

    @property
    def autostart(self):
        return self._autostart

    @autostart.setter
    def autostart(self, state):
        if state and not os.path.exists(self._autostart_path):
            # create the autostart symlink
            try:
                os.symlink(
                    '/usr/share/applications/antergos-welcome.desktop',
                    self._autostart_path)
            except OSError:
                pass
        elif not state and os.path.exists(self._autostart_path):
            # remove the autostart symlink
            try:
                os.unlink(self._autostart_path)
            except OSError:
                pass

        # determine autostart state based on absence of the disable file
        self._autostart = os.path.exists(self._autostart_path)

    @property
    def live(self):
        return self._live


class AppView(WebKit2.WebView):
    def __init__(self):
        WebKit2.WebView.__init__(self)

        self._config = WelcomeConfig()

        self.connect('load-changed', self._load_changed_cb)
        self.connect('load-failed', self._load_failed_cb)

    def _push_config(self):
        self.run_javascript("$('#arch').html('%s')" % self._config.arch)
        self.run_javascript(
            "$('#autostart').toggleClass('icon-check', %s).toggleClass(\
            'icon-check-empty', %s)" % (to_json(self._config.autostart),
                                        to_json(not self._config.autostart)))
        if self._config.live:
            self.run_javascript("$('#install').toggleClass('hide', false);")
            self.run_javascript(
                "$('#install-cli').toggleClass('hide', false);")
        else:
            self.run_javascript("$('#build').toggleClass('hide', false);")
            self.run_javascript("$('#donate').toggleClass('hide', false);")

    def _load_changed_cb(self, view, load_event):
        if load_event == WebKit2.LoadEvent.FINISHED:
            self._push_config()
        elif load_event == WebKit2.LoadEvent.STARTED:
            uri = view.get_uri()
            try:
                if uri.index('#') > 0:
                    uri = uri[:uri.index('#')]
            except ValueError:
                pass

            if uri.startswith('cmd://'):
                self._do_command(uri)

    def _load_failed_cb(self, view, load_event, failing_uri, error):
        # Returns True to stop other handlers from being invoked for the event
        return True

    def _do_command(self, uri):
        if uri.startswith('cmd://'):
            uri = uri[6:]

        if uri == 'gnome-help':
            subprocess.Popen(['yelp'])
        elif uri == 'kde-help':
            subprocess.Popen(['khelpcenter'])
        # elif uri == 'install':
            # subprocess.Popen(['sudo','live-installer'])
        # elif uri == 'install-cli':
            # subprocess.Popen(['xdg-terminal','sudo setup'])
        elif uri == 'close':
            Gtk.main_quit()
        elif uri == 'toggle-startup':
            # toggle autostart
            self._config.autostart ^= True
            self._push_config()
        elif uri.startswith("link?"):
            webbrowser.open_new_tab(uri[5:])
        else:
            print('Unknown command: %s' % uri)


class WelcomeApp(object):
    def __init__(self):
        # establish our location
        self._location = os.path.dirname(
            os.path.abspath(inspect.getfile(inspect.currentframe())))

        # check for relative path
        if(os.path.exists(os.path.join(self._location, 'data/'))):
            print('Using relative path for data source.\
                   Non-production testing.')
            self._data_path = os.path.join(self._location, 'data/')
        elif(os.path.exists('/usr/share/antergos-welcome/')):
            print('Using /usr/share/antergos-welcome/ path.')
            self._data_path = '/usr/share/antergos-welcome/'
        else:
            print('Unable to source the antergos-welcome data directory.')
            sys.exit(1)

        self._build_app()

    def _build_app(self):
        # build window
        w = Gtk.Window()
        w.set_position(Gtk.WindowPosition.CENTER)
        w.set_wmclass('Antergos Welcome', 'Antergos Welcome')
        w.set_title('')
        w.set_size_request(768, 496)

        icon_dir = os.path.join(self._data_path, 'img', 'antergos-icon.png')
        w.set_icon_from_file(icon_dir)

        # build webkit container
        mv = AppView()

        # load our index file
        file = os.path.abspath(os.path.join(self._data_path, 'index.html'))
        uri = 'file://' + urllib.request.pathname2url(file)
        mv.load_uri(uri)

        # build scrolled window widget and add our appview container
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(mv)

        # build a an autoexpanding box and add our scrolled window
        b = Gtk.VBox(homogeneous=False, spacing=0)
        b.pack_start(sw, expand=True, fill=True, padding=0)

        # add the box to the parent window and show
        w.add(b)
        w.connect('delete-event', self.close)
        w.show_all()

        self._window = w
        self._appView = mv

    def run(self):
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        Gtk.main()

    def close(self, p1, p2):
        Gtk.main_quit(p1, p2)

app = WelcomeApp()
app.run()
