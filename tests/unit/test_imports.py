import json
import struct
import tempfile
import unittest
from pathlib import Path

from arvertes_studio.core.imports import ImportValidationError, validate_import_path


def glb(*chunks, version=2):
    body = b"".join(struct.pack("<I4s", len(data), kind) + data for kind, data in chunks)
    return struct.pack("<4sII", b"glTF", version, 12 + len(body)) + body


JSON_CHUNK = (b"JSON", b'{"asset":{"version":"2.0"}} ')


class ImportValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_accepts_uppercase_suffix_and_preserves_file_bytes(self):
        source = self.directory / "Modelo.GLB"
        original = glb(JSON_CHUNK, (b"BIN\x00", b"1234"), (b"TEST", b"5678"))
        source.write_bytes(original)

        self.assertEqual(validate_import_path(source), source)
        self.assertEqual(source.read_bytes(), original)

    def test_rejects_missing_empty_directory_and_unsupported_path(self):
        directory = self.directory / "diretorio.glb"
        directory.mkdir()
        unsupported = self.directory / "modelo.fbx"
        unsupported.write_bytes(glb(JSON_CHUNK))

        for path in ("", None, directory, unsupported, self.directory / "inexistente.glb"):
            with self.subTest(path=path), self.assertRaises(ImportValidationError):
                validate_import_path(path)

    def test_rejects_invalid_container_headers(self):
        source = self.directory / "modelo.glb"
        valid = glb(JSON_CHUNK)
        invalid_headers = [b"", b"falso", b"GLTF" + valid[4:], glb(JSON_CHUNK, version=1), valid[:-4]]

        for data in invalid_headers:
            with self.subTest(data=data), self.assertRaises(ImportValidationError):
                source.write_bytes(data)
                validate_import_path(source)

    def test_rejects_invalid_chunk_layouts(self):
        source = self.directory / "modelo.glb"
        short_chunk = struct.pack("<4sIII4s", b"glTF", 2, 24, 12, b"JSON") + b"1234"
        invalid_chunks = [
            glb(),
            glb((b"BIN\x00", b"1234")),
            glb((b"JSON", b"")),
            glb((b"JSON", b"{}")),
            short_chunk,
        ]
        for data in invalid_chunks:
            with self.subTest(data=data), self.assertRaises(ImportValidationError):
                source.write_bytes(data)
                validate_import_path(source)

    def test_rejects_invalid_json_and_node_mesh_references(self):
        source = self.directory / "modelo.glb"
        documents = [
            b"!   ",
            b"[]  ",
            b"{}  ",
            *(
                json.dumps({"asset": {"version": "2.0"}, "nodes": [{"mesh": index}]}).encode()
                for index in (7, -1, True, None)
            ),
        ]
        for document in documents:
            with self.subTest(document=document), self.assertRaises(ImportValidationError):
                document += b" " * (-len(document) % 4)
                source.write_bytes(glb((b"JSON", document)))
                validate_import_path(source)
