from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import unittest

from arvertes_desktop.office_preview import PreviewServer
from arvertes_desktop.roster import AGENTS
import json

class PreviewTests(unittest.TestCase):
    def test_roster_matches(self):
        roster = json.loads((Path(__file__).resolve().parents[2] / "office_habblaud/roster.json").read_text(encoding="utf-8"))
        self.assertEqual([(a["id"], a["name"], a["role"], a["department"]) for a in roster],
                         [(a.id,a.name,a.role,a.department) for a in AGENTS])

    def test_loopback_read_only(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "public"
            root.mkdir()
            (root / "index.html").write_text("preview", encoding="utf-8")
            (root.parent / "private.txt").write_text("private", encoding="utf-8")
            server = PreviewServer(root)
            try:
                with urlopen(server.url, timeout=3) as response:
                    self.assertEqual(response.read(), b"preview")
                    self.assertIn("default-src 'none'", response.headers["Content-Security-Policy"])
                for req, code in (
                    (Request(server.url + "%2e%2e/private.txt"), 404),
                    (Request(server.url + "api/messages", data=b"{}"), 501),
                    (Request(server.url, headers={"Host":"other.invalid"}), 403),
                ):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(req, timeout=3)
                    self.assertEqual(caught.exception.code, code)
                    caught.exception.close()
            finally:
                server.close()
