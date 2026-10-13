#!/usr/bin/env python3
"""A local, non-focusing Quran overlay for niri/Wayland."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from progress import ReadingProgress, TOTAL_AYAHS

HOME = Path.home()
ROOT = HOME / ".local/share/jisr-quran"
CONFIG = HOME / ".config/jisr-quran/config.json"
STATE = HOME / ".local/state/jisr-quran/state.json"
STATUS = STATE.with_name("status.json")
SERVICE = "jisr-quran.service"

def load_config():
    value = {"interval_seconds": 300, "enabled": True}
    if CONFIG.exists():
        value.update(json.loads(CONFIG.read_text()))
    value["interval_seconds"] = max(10, int(value["interval_seconds"]))
    return value

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)

def control(mode):
    if mode == "--status":
        value = json.loads(STATUS.read_text()) if STATUS.exists() else {"running": False}
        progress = ReadingProgress.from_record(json.loads(STATE.read_text()) if STATE.exists() else {})
        value.update({"read_count": progress.read_count, "tafsir_count": progress.tafsir_count, "percent_read": progress.percent_read, "number": progress.number})
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return
    if mode == "--stop":
        config = load_config()
        config["enabled"] = False
        write_json(CONFIG, config)
        subprocess.run(["systemctl", "--user", "stop", SERVICE], check=True)
        return
    if mode == "--hide":
        subprocess.run(["systemctl", "--user", "kill", "--signal=SIGUSR2", "--kill-whom=main", SERVICE], check=True)
        return
    if mode == "--restore" and not load_config()["enabled"]:
        return
    if mode not in ("--start", "--show", "--restore"):
        raise SystemExit("Usage: jisr-quran [--show|--hide|--start|--stop|--status]")
    config = load_config()
    config["enabled"] = True
    write_json(CONFIG, config)
    names = [key for key in ("WAYLAND_DISPLAY", "NIRI_SOCKET", "XDG_RUNTIME_DIR") if key in os.environ]
    if names:
        subprocess.run(["systemctl", "--user", "import-environment", *names], check=True)
    active = subprocess.run(["systemctl", "--user", "is-active", "--quiet", SERVICE]).returncode == 0
    subprocess.run(["systemctl", "--user", "start", SERVICE], check=True)
    if active and mode == "--show":
        subprocess.run(["systemctl", "--user", "kill", "--signal=SIGUSR1", "--kill-whom=main", SERVICE], check=True)

def run(test_callback=None):
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import Gdk, GLib, Gtk, GtkLayerShell, Pango
    from ui import IconButton, IslamicDivider
    Gtk.init([])
    if not GtkLayerShell.is_supported():
        raise RuntimeError("A Wayland compositor supporting Layer Shell is required")
    data = json.loads((ROOT / "verses.json").read_text())
    verses = data["verses"]
    if len(verses) != 6236:
        raise RuntimeError("Incomplete Quran data")
    settings = Gtk.Settings.get_default()
    settings.set_property("gtk-application-prefer-dark-theme", False)
    css = Gtk.CssProvider()
    css.load_from_data(b"""
        window { background: transparent; }
        #card { background: #fff2d8; border: none; border-radius: 22px; padding: 36px; }
        label { color: #0a4f3e; font-family: 'Noto Sans Arabic'; }
        .reference { font-size: 17px; font-weight: 700; }
        .verse { font-family: 'Noto Naskh Arabic'; font-size: 34px; }
        .meaning { font-size: 19px; color: #293e35; }
        .caption { font-size: 13px; color: #52675b; }
        .progress-label { font-size: 15px; font-weight: 700; }
        .tag { color: #0f6e56; font-size: 17px; font-weight: 700; }
        button { background-image: none; background-color: #0f6e56; color: #fff2d8; border: none; border-radius: 12px; padding: 11px 18px; font-family: 'Noto Sans Arabic'; font-size: 15px; box-shadow: none; text-shadow: none; }
        button label { color: #fff2d8; }
        button.icon-action { padding: 14px; border-radius: 16px; }
        button.dismiss { background-color: #386a57; }
        button:hover { background-image: none; background-color: #0f6e56; }
        button.confirm { background-color: #0f6e56; }
        button.confirm label { color: #fff2d8; }
        button.confirm:checked { background-color: #0a4f3e; }
        button.confirm:checked label { color: #fff2d8; }
        button:disabled { background-color: #a1b6a3; }
        button:disabled label { color: #fff2d8; }
        progressbar trough { background-color: #e8e2c8; border: none; min-height: 4px; border-radius: 4px; }
        progressbar progress { background-color: #0f6e56; border: none; min-height: 4px; border-radius: 4px; }
        scrolledwindow { border: none; background: transparent; }
        scrollbar { background: transparent; }
        scrollbar slider { background: #b8c9b8; border-radius: 6px; min-width: 4px; }
    """)
    # User GTK themes can override application colors, so keep this popup's palette explicit.
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)

    class Reminder:
        def __init__(self):
            self.progress = ReadingProgress.from_record(json.loads(STATE.read_text()) if STATE.exists() else {})
            self.visible = False
            self.animation = None
            self.pending = None
            self.timer = None
            self.next_due = 0
            self.window = Gtk.Window(title="آية من القرآن")
            self.window.set_decorated(False)
            self.window.set_resizable(False)
            self.window.set_accept_focus(False)
            self.window.set_app_paintable(True)
            self.window.set_visual(self.window.get_screen().get_rgba_visual())
            GtkLayerShell.init_for_window(self.window)
            GtkLayerShell.set_namespace(self.window, "jisr-quran-reminder")
            GtkLayerShell.set_layer(self.window, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_keyboard_mode(self.window, GtkLayerShell.KeyboardMode.NONE)
            # No anchors: the compositor centers this layer on both axes.
            GtkLayerShell.set_exclusive_zone(self.window, 0)
            monitor = Gdk.Display.get_default().get_monitor(0)
            geometry = monitor.get_geometry()
            self.popup_width = min(1040, geometry.width - 80)
            self.popup_height = min(480, geometry.height - 100)
            self.window.set_default_size(self.popup_width, self.popup_height)
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            card.set_direction(Gtk.TextDirection.LTR)
            card.set_name("card")
            card.set_size_request(self.popup_width, self.popup_height)
            self.window.add(card)
            header = Gtk.Box(spacing=16)
            header.set_direction(Gtk.TextDirection.LTR)
            tag = Gtk.Label(label="آية من القرآن")
            tag.get_style_context().add_class("tag")
            self.reference = Gtk.Label()
            self.reference.get_style_context().add_class("reference")
            self.reference.set_direction(Gtk.TextDirection.RTL)
            header.pack_start(self.reference, False, False, 0)
            header.pack_end(tag, False, False, 0)
            card.pack_start(header, False, False, 0)
            progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self.progress_label = self.label("progress-label", Pango.Alignment.RIGHT)
            self.progress_bar = Gtk.ProgressBar()
            progress_box.pack_start(self.progress_label, False, False, 0)
            progress_box.pack_start(self.progress_bar, False, False, 0)
            card.pack_start(progress_box, False, False, 0)
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroll.set_propagate_natural_height(True)
            scroll.set_min_content_height(100)
            scroll.set_max_content_height(max(160, self.popup_height - 300))
            self.scroll = scroll
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
            self.arabic = self.label("verse", Pango.Alignment.CENTER)
            content.pack_start(self.arabic, False, False, 0)
            content.pack_start(IslamicDivider(), False, False, 0)
            scroll.add(content)
            card.pack_start(scroll, True, True, 0)
            footer = Gtk.Box(spacing=12)
            footer.set_halign(Gtk.Align.END)
            self.dismiss = IconButton("hide", "إخفاء دون تسجيل القراءة")
            self.dismiss.get_style_context().add_class("dismiss")
            self.dismiss.connect("clicked", lambda *_: self.hide())
            self.read_button = IconButton("read", "تمت القراءة")
            self.read_button.connect("clicked", self.confirm_reading)
            footer.pack_start(self.dismiss, False, False, 0)
            footer.pack_start(self.read_button, False, False, 0)
            card.pack_start(footer, False, False, 0)
            self.window.connect("delete-event", lambda *_: self.hide() or True)
            for sig, action in ((signal.SIGUSR1, self.show), (signal.SIGUSR2, self.hide)):
                GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda callback=action: callback() or True)
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.shutdown)
            self.show()
            self.schedule()

        def label(self, style, alignment, text=""):
            label = Gtk.Label(label=text)
            # Keep physical alignment predictable; Pango shapes Arabic RTL automatically.
            label.set_direction(Gtk.TextDirection.LTR)
            label.set_line_wrap(True)
            label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            label.set_max_width_chars(68)
            label.set_xalign(1 if alignment == Pango.Alignment.RIGHT else 0.5)
            label.set_justify(Gtk.Justification.RIGHT if alignment == Pango.Alignment.RIGHT else Gtk.Justification.CENTER)
            label.get_style_context().add_class(style)
            return label

        def status(self):
            write_json(STATUS, {"running": True, "visible": self.visible, "number": self.progress.number, "interval_seconds": load_config()["interval_seconds"], "next_due_unix": self.next_due, "edition": "quran-uthmani", "tafsir_visible": False, "offline": True, "width": self.window.get_allocated_width(), "height": self.window.get_allocated_height(), "opacity": Gtk.Widget.get_opacity(self.window), "complete_text": self.arabic.get_text() == verses[self.progress.number - 1]["arabic"], "ayah_read": self.progress.ayah_read, "read_count": self.progress.read_count, "tafsir_count": self.progress.tafsir_count, "percent_read": self.progress.percent_read, "centered": True})

        def persist(self):
            write_json(STATE, self.progress.to_record())

        def refresh_progress(self):
            self.progress_label.set_text(f"قرأت {self.progress.read_count:,} من {TOTAL_AYAHS:,} آية · {self.progress.percent_read:.2f}% من آيات المصحف")
            self.progress_bar.set_fraction(self.progress.read_count / TOTAL_AYAHS)

        def confirm_reading(self, *_):
            if not self.visible:
                return
            self.progress.ayah_read = True
            self.persist()
            self.refresh_progress()
            self.hide()

        def animate(self, opening, done=None):
            if self.animation:
                GLib.source_remove(self.animation)
                self.animation = None
            start = time.monotonic()
            initial = Gtk.Widget.get_opacity(self.window)
            target = 1.0 if opening else 0.0
            def tick():
                progress = min(1.0, (time.monotonic() - start) / 0.30)
                eased = 1 - (1 - progress) ** 3
                opacity = initial + (target - initial) * eased
                Gtk.Widget.set_opacity(self.window, opacity)
                if progress < 1:
                    return True
                self.animation = None
                if done:
                    done()
                self.status()
                return False
            self.animation = GLib.timeout_add(16, tick)

        def show(self):
            if self.pending:
                GLib.source_remove(self.pending)
                self.pending = None
            verse = verses[self.progress.number - 1]
            self.reference.set_text(f'{verse["surah_name"]} · الآية {verse["ayah"]}')
            self.arabic.set_text(verse["arabic"])
            self.refresh_progress()
            self.scroll.get_vadjustment().set_value(0)
            Gtk.Widget.set_opacity(self.window, 0)
            self.window.show_all()
            self.visible = True
            self.animate(True)
            self.persist()
            self.status()
            return False

        def hide(self):
            if self.pending:
                GLib.source_remove(self.pending)
                self.pending = None
            if self.visible:
                self.visible = False
                self.animate(False, self.window.hide)
                self.schedule()
            return False

        def schedule(self):
            if self.timer:
                GLib.source_remove(self.timer)
            interval = load_config()["interval_seconds"]
            self.next_due = time.time() + interval
            self.timer = GLib.timeout_add(interval * 1000, self.on_timer)
            self.status()

        def on_timer(self):
            self.timer = None
            if not self.visible:
                self.progress.on_reminder(visible=False)
                self.persist()
                self.show()
            self.schedule()
            return False

        def shutdown(self):
            write_json(STATUS, {"running": False, "visible": False})
            Gtk.main_quit()
            return False

    reminder = Reminder()
    if test_callback:
        GLib.idle_add(test_callback, reminder)
    Gtk.main()

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--show"
    run() if mode == "--run" else control(mode)
