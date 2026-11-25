"""Entrada e revisão local de personagens no Studio Desktop."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from PySide6.QtCore import QProcess, QProcessEnvironment, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFormLayout, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QVBoxLayout)

from .character_production import IDENTIFIER, LocalPackages, _job, _json, publish, review
from .pages import button


class CharacterDialog(QDialog):
    def __init__(self, parent, production):
        super().__init__(parent)
        self.setWindowTitle("Produção local de personagem")
        self.resize(580, 500)
        self.production = production
        self.root = production.root.parent / "character-experiments"
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(Path(__file__).resolve().parents[1]))
        inherited = QProcessEnvironment.systemEnvironment()
        environment = QProcessEnvironment()
        for key in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "HOME", "USERPROFILE"):
            if inherited.contains(key):
                environment.insert(key, inherited.value(key))
        self.process.setProcessEnvironment(environment)
        self.process.finished.connect(self.process_finished)
        self.process.errorOccurred.connect(self.process_error)
        self.input_directory = None
        self.images = []
        self.base = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setMaxLength(100)
        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(115)
        self.quality = QComboBox()
        for key, caption in zip(("lite", "low", "medium", "high", "ultra", "cinematic"),
                                ("Lite", "Baixa", "Média", "Alta", "Ultra", "Cinematográfica")):
            self.quality.addItem(caption, key)
        self.source = QComboBox()
        self.source.addItem("GLB fornecido", "base_glb")
        self.source.addItem("Manequim sintético", "synthetic_fixture")
        self.source.addItem("Imagem → geometria (gerador pendente)", "image_guided")
        form.addRow("Nome", self.name)
        form.addRow("Características", self.description)
        form.addRow("Perfil", self.quality)
        form.addRow("Origem", self.source)
        self.image_button = button("Escolher imagens de referência", self.choose_images)
        self.base_button = button("Escolher GLB base", self.choose_base)
        form.addRow(self.image_button)
        form.addRow(self.base_button)
        layout.addLayout(form)
        self.begin = button("Iniciar produção local", self.start)
        self.jobs = QComboBox()
        self.jobs.currentIndexChanged.connect(self.show_job)
        self.open = button("Abrir pasta para inspecionar", self.open_job)
        self.accept_revision = button("Aprovar revisão local", lambda: self.decide("accept"))
        self.reject_revision = button("Rejeitar revisão", lambda: self.decide("reject"))
        self.deliver = button("Salvar pacote aprovado", self.save)
        self.status = QLabel()
        self.status.setWordWrap(True)
        for item in (self.begin, self.jobs, self.status, self.open, self.accept_revision, self.reject_revision, self.deliver):
            layout.addWidget(item)
        self.refresh()

    def choose_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Imagens de referência", "", "Imagens (*.png *.jpg *.jpeg)")
        if files:
            self.images = files[:4]
            self.image_button.setText(f"{len(self.images)} imagem(ns) selecionada(s)")
            if len(files) > 4:
                self.status.setText("As primeiras quatro imagens foram selecionadas.")

    def choose_base(self):
        file, _ = QFileDialog.getOpenFileName(self, "Modelo base", "", "GLB (*.glb)")
        if file:
            self.base = file
            self.base_button.setText(Path(file).name)

    def start(self):
        source = self.source.currentData()
        description = self.description.toPlainText().strip()
        checkout = self.production.bridge.checkout
        blender = self.production.blender_path()
        if not checkout or not blender:
            self.status.setText("Configure os caminhos locais do Agents e do Blender.")
            return
        if not self.name.text().strip() or not 1 <= len(description) <= 2000 or not self.images:
            self.status.setText("Preencha o nome, a descrição (até 2.000 caracteres) e selecione as imagens.")
            return
        if source == "base_glb" and not self.base:
            self.status.setText("Selecione o modelo-base GLB.")
            return
        self.input_directory = TemporaryDirectory(prefix="arvertes-character-")
        briefing = Path(self.input_directory.name) / "brief.json"
        briefing.write_text(json.dumps({
            "name": self.name.text().strip(), "description": description, "source": source,
            "quality": self.quality.currentData(), "requirements": ["rig", "animations", "materials", "lods"],
        }), encoding="utf-8")
        args = ["-m", "arvertes_desktop.character_production", "--workspace", str(self.root), "start",
                "--agents", checkout, "--blender", blender, "--brief", str(briefing), "--approved"]
        for path in self.images:
            args.extend(("--image", path))
        if source == "base_glb":
            args.extend(("--base", self.base))
        self.begin.setEnabled(False)
        self.status.setText("Planejando ou executando localmente…")
        self.process.start(sys.executable, args)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.process_finished(1, QProcess.ExitStatus.CrashExit)

    def process_finished(self, code, _exit_status):
        if self.input_directory is not None:
            self.input_directory.cleanup()
            self.input_directory = None
        self.begin.setEnabled(True)
        if code:
            self.status.setText(bytes(self.process.readAllStandardError()).decode("utf-8", "replace")[-1500:]
                                or "A execução local foi interrompida.")
            return
        try:
            self.refresh(json.loads(bytes(self.process.readAllStandardOutput()))["job"])
        except (ValueError, KeyError):
            self.status.setText("A produção retornou uma resposta incompatível.")

    def refresh(self, selected=None):
        selected = selected or self.jobs.currentData()
        self.jobs.blockSignals(True)
        self.jobs.clear()
        self.jobs.addItem("Selecionar revisão anterior", "")
        if self.root.is_dir() and not self.root.is_symlink():
            for job in sorted(self.root.iterdir()):
                if not IDENTIFIER.fullmatch(job.name):
                    continue
                try:
                    state = _json(_job(self.root, job.name) / "status.json")
                    name = _json(job / "brief.json")["name"]
                    self.jobs.addItem(f"{name} · {state['job'][:8]}", job.name)
                except (OSError, ValueError, KeyError):
                    continue
        self.jobs.setCurrentIndex(max(0, self.jobs.findData(selected)))
        self.jobs.blockSignals(False)
        self.show_job()

    def show_job(self):
        for action in (self.open, self.accept_revision, self.reject_revision, self.deliver):
            action.setEnabled(False)
        identifier = self.jobs.currentData()
        if not identifier:
            self.status.clear()
            return
        try:
            job = _job(self.root, identifier)
            state = _json(job / "status.json")
            self.open.setEnabled(True)
            if state["state"] != "awaiting_human_review":
                reason = state.get("reason")
                reason = {"image_guided_generator_unavailable": "Gerador de geometria por imagens indisponível.",
                          "quality_profile_requires_executor_validation": "Perfil fora da faixa validada para execução."}.get(
                              reason, reason)
                missing = ", ".join(state.get("missing_required", []))
                referrals = ", ".join(item["agent"] for item in state.get("referrals", []))
                self.status.setText(reason or "\n".join(item for item in (
                    "Produção bloqueada", f"Componentes faltantes · {missing}" if missing else "",
                    f"Encaminhamentos · {referrals}" if referrals else "") if item))
                return
            if (job / "review.json").is_file():
                approval = _json(job / "review.json")["decision"]
                self.deliver.setEnabled(approval == "accept")
                note = "Aceita para entrega local" if approval == "accept" else "Rejeitada"
            else:
                note = "Aguardando revisão local. Inspecione os modelos e relatórios antes de decidir."
                self.accept_revision.setEnabled(True)
                self.reject_revision.setEnabled(True)
            self.status.setText(note + "\nSHA-256 " + state["sha256"])
        except (OSError, ValueError, KeyError) as error:
            self.status.setText(str(error))

    def decide(self, decision):
        job = _job(self.root, self.jobs.currentData())
        answer = QMessageBox.question(self, "Revisão humana", "Registrar esta decisão para o pacote exibido?")
        if answer == QMessageBox.StandardButton.Yes:
            try:
                review(job, _json(job / "status.json")["sha256"], decision)
                self.show_job()
            except (OSError, ValueError) as error:
                self.status.setText(str(error))

    def open_job(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(_job(self.root, self.jobs.currentData()))))

    def save(self):
        folder = QFileDialog.getExistingDirectory(self, "Pasta para salvar a revisão aprovada")
        if folder:
            try:
                path = publish(_job(self.root, self.jobs.currentData()), LocalPackages(Path(folder)))
                self.status.setText("Pacote verificado em " + str(path))
            except (OSError, ValueError) as error:
                self.status.setText(str(error))

    def reject(self):
        if self.process.state() == QProcess.ProcessState.NotRunning:
            super().reject()
        else:
            self.status.setText("Aguarde o checkpoint final da produção local.")
