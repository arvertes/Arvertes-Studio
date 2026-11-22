"""Controles do fluxo de GLB e histórico das mensagens por projeto."""
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QPlainTextEdit, QSpinBox

from .pages import button, plain, rows, table
from .project_runs import STEPS
from .roster import AGENTS

NAMES = {agent.id: agent.name for agent in AGENTS}
STATUS = {"queued": "Na fila", "running": "Executando", "interrupted": "Interrompida", "blocked": "Bloqueada",
          "review": "Revisão humana", "cancelled": "Cancelada"}
EVENTS = {"delegated": "delegou", "help_requested": "solicitou ajuda", "started": "iniciou", "result": "enviou resultado",
          "reserved": "reservou", "interrupted": "interrompeu", "cancelled": "cancelou", "blocked": "bloqueou",
          "review": "encaminhou para revisão"}
LABELS = {"catalog": "Catalogação", "blender": "Importação e análise Blender", "budget": "Orçamento de geometria",
          "inspect": "Inspeção técnica", "audit": "Auditoria", "gate": "Verificação"}


def event_label(row):
    target = f" → {NAMES[row['recipient']]}" if row["recipient"] in NAMES else ""
    step = f" · {LABELS[row['step']]}" if row["step"] in LABELS else ""
    observation = f" · {row['detail']}" if row["detail"] else ""
    return f"{NAMES[row['sender']]}{target} · {EVENTS[row['kind']]}{step}{observation}"


def build_production(layout, production, protect):
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
    listing = table(["Referência GLB", "Andamento"])
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
    records = []

    def current_run():
        row = listing.currentRow()
        return records[row]["id"] if 0 <= row < len(records) else None

    def show_history():
        identity = current_run()
        history.setPlainText("\n".join(event_label(row) for row in production.runs.history(identity)) if identity else "")
        allowed = identity and production.active and production.active[0] == identity
        cancel.setEnabled(bool(allowed))
        pause.setEnabled(bool(allowed))
        active = next((row["status"] for row in records if row["id"] == identity), "")
        start.setEnabled(active in ("queued", "interrupted") and not production.active)
        folder.setEnabled(bool(identity and "blender" in production.runs.checkpoints(identity)))

    def refresh_list():
        nonlocal records
        selected = current_run()
        records = production.runs.list(project.currentData()) if project.currentData() else []
        if selected is not None:
            listing.clearSelection()
        rows(listing, [(entry["title"], STATUS[entry["status"]]) for entry in records])
        index = next((i for i, entry in enumerate(records) if entry["id"] == selected), -1)
        if index >= 0:
            listing.selectRow(index)
        show_history()

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

    start = button("Iniciar ou retomar", lambda: protect(lambda: production.start(current_run())))
    pause = button("Pausar", lambda: production.halt("Inspeção pausada. Checkpoints preservados."))
    cancel = button("Cancelar", lambda: production.halt("Inspeção cancelada pelo operador.", cancelled=True))
    folder = button("Abrir pasta de resultados", lambda: protect(
        lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(production.directory(current_run()))))))
    for control in (start, pause, cancel, folder):
        actions.addWidget(control)
    listing.itemSelectionChanged.connect(show_history)
    production.changed.connect(refresh_list)
    production.notice.connect(status.setText)
    project.currentIndexChanged.connect(refresh_assets)
    refresh_projects()
    return refresh_projects
