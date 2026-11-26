from hashlib import sha256
from pathlib import Path
from struct import pack
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile
import unittest

from arvertes_studio.core.asset_package import (
    ACTIVE_QUALITY, QUALITY, image_info, json_bytes, library_pins, verify_package,
)


class PackageContractTest(unittest.TestCase):
    def test_profiles_and_image_limits(self):
        self.assertEqual(list(QUALITY), ["lite", "low", "medium", "high", "ultra", "cinematic"])
        self.assertEqual(ACTIVE_QUALITY, {"lite", "low", "medium"})

        def header(width, height):
            return b"\x89PNG\r\n\x1a\n" + pack(">I4sII", 13, b"IHDR", width, height)

        self.assertEqual(image_info(header(384, 256))["width"], 384)
        for dimensions in ((0, 5), (4096, 4096), (5, 5000)):
            with self.assertRaises(ValueError):
                image_info(header(*dimensions))
        for data in (b"<svg/>", b"\xff\xd8", b"GIF89a"):
            with self.assertRaises(ValueError):
                image_info(data)

    def test_manifest_detects_changes_traversal_and_compression(self):
        artwork = "references/concept.png"
        entries = {artwork: b"sample", "models/asset.fbx": b"fbx", "models/preview.glb": b"glb",
                   "scene/working.blend": b"blend", "references/library.json": b"[]"}
        expected = {"mode": "static", "quality": "lite", "unreal_import": "pending",
                    "schema": 1, "max_cost_centavos": 0}
        entries["brief.json"] = json_bytes({**expected, "reference": artwork,
                                          "image": {"sha256": sha256(entries[artwork]).hexdigest()}})
        entries["reports/quality.json"] = json_bytes(expected)
        manifest = {**expected, "files": [{"path": name, "bytes": len(data), "sha256": sha256(data).hexdigest()}
                                          for name, data in entries.items()]}
        with TemporaryDirectory() as directory:
            path = Path(directory) / "test.zip"
            for change in ({}, {"models/asset.fbx": b"FBX"}, {"../danger": b"test"}):
                with ZipFile(path, "w") as archive:
                    for key, value in {**entries, **change}.items():
                        archive.writestr(key, value)
                    archive.writestr("manifest.json", json_bytes(manifest))
                if change:
                    with self.assertRaises(ValueError):
                        verify_package(path)
                else:
                    self.assertEqual(verify_package(path), manifest)
            with ZipFile(path, "w", ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", json_bytes(manifest))
            with self.assertRaises(ValueError):
                verify_package(path)

    def test_library_pin_requires_licensed_usage_and_exact_revision(self):
        item = {"id": "fixture", "revision": 2, "category": "textures", "source": "fixture.png",
                "license": "fixture", "sha256": "a" * 64, "credit": "Arvertes Studio", "usage": "reference_only"}
        self.assertEqual(library_pins([item]), [item])
        for items in ([{**item, "usage": "restricted"}], [{**item, "revision": True}], [item, item]):
            with self.assertRaises(ValueError):
                library_pins(items)
