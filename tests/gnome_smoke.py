"""Run with dbus-run-session in a disposable GNOME-capable CI/container environment."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from gi.repository import Gio, GLib

SOURCE = Path(__file__).resolve().parents[1]
BUS = "io.github.Elgedawy31.QuranReminder"
PATH = "/io/github/Elgedawy31/QuranReminder"
PROBE = "io.github.Elgedawy31.QuranTest"


def wait_for(check, timeout=20):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            last = check()
            if last:
                return last
        except GLib.Error:
            pass
        time.sleep(0.1)
    raise AssertionError(f"Timed out; last result: {last}")


def main():
    if os.environ.get("JISR_RUN_GNOME_SMOKE") != "1":
        raise SystemExit("Use JISR_RUN_GNOME_SMOKE=1 inside a disposable CI/container environment.")
    with tempfile.TemporaryDirectory(prefix="jisr-shell-test-") as directory:
        root = Path(directory)
        runtime = root / "runtime"
        runtime.mkdir(mode=0o700)
        environment = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(root / "config"),
                           XDG_DATA_HOME=str(root / "data"), XDG_STATE_HOME=str(root / "state"),
                           XDG_RUNTIME_DIR=str(runtime), XDG_CURRENT_DESKTOP="GNOME",
                           XDG_SESSION_TYPE="wayland", LIBGL_ALWAYS_SOFTWARE="1",
                           GSETTINGS_BACKEND="keyfile",
                           JISR_QURAN_DATA_DIR=str(SOURCE / "data"))
        extensions = root / "data/gnome-shell/extensions"
        shutil.copytree(SOURCE / "gnome-extension", extensions / "jisr-quran@elgedawy31.github.io")
        shutil.copytree(SOURCE / "tests/gnome-probe", extensions / "jisr-test-probe@localhost")
        config = root / "config/jisr-quran/config.json"
        config.parent.mkdir(parents=True)
        config.write_text('{"backend":"gnome","interval_seconds":10}')
        subprocess.run(["gsettings", "set", "org.gnome.shell", "enabled-extensions",
                        '["jisr-quran@elgedawy31.github.io", "jisr-test-probe@localhost"]'],
                       env=environment, check=True)
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)

        def call(destination, path, interface, method, params=None):
            return connection.call_sync(destination, path, interface, method, params,
                                        None, Gio.DBusCallFlags.NONE, 2000, None)

        def snapshot():
            return json.loads(call("org.gnome.Shell", "/io/github/Elgedawy31/QuranTest",
                                   PROBE, "Snapshot").unpack()[0])

        def state():
            return json.loads(call(BUS, PATH, BUS, "GetState").unpack()[0])

        output = Path(os.environ.get("JISR_TEST_OUTPUT", "/tmp/jisr-gnome-test"))
        output.mkdir(parents=True, exist_ok=True)
        with (output / "shell.log").open("w") as shell_log, (output / "backend.log").open("w") as backend_log:
            shell = subprocess.Popen(["gnome-shell", "--headless", "--wayland", "--virtual-monitor",
                                      "1280x800", "--no-x11"], env=environment,
                                     stdout=shell_log, stderr=subprocess.STDOUT)
            backend = subprocess.Popen([sys.executable, str(SOURCE / "app.py"), "--run"],
                                       env=environment, stdout=backend_log, stderr=subprocess.STDOUT)
            try:
                def ready_snapshot():
                    value = snapshot()
                    return value if value_ready(value) else None
                first = wait_for(ready_snapshot)
                expected = json.loads((SOURCE / "data/verses.json").read_text())["verses"][0]["arabic"]
                assert first["verse"] == expected, first
                assert first["width"] == 1040 and first["height"] == 480, first
                assert first["x"] >= 0 and first["y"] >= 0, first
                assert not first["keyboardFocus"], first
                call("org.gnome.Shell", "/io/github/Elgedawy31/QuranTest", PROBE, "Click", GLib.Variant("(u)", (0,)))
                wait_for(lambda: not snapshot()["visible"])
                assert state()["read_count"] == 0
                wait_for(lambda: snapshot()["visible"], timeout=13)
                assert state()["number"] == 1
                call("org.gnome.Shell", "/io/github/Elgedawy31/QuranTest", PROBE, "Click", GLib.Variant("(u)", (1,)))
                wait_for(lambda: not snapshot()["visible"])
                assert state()["read_count"] == 1
                wait_for(lambda: snapshot()["visible"], timeout=13)
                assert state()["number"] == 2
                assert snapshot()["verse"] == json.loads((SOURCE / "data/verses.json").read_text())["verses"][1]["arabic"]
                # Disabling/re-enabling is also what happens on lock/unlock.
                subprocess.run(["gnome-extensions", "disable", "jisr-quran@elgedawy31.github.io"], env=environment, check=True)
                wait_for(lambda: not state()["frontend_connected"])
                subprocess.run(["gnome-extensions", "enable", "jisr-quran@elgedawy31.github.io"], env=environment, check=True)
                wait_for(lambda: state()["frontend_connected"] and snapshot()["visible"])
                backend.terminate()
                backend.wait(timeout=5)
                verses = json.loads((SOURCE / "data/verses.json").read_text())["verses"]
                longest = max(verses, key=lambda verse: len(verse["arabic"]))
                saved_state = root / "state/jisr-quran/state.json"
                saved_state.write_text(json.dumps({"schema_version": 3, "number": longest["number"],
                                                  "ayah_read": False, "tafsir_read": False, "tafsir_completed": 0}))
                backend = subprocess.Popen([sys.executable, str(SOURCE / "app.py"), "--run"],
                                           env=environment, stdout=backend_log, stderr=subprocess.STDOUT)
                wait_for(lambda: state()["frontend_connected"] and ready_snapshot()
                         and snapshot()["number"] == longest["number"])
                long_card = snapshot()
                assert long_card["verse"] == longest["arabic"], long_card
                assert long_card["scrollUpper"] > long_card["scrollPageSize"], long_card
                result = {"gnome": subprocess.check_output(["gnome-shell", "--version"], text=True).strip(),
                          "first_card": first, "long_ayah_scrolls": True,
                          "final_state": state(), "result": "PASS"}
                (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
                print(json.dumps({"gnome": result["gnome"], "result": "PASS",
                                  "centered": True, "long_ayah_scrolls": True,
                                  "buttons_and_reconnect": True}))
            finally:
                for process in (backend, shell):
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


def value_ready(value):
    return value.get("visible") and value.get("connected") and value.get("opacity") == 255


if __name__ == "__main__":
    main()
