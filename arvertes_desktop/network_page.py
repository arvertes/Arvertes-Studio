"""Central de sessões autenticadas e mensagens de diagnóstico."""
import sqlite3

from time import monotonic

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QInputDialog, QLineEdit, QMessageBox, QPushButton,
)
from .network import SENTINEL, THERMAL_STATES, desktop_metrics, interfaces
from .pages import plain, rows, table

TRANSPORTS = (("Wi-Fi local", "wifi_local"), ("Rede por USB", "usb"))
WORK_STATES = {"queued": "Reservado", "running": "Em execução", "paused": "Pausado",
               "completed": "Concluído", "cancelled": "Cancelado", "rejected": "Rejeitado"}
PROBE_STATES = {"queued": "Na fila", "sent": "Aguardando resposta", "confirmed": "Confirmada",
                "cancelled": "Cancelada", "expired": "Expirada"}


def fmt(value, suffix=""):
    return "—" if value is None else f"{value}{suffix}"


def build_network(layout, hub, hub_error, bridge):
    if hub is None:
        layout.addWidget(plain("Central indisponível. " + hub_error))
        layout.addStretch()
        return
    layout.addWidget(plain("Ative apenas na interface privada da rede escolhida. Para USB, use o "
                           "compartilhamento de internet por USB do Android e selecione o adaptador que aparecer."))
    local = plain("")
    layout.addWidget(local)
    adapter = QComboBox()
    transport = QComboBox()
    for title, key in TRANSPORTS:
        transport.addItem(title, key)
    connection = QHBoxLayout()
    connection.addWidget(transport)
    connection.addWidget(adapter, 1)
    layout.addLayout(connection)

    endpoints = plain("")
    layout.addWidget(endpoints)
    invitation = QLineEdit()
    invitation.setReadOnly(True)
    invitation.setPlaceholderText("O código de uso único expira em dois minutos")
    invitation.setVisible(False)
    actions = QHBoxLayout()
    layout.addLayout(actions)
    layout.addWidget(invitation)

    devices = table(["Aparelho", "Conexão", "RAM MiB", "CPU Mobile", "Bateria", "Térmico", "Mensagens", "Cálculo leve"])
    devices.setMinimumHeight(190)
    layout.addWidget(devices, 1)
    feedback = plain("")
    feedback.setObjectName("networkFeedback")
    layout.addWidget(feedback)
    alert = plain("Sentinel monitora as sessões locais.")
    layout.addWidget(alert)
    probes = QHBoxLayout()
    layout.addLayout(probes)

    records = []
    choices = []
    ticket_at = 0.0

    def refresh_adapters():
        nonlocal choices
        current = adapter.currentData()
        found = interfaces()
        if found != choices:
            choices = found
            adapter.clear()
            for name, address in choices:
                adapter.addItem(f"{name}  •  {address}", address)
            index = adapter.findData(current)
            if index >= 0:
                adapter.setCurrentIndex(index)
        active_addresses = {address for _, address in choices}
        for key, listener in list(hub.listeners.items()):
            if str(listener.address) not in active_addresses:
                hub.stop(key)
                feedback.setText("Interface removida ou mudou de endereço. Ative o transporte no novo endereço.")

    def refresh():
        nonlocal records
        try:
            refresh_adapters()
            metrics = desktop_metrics()
            local.setText(f"Computador local  •  RAM {metrics['ram_available']} / {metrics['ram_total']} MiB"
                          f"  •  CPU {metrics['cpu_pct']}%  •  Bateria {fmt(metrics['battery'], '%')}"
                          "  •  Estado térmico indisponível")
            selected = selected_id()
            snapshot = hub.snapshot()
            records = [device for device, _, _, _ in snapshot]
            results = []
            for identity, name, session, probe in snapshot:
                if session:
                    metrics = session["metrics"]
                    status = dict((key, title) for title, key in TRANSPORTS)[session["transport"]]
                    if session["consent"]:
                        status += " · disponível"
                    heat = metrics["thermal"]
                    values = (status, f"{fmt(metrics['ram_available'])} / {fmt(metrics['ram_total'])}",
                              fmt(metrics["cpu_pct"], "%"), fmt(metrics["battery"], "%"),
                              THERMAL_STATES[heat] if heat is not None else "—")
                else:
                    values = ("Desconectado", "—", "—", "—", "—")
                work, checkpoint = hub.work.latest(identity)
                progress = f"{WORK_STATES[work]} {checkpoint}/4" if work else "—"
                results.append((f"{name} · {identity[-6:]}", *values, PROBE_STATES.get(probe.get("state"), "—"),
                                progress))
            if results != refresh.previous:
                devices.clearSelection()
                rows(devices, results)
                refresh.previous = results
                if selected in records:
                    devices.selectRow(records.index(selected))
            endpoints.setText("\n".join(f"{title}   {hub.listeners[key].address.ip}:{hub.listeners[key].server_port}"
                                      for title, key in TRANSPORTS if key in hub.listeners)
                              or "Transportes desativados.")
            if invitation.isVisible():
                if hub.ticket is None or monotonic() >= ticket_at:
                    invitation.clear()
                    invitation.hide()
            update_buttons()
            if hub.notice:
                alert.setText(hub.notice)
        except (OSError, ValueError, sqlite3.Error) as error:
            feedback.setText(str(error))

    refresh.previous = None

    def run(action, *args):
        try:
            action(*args)
            feedback.setText("")
            refresh()
        except (OSError, ValueError, sqlite3.Error) as error:
            message = str(error)
            if message.startswith(SENTINEL):
                hub.alert(message)
                alert.setText(message)
            feedback.setText(message)

    def toggle():
        key = transport.currentData()
        if key in hub.listeners:
            hub.stop(key)
        elif adapter.currentData():
            hub.start(adapter.currentData(), key, port=41873)

    def generate():
        nonlocal ticket_at
        key = transport.currentData()
        if key in hub.listeners:
            invitation.setText(hub.invitation(key))
            ticket_at = monotonic() + 120
            invitation.show()
            invitation.setFocus()
            invitation.selectAll()

    def selected_id():
        row = devices.currentRow()
        return records[row] if 0 <= row < len(records) else None

    def update_buttons():
        enabled = transport.currentData() in hub.listeners
        start.setText("Desativar" if enabled else "Ativar")
        start.setEnabled(enabled or adapter.currentData() is not None)
        invite.setEnabled(enabled)
        selected = selected_id() is not None
        for control in (send, cancel, revoke, rename, work, stop_work):
            control.setEnabled(selected)
        able = bridge.connected and bool(records) and not bridge.busy
        atlas.setEnabled(able)
        atlas_work.setEnabled(able)

    start = QPushButton("Ativar")
    start.clicked.connect(lambda: run(toggle))
    actions.addWidget(start)
    invite = QPushButton("Gerar código")
    invite.clicked.connect(lambda: run(generate))
    actions.addWidget(invite)
    send = QPushButton("Enviar diagnóstico")
    send.clicked.connect(lambda: run(hub.send_probe, selected_id()))
    probes.addWidget(send)
    atlas = QPushButton("Atlas · escolher aparelho")
    atlas.clicked.connect(lambda: run(bridge.recommend_probe, hub))
    probes.addWidget(atlas)
    cancel = QPushButton("Cancelar mensagem")
    cancel.clicked.connect(lambda: run(hub.cancel_probe, selected_id()))
    probes.addWidget(cancel)
    controls = QHBoxLayout()
    layout.addLayout(controls)
    work = QPushButton("Iniciar cálculo leve")
    work.clicked.connect(lambda: run(hub.queue_work, selected_id()))
    controls.addWidget(work)
    atlas_work = QPushButton("Atlas · escolher para cálculo")
    atlas_work.clicked.connect(lambda: run(bridge.recommend_work, hub))
    controls.addWidget(atlas_work)
    stop_work = QPushButton("Cancelar cálculo leve")
    stop_work.clicked.connect(lambda: run(hub.cancel_work, selected_id()))
    controls.addWidget(stop_work)
    rename = QPushButton("Nomear aparelho")

    def rename_selected():
        device = selected_id()
        if device is not None:
            name, confirmed = QInputDialog.getText(devices, "Nome do aparelho", "Nome que aparecerá na lista")
            if confirmed:
                run(hub.rename, device, name)

    rename.clicked.connect(rename_selected)
    controls.addWidget(rename)
    revoke = QPushButton("Revogar pareamento")

    def revoke_selected():
        device = selected_id()
        if device is not None and QMessageBox.question(
            devices, "Revogar pareamento", "Revogar o aparelho selecionado e encerrar sua sessão?"
        ) == QMessageBox.StandardButton.Yes:
            run(hub.revoke, device)

    revoke.clicked.connect(revoke_selected)
    probes.addWidget(revoke)
    transport.currentIndexChanged.connect(update_buttons)
    adapter.currentIndexChanged.connect(update_buttons)
    devices.itemSelectionChanged.connect(update_buttons)
    bridge.changed.connect(update_buttons)
    bridge.notice.connect(feedback.setText)
    timer = QTimer(devices)
    timer.timeout.connect(lambda: refresh() if devices.isVisible() else None)
    timer.start(2000)
    refresh()
