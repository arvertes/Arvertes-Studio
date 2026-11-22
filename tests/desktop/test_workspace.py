from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
import unittest

from arvertes_desktop.roster import AGENTS, DEPARTMENTS, filter_agents
from arvertes_desktop.workspace import Workspace


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "workspace.sqlite3"
        self.store = Workspace(self.path)
        self.addCleanup(self.store.close)
        self.project = self.store.create_project("Personagem")

    def test_roster(self):
        self.assertEqual(len(AGENTS), 26)
        self.assertEqual(len({a.id for a in AGENTS}), 26)
        self.assertEqual(len({a.name for a in AGENTS}), 26)
        self.assertEqual([len(filter_agents(d)) for d in DEPARTMENTS], [4, 6, 6, 5, 5])
        self.assertEqual(filter_agents(query="atlas")[0].id, "coordenador")
        self.assertEqual(filter_agents("Qualidade", "aegis")[0].id, "auditor")
        self.assertEqual(filter_agents("Áudio", "atlas"), ())

    def test_projects(self):
        self.assertEqual(self.store.projects()[0]["name"], "Personagem")
        with self.assertRaises(ValueError):
            self.store.create_project(" ")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.create_project("Personagem")

    def test_references(self):
        file = Path(self.temp.name) / "example.glb"
        file.write_bytes(b"synthetic")
        self.store.add_reference(self.project, str(file))
        self.assertEqual(self.store.assets(self.project)[0]["path"], str(file.resolve()))
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.add_reference(self.project, str(file))
        with self.assertRaises(OSError):
            self.store.add_reference(self.project, str(file.parent / "missing.png"))
        self.assertEqual(file.read_bytes(), b"synthetic")
        other = self.store.create_project("Outro")
        self.assertEqual(self.store.assets(other), [])

    def test_queue(self):
        first = self.store.add_task(self.project, "Modelo", "Preparar geometria")
        second = self.store.add_task(self.project, "Texturas", "Criar material")
        third = self.store.add_task(self.project, "Rig", "Preparar esqueleto")
        self.store.move_task(third, -1)
        self.assertEqual([r["id"] for r in self.store.tasks(self.project)], [first, third, second])
        self.store.cancel_task(third)
        self.store.move_task(second, -1)
        self.assertEqual([r["id"] for r in self.store.tasks(self.project)], [second, third, first])
        self.assertEqual(self.store.tasks(self.project)[1]["status"], "cancelled")
        with self.assertRaises(ValueError):
            self.store.add_task(self.project, " ", "abc")
        with self.assertRaises(ValueError):
            self.store.move_task(second, 0)

    def test_reopen(self):
        self.store.add_task(self.project, "Pacote", "Gerar pacote completo")
        reopened = Workspace(self.path)
        try:
            self.assertEqual(reopened.projects()[0]["id"], self.project)
            self.assertEqual(reopened.tasks(self.project)[0]["status"], "draft")
        finally:
            reopened.close()

    def test_schema_version(self):
        other = Path(self.temp.name) / "other.sqlite3"
        with closing(sqlite3.connect(other)) as db:
            db.execute("PRAGMA user_version=9")
            db.commit()
        with self.assertRaises(ValueError):
            Workspace(other)


if __name__ == "__main__":
    unittest.main()
