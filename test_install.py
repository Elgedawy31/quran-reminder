"""Install/upgrade/uninstall in a temporary HOME, with spaces in its path."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class InstallTests(unittest.TestCase):
    def test_install_preserves_preferences_and_progress(self):
        with tempfile.TemporaryDirectory(prefix="jisr install ") as directory:
            home = Path(directory)
            environment = dict(os.environ, HOME=str(home),
                               XDG_CONFIG_HOME=str(home / "config"),
                               XDG_DATA_HOME=str(home / "data"),
                               XDG_STATE_HOME=str(home / "state"))
            config = home / "config/jisr-quran/config.json"
            state = home / "state/jisr-quran/state.json"
            config.parent.mkdir(parents=True)
            state.parent.mkdir(parents=True)
            config.write_text('{"interval_seconds": 600, "enabled": false, "backend": "auto"}')
            saved = '{"schema_version":3,"number":91,"ayah_read":true,"tafsir_read":false,"tafsir_completed":6}'
            state.write_text(saved)
            command = [sys.executable, "install.py", "--no-start"]
            for _ in range(2):
                subprocess.run(command, env=environment, check=True, capture_output=True)
            self.assertFalse(json.loads(config.read_text())["enabled"])
            self.assertEqual(json.loads(config.read_text())["interval_seconds"], 600)
            self.assertEqual(state.read_text(), saved)
            self.assertTrue((home / "data/jisr-quran/verses.json").is_file())
            self.assertTrue((home / "config/autostart/jisr-quran.desktop").is_file())
            subprocess.run(["sh", "-n", str(home / ".local/bin/jisr-quran")], check=True)
            # The installed wrapper must work outside the checkout, even with spaces.
            result = subprocess.run([str(home / ".local/bin/jisr-quran"), "--status"],
                                    env=environment, cwd="/tmp", check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(result.stdout)["read_count"], 91)
            subprocess.run(command + ["--uninstall"], env=environment, check=True, capture_output=True)
            self.assertEqual(state.read_text(), saved)
            self.assertTrue(config.is_file())
            self.assertFalse((home / "data/jisr-quran").exists())
            self.assertFalse((home / ".local/bin/jisr-quran").exists())
            self.assertFalse((home / "config/autostart/jisr-quran.desktop").exists())


if __name__ == "__main__":
    unittest.main()
