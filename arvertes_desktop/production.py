"""Executor local. A autorização do Studio precede cada ferramenta e checkpoint."""
import json
from pathlib import Path
import re
import sqlite3

import psutil
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from .blender_job import MIN_FREE_MIB, MAX_PROCESS_MIB, fingerprint, read_source, stage, read_result
from .project_runs import STEPS
from .roster import AGENTS
from .settings import validate_blender_path

AGENT_IDS = {agent.id for agent in AGENTS}
WORKER = Path(__file__).with_name("blender_worker.py")


def validated_findings(value):
    findings = value.get("findings") if isinstance(value, dict) else None
    if not isinstance(findings, list) or len(findings) > 100:
        raise ValueError("Achados fora do protocolo.")
    for finding in findings:
        if (not isinstance(finding, dict) or set(finding) != {"agent_id", "severity", "message"}
                or not isinstance(finding["agent_id"], str) or finding["agent_id"] not in AGENT_IDS
                or finding["severity"] not in ("warning", "blocking")
                or not isinstance(finding["message"], str) or not 1 <= len(finding["message"]) <= 500):
            raise ValueError("Achado incompatível.")
    return findings


def review_gate(checkpoints, budget):
    """Verificação independente de Atlas e das conclusões do Agents."""
    report = checkpoints["blender"]["report"]["summary"]
    findings = validated_findings(checkpoints["inspect"])
    audit = checkpoints["audit"]
    if audit.get("findings") != findings or audit.get("requires_human_approval") is not True:
        raise ValueError("Sentinel bloqueou: parecer de auditoria incompatível.")
    geometry = report["geometry_evaluated"]
    if (not geometry or not report["mesh_count"] or not report["geometry_original"]["triangles"]
            or not geometry["triangles"] or report["meshes_without_uv"]
            or report["geometry_original"]["triangles"] > budget or geometry["triangles"] > budget
            or any(item["severity"] == "blocking" for item in findings)):
        return {"reason": "A inspeção encontrou geometria incompleta, UV ausente ou orçamento excedido."}
    return {"reason": "", "requires_human_approval": True}


class Production(QObject):
    changed = Signal()
    notice = Signal(str)

    def __init__(self, parent, workspace, bridge, root, blender_path):
        super().__init__(parent)
        self.workspace, self.runs = workspace, workspace.inspections
        self.bridge, self.root, self.blender_path = bridge, root, blender_path
        self.active = None
        self.step = None
        self.bridge_reservation = None
        self.job_folder = None
        self.job_size = 0
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        inherited = QProcessEnvironment.systemEnvironment()
        environment = QProcessEnvironment()
        for key in ("PATH", "SystemRoot", "WINDIR", "HOME", "USERPROFILE", "TEMP", "TMP", "TMPDIR", "LANG"):
            if inherited.contains(key):
                environment.insert(key, inherited.value(key))
        self.process.setProcessEnvironment(environment)
        self.process.readyRead.connect(self.collect)
        self.process.finished.connect(self.blender_finished)
        self.process.errorOccurred.connect(self.blender_error)
        self.watch = QTimer(self)
        self.watch.setInterval(500)
        self.watch.timeout.connect(self.monitor)
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(lambda: self.halt("Blender excedeu o tempo limite."))
        self.refresh = QTimer(self)
        self.refresh.setInterval(5000)
        self.refresh.timeout.connect(self.recover)
        self.refresh.start()

    def recover(self):
        try:
            self.runs.recover()
        except sqlite3.Error:
            self.notice.emit("Não foi possível verificar reservas da fila.")
        self.changed.emit()

    def queue(self, project, asset, organize, budget):
        reference = next((row for row in self.workspace.assets(project) if row["id"] == asset), None)
        if reference is None:
            raise ValueError("Selecione uma referência GLB do projeto.")
        if not self.bridge.connected or self.bridge.busy:
            raise ValueError("Conecte o Agents e aguarde as consultas em andamento.")
        fingerprinted = fingerprint(read_source(reference["path"]))

        def create(plan):
            try:
                self.runs.create(project, asset, Path(reference["path"]).name, fingerprinted, organize, budget, plan)
                self.notice.emit("Atlas delegou a inspeção. Selecione a fila para iniciar.")
                self.changed.emit()
            except (OSError, ValueError, sqlite3.Error) as error:
                self.notice.emit(str(error))

        self.bridge.call("delegate_inspection", {}, create, failed=self.notice.emit, quiet=True)

    def start(self, run):
        if self.active or self.process.state() != QProcess.ProcessState.NotRunning:
            raise ValueError("Aguarde a inspeção anterior.")
        if not self.bridge.connected or self.bridge.busy:
            raise ValueError("Conecte o Agents e aguarde as consultas em andamento.")
        self.active = (run, self.runs.reserve(run))
        self.advance()

    def advance(self, reservation=None):
        if self.active is None or (reservation is not None and reservation != self.active):
            return
        run, token = self.active
        try:
            record = self.runs.verify(run, token)
            step = self.runs.next_step(run, token)
            self.runs.begin(run, token, step)
            self.step = step
            self.changed.emit()
            if self.active != (run, token):
                return
            done = self.runs.checkpoints(run)
            if step == "catalog":
                self.consult("catalog_file", {"file_name": Path(record["path"]).name}, self.catalog)
            elif step == "blender":
                self.start_blender(record, token)
            elif step == "budget":
                self.consult("assess_triangle_budget", {"report": done["blender"]["report"],
                             "triangle_budget": record["budget"]}, self.budget)
            elif step == "inspect":
                self.consult("inspect_report", {"report": done["blender"]["report"], "requirements": {
                    "require_uv": True, "require_materials": False, "require_rig": False,
                    "triangle_budget": record["budget"]}}, lambda value: {"findings": validated_findings(value)})
            elif step == "audit":
                findings = validated_findings(done["inspect"])
                self.consult("review_stage", {"attempt": 1, "findings": findings},
                             lambda value: self.audit(value, findings))
            else:
                self.finish(review_gate(done, record["budget"]))
        except (OSError, ValueError, KeyError, sqlite3.Error) as error:
            self.halt(str(error))

    def consult(self, action, fields, validate):
        reservation = self.active

        def accept(value):
            if self.bridge_reservation == reservation:
                self.bridge_reservation = None
            if self.active != reservation:
                return
            try:
                self.finish(validate(value))
            except (OSError, ValueError, sqlite3.Error) as error:
                self.halt(str(error))

        def failed(message):
            if self.bridge_reservation == reservation:
                self.bridge_reservation = None
            if self.active == reservation:
                self.halt(message)

        self.bridge_reservation = reservation
        if not self.bridge.call(action, fields, accept, failed=failed, quiet=True):
            self.bridge_reservation = None
            self.halt("Ponte do Agents indisponível para esta etapa.")

    @staticmethod
    def catalog(result):
        if (not isinstance(result, dict) or result.get("category") != "model"
                or type(result.get("needs_review")) is not bool):
            raise ValueError("Nexus não confirmou uma referência de modelo.")
        return {"category": "model", "needs_review": result["needs_review"]}

    @staticmethod
    def budget(result):
        keys = ("triangle_budget", "original_triangles", "evaluated_triangles",
                "evaluation_delta", "original_over_budget", "evaluated_over_budget")
        if not isinstance(result, dict) or any(key not in result or
                type(result[key]) not in (int, type(None)) for key in keys):
            raise ValueError("Orçamento fora do protocolo.")
        return {key: result[key] for key in keys}

    @staticmethod
    def audit(value, findings):
        if (not isinstance(value, dict) or value.get("findings") != findings
                or value.get("requires_human_approval") is not True
                or value.get("status") not in ("retry_proposed", "human_review")):
            raise ValueError("Auditoria incompatível.")
        return {"findings": findings, "status": value["status"], "requires_human_approval": True}

    def start_blender(self, record, token):
        executable = validate_blender_path(self.blender_path())
        if psutil.virtual_memory().available // 1048576 < MIN_FREE_MIB:
            raise ValueError("Sentinel bloqueou: 1.536 MiB de RAM livre são necessários para iniciar o Blender.")
        if not WORKER.is_file() or self.root.is_symlink():
            raise ValueError("Executor Blender local indisponível.")
        folder = self.root / f"{record['id']}-{token}"
        stage(record["path"], record["source_hash"], folder)
        self.job_folder = folder
        self.job_size = 0
        self.process.setWorkingDirectory(str(folder))
        self.process.start(str(executable), ["--background", "--factory-startup", "--offline-mode",
            "--disable-autoexec", "--python-exit-code", "1", "--python", str(WORKER), "--", str(folder),
            "organize" if record["organize"] else "inspect"])
        self.watch.start()
        self.timeout.start(90000)

    def monitor(self):
        try:
            if self.process.processId() and (
                    psutil.Process(self.process.processId()).memory_info().rss // 1048576 > MAX_PROCESS_MIB
                    or psutil.virtual_memory().available // 1048576 < 512):
                self.halt("Sentinel pausou o Blender por limite de RAM.")
        except psutil.NoSuchProcess:
            pass
        except psutil.Error:
            self.halt("Sentinel perdeu a medição do processo Blender.")

    def collect(self):
        self.job_size += self.process.readAllStandardOutput().size()
        if self.active and self.job_size > 2 * 1024 * 1024:
            self.halt("O log Blender excedeu o limite.")

    def blender_error(self, error):
        if error == QProcess.ProcessError.FailedToStart and self.step == "blender":
            self.halt("O Blender selecionado não pôde iniciar.")

    def blender_finished(self, code, status):
        self.watch.stop()
        self.timeout.stop()
        if self.step != "blender" or not self.active:
            return
        try:
            if code != 0 or status != QProcess.ExitStatus.NormalExit:
                raise ValueError("Blender interrompido. Confira a versão 5.3.0 e a referência GLB.")
            record = self.runs.verify(*self.active)
            report = read_result(self.job_folder, record["organize"])
            self.finish({"report": report, "directory": self.job_folder.name})
        except (OSError, ValueError, RecursionError, sqlite3.Error) as error:
            self.halt(str(error))

    def finish(self, output):
        run, token = self.active
        step = self.step
        self.runs.complete(run, token, step, output)
        self.step = None
        if step == "gate":
            self.active = None
            self.notice.emit(output["reason"] or "Inspeção disponível para revisão humana.")
        else:
            QTimer.singleShot(0, lambda: self.advance((run, token)))
        self.changed.emit()

    def halt(self, message, *, cancelled=False):
        reservation = self.active
        if not reservation:
            return
        self.active = self.step = None
        self.watch.stop()
        self.timeout.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
        if self.bridge_reservation == reservation and self.bridge.busy:
            self.bridge_reservation = None
            self.bridge.abort("Consulta interrompida pela fila do Studio.")
        try:
            self.runs.stop(*reservation, reason=message, cancelled=cancelled)
        except sqlite3.Error:
            message = "Não foi possível gravar a interrupção. A reserva expira automaticamente."
        self.notice.emit(message)
        self.changed.emit()

    def directory(self, run):
        result = self.runs.checkpoints(run).get("blender")
        if result and re.fullmatch(rf"{run}-[0-9a-f]{{32}}", result.get("directory", "")):
            folder = self.root / result["directory"]
            if folder.is_dir() and not folder.is_symlink():
                return folder
        raise ValueError("A inspeção ainda não tem um relatório ou cópia de trabalho.")

    def status(self, agent):
        if self.step and STEPS[self.step][0] == agent:
            return "Trabalhando"
        if self.active and agent == "coordenador":
            return "Acompanhando inspeção"
        return None

    def close(self):
        self.refresh.stop()
        self.halt("Studio foi fechado. Use Retomar para continuar dos checkpoints.")
        self.process.waitForFinished(1000)
