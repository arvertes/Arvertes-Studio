"""Fila local experimental independente da aba e das bases oficiais."""
from argparse import ArgumentParser
from contextlib import closing, contextmanager
from hashlib import sha256
from itertools import groupby
from pathlib import Path
from shutil import disk_usage
from struct import pack
from time import time, monotonic
from uuid import uuid4
import json
import re
import sqlite3

import psutil

from .resources import MIB, reading, reserve

SIZES = {3042: 39, 9800: 70, 29768: 122, 99458: 223}
METHODS = ("oriented_hash", "oriented_sort")
LEASE_SECONDS = 6
SIX_HOURS_US = 21_600_000_000
APP_ID = 0x41524C35
SCHEMA = """
CREATE TABLE IF NOT EXISTS control (
  id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL, owner_busy INTEGER NOT NULL,
  elapsed_us INTEGER NOT NULL, cycles INTEGER NOT NULL, cycling_improvements INTEGER NOT NULL
);
INSERT OR IGNORE INTO control VALUES (1,0,0,0,0,0);
CREATE TABLE IF NOT EXISTS workers (
  id TEXT PRIMARY KEY, seen REAL NOT NULL, state TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, size INTEGER NOT NULL, method TEXT NOT NULL, priority INTEGER NOT NULL,
  state TEXT NOT NULL, next_row INTEGER NOT NULL DEFAULT 0, before_faces INTEGER NOT NULL DEFAULT 0,
  after_faces INTEGER NOT NULL DEFAULT 0, chain TEXT NOT NULL DEFAULT '', elapsed_us INTEGER NOT NULL DEFAULT 0,
  peak_rss INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0,
  worker TEXT, lease TEXT, deadline REAL, reason TEXT
);
CREATE TABLE IF NOT EXISTS cycles (
  number INTEGER PRIMARY KEY, completed_at REAL NOT NULL, improvements INTEGER NOT NULL
);
"""


def geometry_row(width, row, method):
    """Triangula uma faixa real. A entrada repete deliberadamente a primeira face."""
    faces = []
    stride = width + 1
    for column in range(width):
        base = row*stride+column
        faces.extend([(base,base+1,base+stride), (base+1,base+stride+1,base+stride)])
    a,b,c = faces[0]
    faces.append((b,c,a))
    canonical = []
    for face in faces:
        # Reconstrói coordenadas integer da grade e confere a orientação/alocação.
        points = [(vertex % stride, vertex // stride) for vertex in face]
        a,b,c = points
        signed_area = (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
        if signed_area != 1:
            raise ValueError("Faixa sintética inválida.")
        start = face.index(min(face))
        canonical.append(face[start:] + face[:start])
    if method == "oriented_hash":
        unique = sorted(set(canonical))
    elif method == "oriented_sort":
        unique = [face for face,_ in groupby(sorted(canonical))]
    else:
        raise ValueError("Método experimental desconhecido.")
    checksum = sha256()
    for face in unique:
        checksum.update(pack("<III", *face))
    return len(faces), len(unique), checksum.hexdigest()


class LeaseExpired(ValueError):
    pass


class Queue:
    def __init__(self, root, clock=time):
        self.root = root
        self.clock = clock
        root.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.path = root / "arvertes-lab-worker.sqlite3"
        if root.is_symlink() or self.path.is_symlink():
            raise ValueError("Escolha uma pasta experimental local.")
        with closing(sqlite3.connect(self.path, timeout=5)) as db:
            identifier = db.execute("PRAGMA application_id").fetchone()[0]
            if identifier not in (0, APP_ID) or (not identifier and db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone()):
                raise ValueError("Arquivo existente não pertence ao laboratório.")
            db.executescript(f"PRAGMA application_id={APP_ID};" + SCHEMA)

    @contextmanager
    def _transaction(self):
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            yield db

    def control(self, option, *, approved=False):
        operations = {"enable": ("enabled", 1), "stop": ("enabled", 0),
                      "owner-busy": ("owner_busy", 1), "owner-idle": ("owner_busy", 0)}
        if option not in operations or (option == "enable" and approved is not True):
            raise ValueError("A ativação exige autorização explícita do operador.")
        field, value = operations[option]
        with self._transaction() as db:
            db.execute(f"UPDATE control SET {field}=? WHERE id=1", (value,))
            if option in ("stop", "owner-busy"):
                for row in db.execute("SELECT * FROM jobs WHERE state='running'").fetchall():
                    self._release(db, row, "owner_priority_or_stop")

    def enqueue(self, size, method, *, priority=False):
        if type(size) is not int or size not in SIZES or method not in METHODS or type(priority) is not bool:
            raise ValueError("Receita ou escala fora dos limites experimentais.")
        job = f"{method}-{size}-v1"
        with self._transaction() as db:
            db.execute("INSERT OR IGNORE INTO jobs(id,size,method,priority,state) VALUES (?,?,?,?,'queued')",
                       (job,size,method,int(priority)))
            if priority:
                db.execute("UPDATE jobs SET priority=1 WHERE id=? AND state='queued'", (job,))
        return job

    def claim(self, worker):
        if not isinstance(worker, str) or not re.fullmatch(r"[a-f0-9]{32}", worker):
            raise ValueError("Identificador de worker inválido.")
        with self._transaction() as db:
            now = self.clock()
            db.execute("DELETE FROM workers WHERE seen<?", (now - 600,))
            db.execute("""UPDATE jobs SET state=CASE WHEN attempts>=3 THEN 'blocked' ELSE 'queued' END,
                worker=NULL,lease=NULL,deadline=NULL,reason='expired' WHERE state='running' AND deadline<=?""", (now,))
            db.execute("""DELETE FROM workers WHERE id IN (SELECT id FROM workers WHERE state='idle'
                ORDER BY seen DESC LIMIT -1 OFFSET 30)""")
            db.execute("""UPDATE workers SET state='idle' WHERE state='busy' AND NOT EXISTS (
                SELECT 1 FROM jobs WHERE worker=workers.id AND state='running')""")
            db.execute("""INSERT INTO workers VALUES (?,?,'idle') ON CONFLICT(id)
                DO UPDATE SET seen=excluded.seen""", (worker,now))
            settings = db.execute("SELECT enabled,owner_busy FROM control").fetchone()
            if not settings["enabled"] or settings["owner_busy"] or db.execute(
                    "SELECT 1 FROM jobs WHERE state='running' LIMIT 1").fetchone():
                return None
            # Progressão por método. Uma etapa grande espera o menor patamar precedente.
            choices = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY priority DESC,size,id")
            for candidate in choices:
                previous = [size for size in SIZES if size < candidate["size"]]
                if previous and not db.execute("""SELECT 1 FROM jobs WHERE size=? AND method=?
                            AND state='done'""", (max(previous),candidate["method"])).fetchone():
                    continue
                lease = uuid4().hex
                db.execute("""UPDATE jobs SET state='running',worker=?,lease=?,deadline=?,attempts=attempts+1,
                            reason=NULL WHERE id=?""", (worker,lease,now+LEASE_SECONDS,candidate["id"]))
                db.execute("UPDATE workers SET state='busy' WHERE id=?", (worker,))
                return {**dict(candidate), "lease":lease, "worker":worker}
            return None

    def heartbeat(self, task):
        with self._transaction() as db:
            now = self.clock()
            row = db.execute("SELECT * FROM jobs WHERE id=? AND lease=? AND worker=? AND state='running'",
                             (task["id"],task["lease"],task["worker"])).fetchone()
            if not row or row["deadline"] <= now:
                return False
            settings = db.execute("SELECT enabled,owner_busy FROM control").fetchone()
            if not settings["enabled"] or settings["owner_busy"]:
                self._release(db, row, "owner_priority_or_stop")
                return False
            db.execute("UPDATE jobs SET deadline=? WHERE id=?", (now+LEASE_SECONDS,row["id"]))
            db.execute("UPDATE workers SET seen=? WHERE id=?", (now,row["worker"]))
            return True

    def checkpoint(self, task, expected, rows, elapsed_us, rss):
        with self._transaction() as db:
            now = self.clock()
            row = db.execute("SELECT * FROM jobs WHERE id=?", (task["id"],)).fetchone()
            if not row or row["lease"] != task["lease"] or row["worker"] != task["worker"] or row["state"] != "running" or row["deadline"] <= now:
                raise LeaseExpired("Checkpoint sem reserva atual.")
            if type(expected) is not int or row["next_row"] != expected or not 1 <= len(rows) <= 4:
                raise ValueError("Índice de checkpoint incompatível.")
            width = SIZES[row["size"]]
            end = expected + len(rows)
            if (end > width or type(elapsed_us) is not int or not 0 <= elapsed_us <= LEASE_SECONDS*1_000_000
                    or type(rss) is not int or not 0 < rss <= 512*MIB):
                raise ValueError("Checkpoint fora dos limites.")
            digest = row["chain"]
            for before,after,checksum in rows:
                if type(after) is not int or type(before) is not int or before != 2*width+1 or after != 2*width:
                    raise ValueError("Quantidade de faces divergente.")
                part = bytes.fromhex(checksum)
                if len(part) != 32:
                    raise ValueError("Digest de faixa incompatível.")
                digest = sha256(bytes.fromhex(digest) + part).hexdigest()
            done = end == width
            settings = db.execute("SELECT * FROM control").fetchone()
            active = settings["enabled"] and not settings["owner_busy"]
            # Se a autorização mudou durante a faixa, ela volta ao último checkpoint confirmado.
            if not active:
                self._release(db, row, "owner_priority_or_stop")
                return False
            db.execute("""UPDATE jobs SET next_row=?,before_faces=?,after_faces=?,chain=?,
                elapsed_us=elapsed_us+?,peak_rss=MAX(peak_rss,?),state=?,deadline=?,
                worker=CASE WHEN ? THEN NULL ELSE worker END,lease=CASE WHEN ? THEN NULL ELSE lease END WHERE id=?""",
                (end,end*(2*width+1),end*2*width,digest,elapsed_us,rss,"done" if done else "running",
                 None if done else now+LEASE_SECONDS,done,done,row["id"]))
            db.execute("UPDATE workers SET seen=?,state=? WHERE id=?", (now,"idle" if done else "busy",row["worker"]))
            total = settings["elapsed_us"] + elapsed_us
            cycles = total // SIX_HOURS_US
            found = settings["cycling_improvements"] + int(done)
            if cycles > settings["cycles"]:
                db.execute("INSERT INTO cycles VALUES (?,?,?)", (cycles,now,found))
                found = 0
            db.execute("UPDATE control SET elapsed_us=?,cycles=?,cycling_improvements=?", (total,cycles,found))
            return not done

    def _release(self, db, row, reason):
        db.execute("""UPDATE jobs SET state='queued',lease=NULL,deadline=NULL,worker=NULL,
                    attempts=attempts-1,reason=? WHERE id=?""", (reason,row["id"]))
        db.execute("UPDATE workers SET state='idle',seen=? WHERE id=?", (self.clock(),row["worker"]))

    def release(self, task, reason, *, failed=False):
        with self._transaction() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=? AND lease=? AND state='running'",
                             (task["id"],task["lease"])).fetchone()
            if row and failed:
                db.execute("""UPDATE jobs SET state=CASE WHEN attempts>=3 THEN 'blocked' ELSE 'queued' END,
                    lease=NULL,deadline=NULL,worker=NULL,reason=? WHERE id=?""", (reason,row["id"]))
                db.execute("UPDATE workers SET state='idle',seen=? WHERE id=?", (self.clock(),row["worker"]))
            elif row:
                self._release(db, row, reason)

    def read(self):
        with self._transaction() as db:
            return {"control": dict(db.execute("SELECT * FROM control").fetchone()),
                    "jobs": [dict(row) for row in db.execute("""SELECT id,size,method,priority,
                               CASE WHEN state='running' AND deadline<=? THEN 'interrupted' ELSE state END AS state,
                               next_row,before_faces,
                               after_faces,chain,elapsed_us,peak_rss,attempts,
                               CASE WHEN state='running' AND deadline<=? THEN 'awaiting_recovery' ELSE reason END AS reason
                               FROM jobs ORDER BY size,method""",(self.clock(),self.clock(),))],
                    "workers": [dict(row) for row in db.execute("""SELECT id,seen,
                               CASE WHEN seen<? THEN 'offline' ELSE state END AS state
                               FROM workers ORDER BY seen DESC""",(self.clock()-LEASE_SECONDS*2,))],
                    "evaluations": [dict(row) for row in db.execute("SELECT * FROM cycles ORDER BY number DESC LIMIT 24")]}


def run_local(queue):
    sample = reading(cpu_interval=.2)
    if sample.available < reserve(sample) + 128 or sample.cpu >= 90 or disk_usage(queue.root).free < 16*MIB:
        return {"state":"blocked", "reason":"Capacidade local insuficiente para a reserva experimental."}
    task = queue.claim(uuid4().hex)
    if task is None:
        return {"state":"waiting", "reason":"Sem tarefa autorizada e disponível."}
    width = SIZES[task["size"]]
    row = task["next_row"]
    process = psutil.Process()
    deadline = monotonic()+20
    next_sample = monotonic()+.25
    try:
        while row < width:
            rss = process.memory_info().rss
            if monotonic() >= next_sample:
                sample = reading()
                next_sample = monotonic()+.25
                if not queue.heartbeat(task):
                    break
            if (psutil.virtual_memory().available < (reserve(sample)+128)*MIB or sample.cpu >= 95
                    or monotonic() >= deadline or rss > 128*MIB):
                queue.release(task, "sentinel_resource_limit")
                return {"state":"paused", "job":task["id"]}
            batch_size = 1 if sample.cpu >= 75 else 4
            started = monotonic()
            results = [geometry_row(width,index,task["method"]) for index in range(row,min(row+batch_size,width))]
            active = queue.checkpoint(task,row,results,
                                      round((monotonic()-started)*1_000_000),rss)
            if not active:
                break
            row += len(results)
    except LeaseExpired:
        pass  # O operador ou outra reserva já encerrou este token.
    except KeyboardInterrupt:
        queue.release(task, "operator_interrupted")
        return {"state":"paused", "job":task["id"]}
    except BaseException:
        queue.release(task, "worker_interrupted", failed=True)
        raise
    return next(job for job in queue.read()["jobs"] if job["id"] == task["id"])


def main(argv=None):
    parser = ArgumentParser(description="Worker local isolado do Laboratório Arvertes")
    parser.add_argument("--workspace", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    enable = sub.add_parser("enable")
    enable.add_argument("--approved", action="store_true")
    for command in ("stop","owner-busy","owner-idle","run","status"):
        sub.add_parser(command)
    schedule = sub.add_parser("enqueue")
    schedule.add_argument("triangles", type=int, choices=SIZES)
    schedule.add_argument("--method", choices=METHODS, default=METHODS[0])
    schedule.add_argument("--priority", action="store_true")
    args = parser.parse_args(argv)
    try:
        queue = Queue(args.workspace.absolute())
        if args.command == "enqueue":
            result = {"job":queue.enqueue(args.triangles,args.method,priority=args.priority)}
        elif args.command == "run":
            result = run_local(queue)
        elif args.command == "status":
            result = queue.read()
        else:
            queue.control(args.command, approved=getattr(args,"approved",False))
            result = queue.read()["control"]
    except (ValueError, OSError, sqlite3.Error, psutil.Error) as error:
        parser.exit(2, f"Laboratório bloqueado. {error}\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
