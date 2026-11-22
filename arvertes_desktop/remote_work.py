"""Checkpoint e reserva por aparelho para uma única operação sintética."""
from contextlib import closing, contextmanager
from hashlib import sha256
import hmac
import re
import secrets
import sqlite3
from time import time

KIND = "digest_fixture"
STEPS = 4
ROUNDS = 128
LEASE_SECONDS = 12
RESERVATION_MIB = 8
HEX32 = re.compile(r"[0-9a-f]{32}")
HEX64 = re.compile(r"[0-9a-f]{64}")


def digest_step(seed, index):
    value = bytes.fromhex(seed) + bytes([index])
    for _ in range(ROUNDS):
        value = sha256(value).digest()
    return value.hex()


class RemoteWork:
    def __init__(self, registry):
        self.registry = registry
        with closing(registry.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS mobile_work (
                       id TEXT PRIMARY KEY, device TEXT NOT NULL, seed TEXT NOT NULL, step INTEGER NOT NULL,
                       state TEXT NOT NULL, lease TEXT, expiry REAL, created REAL NOT NULL)""")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS mobile_work_active ON mobile_work(device)
                       WHERE state IN ('queued','running','paused')""")

    @contextmanager
    def transaction(self):
        with closing(self.registry.connect()) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            yield db

    def latest(self, device):
        with closing(self.registry.connect()) as db:
            return db.execute("SELECT state,step FROM mobile_work WHERE device=? ORDER BY created DESC LIMIT 1",
                              (device,)).fetchone() or ("", 0)

    def progress(self, device):
        with closing(self.registry.connect()) as db:
            record = db.execute("SELECT id,state,step FROM mobile_work WHERE device=? ORDER BY created DESC LIMIT 1",
                                (device,)).fetchone()
        return {"job": record[0], "state": record[1], "confirmed": record[2], "total": STEPS} if record else None

    def create(self, device, kind):
        if kind != KIND:
            raise ValueError("Sentinel bloqueou: trabalho móvel fora do contrato leve.")
        with self.transaction() as db:
            if self.active(db, device):
                raise ValueError("Já há um trabalho reservado para este aparelho.")
            db.execute("INSERT INTO mobile_work VALUES (?,?,?,0,'queued',NULL,NULL,?)",
                       (secrets.token_hex(16), device, secrets.token_hex(16), time()))

    @staticmethod
    def active(db, device):
        return db.execute("""SELECT * FROM mobile_work WHERE device=?
                             AND state IN ('queued','running','paused')""", (device,)).fetchone()

    def stop(self, device, *, cancel=False):
        with self.transaction() as db:
            db.execute("""UPDATE mobile_work SET state=?,lease=NULL,expiry=NULL WHERE device=?
                           AND state IN ('queued','running','paused')""",
                       ("cancelled" if cancel else "paused", device))

    def exchange(self, device, ready, reply):
        if reply is not None and (
                not isinstance(reply, dict) or set(reply) != {"lease", "digest"}
                or not isinstance(reply["lease"], str) or not HEX32.fullmatch(reply["lease"])
                or not isinstance(reply["digest"], str) or not HEX64.fullmatch(reply["digest"])):
            raise ValueError("Resultado móvel fora do protocolo.")
        with self.transaction() as db:
            work = self.active(db, device)
            if work is None:
                return None
            if not ready:
                if work["state"] != "paused":
                    db.execute("UPDATE mobile_work SET state='paused',lease=NULL,expiry=NULL WHERE id=?", (work["id"],))
                return None
            index, lease, now = work["step"], work["lease"], time()
            if lease and work["expiry"] > now:
                if reply is not None and hmac.compare_digest(reply["lease"], lease):
                    if not hmac.compare_digest(digest_step(work["seed"], index), reply["digest"]):
                        db.execute("UPDATE mobile_work SET state='rejected',lease=NULL,expiry=NULL WHERE id=?", (work["id"],))
                        return "rejected"
                    index += 1
                    lease = None
                    db.execute("UPDATE mobile_work SET step=?,state=?,lease=NULL,expiry=NULL WHERE id=?",
                               (index, "completed" if index == STEPS else "queued", work["id"]))
                    if index == STEPS:
                        return None
            else:
                lease = None
            if lease is None:
                lease = secrets.token_hex(16)
                db.execute("UPDATE mobile_work SET state='running',lease=?,expiry=? WHERE id=?",
                           (lease, now + LEASE_SECONDS, work["id"]))
            return {"kind": KIND, "seed": work["seed"], "index": index, "lease": lease}
