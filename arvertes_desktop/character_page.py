"""Entrada e revisão local de personagens no Studio Desktop."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from PySide6.QtCore import QProcess, QProcessEnvironment, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QInputDialog, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QVBoxLayout)

from .character_production import IDENTIFIER, LocalPackages, _job, _json, publish, review
from .pages import button
from .settings import validate_blender_path
from .setup_check import diagnose
from arvertes_studio.core.character_style import study_presets, validate_style


class CharacterDialog(QDialog):
    def __init__(self, parent, production):
        super().__init__(parent)
        self.setWindowTitle("Produção local de personagem")
        self.resize(580, 500)
        self.production = production
        self.root = production.root.parent / "character-experiments"
        self.executor_config = production.root.parent / "production-executors.json"
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
        self.process.readyReadStandardError.connect(self.process_progress)
        self.stderr = ""
        self.input_directory = None
        self.images = []
        self.base = self.handoff = self.custom = self.dossier = None

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
        self.source.addItem("Imagens → geometria", "image_guided")
        self.source.addItem("GLB fornecido", "base_glb")
        self.source.addItem("Manequim sintético", "synthetic_fixture")
        self.source.addItem("Blender procedural", "procedural")
        self.source.addItem("GLB externo com comprovante", "external_glb")
        self.vision = QCheckBox("Solicitar análise visual local")
        self.vision.setEnabled(self.executor_config.is_file())
        self.tools_label = QLabel()
        self.tools_label.setWordWrap(True)
        try:
            validate_blender_path(production.blender_path())
            self.tools_label.setText("Blender configurado. A disponibilidade é medida ao iniciar.")
        except (OSError, ValueError):
            self.tools_label.setText("Blender pendente. Configure o caminho uma vez no Studio.")
        if not self.executor_config.is_file():
            self.tools_label.setText(self.tools_label.text() + "\nTripoSR e Ollama aguardam configuração local. "
                                     "Use um GLB fornecido ou selecione Blender procedural.")
        form.addRow("Nome", self.name)
        form.addRow("Características", self.description)
        form.addRow("Perfil", self.quality)
        form.addRow("Origem", self.source)
        form.addRow(self.tools_label)
        form.addRow(button("Verificar configuração local", self.check_setup))
        form.addRow(self.vision)
        self.image_button = button("Escolher imagens de referência", self.choose_images)
        self.base_button = button("Escolher GLB base", self.choose_base)
        form.addRow(self.image_button)
        form.addRow(self.base_button)
        self.dossier_button = button("Selecionar vínculo da ficha", self.choose_dossier)
        form.addRow(self.dossier_button)
        self.handoff_button = button("Selecionar comprovante JSON", self.choose_handoff)
        form.addRow(self.handoff_button)
        self.design = QComboBox()
        for label, value in study_presets().items():
            self.design.addItem(label.capitalize(), value)
        self.design.addItem("Personalizado por JSON")
        form.addRow("Receita", self.design)
        self.design_button = button("Escolher receita personalizada", self.choose_design)
        form.addRow(self.design_button)
        self.source.currentIndexChanged.connect(self.update_controls)
        self.design.currentIndexChanged.connect(self.update_controls)
        self.update_controls()
        layout.addLayout(form)
        self.begin = button("Iniciar produção local", self.start)
        self.jobs = QComboBox()
        self.jobs.currentIndexChanged.connect(self.show_job)
        self.open = button("Abrir pasta para inspecionar", self.open_job)
        self.accept_revision = button("Aprovar revisão local", lambda: self.decide("accept"))
        self.reject_revision = button("Solicitar correções", lambda: self.decide("reject"))
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
            if self.source.currentData() == "image_guided":
                self.source.setCurrentIndex(self.source.findData("base_glb"))

    def update_controls(self):
        source = self.source.currentData()
        self.base_button.setEnabled(source in ("base_glb", "external_glb"))
        self.handoff_button.setEnabled(source == "external_glb")
        self.design.setEnabled(source == "procedural")
        self.design_button.setEnabled(source == "procedural" and self.design.currentData() is None)

    def check_setup(self):
        blender = self.production.blender_path()
        checkout = self.production.bridge.checkout
        try:
            report = diagnose(self.root.parent, Path(blender) if blender else None,
                              Path(checkout) if checkout else None,
                              self.executor_config if self.executor_config.is_file() else None)
        except (ValueError, OSError) as error:
            self.tools_label.setText(str(error))
            return
        values = report["components"]
        labels = {"compatible":"compatível","incompatible":"incompatível","missing":"ausente"}
        capacity = report["hardware"]
        self.tools_label.setText(
            f"Blender · {labels[values['blender']]} | Agents · {labels[values['agents_checkout']]}\n"
            f"CPU disponível · {capacity['cpu_threads_effective']:g} | RAM acima da reserva · "
            f"{capacity['ram_available_above_reserve_mib']} MiB\n"
            + ("Opções locais · Blender procedural e GLB fornecido." if report["admitted_local"] else
               "Confira os caminhos e recursos antes de iniciar."))

    def choose_dossier(self):
        file, _ = QFileDialog.getOpenFileName(self, "Vínculo baixado da ficha do Studio", "", "JSON (*.json)")
        if file:
            try:
                data = _json(Path(file), 1024)
                if not isinstance(data, dict) or data.keys() != {"id", "revision"}:
                    raise ValueError("Selecione um vínculo exportado da ficha.")
                self.dossier = data
                self.dossier_button.setText(f"Ficha vinculada · revisão {data['revision']}")
            except (OSError, ValueError) as error:
                self.status.setText(str(error))

    def choose_handoff(self):
        file, _ = QFileDialog.getOpenFileName(self, "Comprovante do executor", "", "JSON (*.json)")
        if file:
            self.handoff = file
            self.handoff_button.setText(Path(file).name)

    def choose_design(self):
        file, _ = QFileDialog.getOpenFileName(self, "Receita procedural", "", "JSON (*.json)")
        if file:
            try:
                self.custom = validate_style(_json(Path(file), 8192))
                self.design_button.setText(Path(file).name)
            except (ValueError, OSError) as error:
                self.status.setText(str(error))

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
        if source in ("base_glb", "external_glb") and not self.base:
            self.status.setText("Selecione o modelo-base GLB.")
            return
        if source == "external_glb" and not self.handoff:
            self.status.setText("Selecione o comprovante de origem do GLB.")
            return
        design = self.design.currentData() or self.custom
        if source == "procedural" and design is None:
            self.status.setText("Selecione uma receita procedural.")
            return
        self.input_directory = TemporaryDirectory(prefix="arvertes-character-")
        briefing = Path(self.input_directory.name) / "brief.json"
        briefing.write_text(json.dumps({
            "name": self.name.text().strip(), "description": description, "source": source,
            "quality": self.quality.currentData(), "dossier":self.dossier, "requirements": ["rig", "animations", "materials", "lods"],
            **({"design": design, "requirements": ["rig", "animations", "materials", "lods", "pbr_maps"]}
               if source == "procedural" else {}),
        }), encoding="utf-8")
        args = ["-m", "arvertes_desktop.character_production", "--workspace", str(self.root), "start",
                "--agents", checkout, "--blender", blender, "--brief", str(briefing), "--approved", "--progress"]
        for path in self.images:
            args.extend(("--image", path))
        if source in ("base_glb", "external_glb"):
            args.extend(("--base", self.base))
        if source == "external_glb":
            args.extend(("--handoff", self.handoff))
        if self.executor_config.is_file():
            args.extend(("--executor-config", str(self.executor_config)))
            if self.vision.isChecked():
                args.append("--analyze-visual")
        self.stderr = ""
        self.begin.setEnabled(False)
        self.status.setText("Planejando ou executando localmente…")
        self.process.start(sys.executable, args)

    def process_progress(self):
        output = bytes(self.process.readAllStandardError()).decode("utf-8", "replace")
        self.stderr = (self.stderr + output)[-3000:]
        labels = {"references": "Validando imagens de referência", "planning": "Atlas está elaborando o plano",
                  "vision": "Consultando o analisador visual local", "generation": "Gerador local em execução",
                  "blender": "Blender local em execução", "checking": "Verificando materiais, malhas e relatórios",
                  "packaging": "Empacotando a revisão por SHA-256"}
        for line in reversed(self.stderr.splitlines()):
            if line.startswith("ARVERTES_STAGE ") and line[15:] in labels:
                self.status.setText(labels[line[15:]])
                break

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.process_finished(1, QProcess.ExitStatus.CrashExit)

    def process_finished(self, code, _exit_status):
        if self.input_directory is not None:
            self.input_directory.cleanup()
            self.input_directory = None
        self.begin.setEnabled(True)
        if code:
            self.process_progress()
            self.status.setText(self.stderr[-1500:] or "A execução local foi interrompida.")
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
            plan = _json(job / "plan.json")
            selected = plan.get("tool_selection", {}).get("executor")
            readiness = plan.get("executor_inventory", {})
            choices = {"blender_procedural":"Blender procedural", "blender_reuse":"Reuso de GLB",
                       "triposr":"TripoSR", "ollama":"Ollama", "sf3d":"Stable Fast 3D",
                       "trellis":"TRELLIS", "trellis2":"TRELLIS.2", "hunyuan21":"Hunyuan3D", "unirig":"UniRig"}
            if readiness:
                active = [choices[name] for name in choices if readiness.get(name, {}).get("available")]
                blocked = [choices[name] for name in choices if name in readiness and not readiness[name]["available"]]
                self.tools_label.setText("Escolha de Atlas · " + (choices.get(selected) or "aguardando executor")
                                         + "\nDisponíveis · " + (", ".join(active) or "nenhum")
                                         + "\nBloqueados · " + ", ".join(blocked))
            self.open.setEnabled(True)
            if state["state"] != "awaiting_human_review":
                reason = state.get("reason")
                reason = {"image_guided_generator_unavailable": "Gerador de geometria por imagens indisponível. "
                          "Forneça um GLB ou escolha uma receita Blender.",
                          "executor_or_sentinel_blocked": "Sentinel ou executor bloqueou o início. Confira o plano salvo.",
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
                fidelity = None
                if decision == "accept" and _json(job / "brief.json")["source"] in ("procedural", "base_glb", "external_glb", "image_guided"):
                    notes, accepted = QInputDialog.getMultiLineText(
                        self, "Comparação visual", "Após conferir as imagens, descreva silhueta, proporções, "
                        "cores, materiais, roupa, acessórios, estilo e diferenças ainda presentes.")
                    if not accepted:
                        return
                    fidelity = {"references": _json(job / "plan.json")["references"], "notes": notes,
                                "verdict": "enough_for_local_review"}
                if decision == "reject":
                    notes, accepted = QInputDialog.getMultiLineText(
                        self, "Solicitar correções", "Descreva o que deve ser revisto na próxima tentativa.")
                    if not accepted:
                        return
                    fidelity = {"notes": notes}
                review(job, _json(job / "status.json")["sha256"], decision, fidelity)
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
