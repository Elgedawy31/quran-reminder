"""Real session-bus integration; run with dbus-run-session -- python -m unittest test_gnome_backend."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from gi.repository import Gio, GLib
from gnome_backend import BUS_NAME, OBJECT_PATH


class GnomeBackendTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="jisr-gnome-test-")
        self.root = Path(self.directory.name)
        self.environment = dict(os.environ, XDG_CONFIG_HOME=str(self.root / "config"),
                                XDG_STATE_HOME=str(self.root / "state"),
                                JISR_QURAN_DATA_DIR=str(Path(__file__).parent / "data"))
        config = self.root / "config/jisr-quran/config.json"
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({"backend": "gnome", "interval_seconds": 10}))
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.start()

    def start(self):
        self.process = subprocess.Popen([sys.executable, "app.py", "--run"],
                                        env=self.environment, stderr=subprocess.PIPE)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                self.state()
                return
            except GLib.Error:
                if self.process.poll() is not None:
                    self.fail(self.process.stderr.read().decode())
                time.sleep(0.05)
        self.fail("Backend did not acquire its bus name")

    def stop(self):
        self.process.terminate()
        self.process.wait(timeout=5)
        self.assertEqual(self.process.returncode, 0, self.process.stderr.read().decode())
        self.process.stderr.close()

    def tearDown(self):
        if self.process.poll() is None:
            self.stop()
        self.directory.cleanup()

    def call(self, method, number=None):
        parameters = None if number is None else GLib.Variant("(u)", (number,))
        return self.connection.call_sync(BUS_NAME, OBJECT_PATH, BUS_NAME, method, parameters,
                                         None, Gio.DBusCallFlags.NONE, 2000, None)

    def state(self):
        return json.loads(self.call("GetState").unpack()[0])

    def test_unread_repeat_confirm_stale_click_and_restart(self):
        self.assertFalse(self.state()["frontend_connected"])
        attached = json.loads(self.call("Attach").unpack()[0])
        self.assertTrue(attached["frontend_connected"])
        self.assertTrue(attached["visible"])
        self.assertEqual(attached["number"], 1)
        self.assertTrue(attached["arabic"])
        self.call("Hide", 1)
        self.assertFalse(self.state()["visible"])
        self.call("Show")
        self.assertEqual(self.state()["number"], 1)
        self.call("ConfirmRead", 1)
        self.assertEqual(self.state()["read_count"], 1)
        self.assertGreater(self.state()["next_due_unix"] - time.time(), 9)
        self.call("ConfirmRead", 1)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline and not self.state()["visible"]:
            time.sleep(0.1)
        self.assertEqual(self.state()["number"], 2)
        self.assertTrue(self.state()["visible"])
        self.call("ConfirmRead", 1)
        self.assertEqual(self.state()["read_count"], 1)
        self.assertTrue(self.state()["visible"])
        self.stop()
        self.start()
        self.assertEqual(self.state()["number"], 2)
        self.assertEqual(self.state()["read_count"], 1)

    def test_signals_and_disconnected_frontend_do_not_advance(self):
        self.call("Hide", 1)
        deadline = time.monotonic() + 11
        while time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertEqual(self.state()["number"], 1)
        self.assertFalse(self.state()["visible"])
        self.process.send_signal(signal.SIGUSR1)
        deadline = time.monotonic() + 2
        while not self.state()["visible"] and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertTrue(self.state()["visible"])
        self.process.send_signal(signal.SIGUSR2)
        deadline = time.monotonic() + 2
        while self.state()["visible"] and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(self.state()["visible"])


if __name__ == "__main__":
    unittest.main()
