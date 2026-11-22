import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from arvertes_studio.core.reports import ReportError, SCHEMA_VERSION, write_report


class ReportWriterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.report = {
            "schema_version": SCHEMA_VERSION,
            "asset": {
                "id": "sample",
                "name": "Peça sintética",
                "source_file": "peça.glb",
            },
            "summary": {},
            "meshes": [],
            "issues": [],
        }

    def test_write_utf8_versioned_json_and_replace_existing_report(self):
        destination = self.root / "relatório.JSON"
        destination.write_text("relatório anterior", encoding="utf-8")

        self.assertEqual(write_report(self.report, destination), destination)
        content = destination.read_text(encoding="utf-8")
        self.assertIn("Peça sintética", content)
        self.assertEqual(json.loads(content), self.report)
        self.assertEqual(list(self.root.iterdir()), [destination])

    def test_reject_empty_unsupported_and_missing_paths(self):
        invalid_paths = [
            "",
            None,
            "bad\x00.json",
            self.root / "arquivo.glb",
            self.root / "inexistente" / "relatorio.json",
        ]
        for path in invalid_paths:
            with self.subTest(path=path), self.assertRaises(ReportError):
                write_report(self.report, path)

    def test_reject_directory_destination_even_if_extension_matches(self):
        directory = self.root / "diretorio.json"
        directory.mkdir()
        with self.assertRaises(ReportError):
            write_report(self.report, directory)
        self.assertTrue(directory.is_dir())

    def test_reject_unversioned_or_unknown_report(self):
        invalid_reports = [
            None,
            [],
            {},
            {"schema_version": True},
            {"schema_version": "1"},
            {"schema_version": SCHEMA_VERSION + 1},
        ]
        for report in invalid_reports:
            with self.subTest(report=report), self.assertRaises(ReportError):
                write_report(report, self.root / "out.json")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_failed_encoding_preserves_existing_file_and_removes_temporary(self):
        destination = self.root / "relatorio.json"
        destination.write_text("conteúdo existente", encoding="utf-8")
        self.report["summary"]["invalid_value"] = float("nan")

        with self.assertRaises(ReportError):
            write_report(self.report, destination)

        self.assertEqual(destination.read_text(encoding="utf-8"), "conteúdo existente")
        self.assertEqual(list(self.root.iterdir()), [destination])

    def test_failed_replace_preserves_existing_file_and_removes_temporary(self):
        destination = self.root / "relatorio.json"
        destination.write_bytes(b"original")

        with patch("arvertes_studio.core.reports.os.replace", side_effect=OSError("falha")):
            with self.assertRaises(ReportError):
                write_report(self.report, destination)

        self.assertEqual(destination.read_bytes(), b"original")
        self.assertEqual(list(self.root.iterdir()), [destination])


if __name__ == "__main__":
    unittest.main()
