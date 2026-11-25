"""Publicação opcional pelo Studio, sem credencial em disco."""
import json
import re
import sqlite3
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkProxy, QNetworkRequest
from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit

from .cloud_projection import CATEGORIES, projection
from .pages import button, plain

TITLES = dict(zip(CATEGORIES, ("Projetos", "Tarefas", "Agentes", "Dispositivos", "Histórico", "Relatórios técnicos", "Sentinel")))


def endpoint(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query
            or parsed.fragment or parsed.path.rstrip("/") or any(char.isspace() for char in value)):
        raise ValueError("Informe a origem HTTPS do Arvertes Cloud.")
    return QUrl(value.rstrip("/") + "/v1/snapshot")


class CloudSync(QObject):
    def __init__(self, parent, window):
        super().__init__(parent)
        self.window = window
        self.reply = None
        self.config = None
        self.retry = 30_000
        self.network = QNetworkAccessManager(self)
        self.network.setProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.send)

    def start(self, origin, secret, project, selected):
        url = endpoint(origin)
        if not re.fullmatch(r"[0-9a-f]{64}", secret):
            raise ValueError("Informe a credencial de sincronização de 64 caracteres.")
        self.stop()
        self.config = (url, secret.encode("ascii"), project, selected)
        self.retry = 30_000
        self.send()

    def stop(self):
        self.timer.stop()
        self.config = None
        if self.reply is not None:
            active, self.reply = self.reply, None
            active.abort()
        if hasattr(self, "status"):
            self.status.setText("Sincronização pausada. A projeção anterior expira no servidor.")

    def send(self):
        if self.config is None or self.reply is not None:
            return
        url, secret, project, selected = self.config
        try:
            data = projection(self.window.workspace, self.window._network, self.window.agent_bridge,
                              self.window._production, project, selected)
            body = json.dumps(data, separators=(",", ":")).encode()
            if len(body) > 65536:
                raise ValueError("Projeção acima de 64 KiB.")
        except (ValueError, sqlite3.Error) as error:
            self.stop()
            self.status.setText(str(error))
            return
        self.send_request(url, secret, body)

    def send_request(self, url, secret, body):
        request = QNetworkRequest(url)
        request.setRawHeader(b"X-Arvertes-Sync", secret)
        request.setTransferTimeout(8000)
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        if body is None:
            self.reply = self.network.deleteResource(request)
        else:
            request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
            self.reply = self.network.put(request, body)
        self.reply.setReadBufferSize(4096)
        active = self.reply
        active.readyRead.connect(lambda: active.readAll())
        active.finished.connect(lambda: self.finished(active, body is None))

    def clear(self):
        if self.config is None:
            self.status.setText("Conecte a sincronização para apagar a projeção remota.")
            return
        url, secret, _, _ = self.config
        self.stop()
        self.send_request(url, secret, None)

    def finished(self, active, clearing):
        try:
            if active != self.reply:
                return
            self.reply = None
            code = active.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if code == 200:
                self.retry = 30_000
                self.status.setText("Projeção removida." if clearing else "Projeção autorizada sincronizada.")
            elif code in (400, 401, 403, 413, 415, 422) or code and 300 <= code < 400:
                self.stop()
                self.status.setText(f"Sincronização encerrada. O servidor recusou a solicitação ({code}).")
            else:
                self.retry = min(120_000, self.retry * 2)
                self.status.setText("Servidor indisponível." if clearing else "Sem confirmação. Tentando reconectar.")
            if self.config is not None:
                self.timer.start(self.retry)
        finally:
            active.deleteLater()


def build_cloud_controls(layout, window):
    layout.addWidget(plain("Arvertes Cloud"))
    layout.addWidget(plain("Compartilhe apenas estados técnicos das seções escolhidas. "
                           "A sincronização começa quando autorizada e para ao fechar o Studio."))
    controller = CloudSync(window, window)
    window.cloud_sync = controller
    origin = QLineEdit()
    origin.setPlaceholderText("https://cloud.exemplo.org")
    secret = QLineEdit()
    secret.setPlaceholderText("Credencial de sincronização")
    secret.setEchoMode(QLineEdit.EchoMode.Password)
    project = QComboBox()
    checks = {key: QCheckBox(title) for key, title in TITLES.items()}

    def refresh():
        current = project.currentData()
        project.clear()
        project.addItem("Selecione um projeto", None)
        if window.workspace:
            for row in window.workspace.projects():
                project.addItem(row["name"], row["id"])
        index = project.findData(current)
        project.setCurrentIndex(max(0, index))

    refresh()
    for widget in (origin, secret, project, *checks.values()):
        layout.addWidget(widget)
    controller.status = plain("Sincronização desativada.")

    def start():
        try:
            controller.start(origin.text().strip(), secret.text().strip(), project.currentData(),
                             tuple(key for key, checked in checks.items() if checked.isChecked()))
            secret.clear()
        except ValueError as error:
            controller.status.setText(str(error))

    layout.addWidget(button("Autorizar sincronização", start))
    layout.addWidget(button("Pausar sincronização", controller.stop))
    layout.addWidget(button("Apagar projeção remota", controller.clear))
    layout.addWidget(controller.status)
    return refresh
