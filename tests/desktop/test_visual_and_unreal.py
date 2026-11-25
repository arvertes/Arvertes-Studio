import json
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from unittest import TestCase

from arvertes_desktop.visual_executor import TRAITS, observations, probe
from scripts.unreal_acceptance import load_plan


class VisionContract(TestCase):
    def test_observations_remain_tied_to_reference_and_require_confirmation(self):
        fixture = {field:{"state":"missing","text":""} for field in TRAITS}
        fixture["hair"] = {"state":"observed","text":"Trança escura"}
        fixture["materials"] = {"state":"hypothesis","text":"Possivelmente tecido"}
        result = observations(fixture, "a"*64, "fixture:q4", "b"*64)
        self.assertEqual(result["reference_sha256"], "a"*64)
        self.assertFalse(result["traits"]["hair"]["human_confirmed"])
        self.assertEqual(result["traits"]["materials"]["state"], "hypothesis")
        with self.assertRaises(ValueError):
            observations({**fixture, "face":{"state":"approved","text":"inventado"}}, "a"*64, "fixture:q4", "b"*64)

    def test_loopback_probes_metadata_and_rejects_unapproved_and_cloud(self):
        hits = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def send_data(self, data):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())

            def do_GET(self):
                hits.append(self.path)
                self.send_data({"models":[{"name":"fixture:q4","size":256,"digest":"a"*64}]})

            def do_POST(self):
                hits.append(self.path)
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_data({"capabilities":["vision"]})

        with HTTPServer(("127.0.0.1",0), Handler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_port
                self.assertFalse(probe("fixture:q4",port)["available"])
                self.assertFalse(probe("fixture:cloud",port,approved=True,license_reviewed=True)["available"])
                self.assertEqual(hits, [])
                self.assertTrue(probe("fixture:q4",port,approved=True,license_reviewed=True)["available"])
                self.assertEqual(hits, ["/api/tags","/api/show"])
            finally:
                server.shutdown()
                thread.join()


class UnrealPreparedPlan(TestCase):
    def test_plan_requires_new_namespace_and_exact_artifact_hashes(self):
        with TemporaryDirectory() as scratch:
            directory = Path(scratch)
            (directory / "models").mkdir()
            paths = ["models/asset.fbx", "models/lod1.fbx"]
            payload = b"synthetic staging fixture"
            for name in paths:
                (directory / name).write_bytes(payload)
            files = [{"path":name, "bytes":len(payload), "sha256":sha256(payload).hexdigest()} for name in paths]
            plan = {"schema":1,"state":"unreal_import_pending","package_sha256":"a"*64,"destination":
                    "/Game/ArvertesAcceptance/"+"f"*32, "base":paths[0], "lods":paths[1:],"textures":[],
                    "units":"cm","height_cm":170.0,"fbx_axes":{"forward":"-Y","up":"Z"},
                    "minimum_materials":2,"clips":["Walk"],"files":files}
            raw = json.dumps(plan).encode()
            (directory / "import-plan.json").write_bytes(raw)
            with self.assertRaises(ValueError):
                load_plan(directory, "b"*64)
            self.assertEqual(load_plan(directory, sha256(raw).hexdigest()), plan)
            (directory / paths[1]).write_bytes(b"altered")
            with self.assertRaises(ValueError):
                load_plan(directory, sha256(raw).hexdigest())
