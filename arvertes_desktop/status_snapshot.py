"""Exportação local e explícita de estado público ao cliente MCP selecionado."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
import json
import os


def snapshot(workspace, hub, bridge):
    data = {"version": 1, "exported_at": datetime.now(timezone.utc).isoformat(),
            "projects": [], "tasks": [], "devices": [], "tests": [], "sentinel": []}
    if workspace:
        db = workspace.db
        data["projects"] = [dict(row) for row in db.execute("""
            SELECT project.id, project.name, COUNT(asset.id) AS reference_count FROM project
            LEFT JOIN asset ON project.id=asset.project_id GROUP BY project.id ORDER BY project.id LIMIT 100""")]
        data["tasks"] = [dict(row) for row in db.execute("""
            SELECT id,project_id,title,status,'draft' AS kind FROM task
            UNION ALL SELECT id,project_id,title,status,'inspection' FROM inspection
            ORDER BY id DESC LIMIT 100""")]
        ok = db.execute("PRAGMA quick_check(1)").fetchone()[0] == "ok"
        data["tests"].append({"check": "workspace_quick_check", "status": "pass" if ok else "fail",
                              "source": "Banco local no momento da exportação"})
        for run in workspace.inspections.list():
            if run["status"] in ("blocked", "review"):
                reason = workspace.inspections.checkpoints(run["id"])["gate"]["reason"]
                data["sentinel"].append({"status": run["status"], "reason": reason or "Revisão humana exigida."})
    if bridge and bridge.connected:
        data["tests"].append({"check": "agents_roster", "status": "pass", "source": "Ponte local Agents"})
    if hub:
        for device, name, session, probe in hub.snapshot():
            data["devices"].append({"name": name, "transport": session.get("transport", ""),
                                    "connected": bool(session), "work_state": hub.work.latest(device)[0],
                                    "available_ram_mib": session.get("metrics", {}).get("ram_available")})
            if probe.get("state") == "confirmed":
                data["tests"].append({"check": "tls_round_trip", "status": "pass",
                                      "source": "Resposta autenticada de diagnóstico"})
    return data


def export(path, data):
    path = Path(path)
    if path.name != "arvertes-status.json":
        raise ValueError("Use o nome arvertes-status.json.")
    tmp = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            tmp = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, allow_nan=False, indent=2)
        os.replace(tmp, path)
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)
