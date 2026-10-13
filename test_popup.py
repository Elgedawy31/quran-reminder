"""Native GTK integration checks. Uses isolated progress and config files."""
import json
from pathlib import Path
import tempfile
import time
import unittest

import app

class PopupTests(unittest.TestCase):
    def test_layout_palette_and_confirmation_gates(self):
        import cairo
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        gi.require_version("GtkLayerShell", "0.1")
        from gi.repository import GLib, Gtk, GtkLayerShell
        errors = []
        with tempfile.TemporaryDirectory(prefix="jisr-quran-test-") as directory:
            original = app.CONFIG, app.STATE, app.STATUS
            app.CONFIG = Path(directory) / "config.json"
            app.STATE = Path(directory) / "state.json"
            app.STATUS = Path(directory) / "status.json"
            app.write_json(app.CONFIG, {"interval_seconds": 10, "enabled": True})

            def timed(reminder):
                if reminder.timer:
                    GLib.source_remove(reminder.timer)
                    reminder.timer = None
                reminder.on_timer()

            def after_render(reminder):
                try:
                    self.assertEqual(reminder.progress.number, 1)
                    self.assertFalse(hasattr(reminder, "following"))
                    self.assertGreaterEqual(reminder.window.get_allocated_width(), 1000)
                    self.assertGreaterEqual(reminder.window.get_allocated_height(), 400)
                    self.assertLess(reminder.window.get_allocated_height(), 700)
                    for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM, GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
                        self.assertFalse(GtkLayerShell.get_anchor(reminder.window, edge))
                    self.assertFalse(hasattr(reminder, "tafsir"))
                    self.assertFalse(hasattr(reminder, "tafsir_button"))
                    self.assertNotIn("التفسير", reminder.progress_label.get_text())
                    for button in (reminder.read_button,):
                        color = button.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
                        self.assertAlmostEqual(color.red, 15 / 255, places=2)
                        self.assertAlmostEqual(color.green, 110 / 255, places=2)
                        self.assertAlmostEqual(color.blue, 86 / 255, places=2)
                    self.assertIsInstance(reminder.window.get_child(), Gtk.Box)
                    buttons = []
                    def collect(widget):
                        if isinstance(widget, Gtk.Button):
                            buttons.append(widget)
                        if isinstance(widget, Gtk.Container):
                            for child in widget.get_children():
                                collect(child)
                    collect(reminder.window)
                    self.assertEqual(len(buttons), 2)
                    for button in buttons:
                        self.assertIsInstance(button.get_child(), Gtk.Image)
                        self.assertIsNotNone(button.get_tooltip_text())
                        self.assertIsNotNone(button.get_accessible().get_name())
                    reminder.read_button.on_pointer_enter()
                    self.assertIsNotNone(reminder.read_button.get_event_window().get_cursor())
                    deadline = time.monotonic() + 0.28
                    while time.monotonic() < deadline:
                        GLib.MainContext.default().iteration(False)
                        time.sleep(0.005)
                    self.assertGreater(reminder.read_button.hover_progress, 0.95)
                    reminder.read_button.on_pointer_leave()
                    deadline = time.monotonic() + 0.28
                    while time.monotonic() < deadline:
                        GLib.MainContext.default().iteration(False)
                        time.sleep(0.005)
                    self.assertLess(reminder.read_button.hover_progress, 0.05)
                    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, reminder.window.get_allocated_width(), reminder.window.get_allocated_height())
                    reminder.window.draw(cairo.Context(surface))
                    surface.write_to_png(str(Path(__file__).parent / "preview.png"))
                    # Hide repeats an unread verse; the timer never replaces a visible one.
                    timed(reminder)
                    self.assertEqual(reminder.progress.number, 1)
                    self.assertTrue(reminder.visible)
                    reminder.next_due = time.time() + 1
                    reminder.dismiss.emit("clicked")
                    self.assertFalse(reminder.visible)
                    self.assertEqual(reminder.progress.read_count, 0)
                    self.assertGreater(reminder.next_due - time.time(), 9)
                    timed(reminder)
                    self.assertEqual(reminder.progress.number, 1)
                    self.assertTrue(reminder.visible)
                    reminder.next_due = time.time() + 1
                    reminder.read_button.emit("clicked")
                    self.assertFalse(reminder.visible)
                    self.assertEqual(reminder.progress.number, 1)
                    self.assertEqual(reminder.progress.read_count, 1)
                    self.assertEqual(reminder.progress.tafsir_count, 0)
                    self.assertGreater(reminder.next_due - time.time(), 9)
                    saved = app.ReadingProgress.from_record(json.loads(app.STATE.read_text()))
                    self.assertEqual((saved.number, saved.ayah_read), (1, True))
                    # Repeated clicks during the closing animation cannot skip verses.
                    reminder.read_button.emit("clicked")
                    self.assertEqual(reminder.progress.read_count, 1)
                    timed(reminder)
                    self.assertEqual(reminder.progress.number, 2)
                    self.assertEqual((reminder.progress.read_count, reminder.progress.tafsir_count), (1, 0))
                    reminder.dismiss.emit("clicked")
                    timed(reminder)
                    self.assertEqual(reminder.progress.number, 2)
                    reminder.read_button.emit("clicked")
                    timed(reminder)
                    self.assertEqual(reminder.progress.number, 3)
                    self.assertEqual(json.loads(app.STATE.read_text())["number"], 3)
                except Exception as error:
                    errors.append(error)
                finally:
                    reminder.shutdown()
                return False

            def initialized(reminder):
                GLib.timeout_add(700, after_render, reminder)
                return False
            try:
                app.run(initialized)
            finally:
                app.CONFIG, app.STATE, app.STATUS = original
            if errors:
                raise errors[0]

if __name__ == "__main__":
    unittest.main()
