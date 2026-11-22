"""Fila SQLite de inspeção, com eventos e checkpoints no banco do projeto."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from time import time
from uuid import uuid4

FLOW = (
    ("catalog", "catalogador", ()),
    ("blender", "modelador", ("catalog",)),
    ("budget", "otimizador", ("blender",)),
    ("inspect", "inspetor", ("blender", "budget")),
    ("audit", "auditor", ("inspect",)),
    ("gate", "seguranca", ("audit",)),
)
STEPS = {step: (agent, dependencies) for step, agent, dependencies in FLOW}
LEASE_SECONDS = 150


def check_delegation(plan):
    expected = {"workflow": "glb_inspection", "sender": "coordenador",
                "messages": [{"type": "delegate", "step": step, "to": agent, "depends_on": list(deps)}
                             for step, agent, deps in FLOW]}
    if plan != expected:
        raise ValueError("Sentinel bloqueou: delegação fora do fluxo GLB autorizado.")


class ProjectRuns:
    def __init__(self, db):
        self.db = db
        self.db.executescript("""
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS inspection (
                id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES project(id),
                asset_id INTEGER NOT NULL REFERENCES asset(id), title TEXT NOT NULL,
                source_hash TEXT NOT NULL, organize INTEGER NOT NULL,
                budget INTEGER NOT NULL, status TEXT NOT NULL, lease TEXT, expires REAL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_inspection_running
                ON inspection(status) WHERE status='running';
            CREATE TABLE IF NOT EXISTS inspection_checkpoint (
                run_id INTEGER REFERENCES inspection(id), step TEXT, output TEXT NOT NULL,
                PRIMARY KEY(run_id, step)
            );
            CREATE TABLE IF NOT EXISTS inspection_event (
                id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES inspection(id),
                sender TEXT NOT NULL, recipient TEXT, kind TEXT NOT NULL,
                step TEXT, detail TEXT NOT NULL, created TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS inspection_events ON inspection_event(run_id, id);
            COMMIT;
        """)

    @contextmanager
    def transaction(self):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            yield

    def event(self, run, sender, recipient, kind, step, detail=""):
        self.db.execute("""INSERT INTO inspection_event(run_id,sender,recipient,kind,step,detail,created)
                        VALUES(?,?,?,?,?,?,?)""",
                        (run, sender, recipient, kind, step, detail, datetime.now(timezone.utc).isoformat()))

    def create(self, project, asset, title, source_hash, organize, budget, plan):
        check_delegation(plan)
        if type(organize) is not bool or type(budget) is not int or not 1 <= budget <= 1_000_000_000:
            raise ValueError("Configuração de inspeção incompatível.")
        with self.transaction():
            if not self.db.execute("SELECT 1 FROM asset WHERE project_id=? AND id=?", (project, asset)).fetchone():
                raise ValueError("A referência deve pertencer ao projeto selecionado.")
            run = self.db.execute("""INSERT INTO inspection(project_id,asset_id,title,source_hash,organize,budget,status)
                                    VALUES (?,?,?,?,?,?,'queued')""",
                                  (project, asset, title[:120], source_hash, organize, budget)).lastrowid
            for step, agent, _ in FLOW:
                self.event(run, "coordenador", agent, "delegated", step)
        return run

    def get(self, run):
        return self.db.execute("""SELECT inspection.*,asset.path FROM inspection
                                JOIN asset ON asset.id=inspection.asset_id WHERE inspection.id=?""",
                               (run,)).fetchone()

    def list(self, project=None):
        if project is None:
            return self.db.execute("SELECT id,project_id,title,status FROM inspection ORDER BY id DESC LIMIT 100").fetchall()
        return self.db.execute("""SELECT id,project_id,title,status FROM inspection
                                WHERE project_id=? ORDER BY id DESC LIMIT 100""", (project,)).fetchall()

    def history(self, run):
        return self.db.execute("""SELECT sender,recipient,kind,step,detail,created FROM inspection_event
                                WHERE run_id=? ORDER BY id DESC LIMIT 100""", (run,)).fetchall()

    def office_history(self):
        return self.db.execute("""SELECT sender,recipient,kind,step,'' AS detail FROM inspection_event
                                ORDER BY id DESC LIMIT 100""").fetchall()

    def checkpoints(self, run):
        return {row["step"]: json.loads(row["output"]) for row in self.db.execute(
            "SELECT step,output FROM inspection_checkpoint WHERE run_id=?", (run,))}

    def recover_expired(self, now):
        expired = self.db.execute("SELECT id FROM inspection WHERE status='running' AND expires<=?", (now,))
        for row in expired.fetchall():
            self.db.execute("UPDATE inspection SET status='interrupted',lease=NULL,expires=NULL WHERE id=?", (row["id"],))
            self.event(row["id"], "seguranca", "coordenador", "interrupted", None, "Reserva de execução expirada.")

    def recover(self):
        with self.transaction():
            self.recover_expired(time())

    def reserve(self, run, *, now=None):
        now = time() if now is None else now
        token = uuid4().hex
        with self.transaction():
            self.recover_expired(now)
            if self.db.execute("SELECT 1 FROM inspection WHERE status='running'").fetchone():
                raise ValueError("Já existe uma inspeção reservada neste workspace.")
            if self.db.execute("""UPDATE inspection SET status='running',lease=?,expires=? WHERE id=?
                                  AND status IN ('queued','interrupted')""", (token, now + LEASE_SECONDS, run)).rowcount != 1:
                raise ValueError("Inspeção indisponível para execução.")
            self.event(run, "seguranca", "coordenador", "reserved", None)
        return token

    def verify(self, run, token):
        record = self.get(run)
        if (record is None or record["status"] != "running" or record["lease"] != token
                or record["expires"] <= time()):
            raise ValueError("Sentinel bloqueou: reserva de inspeção inválida ou encerrada.")
        return record

    def next_step(self, run, token):
        self.verify(run, token)
        done = self.checkpoints(run)
        for step, _, depends in FLOW:
            if step not in done and all(key in done for key in depends):
                return step
        raise ValueError("Sentinel bloqueou: dependência inexistente ou fila sem próxima etapa.")

    def begin(self, run, token, step):
        with self.transaction():
            if self.next_step(run, token) != step:
                raise ValueError("Sentinel bloqueou: ordem de execução inválida.")
            agent = STEPS[step][0]
            self.db.execute("UPDATE inspection SET expires=? WHERE id=?", (time() + LEASE_SECONDS, run))
            if step == "budget":
                self.event(run, "inspetor", agent, "help_requested", step,
                           "Comparar a geometria original e avaliada ao orçamento.")
            self.event(run, agent, "coordenador", "started", step)

    def complete(self, run, token, step, output):
        encoded = json.dumps(output, allow_nan=False)
        if len(encoded) > 32768 or not isinstance(output, dict):
            raise ValueError("Checkpoint fora do contrato.")
        with self.transaction():
            if self.next_step(run, token) != step:
                raise ValueError("Sentinel bloqueou: resposta fora da etapa atual.")
            self.db.execute("INSERT INTO inspection_checkpoint VALUES (?,?,?)", (run, step, encoded))
            agent = STEPS[step][0]
            recipient = {"inspect": "auditor", "audit": "seguranca", "budget": "inspetor"}.get(step, "coordenador")
            self.event(run, agent, recipient, "result", step)
            if step == "gate":
                status = "blocked" if output.get("reason") else "review"
                self.db.execute("UPDATE inspection SET status=?,lease=NULL,expires=NULL WHERE id=?", (status, run))
                self.event(run, "seguranca", "coordenador", status, step, output.get("reason", ""))

    def stop(self, run, token, *, cancelled=False, reason=""):
        status = "cancelled" if cancelled else "interrupted"
        with self.transaction():
            changed = self.db.execute("""UPDATE inspection SET status=?,lease=NULL,expires=NULL WHERE id=?
                                       AND status='running' AND lease=?""", (status, run, token)).rowcount
            if changed:
                self.event(run, "seguranca", "coordenador", status, None, reason[:200])
        return bool(changed)
