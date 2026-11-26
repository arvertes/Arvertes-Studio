from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import sqlite3
import unittest

from arvertes_desktop.lab_queue import LEASE_SECONDS, Queue, geometry_row


class WorkerQueueTest(unittest.TestCase):
    def setUp(self):
        scratch = TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.now = 100
        self.queue = Queue(self.root, clock=lambda: self.now)
        self.small = self.queue.enqueue(3042, "oriented_hash")

    def claim(self):
        return self.queue.claim(uuid4().hex)

    def test_approval_parallel_claims_priority_and_stop(self):
        self.assertIsNone(self.claim())
        with self.assertRaises(ValueError):
            self.queue.control("enable")
        self.queue.control("enable", approved=True)
        self.queue.enqueue(9800, "oriented_hash", priority=True)
        with ThreadPoolExecutor(4) as threads:
            claimed = [task for task in threads.map(lambda _: self.claim(), range(4)) if task]
        self.assertEqual(len(claimed), 1)
        current = claimed[0]
        self.assertEqual(current["id"], self.small)
        self.assertTrue(self.queue.checkpoint(current, 0, [geometry_row(39,0,"oriented_hash")], 1, 1024))
        self.queue.control("owner-busy")
        self.assertFalse(self.queue.heartbeat(current))
        self.assertIsNone(self.claim())
        self.queue.control("owner-idle")
        current = self.claim()
        self.assertEqual(current["next_row"], 1)
        self.queue.control("stop")
        with self.assertRaises(ValueError):
            self.queue.checkpoint(current, 1, [geometry_row(39,1,"oriented_hash")], 1, 1024)
        self.assertEqual(self.queue.read()["jobs"][0]["next_row"], 1)

    def test_expiry_resume_fences_old_results_and_saves_cycle(self):
        self.queue.control("enable", approved=True)
        original = self.claim()
        row = geometry_row(39,0,"oriented_hash")
        self.queue.checkpoint(original, 0, [row], 5, 1000)
        self.now += LEASE_SECONDS+1
        self.queue = Queue(self.root, clock=lambda: self.now)
        recovered = self.claim()
        self.assertEqual(recovered["next_row"], 1)
        with self.assertRaises(ValueError):
            self.queue.checkpoint(original, 1, [row], 5, 1000)
        with self.queue._transaction() as db:
            db.execute("UPDATE control SET elapsed_us=21599999999")
        self.queue.checkpoint(recovered, 1, [geometry_row(39,1,"oriented_hash")], 2, 1000)
        self.assertEqual(self.queue.read()["evaluations"][0]["number"], 1)
        with self.assertRaises(ValueError):
            self.queue.checkpoint(recovered, 1, [row], 2, 1000)

    def test_work_is_real_and_methods_agree(self):
        for row in (0,4,38):
            a = geometry_row(39,row,"oriented_hash")
            b = geometry_row(39,row,"oriented_sort")
            self.assertEqual(a,b)
            self.assertEqual(a[:2], (79,78))
        with self.assertRaises(ValueError):
            geometry_row(39,0,"unknown")

    def test_journal_cannot_replace_another_database(self):
        other = self.root / "external"
        other.mkdir()
        target = other / self.queue.path.name
        with closing(sqlite3.connect(target)) as db, db:
            db.execute("CREATE TABLE original (data TEXT)")
        snapshot = target.read_bytes()
        with self.assertRaises(ValueError):
            Queue(other)
        self.assertEqual(target.read_bytes(), snapshot)

    def test_new_authorization_fences_previous_service_and_its_results(self):
        self.queue.control("enable", approved=True)
        previous = self.queue.authorization()
        task = self.queue.claim(uuid4().hex, previous)
        self.queue.checkpoint(task, 0, [geometry_row(39, 0, "oriented_hash")], 2, 1000)
        self.queue.control("stop")
        self.queue.control("enable", approved=True)
        with self.assertRaises(ValueError):
            self.queue.checkpoint(task, 1, [geometry_row(39, 1, "oriented_hash")], 2, 1000)
        self.assertIsNone(self.queue.claim(uuid4().hex, previous))
        new_task = self.queue.claim(uuid4().hex, self.queue.authorization())
        self.assertEqual(new_task["next_row"], 1)

    def test_service_runs_without_ui_and_stops_after_revocation(self):
        import json
        import subprocess
        import sys
        from time import monotonic, sleep

        self.queue.control("enable", approved=True)
        command = [sys.executable, "-m", "arvertes_desktop.lab_queue", "--workspace", str(self.root)]
        with subprocess.Popen([*command, "serve", "--max-seconds", "12"], stdout=subprocess.PIPE) as process:
            try:
                standby = monotonic() + 8
                while monotonic() < standby and self.queue.read()["jobs"][0]["state"] != "done":
                    sleep(.1)
                self.assertEqual(self.queue.read()["jobs"][0]["state"], "done")
                self.queue.control("stop")
                self.queue.control("enable", approved=True)
                output = process.communicate(timeout=4)[0]
                self.assertEqual(json.loads(output), {"state":"authorization_revoked", "processed":1})
            finally:
                if process.poll() is None:
                    process.terminate()
