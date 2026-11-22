"""Optional offline renderer. Serve only reviewed static build files on loopback."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import unquote, urlsplit
import json
import mimetypes

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

BUILD = Path(__file__).resolve().parent / "habblaud_client"
MAX_FILE = 32 * 1024 * 1024


class StaticHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        server = self.server
        if self.headers.get("Host") != f"127.0.0.1:{server.server_port}":
            self.send_error(403)
            return
        if self.path == "/office-state.json":
            self.respond("application/json", server.states)
            return
        try:
            path = unquote(urlsplit(self.path).path).lstrip("/") or "index.html"
            file = (server.root / path).resolve()
            if not file.is_relative_to(server.root) or not file.is_file():
                self.send_error(404)
                return
            if file.stat().st_size > MAX_FILE:
                self.send_error(413)
                return
            data = file.read_bytes()
        except (OSError, ValueError):
            self.send_error(404)
            return
        kind = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        if file.suffix == ".js":
            kind = "text/javascript"
        self.respond(kind, data)

    def respond(self, kind, data):
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class PreviewServer:
    def __init__(self, root):
        root = Path(root).resolve(strict=True)
        if not (root / "index.html").is_file():
            raise ValueError("Bundle visual ausente.")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), StaticHandler)
        self.server.root = root
        self.server.states = b"{}"
        self.thread = Thread(target=self.server.serve_forever, daemon=True,
                             kwargs={"poll_interval": 0.1})
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}/"

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class OfficePreview(QWidget):
    """Explicit, optional WebEngine preview; no process runs until requested."""
    active_changed = Signal(bool)
    def __init__(self, auto=False):
        super().__init__()
        self.desired, self.suspended = auto, False
        self.server = None
        self.view = None
        self.states = {"states": {}, "history": {}, "flow": ""}
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.button = QPushButton("Abrir escritório Habblaud")
        self.box.addWidget(self.button)
        self.message = QLabel("Habblaud · motor visual de Márcio Junior (MIT)")
        self.message.setWordWrap(True)
        self.box.addWidget(self.message)
        self.button.clicked.connect(self.toggle)

    def update_states(self, states, history, flow=""):
        self.states = {"states": states, "history": history, "flow": flow}
        if self.server:
            self.server.server.states = json.dumps(self.states).encode("ascii")

    def toggle(self):
        self.desired = self.view is None
        if self.desired:
            self.activate()
        else:
            self.stop()

    def activate(self):
        if not self.desired or self.suspended or not self.isVisible() or self.view is not None:
            return
        if not (BUILD / "index.html").is_file():
            self.message.setText("Bundle Habblaud ainda não instalado nesta edição. Use o mapa leve abaixo.")
            return
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor
            from PySide6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            self.message.setText("Qt WebEngine opcional indisponível; mapa leve mantido.")
            return
        try:
            self.server = PreviewServer(BUILD)
            self.update_states(**self.states)
            origin = QUrl(self.server.url)
            class LocalOnly(QWebEngineUrlRequestInterceptor):
                def interceptRequest(self, info):
                    url = info.requestUrl()
                    info.block(not (url.scheme() == "http" and url.host() == "127.0.0.1" and url.port() == origin.port()))
            self.view = QWebEngineView(self)
            self.view.setMinimumHeight(440)
            # Off-the-record profile; no account, history or persistent cookies.
            self.profile = QWebEngineProfile(self.view)
            self.interceptor = LocalOnly(self.profile)
            self.profile.setUrlRequestInterceptor(self.interceptor)
            self.profile.downloadRequested.connect(lambda download: download.cancel())
            self.page = QWebEnginePage(self.profile, self.view)
            self.view.setPage(self.page)
            self.box.addWidget(self.view, 1)
            self.view.load(origin)
            self.button.setText("Usar mapa leve")
            self.message.setText("Habblaud · eventos de produção e movimento ambiente decorativo")
            self.active_changed.emit(True)
        except (OSError, RuntimeError, ValueError) as error:
            self.stop()
            self.message.setText("Não foi possível abrir a prévia: " + str(error))

    def stop(self):
        if self.view is not None:
            self.view.stop()
            self.box.removeWidget(self.view)
            self.view.hide()
            self.page.deleteLater()
            self.view.deleteLater()
            self.view = self.page = self.profile = self.interceptor = None
        if self.server is not None:
            self.server.close()
            self.server = None
        self.button.setText("Abrir escritório Habblaud")
        self.message.setText("Modo econômico · mapa Qt")
        self.active_changed.emit(False)

    def set_suspended(self, suspended):
        self.suspended = suspended
        if suspended and self.view is not None:
            self.stop()
        elif not suspended:
            QTimer.singleShot(0, self.activate)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.activate)

    def hideEvent(self, event):
        if self.server is not None or self.view is not None:
            self.stop()
        super().hideEvent(event)
