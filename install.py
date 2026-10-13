#!/usr/bin/env python3
"""Per-user installer. Keeps config/progress and never needs root."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

UUID = "jisr-quran@elgedawy31.github.io"
SOURCE = Path(__file__).resolve().parent
HOME = Path.home()
DATA = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
APP = DATA / "jisr-quran"
BIN = HOME / ".local/bin/jisr-quran"
UNIT = CONFIG / "systemd/user/jisr-quran.service"
AUTOSTART = CONFIG / "autostart/jisr-quran.desktop"
EXTENSION = DATA / "gnome-shell/extensions" / UUID


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def exec_quote(path):
    # systemd and Desktop Entry Exec share quoted arguments and % specifiers.
    return '"' + str(path).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("`", "\\`").replace("$", "\\$") + '"'


def systemctl(*args, check=True):
    return subprocess.run(["systemctl", "--user", *args], check=check,
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["auto", "gnome", "layer-shell", "window"], default=None)
    parser.add_argument("--no-start", action="store_true", help="Install files without contacting the desktop/session")
    parser.add_argument("--uninstall", action="store_true", help="Remove application files; retain reading progress and config")
    args = parser.parse_args()
    if args.uninstall:
        if not args.no_start:
            systemctl("stop", "jisr-quran.service", check=False)
            if shutil.which("gnome-extensions"):
                subprocess.run(["gnome-extensions", "disable", UUID], check=False, capture_output=True)
        for path in [BIN, UNIT, AUTOSTART, DATA / "applications/jisr-quran.desktop",
                     DATA / "applications/jisr-quran-stop.desktop"]:
            path.unlink(missing_ok=True)
        for path in [APP, EXTENSION]:
            if path.is_dir():
                shutil.rmtree(path)
        if not args.no_start:
            systemctl("daemon-reload", check=False)
        print("Uninstalled. Your jisr-quran config and reading progress were retained.")
        return

    if not shutil.which("systemctl"):
        raise SystemExit("This installer requires systemd user services. See README for dependencies.")
    try:
        from gi.repository import Gio, GLib  # noqa: F401
    except ImportError:
        raise SystemExit("PyGObject is missing. Run ./scripts/install-deps.sh first.")
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower().split(":")
    is_gnome = args.backend == "gnome" or (args.backend in (None, "auto") and "gnome" in desktop)
    if is_gnome and not args.no_start:
        if not shutil.which("gnome-shell"):
            raise SystemExit("GNOME Shell is missing. Choose the backend matching your desktop.")
        version = subprocess.check_output(["gnome-shell", "--version"], text=True)
        match = re.search(r"\b(\d+)\.", version)
        supported = json.loads((SOURCE / "gnome-extension/metadata.json").read_text())["shell-version"]
        if not match or match[1] not in supported:
            raise SystemExit(f"{version.strip()} is not supported by the GNOME extension. Supported: {', '.join(supported)}.")
    data = json.loads((SOURCE / "data/verses.json").read_text())
    if len(data["verses"]) != 6236:
        raise SystemExit("Incomplete Quran data; refusing to install.")

    APP.mkdir(parents=True, exist_ok=True)
    for name in ["app.py", "ui.py", "progress.py", "gnome_backend.py", "download_data.py"]:
        shutil.copy2(SOURCE / name, APP / name)
    shutil.copy2(SOURCE / "data/verses.json", APP / "verses.json")
    EXTENSION.mkdir(parents=True, exist_ok=True)
    for name in ["metadata.json", "extension.js", "stylesheet.css"]:
        shutil.copy2(SOURCE / "gnome-extension" / name, EXTENSION / name)
    wrapper = "#!/bin/sh\nset -eu\n"
    # Retain support for the original local Arch runtime on upgrades.
    runtime = APP / "runtime/usr/lib"
    if runtime.is_dir():
        wrapper += f"QURAN_RUNTIME={shlex.quote(str(runtime))}\n"
        wrapper += 'export GI_TYPELIB_PATH="$QURAN_RUNTIME/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"\n'
        wrapper += 'export LD_LIBRARY_PATH="$QURAN_RUNTIME${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n'
    wrapper += f"export JISR_QURAN_DATA_DIR={shlex.quote(str(APP))}\n"
    wrapper += f"exec /usr/bin/python3 {shlex.quote(str(APP / 'app.py'))} \"$@\"\n"
    write(BIN, wrapper)
    BIN.chmod(0o755)
    write(UNIT, f"""[Unit]
Description=Offline Quran reminder
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart={exec_quote(BIN)} --run
Restart=on-failure
RestartSec=10
TimeoutStopSec=5
""")
    entry = f"""[Desktop Entry]
Type=Application
Name=Quran Reminder
Name[ar]=آية من القرآن
Comment=An offline Quran verse every five minutes
Exec={exec_quote(BIN)} --show
Icon=accessories-text-editor
Terminal=false
Categories=Utility;
"""
    write(DATA / "applications/jisr-quran.desktop", entry)
    write(DATA / "applications/jisr-quran-stop.desktop",
          entry.replace("Name=Quran Reminder", "Name=Quran Reminder Stop")
          .replace("Name[ar]=آية من القرآن", "Name[ar]=إيقاف تذكير القرآن")
          .replace(" --show", " --stop"))
    write(AUTOSTART, entry.replace(" --show", " --restore"))
    config_path = CONFIG / "jisr-quran/config.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {
        "interval_seconds": 300, "enabled": True, "backend": "auto"}
    if args.backend:
        config["backend"] = args.backend
    write(config_path, json.dumps(config, indent=2) + "\n")
    if not args.no_start:
        systemctl("daemon-reload")
        if is_gnome:
            result = subprocess.run(["gnome-extensions", "enable", UUID], capture_output=True, text=True)
            if result.returncode:
                print("GNOME needs a logout/login to discover the extension. Afterwards run:")
                print(f"  gnome-extensions enable {UUID}")
        # --restore respects an existing deliberate --stop preference.
        subprocess.run([str(BIN), "--restore"], check=True)
    print(f"Installed: {BIN}")
    print("Controls: ~/.local/bin/jisr-quran --show | --hide | --stop | --start | --status")
    if is_gnome:
        print("Enable 'Jisr Quran Reminder' in GNOME Extensions. A first installation may require logout/login.")
    print("Existing config and reading progress are preserved.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"Installation command failed: {error.cmd}\n{error.stderr or ''}")
