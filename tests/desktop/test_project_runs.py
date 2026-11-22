from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
import unittest

from arvertes_desktop.project_runs import FLOW, LEASE_SECONDS
from arvertes_desktop.production import review_gate
from arvertes_desktop.status_snapshot import snapshot
from arvertes_desktop.workspace import Workspace


def plan():
    return {"workflow": "glb_inspection", "sender": "coordenador",
            "messages": [{"type": "delegate", "step": step, "to": agent, "depends_on": list(deps)}
                         for step, agent, deps in FLOW]}


class ProjectRunTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "workspace.sqlite3"
        self.workspace = Workspace(self.path)
        self.addCleanup(self.workspace.close)
        self.project = self.workspace.create_project("Fixture")
        asset = self.path.parent / "source.glb"
        asset.write_bytes(b"fixture")
        self.asset = self.workspace.add_reference(self.project, str(asset))
        self.workspace.add_task(self.project, "Rascunho antigo", "Continua no banco.")
        self.runs = self.workspace.inspections

    def queue(self, proposal=None):
        return self.runs.create(self.project, self.asset, "Fixture", sha256(b"fixture").hexdigest(),
                                False, 512, proposal or plan())

    def test_checkpoint_recovery_and_old_workspace(self):
        run = self.queue()
        token = self.runs.reserve(run)
        self.runs.begin(run, token, "catalog")
        self.runs.complete(run, token, "catalog", {"category": "model"})
        self.runs.begin(run, token, "blender")
        self.assertTrue(self.runs.stop(run, token, reason="Simulação de encerramento"))
        reopened = Workspace(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.tasks(self.project)[0]["title"], "Rascunho antigo")
        self.assertEqual(reopened.db.execute("PRAGMA user_version").fetchone()[0], 1)
        lease = reopened.inspections.reserve(run)
        self.assertEqual(reopened.inspections.next_step(run, lease), "blender")
        with self.assertRaisesRegex(ValueError, "reserva"):
            self.runs.complete(run, token, "blender", {"report": "atrasado"})
        self.runs.stop(run, lease, cancelled=True)
        with self.assertRaises(ValueError):
            self.runs.reserve(run)

    def test_crash_reservation_expiry_fences_another_instance(self):
        first, second = self.queue(), self.queue()
        expired = self.runs.reserve(first, now=time() - LEASE_SECONDS - 2)
        reserved = self.runs.reserve(second)
        self.assertEqual(self.runs.get(first)["status"], "interrupted")
        self.assertFalse(self.runs.stop(first, expired))
        with self.assertRaises(ValueError):
            self.runs.reserve(first)
        self.runs.stop(second, reserved)

    def test_sentinel_rejects_plan_and_bypassing_dependencies(self):
        forged = plan()
        forged["messages"][-1]["to"] = "coordenador"
        with self.assertRaisesRegex(ValueError, "Sentinel"):
            self.queue(forged)
        run = self.queue()
        token = self.runs.reserve(run)
        with self.assertRaisesRegex(ValueError, "Sentinel"):
            self.runs.begin(run, token, "gate")

    def test_help_history_and_snapshot_summary(self):
        run = self.queue()
        token = self.runs.reserve(run)
        for key in ("catalog", "blender", "budget"):
            self.runs.begin(run, token, key)
            self.runs.complete(run, token, key, {"fixture": True})
        event = next(row for row in self.runs.history(run) if row["kind"] == "help_requested")
        self.assertEqual((event["sender"], event["recipient"]), ("inspetor", "otimizador"))
        data = snapshot(self.workspace, None, None)
        self.assertEqual(data["projects"][0]["reference_count"], 1)
        self.assertEqual({item["kind"] for item in data["tasks"]}, {"draft", "inspection"})
        self.assertNotIn(str(self.path.parent), str(data))

    def test_independent_gate_uses_report_even_when_agents_omit_an_issue(self):
        report = {"summary": {"geometry_evaluated": {"triangles": 1001},
                  "geometry_original": {"triangles": 200}, "mesh_count": 1, "meshes_without_uv": 0}}
        done = {"blender": {"report": report}, "inspect": {"findings": []}, "audit": {
                "findings": [], "requires_human_approval": True}}
        self.assertTrue(review_gate(done, 1000)["reason"])
        self.assertTrue(review_gate(done, 2000)["requires_human_approval"])
        done["audit"]["requires_human_approval"] = False
        with self.assertRaisesRegex(ValueError, "Sentinel"):
            review_gate(done, 2000)
