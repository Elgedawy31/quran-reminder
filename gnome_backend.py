"""Headless GLib scheduler and session D-Bus API for the GNOME Shell frontend."""
import json
import signal
import time

import gi
from gi.repository import Gio, GLib

from progress import ReadingProgress, TOTAL_AYAHS

BUS_NAME = "io.github.Elgedawy31.QuranReminder"
OBJECT_PATH = "/io/github/Elgedawy31/QuranReminder"
INTERFACE_XML = """<node><interface name="io.github.Elgedawy31.QuranReminder">
  <method name="Attach"><arg type="s" direction="out" name="state"/></method>
  <method name="Detach"/>
  <method name="GetState"><arg type="s" direction="out" name="state"/></method>
  <method name="Show"/>
  <method name="Hide"><arg type="u" direction="in" name="number"/></method>
  <method name="ConfirmRead"><arg type="u" direction="in" name="number"/></method>
  <signal name="StateChanged"><arg type="s" name="state"/></signal>
</interface></node>"""


class GnomeReminder:
    def __init__(self, app, connection, loop):
        self.app, self.connection, self.loop = app, connection, loop
        self.verses = json.loads((app.ROOT / "verses.json").read_text())["verses"]
        if len(self.verses) != TOTAL_AYAHS:
            raise RuntimeError("Incomplete Quran data")
        record = json.loads(app.STATE.read_text()) if app.STATE.exists() else {}
        self.progress = ReadingProgress.from_record(record)
        self.visible = True
        self.frontend = None
        self.timer = None
        self.next_due = 0
        self.running = True
        self.registration = connection.register_object(
            OBJECT_PATH, Gio.DBusNodeInfo.new_for_xml(INTERFACE_XML).interfaces[0],
            self.dispatch, None, None)
        self.subscription = connection.signal_subscribe(
            "org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged",
            "/org/freedesktop/DBus", None, Gio.DBusSignalFlags.NONE, self.owner_changed)
        self.persist()
        self.schedule()

    def state(self):
        verse = self.verses[self.progress.number - 1]
        return {"running": self.running, "visible": self.visible,
                "backend": "gnome", "frontend_connected": self.frontend is not None,
                "number": self.progress.number, "arabic": verse["arabic"],
                "reference": f'{verse["surah_name"]} · الآية {verse["ayah"]}',
                "read_count": self.progress.read_count, "total_ayahs": TOTAL_AYAHS,
                "percent_read": self.progress.percent_read,
                "tafsir_count": self.progress.tafsir_count,
                "interval_seconds": self.app.load_config()["interval_seconds"],
                "next_due_unix": self.next_due, "offline": True}

    def publish(self):
        state = self.state()
        self.app.write_json(self.app.STATUS, state)
        self.connection.emit_signal(None, OBJECT_PATH, BUS_NAME, "StateChanged",
                                    GLib.Variant("(s)", (json.dumps(state, ensure_ascii=False),)))

    def persist(self):
        self.app.write_json(self.app.STATE, self.progress.to_record())

    def dispatch(self, connection, sender, path, interface, method, parameters, invocation):
        try:
            if method == "Attach":
                self.frontend = sender
                self.publish()
            if method in ("Attach", "GetState"):
                invocation.return_value(GLib.Variant("(s)", (json.dumps(self.state(), ensure_ascii=False),)))
                return
            if method == "Show":
                self.show()
            elif method == "Detach":
                if self.frontend == sender:
                    self.frontend = None
                    self.publish()
            elif method in ("Hide", "ConfirmRead"):
                number, = parameters.unpack()
                # A delayed click on an old card must never confirm another ayah.
                if self.visible and number == self.progress.number:
                    if method == "ConfirmRead":
                        self.progress.ayah_read = True
                        self.persist()
                    self.hide()
            else:
                invocation.return_dbus_error(BUS_NAME + ".UnknownMethod", method)
                return
            invocation.return_value(None)
        except Exception as error:
            invocation.return_dbus_error(BUS_NAME + ".Error", str(error))

    def owner_changed(self, connection, sender, path, interface, signal_name, parameters):
        name, old_owner, new_owner = parameters.unpack()
        if name == self.frontend and not new_owner:
            self.frontend = None
            self.publish()

    def schedule(self):
        if self.timer:
            GLib.source_remove(self.timer)
        interval = self.app.load_config()["interval_seconds"]
        self.next_due = time.time() + interval
        self.timer = GLib.timeout_add(interval * 1000, self.on_timer)
        self.publish()

    def show(self):
        self.visible = True
        self.persist()
        self.publish()
        return False

    def hide(self):
        if self.visible:
            self.visible = False
            self.schedule()
        return False

    def on_timer(self):
        self.timer = None
        if self.frontend and not self.visible:
            self.progress.on_reminder(visible=False)
            self.show()
        self.schedule()
        return False

    def shutdown(self):
        self.running = False
        self.visible = False
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None
        self.publish()
        self.connection.signal_unsubscribe(self.subscription)
        self.connection.unregister_object(self.registration)
        self.loop.quit()
        return False


def run(app, test_callback=None):
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    reply = connection.call_sync(
        "org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
        "RequestName", GLib.Variant("(su)", (BUS_NAME, 4)),
        GLib.VariantType.new("(u)"), Gio.DBusCallFlags.NONE, -1, None)
    if reply.unpack()[0] != 1:
        raise RuntimeError("Another GNOME Quran reminder is already running")
    loop = GLib.MainLoop()
    reminder = GnomeReminder(app, connection, loop)
    handlers = []
    for sig, action in ((signal.SIGUSR1, reminder.show), (signal.SIGUSR2, reminder.hide),
                        (signal.SIGTERM, reminder.shutdown), (signal.SIGINT, reminder.shutdown)):
        handlers.append(GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, action))
    if test_callback:
        GLib.idle_add(test_callback, reminder)
    try:
        loop.run()
    finally:
        connection.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                             "ReleaseName", GLib.Variant("(s)", (BUS_NAME,)), None,
                             Gio.DBusCallFlags.NONE, -1, None)
