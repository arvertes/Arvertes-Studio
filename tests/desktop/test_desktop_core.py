import json
from pathlib import Path
import tempfile
import unittest

from arvertes_desktop.navigation import AGENT_NAMES, SECTIONS
from arvertes_desktop.settings import Settings, load_settings, save_settings, validate_blender_path


class DesktopCoreTests(unittest.TestCase):
    def test_missing_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_settings(Path(directory) / "settings.json"), Settings())

    def test_settings_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config" / "settings.json"
            settings = Settings("C:/Program Files/Blender Foundation/Blender/blender.exe")
            save_settings(path, settings)
            self.assertEqual(load_settings(path), settings)
            save_settings(path, Settings())
            self.assertEqual(load_settings(path), Settings())
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_invalid_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            for data in ([], {"version": True, "blender_path": ""}, {"version": 2, "blender_path": ""}, {"version": 1, "blender_path": 42}):
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.subTest(data=data), self.assertRaises(ValueError):
                    load_settings(path)

    def test_path_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blender.exe"
            path.touch()
            self.assertEqual(validate_blender_path(str(path)), path)
            for value in ("blender.exe", str(path.parent / "other.exe"), str(path.parent / "blender")):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    validate_blender_path(value)

    def test_navigation(self):
        self.assertEqual(len(SECTIONS), 16)
        self.assertIn("network", {section.key for section in SECTIONS})
        self.assertEqual(len({section.key for section in SECTIONS}), len(SECTIONS))
        self.assertEqual(len(set(AGENT_NAMES)), 26)


if __name__ == "__main__":
    unittest.main()
