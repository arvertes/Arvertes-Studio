"""Projeção remota. Campos pessoais, caminhos e observações locais ficam fora."""
from .roster import AGENTS

CATEGORIES = ("projects", "tasks", "agents", "devices", "history", "reports", "sentinel")
PROJECT_SECTIONS = frozenset(("projects", "tasks", "history", "reports", "sentinel"))
EVENTS = frozenset(("delegated", "help_requested", "started", "result", "reserved", "interrupted",
                    "cancelled", "blocked", "review", "approved", "exported"))
STEPS = frozenset(("", "catalog", "blender", "budget", "materials", "inspect", "audit", "gate",
                   "unreal", "mesh_tools", "export"))


def projection(workspace, hub, bridge, production, project, selected):
    if not selected or set(selected) - set(CATEGORIES):
        raise ValueError("Selecione o que deseja compartilhar.")
    if PROJECT_SECTIONS.intersection(selected):
        if not workspace or not any(row["id"] == project for row in workspace.projects()):
            raise ValueError("Selecione o projeto autorizado para as seções solicitadas.")

    sections = {}
    for field in selected:
        if field == "projects":
            sections[field] = [{"id": project, "references": len(workspace.assets(project))}]
        elif field == "tasks":
            tasks = [{"id": row["id"], "project": project, "status": row["status"], "kind": "draft"}
                     for row in workspace.tasks(project)[-100:]]
            tasks.extend({"id": row["id"], "project": project, "status": row["status"], "kind": "inspection"}
                         for row in workspace.inspections.list(project))
            sections[field] = tasks[-100:]
        elif field == "agents":
            states = bridge.team
            sections[field] = [{"id": agent.id, "state":
                "working" if production and production.status(agent.id) or bridge.status(agent.id) == "Trabalhando"
                else "monitoring" if agent.id == "seguranca"
                else "available" if states.get(agent.id) == "rules"
                else "planned" if agent.id in states else "offline"} for agent in AGENTS]
        elif field == "devices":
            sections[field] = [
                {"connected": bool(session), "transport": session.get("transport", "unknown"),
                 "available_mib": session.get("metrics", {}).get("ram_available"),
                 "work": hub.work.latest(key)[0] or "none"}
                for key, _, session, _ in hub.snapshot()] if hub else []
        elif field == "history":
            rows = workspace.db.execute("""
                SELECT e.sender,e.recipient,e.kind,e.step FROM inspection_event e
                JOIN inspection i ON i.id=e.run_id WHERE i.project_id=? ORDER BY e.id DESC LIMIT 100
                """, (project,))
            sections[field] = [{"sender": row["sender"], "recipient": row["recipient"] or "",
                                "event": row["kind"], "step": row["step"] or ""}
                               for row in rows if row["kind"] in EVENTS and (row["step"] or "") in STEPS]
        elif field == "reports":
            reports = []
            for row in workspace.inspections.list(project):
                if row["status"] not in ("review", "blocked"):
                    continue
                summary = workspace.inspections.checkpoints(row["id"]).get("blender", {}).get("report", {}).get("summary")
                if summary:
                    reports.append({"run": row["id"], "meshes": summary["mesh_count"],
                                    "triangles": summary["geometry_original"]["triangles"],
                                    "materials": summary.get("material_count", 0),
                                    "topology": "measured" if summary.get("technical", {}).get("topology_measured")
                                    else "not_measured"})
            sections[field] = reports
        else:
            sections[field] = [{"run": row["id"], "decision":
                               "human_review" if row["status"] == "review" else "blocked"}
                               for row in workspace.inspections.list(project) if row["status"] in ("review", "blocked")]
    return {"version": 1, "sections": sections}
