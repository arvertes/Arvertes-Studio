"""Dados locais de trabalho; nenhuma execução ou alteração dos assets."""
from pathlib import Path
import sqlite3


def required(value: str, limit: int) -> str:
    value = value.strip()
    if not value or len(value) > limit:
        raise ValueError(f"Preencha um texto de 1 a {limit} caracteres.")
    return value


class Workspace:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute("PRAGMA foreign_keys = ON")
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("Banco de dados de versão incompatível.")
            if version == 0:
                self.db.executescript("""
                    BEGIN;
                    CREATE TABLE project (
                        id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE
                    );
                    CREATE TABLE asset (
                        id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES project(id),
                        path TEXT NOT NULL, UNIQUE(project_id, path)
                    );
                    CREATE TABLE task (
                        id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL REFERENCES project(id),
                        title TEXT NOT NULL, instruction TEXT NOT NULL,
                        position INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'draft'
                        CHECK(status IN ('draft', 'cancelled'))
                    );
                    PRAGMA user_version = 1;
                    COMMIT;
                """)
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def dashboard_summary(self):
        counts = self.db.execute("""
            SELECT (SELECT COUNT(*) FROM project),
                   (SELECT COUNT(*) FROM asset),
                   (SELECT COUNT(*) FROM task WHERE status='draft')
        """).fetchone()
        recent = self.db.execute("""
            SELECT project.name, task.title FROM task
            JOIN project ON task.project_id=project.id
            WHERE task.status='draft' ORDER BY task.id DESC LIMIT 4
        """).fetchall()
        return tuple(counts), [(row["name"], row["title"]) for row in recent]

    def projects(self):
        return self.db.execute("SELECT * FROM project ORDER BY name COLLATE NOCASE").fetchall()

    def create_project(self, name: str) -> int:
        with self.db:
            return self.db.execute("INSERT INTO project(name) VALUES (?)",
                                   (required(name, 100),)).lastrowid

    def assets(self, project_id: int):
        return self.db.execute("SELECT * FROM asset WHERE project_id=? ORDER BY id",
                               (project_id,)).fetchall()

    def add_reference(self, project_id: int, path: str) -> int:
        file = Path(path).resolve(strict=True)
        if not file.is_file():
            raise ValueError("Selecione um arquivo existente.")
        with self.db:
            return self.db.execute("INSERT INTO asset(project_id,path) VALUES (?,?)",
                                   (project_id, str(file))).lastrowid

    def tasks(self, project_id: int):
        return self.db.execute("SELECT * FROM task WHERE project_id=? ORDER BY position,id",
                               (project_id,)).fetchall()

    def add_task(self, project_id: int, title: str, instruction: str) -> int:
        title, instruction = required(title, 120), required(instruction, 12000)
        with self.db:
            return self.db.execute("""
                INSERT INTO task(project_id,title,instruction,position)
                VALUES (?,?,?,(SELECT COALESCE(MAX(position),0)+1 FROM task WHERE project_id=?))
            """, (project_id, title, instruction, project_id)).lastrowid

    def move_task(self, task_id: int, direction: int):
        if direction not in (-1, 1):
            raise ValueError("Direção inválida.")
        with self.db:
            task = self.db.execute("SELECT * FROM task WHERE id=? AND status='draft'",
                                   (task_id,)).fetchone()
            if task is None:
                return
            drafts = [row for row in self.tasks(task["project_id"]) if row["status"] == "draft"]
            index = next(i for i, row in enumerate(drafts) if row["id"] == task_id)
            other_index = index + direction
            if 0 <= other_index < len(drafts):
                other = drafts[other_index]
                self.db.execute("UPDATE task SET position=? WHERE id=?", (other["position"], task_id))
                self.db.execute("UPDATE task SET position=? WHERE id=?", (task["position"], other["id"]))

    def cancel_task(self, task_id: int):
        with self.db:
            self.db.execute("UPDATE task SET status='cancelled' WHERE id=? AND status='draft'", (task_id,))
