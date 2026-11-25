"""Janela inicial; sem importação de bpy e sem agentes executores."""
from dataclasses import replace
from pathlib import Path
import sqlite3

from PySide6.QtCore import QEvent, QProcess, QStandardPaths, QTimer, Qt
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QStackedWidget, QTabWidget, QVBoxLayout, QWidget, QStyle, QListWidgetItem,
)

from .agent_bridge import AgentBridge
from .agent_panel import build_agent_tools
from .navigation import SECTIONS
from .dashboard import build_dashboard
from .roster import AGENTS
from .pages import WorkspacePages, build_agents
from .status_snapshot import snapshot, export
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
        self.setWindowTitle("Arvertes Studio — 0.2.4 dev")
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
        self._network = None
        self.network_error = ""
        self._production = None
        self.agent_bridge = AgentBridge(self)
        self.work_pages = WorkspacePages(self, self.workspace) if self.workspace else None
        self.section_layouts = {}

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
            "home": "SP_ComputerIcon", "office": "SP_DirHomeIcon", "projects": "SP_DirIcon", "library": "SP_FileDialogContentsView",
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
            self.section_layouts[section.key] = (section, layout)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.pages.addWidget(scroll)

        self.menu.currentRowChanged.connect(self._open_section)
        self._navigate("home")
        self.statusBar().showMessage("Versão de desenvolvimento • Conexões locais")
        self.resource_display = label("", "muted")
        self.statusBar().addPermanentWidget(self.resource_display)
        self.resource_timer = QTimer(self)
        self.resource_timer.timeout.connect(self._show_resources)
        self.resource_timer.start(2500)
        QTimer.singleShot(300, self._show_resources)

    @property
    def production(self):
        if self._production is None and self.workspace is not None:
            from .production import Production
            self._production = Production(self, self.workspace, self.agent_bridge,
                                          self.config_path.parent / "inspections",
                                          lambda: self.settings.blender_path)
        return self._production

    @property
    def network(self):
        if self._network is None and not self.network_error:
            try:
                from .network import DeviceHub
                self._network = DeviceHub(self.config_path.parent / "devices.sqlite3")
            except (OSError, ValueError, sqlite3.Error) as error:
                self.network_error = str(error)
        return self._network

    def _show_resources(self):
        if self.isMinimized():
            return
        from .resources import reading
        sample = reading()
        self.resource_display.setText(
            f"RAM livre {sample.available} / {sample.total} MiB   •   CPU {sample.cpu:.0f}%")

    def _open_section(self, row):
        if row < 0:
            return
        key = SECTIONS[row].key
        work = ("projects", "library", "tasks")
        if key in work and key in self.section_layouts:
            for section in work:
                self._fill_section(section)
            if self.work_pages:
                self.work_pages.refresh()
        else:
            self._fill_section(key)
        self.pages.setCurrentIndex(row)
        if key == "home":
            self.refresh_dashboard()
        elif key == "settings" and hasattr(self, "refresh_cloud"):
            self.refresh_cloud()

    def _fill_section(self, key):
        if key not in self.section_layouts:
            return
        section, layout = self.section_layouts.pop(key)
        if section.key == "home":
            self.refresh_dashboard = build_dashboard(layout, self.workspace, self._navigate)
        elif section.key == "settings":
            self._settings_page(layout)
        elif section.key == "agents":
            build_agents(layout, self.agent_bridge)
            build_agent_tools(layout, self.agent_bridge, self.settings, self._save_agents)
        elif section.key == "office":
            from .office import build_office
            self.office_preview = build_office(layout, self._navigate, self.agent_bridge, self.production)
        elif section.key == "sentinel":
            from .sentinel_page import build_sentinel
            build_sentinel(layout, lambda: self._network, self.agent_bridge)
        elif section.key == "network":
            from .network_page import build_network
            build_network(layout, self.network, self.network_error, self.agent_bridge)
        elif section.key == "audio":
            from .audio_page import build_audio
            build_audio(layout, self.agent_bridge)
        elif section.key in ("pipeline", "export"):
            entry = QPushButton("Abrir fila e entregas FBX")
            entry.setEnabled(self.work_pages is not None)
            entry.clicked.connect(self._open_pipeline)
            layout.addWidget(entry)
            layout.addStretch()
        elif section.key in ("projects", "library", "tasks"):
            if self.work_pages is None:
                layout.addWidget(label("Banco local indisponível: " + self.workspace_error, "muted"))
                layout.addStretch()
            elif section.key == "tasks":
                from .production_page import build_production
                tabs = QTabWidget()
                for title in ("Rascunhos", "Inspeções GLB"):
                    tab = QWidget()
                    tabs.addTab(tab, title)
                    tab_layout = QVBoxLayout(tab)
                    if title == "Rascunhos":
                        self.work_pages.tasks_page(tab_layout)
                    else:
                        refresh = build_production(tab_layout, self.production, self.work_pages.protect)
                        tabs.currentChanged.connect(lambda index: refresh() if index == 1 else None)
                layout.addWidget(tabs, 1)
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


    def _open_pipeline(self):
        self._navigate("tasks")
        tabs = self.pages.currentWidget().findChild(QTabWidget)
        if tabs:
            tabs.setCurrentIndex(1)

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
        sharing = QPushButton("Exportar estado para MCP")
        sharing.setToolTip("Exporta nomes e estados locais. Revise o JSON antes de compartilhá-lo.")
        sharing.clicked.connect(self._export_snapshot)
        layout.addWidget(sharing)
        from .cloud_page import build_cloud_controls
        self.refresh_cloud = build_cloud_controls(layout, self)
        from .update_panel import build_update_panel
        build_update_panel(layout, self)
        layout.addStretch()

    def _export_snapshot(self):
        directory = QFileDialog.getExistingDirectory(self, "Pasta para exportar arvertes-status.json")
        if directory:
            try:
                target = Path(directory) / "arvertes-status.json"
                if target.exists() and QMessageBox.question(
                        self, "Atualizar exportação", "Substituir o arquivo de estado desta pasta?"
                ) != QMessageBox.StandardButton.Yes:
                    return
                export(target, snapshot(self.workspace, self._network, self.agent_bridge))
                self.statusBar().showMessage("Estado exportado. Revise o arquivo antes de compartilhá-lo.", 6000)
            except (OSError, ValueError, sqlite3.Error) as error:
                QMessageBox.warning(self, "Exportação indisponível", str(error))

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
            settings = replace(self.settings, blender_path=value)
            save_settings(self.config_path, settings)
            self.settings = settings
            self.feedback.setText("Configuração salva localmente.")
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Configuração não salva", str(error))

    def _save_agents(self, python, checkout):
        try:
            settings = replace(self.settings, agents_python=python, agents_checkout=checkout)
            save_settings(self.config_path, settings)
            self.settings = settings
        except OSError as error:
            QMessageBox.warning(self, "Conexão não gravada", str(error))

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

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, "office_preview"):
            self.office_preview.set_suspended(self.isMinimized())

    def closeEvent(self, event):
        self.resource_timer.stop()
        if hasattr(self, "update_check"):
            self.update_check.cancelled.set()
        if hasattr(self, "cloud_sync"):
            self.cloud_sync.stop()
        if self._production:
            self._production.close()
        self.agent_bridge.close()
        if self._network is not None:
            self._network.close()
        self.timeout.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(500)
        if self.workspace is not None:
            self.workspace.close()
            self.workspace = None
        super().closeEvent(event)
