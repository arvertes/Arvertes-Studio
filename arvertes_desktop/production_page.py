"""Controles do fluxo de GLB e histórico das mensagens por projeto."""
from pathlib import Path
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QInputDialog, QMessageBox, QPlainTextEdit, QSpinBox

from .pages import button, plain, rows, table
from .project_runs import MEMORY
from .roster import AGENTS

NAMES = {agent.id: agent.name for agent in AGENTS}
STATUS = {"queued": "Na fila", "running": "Executando", "interrupted": "Interrompida", "blocked": "Bloqueada",
          "review": "Revisão humana", "cancelled": "Cancelada"}
EVENTS = {"delegated": "delegou", "help_requested": "solicitou ajuda", "started": "iniciou", "result": "enviou resultado",
          "reserved": "reservou", "interrupted": "interrompeu", "cancelled": "cancelou", "blocked": "bloqueou",
          "review": "encaminhou para revisão", "approved": "recebeu aprovação", "exported": "entregou FBX"}
LABELS = {"catalog": "Catalogação", "blender": "Importação e análise Blender", "budget": "Orçamento de geometria",
          "materials": "Cobertura de materiais", "inspect": "Inspeção técnica", "audit": "Auditoria", "gate": "Verificação", "unreal": "Pré-verificação Unreal", "export": "Exportação FBX"}


def event_label(row):
    target = f" → {NAMES[row['recipient']]}" if row["recipient"] in NAMES else ""
    step = f" · {LABELS[row['step']]}" if row["step"] in LABELS else ""
    observation = f" · {row['detail']}" if row["detail"] else ""
    return f"{NAMES[row['sender']]}{target} · {EVENTS[row['kind']]}{step}{observation}"


def build_production(layout, production, protect):
    if not getattr(sys, "frozen", False):
        from .character_page import CharacterDialog

        layout.addWidget(button("Produzir personagem localmente",
                                lambda: CharacterDialog(production.parent(), production).exec()))
    layout.addWidget(plain("Fluxo GLB local. Atlas delega a partir de uma referência do projeto. "
                           "Selecione uma inspeção e autorize o início no Studio."))
    project = QComboBox()
    asset = QComboBox()
    layout.addWidget(project)
    layout.addWidget(asset)
    options = QHBoxLayout()
    organize = QCheckBox("Salvar .blend organizado em cópia")
    budget = QSpinBox()
    budget.setRange(1, 1_000_000_000)
    budget.setValue(100_000)
    options.addWidget(organize)
    options.addWidget(plain("Orçamento de triângulos"))
    options.addWidget(budget)
    layout.addLayout(options)
    status = plain("")
    listing = table(["Referência GLB", "Andamento", "Entrega"])
    listing.setMinimumHeight(130)
    history = QPlainTextEdit()
    history.setReadOnly(True)
    history.setPlaceholderText("Histórico e mensagens estruturadas")
    history.setMaximumHeight(150)
    layout.addWidget(button("Delegar inspeção ao Atlas", lambda: protect(
        lambda: production.queue(project.currentData(), asset.currentData(), organize.isChecked(), budget.value()))))
    layout.addWidget(listing, 1)
    layout.addWidget(status)
    layout.addWidget(history)
    actions = QHBoxLayout()
    layout.addLayout(actions)
    memory = QPlainTextEdit()
    memory.setReadOnly(True)
    memory.setMaximumHeight(105)
    memory.setPlaceholderText("Memória local do projeto")
    learning = QHBoxLayout()
    layout.addLayout(learning)
    layout.addWidget(memory)
    records = []

    def current_run():
        row = listing.currentRow()
        return records[row]["id"] if 0 <= row < len(records) else None

    def show_history():
        identity = current_run()
        checkpoints = production.runs.checkpoints(identity) if identity else {}
        entries = [event_label(row) for row in production.runs.history(identity)] if identity else []
        if "unreal" in checkpoints:
            entries.insert(0, "Metas sugeridas de LOD: " + " / ".join(map(str, checkpoints["unreal"]["lod_targets"])))
        history.setPlainText("\n".join(entries))
        working = production.active or production.delivery_job
        allowed = identity and working and working[0] == identity
        cancel.setEnabled(bool(allowed))
        pause.setEnabled(bool(allowed))
        active = next((row["status"] for row in records if row["id"] == identity), "")
        start.setEnabled(active in ("queued", "interrupted") and not working)
        folder.setEnabled("blender" in checkpoints)
        delivery = production.runs.delivery(identity) if identity else None
        ready = active == "review" and "unreal" in checkpoints and bool(checkpoints.get("blender", {}).get("blend_sha256")) and not working
        approve.setEnabled(ready and not (delivery and delivery["state"] == "exported"))
        delivered.setEnabled(bool(delivery and delivery["state"] == "exported"))

    def refresh_list():
        nonlocal records
        selected = current_run()
        records = production.runs.list(project.currentData()) if project.currentData() else []
        if selected is not None:
            listing.clearSelection()
        listing_rows = []
        for entry in records:
            run = entry["id"]
            done = len(production.runs.checkpoints(run))
            delivery = production.runs.delivery(run)
            state = {"running": "Exportando", "exported": "FBX verificado", "interrupted": "Exportação interrompida"}
            listing_rows.append((entry["title"], f'{STATUS[entry["status"]]} · {done}/{len(production.runs.flow(run))}',
                                 state[delivery["state"]] if delivery else "—"))
        rows(listing, listing_rows)
        index = next((i for i, entry in enumerate(records) if entry["id"] == selected), -1)
        if index >= 0:
            listing.selectRow(index)
        show_history()

    def refresh_memory():
        notes = production.runs.memory(project.currentData()) if project.currentData() else []
        memory.setPlainText("\n".join(f'{MEMORY[row["kind"]]} · {row["note"]}' for row in notes))

    def refresh_assets():
        previous = asset.currentData()
        asset.clear()
        if project.currentData() is not None:
            for entry in production.workspace.assets(project.currentData()):
                path = Path(entry["path"])
                if path.suffix.casefold() == ".glb":
                    asset.addItem(path.name, entry["id"])
        if asset.findData(previous) >= 0:
            asset.setCurrentIndex(asset.findData(previous))
        refresh_memory()
        refresh_list()

    def refresh_projects():
        previous = project.currentData()
        project.blockSignals(True)
        project.clear()
        for entry in production.workspace.projects():
            project.addItem(entry["name"], entry["id"])
        if project.findData(previous) >= 0:
            project.setCurrentIndex(project.findData(previous))
        project.blockSignals(False)
        refresh_assets()

    def note():
        project_id = project.currentData()
        if not project_id:
            return
        category, confirmed = QInputDialog.getItem(memory, "Memória do projeto", "Categoria",
                                                   list(MEMORY.values()), 0, False)
        if confirmed:
            detail, accepted = QInputDialog.getMultiLineText(memory, "Registro local aprovado", "Observação")
            if accepted:
                kind = next(key for key, value in MEMORY.items() if value == category)
                production.runs.note(project_id, kind, detail)
                refresh_memory()

    def save_budget():
        project_id = project.currentData()
        if project_id:
            production.runs.save_budget(project_id, budget.value())
            refresh_memory()

    learning.addWidget(button("Registrar memória", lambda: protect(note)))
    learning.addWidget(button("Salvar orçamento como preferência", lambda: protect(save_budget)))

    def approve_export():
        if QMessageBox.question(listing, "Autorizar FBX", "Exportar esta cópia revisada para um novo arquivo local?"
                ) == QMessageBox.StandardButton.Yes:
            production.export(current_run())

    approve = button("Aprovar e exportar FBX", lambda: protect(approve_export))
    delivered = button("Abrir entrega FBX", lambda: protect(
        lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(production.delivery_path(current_run()))))))
    start = button("Iniciar ou retomar", lambda: protect(lambda: production.start(current_run())))
    pause = button("Pausar", lambda: production.halt("Inspeção pausada. Checkpoints preservados.", record_error=False))
    cancel = button("Cancelar", lambda: production.halt("Inspeção cancelada pelo operador.", cancelled=True))
    folder = button("Abrir pasta de resultados", lambda: protect(
        lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(production.directory(current_run()))))))
    for control in (start, pause, cancel, folder):
        actions.addWidget(control)
    deliveries = QHBoxLayout()
    layout.addLayout(deliveries)
    deliveries.addWidget(approve)
    deliveries.addWidget(delivered)
    listing.itemSelectionChanged.connect(show_history)
    production.changed.connect(refresh_list)
    production.changed.connect(refresh_memory)
    production.notice.connect(status.setText)
    project.currentIndexChanged.connect(refresh_assets)
    refresh_projects()
    return refresh_projects
