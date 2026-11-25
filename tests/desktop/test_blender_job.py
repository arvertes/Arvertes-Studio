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
    path.write_bytes(pack("<4sIII4s", b"glTF", 2, 32 + len(data), len(data), b"JSON") + data
                     + pack("<I4s",4,b"BIN\x00") + b"\x00"*4)


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

    def test_invalid_bin_range_and_scene_graph_are_rejected_before_blender(self):
        from arvertes_studio.core.glb_admission import validate_payload

        with self.assertRaisesRegex(ValueError, "ciclo"):
            validate_payload({"nodes":[{"children":[0]}]},0)
        doc = {"buffers":[{"byteLength":4}],"bufferViews":[{"buffer":0,"byteLength":4}],
               "accessors":[{"bufferView":0,"componentType":5126,"count":2,"type":"SCALAR"}]}
        with self.assertRaisesRegex(ValueError, "além"):
            validate_payload(doc,4)
