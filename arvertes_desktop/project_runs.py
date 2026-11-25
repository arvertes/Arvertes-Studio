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
    ("materials", "texturizador", ("blender",)),
    ("unreal", "integrador_unreal", ("blender", "materials")),
    ("inspect", "inspetor", ("blender", "budget", "materials", "unreal")),
    ("audit", "auditor", ("inspect",)),
    ("gate", "seguranca", ("audit",)),
)
LEGACY_FLOW = tuple((step, agent, tuple(dependency for dependency in deps if dependency != "unreal"))
                    for step, agent, deps in FLOW if step != "unreal")
STEPS = {step: (agent, dependencies) for step, agent, dependencies in FLOW}
LEASE_SECONDS = 150
MEMORY = {"error": "Erros", "correction": "Correções aprovadas", "preference": "Preferências",
          "technique": "Técnicas validadas", "art": "Decisões artísticas", "assessment": "Avaliações"}


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
            CREATE TABLE IF NOT EXISTS inspection_contract (
                run_id INTEGER PRIMARY KEY REFERENCES inspection(id), profile TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inspection_delivery (
                run_id INTEGER PRIMARY KEY REFERENCES inspection(id), state TEXT NOT NULL,
                lease TEXT, expires REAL, directory TEXT, digest TEXT
            );
            CREATE TABLE IF NOT EXISTS project_memory (
                id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES project(id),
                kind TEXT NOT NULL, note TEXT NOT NULL, created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS project_budget (
                project_id INTEGER PRIMARY KEY REFERENCES project(id), triangles INTEGER NOT NULL
            );
            COMMIT;
        """)

    @contextmanager
    def transaction(self):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            yield

    def memory(self, project):
        return self.db.execute("""SELECT kind,note,created FROM project_memory WHERE project_id=?
                                ORDER BY id DESC LIMIT 50""", (project,)).fetchall()

    def record_memory(self, project, kind, note):
        note = note.strip()
        if kind not in MEMORY or not 1 <= len(note) <= 2000:
            raise ValueError("Informe uma nota local de 1 a 2.000 caracteres.")
        self.db.execute("INSERT INTO project_memory(project_id,kind,note,created) VALUES(?,?,?,?)",
                        (project, kind, note, datetime.now(timezone.utc).isoformat()))

    def note(self, project, kind, note):
        with self.transaction():
            self.record_memory(project, kind, note)

    def project_budget(self, project):
        row = self.db.execute("SELECT triangles FROM project_budget WHERE project_id=?", (project,)).fetchone()
        return row[0] if row else None

    def save_budget(self, project, value):
        if type(value) is not int or not 1 <= value <= 1_000_000_000:
            raise ValueError("Orçamento do projeto inválido.")
        with self.transaction():
            self.db.execute("INSERT OR REPLACE INTO project_budget VALUES (?,?)", (project, value))
            self.record_memory(project, "preference", f"Orçamento máximo aprovado: {value} triângulos.")

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
            limit = self.project_budget(project)
            previous_errors = self.db.execute(
                "SELECT count(*) FROM project_memory WHERE project_id=? AND kind='error'", (project,)).fetchone()[0]
            chosen = min(budget, limit) if limit else budget
            run = self.db.execute("""INSERT INTO inspection(project_id,asset_id,title,source_hash,organize,budget,status)
                                    VALUES (?,?,?,?,?,?,'queued')""",
                                  (project, asset, title[:120], source_hash, organize, chosen)).lastrowid
            self.db.execute("INSERT INTO inspection_contract VALUES (?,'unreal')", (run,))
            if limit or previous_errors:
                self.event(run, "coordenador", "inspetor", "delegated", None,
                           f"Memória consultada. Orçamento de {chosen} triângulos e {previous_errors} erros anteriores registrados.")
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

    def flow(self, run):
        record = self.db.execute("SELECT profile FROM inspection_contract WHERE run_id=?", (run,)).fetchone()
        return FLOW if record and record[0] == "unreal" else LEGACY_FLOW

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
        expired = expired.fetchall()
        for row in expired:
            self.db.execute("UPDATE inspection SET status='interrupted',lease=NULL,expires=NULL WHERE id=?", (row["id"],))
            self.event(row["id"], "seguranca", "coordenador", "interrupted", None, "Reserva de execução expirada.")

        deliveries = self.db.execute(
            "SELECT run_id FROM inspection_delivery WHERE state='running' AND expires<=?", (now,)).fetchall()
        for row in deliveries:
            self.db.execute("UPDATE inspection_delivery SET state='interrupted',lease=NULL WHERE run_id=?", (row[0],))
            self.event(row[0], "seguranca", "integrador_unreal", "interrupted", "export", "Reserva de exportação expirada.")
        return len(expired) + len(deliveries)

    def ensure_available(self):
        if (self.db.execute("SELECT 1 FROM inspection WHERE status='running'").fetchone()
                or self.db.execute("SELECT 1 FROM inspection_delivery WHERE state='running'").fetchone()):
            raise ValueError("Já existe uma inspeção ou exportação reservada neste workspace.")

    def delivery(self, run):
        return self.db.execute("SELECT * FROM inspection_delivery WHERE run_id=?", (run,)).fetchone()

    def reserve_delivery(self, run):
        token = uuid4().hex
        with self.transaction():
            self.recover_expired(time())
            self.ensure_available()
            record = self.get(run)
            gate = self.checkpoints(run).get("gate", {})
            if (not record or record["status"] != "review" or gate.get("reason")
                    or gate.get("requires_human_approval") is not True or not record["organize"]):
                raise ValueError("Sentinel bloqueou: a cópia não foi liberada para aprovação de exportação.")
            current = self.delivery(run)
            if current and current["state"] == "exported":
                raise ValueError("A entrega já foi gerada.")
            self.db.execute("INSERT OR REPLACE INTO inspection_delivery VALUES (?,'running',?,?,NULL,NULL)",
                            (run, token, time() + LEASE_SECONDS))
            self.event(run, "seguranca", "integrador_unreal", "approved", "export", "Aprovação humana explícita.")
        return token

    def complete_delivery(self, run, token, directory, digest):
        with self.transaction():
            if self.db.execute("""UPDATE inspection_delivery SET state='exported',lease=NULL,directory=?,digest=?
                                  WHERE run_id=? AND lease=? AND state='running' AND expires>?""",
                               (directory, digest, run, token, time())).rowcount != 1:
                raise ValueError("Sentinel bloqueou: reserva de exportação inválida.")
            self.event(run, "integrador_unreal", "coordenador", "exported", "export")

    def stop_delivery(self, run, token, message):
        with self.transaction():
            changed = self.db.execute("""UPDATE inspection_delivery SET state='interrupted',lease=NULL
                                         WHERE run_id=? AND lease=? AND state='running'""",
                                      (run, token)).rowcount
            if changed:
                self.event(run, "seguranca", "integrador_unreal", "interrupted", "export", message[:200])

    def recover(self):
        with self.transaction():
            return self.recover_expired(time())

    def reserve(self, run, *, now=None):
        now = time() if now is None else now
        token = uuid4().hex
        with self.transaction():
            self.recover_expired(now)
            self.ensure_available()
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
        for step, _, depends in self.flow(run):
            if step not in done and all(key in done for key in depends):
                return step
        raise ValueError("Sentinel bloqueou: dependência inexistente ou fila sem próxima etapa.")

    def begin(self, run, token, step):
        with self.transaction():
            if self.next_step(run, token) != step:
                raise ValueError("Sentinel bloqueou: ordem de execução inválida.")
            agent = STEPS[step][0]
            self.db.execute("UPDATE inspection SET expires=? WHERE id=?", (time() + LEASE_SECONDS, run))
            question = {"budget": "Comparar a geometria original e avaliada ao orçamento.",
                        "materials": "Verificar a cobertura de materiais nas malhas."}.get(step)
            if question:
                self.event(run, "inspetor", agent, "help_requested", step, question)
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
            recipient = {"inspect": "auditor", "audit": "seguranca", "budget": "inspetor", "materials": "inspetor"}.get(step, "coordenador")
            self.event(run, agent, recipient, "result", step)
            if step == "gate":
                status = "blocked" if output.get("reason") else "review"
                self.db.execute("UPDATE inspection SET status=?,lease=NULL,expires=NULL WHERE id=?", (status, run))
                self.event(run, "seguranca", "coordenador", status, step, output.get("reason", ""))
                self.record_memory(self.get(run)["project_id"], "assessment",
                                   output.get("reason") or "Validação concluída. Revisão humana necessária.")

    def stop(self, run, token, *, cancelled=False, reason="", record_error=True):
        status = "cancelled" if cancelled else "interrupted"
        with self.transaction():
            changed = self.db.execute("""UPDATE inspection SET status=?,lease=NULL,expires=NULL WHERE id=?
                                       AND status='running' AND lease=?""", (status, run, token)).rowcount
            if changed:
                self.event(run, "seguranca", "coordenador", status, None, reason[:200])
                if record_error and not cancelled and reason:
                    self.record_memory(self.get(run)["project_id"], "error", reason[:500])
        return bool(changed)
