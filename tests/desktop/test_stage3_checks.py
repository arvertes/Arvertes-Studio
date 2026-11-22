from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from arvertes_desktop.cloud_projection import projection
from arvertes_desktop.resources import Reading, budget, reserve, stop_children
from arvertes_desktop.update_check import MEMBER, verify
from arvertes_desktop.workspace import Workspace


class Stage3Checks(unittest.TestCase):
    def test_resource_gates_use_per_machine_headroom(self):
        self.assertEqual(reserve(Reading(5000, 8192, 20)), 1024)
        self.assertEqual(budget(Reading(2200, 8192, 20)), 1176)
        with self.assertRaisesRegex(ValueError, "memória"):
            budget(Reading(2000, 8192, 20))
        with self.assertRaisesRegex(ValueError, "CPU"):
            budget(Reading(4000, 8192, 95))

    def test_owned_child_is_reaped(self):
        script = ("import subprocess,sys; "
                  "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                  "print(p.pid,flush=True); p.wait(timeout=28)")
        with subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True) as parent:
            self.assertGreater(int(parent.stdout.readline()), 0)
            try:
                stop_children(parent.pid)
                self.assertEqual(parent.wait(timeout=5), 0)
            finally:
                stop_children(parent.pid)
                if parent.poll() is None:
                    parent.kill()

    def test_cloud_selection_rejects_other_projects_and_strips_names(self):
        with TemporaryDirectory() as directory:
            store = Workspace(Path(directory) / "state.sqlite3")
            try:
                project = store.create_project("Nome privado")
                other = store.create_project("Outro privado")
                store.add_task(project, "Título privado", "Instrução privada")
                store.add_task(other, "Rascunho fora do escopo", "Fora")
                store.inspections.note(project, "art", "Decisão privada")
                selection = projection(store, None, None, None, project, ("projects", "tasks", "history"))
                self.assertEqual(len(selection["sections"]["tasks"]), 1)
                self.assertEqual(selection["sections"]["tasks"][0]["project"], project)
                self.assertNotIn("privad", str(selection))
                with self.assertRaises(ValueError):
                    projection(store, None, None, None, None, ("tasks",))
            finally:
                store.close()

    def test_manual_update_validates_revision_version_and_hash(self):
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            archive, manifest = directory / "Arvertes.zip", directory / "UpdateManifest.json"
            content = {"platform": "windows-x64", "version": "0.2.5", "revision": "a" * 40}
            with ZipFile(archive, "w") as package:
                package.writestr(MEMBER, json.dumps(content))
            expected = {**content, "sha256": sha256(archive.read_bytes()).hexdigest()}
            manifest.write_text(json.dumps(expected))
            self.assertIn("mais recente", verify(archive, manifest))
            manifest.write_text(json.dumps({**expected, "version": "0.2.8"}))
            with self.assertRaisesRegex(ValueError, "metadados"):
                verify(archive, manifest)
            manifest.write_text(json.dumps({**expected, "sha256": "1" * 64}))
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                verify(archive, manifest)
