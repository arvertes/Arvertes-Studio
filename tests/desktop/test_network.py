import http.client
from hashlib import sha256
import json
from pathlib import Path
import secrets
import ssl
from tempfile import TemporaryDirectory
from time import monotonic
import unittest

from arvertes_desktop.network import DeviceHub, SESSION_TIMEOUT
from arvertes_desktop.remote_work import digest_step

METRICS = {"ram_available": 900, "ram_total": 4096, "cpu_pct": 2, "battery": 95, "thermal": 0}


class NetworkTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "devices.sqlite3"
        self.hub = DeviceHub(self.path)
        self.addCleanup(self.hub.close)
        self.listener = self.start("wifi_local")
        self.identity = {"id": secrets.token_hex(16), "token": secrets.token_hex(32)}

    def start(self, transport):
        return self.hub.start("127.0.0.1/8", transport, advertise=False, test_loopback=True)

    def request(self, action, identity=None, listener=None, pin=None, **data):
        listener = listener or self.listener
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        cert, _ = self.hub.registry.identity()
        context.load_verify_locations(cadata=cert.decode())
        context.check_hostname = False
        connection = http.client.HTTPSConnection("127.0.0.1", listener.server_port, context=context, timeout=3)
        try:
            connection.connect()
            expected = self.hub.fingerprint if pin is None else pin
            if sha256(connection.sock.getpeercert(binary_form=True)).hexdigest() != expected:
                raise ssl.SSLError("Identidade TLS divergente")
            connection.request("POST", "/v1/session", json.dumps(
                {"version": 1, "action": action, **(identity or self.identity), **data}),
                {"Content-Type": "application/json"})
            response = connection.getresponse()
            return response.status, json.load(response)
        finally:
            connection.close()

    def pair(self, identity=None, listener=None):
        listener = listener or self.listener
        invitation = self.hub.invitation(listener.transport).split(":")
        self.assertEqual(invitation[4], self.hub.fingerprint)
        code = invitation[-1]
        self.assertEqual(self.request("pair", identity, listener, code=code, name="Celular")[0], 200)
        return code

    def poll(self, identity=None, listener=None, reply=None, consent=True, metrics=METRICS):
        return self.request("poll", identity, listener, reply=reply, consent=consent, metrics=metrics)

    def test_tls_pairing_reuse_unknown_revocation_and_forbidden_action(self):
        with self.assertRaises(ssl.SSLError):
            self.request("poll", pin="0" * 64)
        self.assertEqual(self.poll()[0], 401)
        code = self.pair()
        self.assertEqual(self.request("pair", code=code, name="Celular")[0], 401)
        self.assertEqual(self.poll()[0], 200)
        self.assertEqual(self.request("execute", command="unknown")[0], 403)
        self.assertIn("Sentinel bloqueou", self.hub.notice)
        self.hub.revoke(self.identity["id"])
        self.assertEqual(self.poll()[0], 401)
        self.assertEqual(self.hub.snapshot(), [])

    def test_bidirectional_multiple_nodes_and_reconnect_after_timeout(self):
        self.pair()
        usb = self.start("usb")
        other = {"id": secrets.token_hex(16), "token": secrets.token_hex(32)}
        self.pair(other, usb)
        self.assertEqual(self.poll(listener=usb)[0], 401)
        self.assertEqual(self.poll(other)[0], 401)
        self.assertEqual(self.poll()[0], 200)
        self.assertEqual(self.poll(other, usb)[0], 200)
        self.hub.send_probe(self.identity["id"])
        nonce = self.poll()[1]["probe"]
        self.assertIsNotNone(nonce)
        self.assertIsNone(self.poll(other, usb)[1]["probe"])
        self.assertIsNone(self.poll(reply=nonce)[1]["probe"])
        self.assertEqual(self.hub.probes[self.identity["id"]]["state"], "confirmed")
        self.hub.send_probe(other["id"])
        with self.hub.lock:
            self.hub.sessions[other["id"]]["seen"] = monotonic() - SESSION_TIMEOUT - 1
        self.assertEqual(len([session for _, _, session, _ in self.hub.snapshot() if session]), 1)
        self.assertEqual(self.hub.probes[other["id"]]["state"], "cancelled")
        self.assertEqual(self.poll(other, usb)[0], 200)
        self.assertEqual(len([session for _, _, session, _ in self.hub.snapshot() if session]), 2)
        self.assertEqual(self.request("disconnect", other, usb)[0], 200)
        self.assertNotIn(other["id"], self.hub.sessions)

    def test_consent_resource_gate_and_cancelled_reply(self):
        self.pair()
        self.assertEqual(self.poll(consent=False)[0], 200)
        with self.assertRaisesRegex(ValueError, "Sentinel bloqueou"):
            self.hub.send_probe(self.identity["id"])
        self.poll(metrics={**METRICS, "thermal": 3})
        with self.assertRaisesRegex(ValueError, "recursos"):
            self.hub.send_probe(self.identity["id"])
        self.poll()
        self.hub.send_probe(self.identity["id"])
        nonce = self.poll()[1]["probe"]
        self.hub.cancel_probe(self.identity["id"])
        self.poll(reply=nonce)
        self.assertEqual(self.hub.probes[self.identity["id"]]["state"], "cancelled")
        self.hub.send_probe(self.identity["id"])
        nonce = self.poll()[1]["probe"]
        self.poll(reply=nonce, consent=False)
        self.assertEqual(self.hub.probes[self.identity["id"]]["state"], "cancelled")

    def test_pairing_and_identity_persist_across_restart(self):
        self.pair()
        original = self.hub.fingerprint
        self.hub.close()
        self.hub = DeviceHub(self.path)
        self.addCleanup(self.hub.close)
        self.listener = self.start("wifi_local")
        self.assertEqual(original, self.hub.fingerprint)
        self.assertEqual(self.poll()[0], 200)

    def work_poll(self, enabled=True, result=None, metrics=METRICS):
        return self.request("poll", reply=None, consent=True, metrics=metrics,
                            work_enabled=enabled, work_result=result)

    def test_mobile_work_checkpoint_resume_and_authentication(self):
        self.pair()
        device = self.identity["id"]
        self.poll()
        with self.assertRaisesRegex(ValueError, "Sentinel"):
            self.hub.queue_work(device)
        self.work_poll()
        with self.assertRaisesRegex(ValueError, "Sentinel"):
            self.hub.queue_work(device, "blender")
        self.hub.queue_work(device)
        with self.assertRaises(ValueError):
            self.hub.queue_work(device)
        with self.assertRaisesRegex(ValueError, "reservado"):
            self.hub.send_probe(device)
        first = self.work_poll()[1]["work"]
        result = {"lease": first["lease"], "digest": digest_step(first["seed"], first["index"])}
        second = self.work_poll(result=result)[1]["work"]
        self.assertEqual(second["index"], 1)
        self.hub.close()
        self.hub = DeviceHub(self.path)
        self.addCleanup(self.hub.close)
        self.listener = self.start("wifi_local")
        self.assertEqual(self.hub.work.latest(device), ("paused", 1))
        resumed = self.work_poll(result=result)[1]["work"]
        self.assertEqual(resumed["index"], 1)
        self.assertNotEqual(resumed["lease"], second["lease"])
        self.hub.cancel_work(device)
        late = {"lease": resumed["lease"], "digest": digest_step(resumed["seed"], resumed["index"])}
        self.assertIsNone(self.work_poll(result=late)[1]["work"])
        self.assertEqual(self.hub.work.latest(device), ("cancelled", 1))

    def test_mobile_work_refuses_bad_results_and_low_budget(self):
        self.pair()
        device = self.identity["id"]
        self.work_poll(metrics={**METRICS, "ram_available": 519})
        with self.assertRaisesRegex(ValueError, "Sentinel"):
            self.hub.queue_work(device)
        self.work_poll()
        self.hub.queue_work(device)
        offered = self.work_poll()[1]["work"]
        self.work_poll(result={"lease": offered["lease"], "digest": "0" * 64})
        self.assertEqual(self.hub.work.latest(device), ("rejected", 0))
        self.assertIn("divergiu", self.hub.notice)

    def test_public_or_wildcard_addresses_rejected(self):
        for address in ("0.0.0.0/0", "8.8.8.8/24", "127.0.0.1/8"):
            with self.assertRaises(ValueError):
                self.hub.start(address, "usb")


if __name__ == "__main__":
    unittest.main()
