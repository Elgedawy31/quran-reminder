#!/usr/bin/env python3
"""Build portable source and GNOME extension archives from an explicit manifest."""
import hashlib
from pathlib import Path
import re
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = sys.argv[1] if len(sys.argv) > 1 else "0.1.0"
if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", VERSION):
    raise SystemExit("Expected a version such as 0.1.0")
OUTPUT = ROOT / "dist"
OUTPUT.mkdir(exist_ok=True)
FILES = ["app.py", "ui.py", "progress.py", "gnome_backend.py", "download_data.py",
         "install.py", "install.sh", "README.md", "README.ar.md", "LICENSE", "preview.png",
         "data/verses.json", "scripts/install-deps.sh", "scripts/package.py",
         "gnome-extension/metadata.json", "gnome-extension/extension.js", "gnome-extension/stylesheet.css",
         "test_progress.py", "test_install.py", "test_gnome_backend.py", "test_window.py", "test_popup.py",
         "tests/gnome_smoke.py", "tests/gnome-probe/extension.js", "tests/gnome-probe/metadata.json",
         ".github/workflows/checks.yml", ".gitignore", "USAGE.txt"]
archive = OUTPUT / f"quran-reminder-{VERSION}.tar.gz"
with tarfile.open(archive, "w:gz") as bundle:
    for filename in FILES:
        bundle.add(ROOT / filename, arcname=f"quran-reminder-{VERSION}/{filename}")
extension = OUTPUT / "jisr-quran@elgedawy31.github.io.zip"
with zipfile.ZipFile(extension, "w", zipfile.ZIP_DEFLATED) as bundle:
    for filename in ["metadata.json", "extension.js", "stylesheet.css"]:
        bundle.write(ROOT / "gnome-extension" / filename, filename)
checksums = OUTPUT / "SHA256SUMS"
checksums.write_text("".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
                             for path in [archive, extension]))
for path in [archive, extension, checksums]:
    print(path)
