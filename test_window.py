"""Portable GTK frontend smoke test. Run under xvfb-run on CI."""
import json
from pathlib import Path
import tempfile
import unittest

import app


class WindowTests(unittest.TestCase):
    def test_buttons_full_text_and_progress(self):
        from gi.repository import GLib
        errors = []
        with tempfile.TemporaryDirectory() as directory:
            original = app.CONFIG, app.STATE, app.STATUS
            app.CONFIG = Path(directory) / "config.json"
            app.STATE = Path(directory) / "state.json"
            app.STATUS = Path(directory) / "status.json"
            app.write_json(app.CONFIG, {"backend": "window", "interval_seconds": 10})

            def verify(reminder):
                try:
                    state = json.loads(app.STATUS.read_text())
                    self.assertEqual(state["backend"], "window")
                    self.assertTrue(state["complete_text"])
                    self.assertFalse(reminder.window.get_accept_focus())
                    self.assertFalse(reminder.window.get_focus_on_map())
                    reminder.dismiss.emit("clicked")
                    self.assertEqual(reminder.progress.read_count, 0)
                    self.assertFalse(reminder.visible)
                    reminder.show()
                    reminder.read_button.emit("clicked")
                    reminder.read_button.emit("clicked")
                    self.assertEqual(reminder.progress.read_count, 1)
                    self.assertFalse(reminder.visible)
                    if reminder.timer:
                        GLib.source_remove(reminder.timer)
                        reminder.timer = None
                    reminder.on_timer()
                    self.assertTrue(reminder.visible)
                    self.assertEqual(reminder.progress.number, 2)
                except Exception as error:
                    errors.append(error)
                finally:
                    reminder.shutdown()
                return False

            def initialized(reminder):
                GLib.timeout_add(500, verify, reminder)
                return False

            try:
                app.run(initialized)
            finally:
                app.CONFIG, app.STATE, app.STATUS = original
        if errors:
            raise errors[0]


if __name__ == "__main__":
    unittest.main()
