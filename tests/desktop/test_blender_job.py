from pathlib import Path
from struct import pack
from tempfile import TemporaryDirectory
import json
import unittest

from arvertes_desktop.blender_job import fingerprint, read_source, stage


def fixture(path, uri=None):
    doc = {"asset": {"version": "2.0"}, "nodes": [], "buffers": [{"byteLength": 4}]}
    if uri:
        doc["images"] = [{"uri": uri}]
    data = json.dumps(doc).encode("ascii")
    data += b" " * (-len(data) % 4)
    path.write_bytes(pack("<4sIII4s", b"glTF", 2, 20 + len(data), len(data), b"JSON") + data)


class BlenderJobTests(unittest.TestCase):
    def test_reject_external_resource_and_changed_authorized_source(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            asset = root / "asset.glb"
            fixture(asset, "../sensitive.png")
            with self.assertRaisesRegex(ValueError, "externos"):
                read_source(asset)
            fixture(asset, "data:image/png;base64,AAAA")
            auth = fingerprint(read_source(asset))
            fixture(asset)
            with self.assertRaisesRegex(ValueError, "mudou"):
                stage(asset, auth, root / "other_copy")
            correct = fingerprint(read_source(asset))
            copy = stage(asset, correct, root / "valid_copy")
            self.assertEqual(copy.read_bytes(), asset.read_bytes())
            self.assertNotEqual(copy, asset)
