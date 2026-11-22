"""Janela inicial; sem importação de bpy e sem agentes executores."""
from pathlib import Path
import sqlite3

from PySide6.QtCore import QProcess, QStandardPaths, QTimer, Qt
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QStackedWidget, QVBoxLayout, QWidget, QStyle, QListWidgetItem,
)

from .navigation import SECTIONS
from .network_page import build_network
from .dashboard import build_dashboard
from .sentinel_page import build_sentinel
from .roster import AGENTS
from .pages import WorkspacePages, build_agents
from .workspace import Workspace
from .settings import Settings, load_settings, save_settings, validate_blender_path
from .theme import DARK_THEME

CAPABILITIES = {
    "model": ("Importação e análise de modelos", "Edição seletiva", "Variações e kits modulares"),
    "materials": ("Materiais PBR", "UVs e bake", "Presets e texturas"),
    "rig": ("Topologia", "Esqueletos e pesos", "Validação de deformações"),
    "animation": ("Ciclos de movimento", "Expressões", "Transferência de animações"),
    "effects": ("Partículas", "Simulações", "Cinematografia"),
    "audio": ("Vozes originais", "Efeitos sonoros", "Trilhas", "Sincronização labial"),
    "pipeline": ("Imagem para pacote", "Modelo para pacote", "Dependências e aprovação"),
    "quality": ("Inspeção técnica", "Auditoria final", "Ciclos de correção e continuidade"),
    "export": ("Validação Unreal", "Pacotes de assets", "Relatórios e formatos de exportação"),
}


def label(text: str, style: str = "") -> QLabel:
    result = QLabel(text)
    result.setTextFormat(Qt.TextFormat.PlainText)
    result.setWordWrap(True)
    if style:
        result.setObjectName(style)
    return result


def panel() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(10)
    return frame, layout


class StudioWindow(QMainWindow):
    def __init__(self, *, config_dir=None):
        super().__init__()
        self.setWindowTitle("Arvertes Studio — 0.2.1 dev")
        self.setMinimumSize(860, 540)
        self.resize(1200, 760)
        self.setStyleSheet(DARK_THEME)
        if config_dir is None:
            config_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        self.config_path = Path(config_dir) / "settings.json"
        self.load_error = ""
        try:
            self.settings = load_settings(self.config_path)
        except (OSError, ValueError, RecursionError) as error:
            self.settings = Settings()
            self.load_error = str(error)

        self.workspace = None
        self.workspace_error = ""
        try:
            self.workspace = Workspace(self.config_path.parent / "workspace.sqlite3")
        except (OSError, ValueError, sqlite3.Error) as error:
            self.workspace_error = str(error)
        self.work_pages = WorkspacePages(self, self.workspace) if self.workspace else None

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.finished.connect(self._version_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self._version_timeout)
        self.timed_out = False
        self._build()

    def _build(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        top = QFrame()
        top.setObjectName("topbar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(18, 12, 18, 12)
        top_layout.addWidget(label("A  /  ARVERTES STUDIO", "brand"))
        top_layout.addWidget(label("WORKSPACE", "eyebrow"))
        top_layout.addStretch()
        top_layout.addWidget(label("●  Modo diagnóstico", "networkTag"))
        self.blender_status = label("Blender não verificado", "muted")
        top_layout.addWidget(self.blender_status)
        outer.addWidget(top)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.menu = QListWidget()
        self.menu.setObjectName("navigation")
        self.menu.setFixedWidth(194)
        icons = {
            "home": "SP_ComputerIcon", "projects": "SP_DirIcon", "library": "SP_FileDialogContentsView",
            "model": "SP_FileIcon", "materials": "SP_DialogApplyButton", "rig": "SP_FileDialogDetailedView",
            "animation": "SP_MediaPlay", "effects": "SP_BrowserReload", "audio": "SP_MediaVolume",
            "pipeline": "SP_ArrowForward", "quality": "SP_DialogYesButton", "agents": "SP_DirOpenIcon",
            "tasks": "SP_FileDialogListView", "export": "SP_DialogSaveButton",
            "network": "SP_DriveNetIcon", "sentinel": "SP_MessageBoxWarning", "settings": "SP_FileDialogInfoView",
        }
        for section in SECTIONS:
            icon = self.style().standardIcon(getattr(QStyle.StandardPixmap, icons[section.key]))
            item = QListWidgetItem(icon, section.title)
            item.setToolTip(section.description)
            self.menu.addItem(item)
        body.addWidget(self.menu)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        outer.addLayout(body, 1)
        self.setCentralWidget(root)

        for section in SECTIONS:
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setContentsMargins(24, 20, 24, 20)
            layout.setSpacing(12)
            layout.addWidget(label(section.title, "heading"))
            layout.addWidget(label(section.description, "muted"))
            if section.key == "home":
                self.refresh_dashboard = build_dashboard(layout, self.workspace, self._navigate)
            elif section.key == "settings":
                self._settings_page(layout)
            elif section.key == "agents":
                build_agents(layout)
            elif section.key == "sentinel":
                build_sentinel(layout)
            elif section.key == "network":
                build_network(layout)
            elif section.key in ("projects", "library", "tasks"):
                if self.work_pages is None:
                    layout.addWidget(label("Banco local indisponível: " + self.workspace_error, "muted"))
                    layout.addStretch()
                else:
                    getattr(self.work_pages, section.key + "_page")(layout)
            else:
                box, box_layout = panel()
                box_layout.addWidget(label("Funcionalidade planejada"))
                milestone = section.milestone
                if not milestone.startswith("Etapa"):
                    milestone = "v" + milestone
                box_layout.addWidget(label("Etapa prevista: " + milestone + ". Ferramentas ainda não conectadas.", "muted"))
                for capability in CAPABILITIES.get(section.key, ()):
                    box_layout.addWidget(label("• " + capability))
                navigate = QPushButton("Planejar tarefa")
                navigate.clicked.connect(lambda: self._navigate("tasks"))
                navigate.setEnabled(self.work_pages is not None)
                box_layout.addWidget(navigate)
                layout.addWidget(box)
                layout.addStretch()

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.pages.addWidget(scroll)

        if self.work_pages:
            self.work_pages.refresh()
        self.menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.menu.currentRowChanged.connect(lambda row: self.refresh_dashboard() if row == 0 else None)
        self.menu.setCurrentRow(0)
        self.statusBar().showMessage("Versão de desenvolvimento • Modo de planejamento, sem execução")

    def _navigate(self, key):
        self.menu.setCurrentRow(next(i for i, section in enumerate(SECTIONS) if section.key == key))

    def _settings_page(self, layout):
        frame, form = panel()
        form.addWidget(label("Executável do Blender"))
        form.addWidget(label("Selecione uma instalação confiável. O teste apenas executa blender --version.", "muted"))
        self.path = QLineEdit(self.settings.blender_path)
        self.path.setPlaceholderText("C:/Program Files/Blender Foundation/.../blender.exe")
        self.path.textChanged.connect(self._path_changed)
        row = QHBoxLayout()
        row.addWidget(self.path, 1)
        self.browse = QPushButton("Procurar")
        self.browse.clicked.connect(self._browse)
        row.addWidget(self.browse)
        form.addLayout(row)
        actions = QHBoxLayout()
        self.test_button = QPushButton("Verificar Blender")
        self.test_button.clicked.connect(self._check_version)
        self.save_button = QPushButton("Salvar configuração")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self._save)
        actions.addWidget(self.test_button)
        actions.addWidget(self.save_button)
        actions.addStretch()
        form.addLayout(actions)
        self.feedback = label("Nenhum teste realizado.", "muted")
        form.addWidget(self.feedback)
        if self.load_error:
            form.addWidget(label("Não foi possível carregar a configuração anterior: " + self.load_error, "muted"))
        form.addWidget(label("Configuração local: " + str(self.config_path), "muted"))
        layout.addWidget(frame)
        layout.addStretch()

    def _path_changed(self):
        self.blender_status.setText("Blender não verificado")
        self.feedback.setText("Caminho alterado. Verifique e salve se desejar.")

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar Blender", self.path.text(),
                                              "Blender (blender.exe blender);;Todos os arquivos (*)")
        if path:
            self.path.setText(path)

    def _save(self):
        try:
            value = self.path.text().strip()
            if value:
                validate_blender_path(value)
            settings = Settings(value)
            save_settings(self.config_path, settings)
            self.settings = settings
            self.feedback.setText("Configuração salva localmente.")
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Configuração não salva", str(error))

    def _set_busy(self, busy):
        for widget in (self.path, self.browse, self.test_button, self.save_button):
            widget.setEnabled(not busy)

    def _check_version(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return
        try:
            path = validate_blender_path(self.path.text().strip())
        except (OSError, ValueError) as error:
            self.feedback.setText(str(error))
            return
        self.timed_out = False
        self._set_busy(True)
        self.feedback.setText("Verificando versão...")
        self.blender_status.setText("Blender em verificação")
        self.timeout.start(10000)
        self.process.start(str(path), ["--version"])

    def _version_timeout(self):
        self.timed_out = True
        self.process.kill()

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.timeout.stop()
            self._set_busy(False)
            self.feedback.setText("Não foi possível iniciar o Blender.")
            self.blender_status.setText("Blender não verificado")

    def _version_finished(self, exit_code, exit_status):
        self.timeout.stop()
        output = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._set_busy(False)
        first_line = output.strip().splitlines()[0] if output.strip() else ""
        if self.timed_out:
            self.feedback.setText("Verificação interrompida: tempo limite.")
        elif exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0 and first_line.startswith("Blender "):
            self.feedback.setText("Versão encontrada: " + first_line[:150])
            self.blender_status.setText("Blender verificado")
            return
        else:
            self.feedback.setText("O executável não retornou uma versão válida do Blender.")
        self.blender_status.setText("Blender não verificado")

    def closeEvent(self, event):
        self.timeout.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(500)
        if self.workspace is not None:
            self.workspace.close()
            self.workspace = None
        super().closeEvent(event)
