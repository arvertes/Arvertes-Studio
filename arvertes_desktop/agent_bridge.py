"""Ponte local para uma instalação do Agents selecionada pelo operador."""
import json
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from .network import limits_ok
from .roster import AGENTS

MAX_REQUEST = 65536
MAX_RESPONSE = 131072
BOOTSTRAP = ("import sys; sys.path.insert(0, sys.argv[1]); "
             "from arvertes_agents.__main__ import main; sys.exit(main())")
ACTIONS = {
    "list_team": (),
    "delegate_inspection": ("coordenador",),
    "inspect_report": ("inspetor",),
    "review_stage": ("auditor",),
    "catalog_file": ("catalogador",),
    "plan_production": ("coordenador",),
    "interpret_instruction": ("coordenador",),
    "inspect_and_review": ("inspetor", "auditor"),
    "assess_triangle_budget": ("otimizador",),
    "recommend_device": ("coordenador",),
}


class AgentBridge(QObject):
    changed = Signal()
    notice = Signal(str)
    result = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.python = self.checkout = ""
        self.team = {}
        self.latest = {}
        self.operation = None
        self.process = QProcess(self)
        inherited = QProcessEnvironment.systemEnvironment()
        environment = QProcessEnvironment()
        for key in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG"):
            if inherited.contains(key):
                environment.insert(key, inherited.value(key))
        self.process.setProcessEnvironment(environment)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_error)
        self.process.started.connect(self.send)
        self.process.finished.connect(self.finish)
        self.process.errorOccurred.connect(self.error)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.abort("Tempo limite do Agents."))
        self.output = bytearray()
        self.error_size = 0
        self.failure = ""
        self.request_bytes = b""
        self.callback = self.failure_callback = None
        self.quiet = False

    @property
    def busy(self):
        return self.operation is not None

    @property
    def connected(self):
        return bool(self.team)

    def status(self, identifier):
        if identifier in ACTIONS.get(self.operation, ()):
            return "Trabalhando"
        if identifier == "seguranca":
            return "Regras locais · monitoramento"
        if identifier not in self.team:
            return "Não conectado"
        return self.latest.get(identifier, "Disponível" if self.team[identifier] == "rules"
                               else "Ferramenta em preparação")

    def configure(self, python, checkout):
        if self.busy:
            raise ValueError("Aguarde o fim da operação atual.")
        interpreter, root = Path(python), Path(checkout)
        if (not interpreter.is_absolute() or not interpreter.is_file()
                or interpreter.name.lower() not in {"python", "python3", "python.exe", "python3.exe"}):
            raise ValueError("Selecione o executável Python de uma instalação confiável.")
        if not root.is_absolute() or not (root / "arvertes_agents" / "__main__.py").is_file():
            raise ValueError("Selecione a pasta do checkout autorizado do Agents.")
        self.python, self.checkout = str(interpreter), str(root.resolve())
        self.team = {}
        self.latest.clear()
        self.call("list_team", {}, self.load_team)

    def call(self, action, fields, callback=None, *, failed=None, quiet=False):
        if action not in ACTIONS or (action != "list_team" and not self.connected):
            self.notice.emit("Sentinel bloqueou: ferramenta sem conexão ou fora do contrato.")
            return False
        if self.busy:
            self.notice.emit("Aguarde o fim da operação atual.")
            return False
        request = (json.dumps({"version": 1, **fields, "action": action}, allow_nan=False) + "\n").encode()
        if len(request) > MAX_REQUEST:
            self.notice.emit("A entrada excede o limite de 64 KiB.")
            return False
        self.request_bytes = request
        self.failure_callback, self.quiet = failed, quiet
        self.operation, self.callback = action, callback
        self.output.clear()
        self.error_size = 0
        self.failure = ""
        self.process.setWorkingDirectory(self.checkout)
        self.process.start(self.python, ["-I", "-B", "-c", BOOTSTRAP, self.checkout])
        self.timer.start(95000 if action == "interpret_instruction" else 12000)
        self.changed.emit()
        return True

    def send(self):
        self.process.write(self.request_bytes)
        self.process.closeWriteChannel()

    def read_output(self):
        self.output.extend(bytes(self.process.readAllStandardOutput()))
        if len(self.output) > MAX_RESPONSE:
            self.abort("Resposta do Agents acima do limite.")

    def read_error(self):
        self.error_size += self.process.readAllStandardError().size()
        if self.error_size > MAX_RESPONSE:
            self.abort("Saída de diagnóstico acima do limite.")

    def abort(self, message):
        if not self.failure:
            self.failure = message
        self.process.kill()

    def error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.failure = "Não foi possível iniciar o Python selecionado."
            self.finish(1, QProcess.ExitStatus.CrashExit)

    def finish(self, code, status):
        self.timer.stop()
        self.read_output()
        self.read_error()
        action, callback, failed, quiet = self.operation, self.callback, self.failure_callback, self.quiet
        if action is None:
            return
        self.operation = self.callback = self.failure_callback = None
        self.request_bytes = b""
        completed = False
        try:
            if self.failure:
                raise ValueError(self.failure)
            response = json.loads(self.output)
            if (code != 0 or status != QProcess.ExitStatus.NormalExit or not isinstance(response, dict)
                    or type(response.get("version")) is not int or response["version"] != 1
                    or response.get("ok") is not True or "result" not in response):
                raise ValueError("Agents recusou a operação. Confira a entrada e a revisão do checkout.")
            if callback:
                callback(response["result"])
            if not quiet and action not in ("list_team", "recommend_device"):
                self.result.emit(action, response["result"])
            completed = True
        except (UnicodeError, json.JSONDecodeError, RecursionError):
            message = "Agents retornou uma resposta fora do protocolo."
            self.notice.emit(message)
            if failed:
                failed(message)
        except (ValueError, OSError) as error:
            self.notice.emit(str(error))
            if failed:
                failed(str(error))
        finally:
            for identifier in ACTIONS.get(action, ()):
                self.latest[identifier] = "Consulta concluída" if completed else "Consulta interrompida"
            self.output.clear()
            self.changed.emit()

    def load_team(self, result):
        expected = {agent.id: (agent.name, agent.role, agent.department) for agent in AGENTS}
        team = {}
        if not isinstance(result, list) or len(result) != len(expected):
            raise ValueError("Catálogo Agents incompatível. Atualize o checkout autorizado.")
        for profile in result:
            if not isinstance(profile, dict):
                raise ValueError("Catálogo Agents inválido.")
            key = profile.get("id")
            metadata = tuple(profile.get(field) for field in ("name", "role", "department"))
            if (not isinstance(key, str) or key in team or expected.get(key) != metadata
                    or profile.get("status") not in ("rules", "planned")):
                raise ValueError("O catálogo Agents diverge dos 26 perfis do Studio.")
            team[key] = profile["status"]
        self.team = team
        self.notice.emit("Catálogo conferido · 26 perfis conectados.")

    def recommend_probe(self, hub):
        nodes = []
        candidates = set()
        for device, _, session, probe in hub.snapshot():
            if not session:
                continue
            metrics = session["metrics"]
            nodes.append({"id": device, "kind": "mobile", "transport": session["transport"],
                          "authorized": True, "enabled": session["consent"],
                          "busy": probe.get("state") in ("queued", "sent"),
                          "limits_ok": limits_ok(metrics),
                          "available_ram_mib": metrics["ram_available"] or 0,
                          "capabilities": ["session_probe"]})
            candidates.add(device)

        def recommend(result):
            if not isinstance(result, dict):
                raise ValueError("Resposta de seleção inválida.")
            if result.get("status") == "waiting":
                self.notice.emit("Atlas aguarda um aparelho autenticado e disponível para diagnóstico.")
                return
            selected = result.get("device_id")
            if result.get("status") != "recommended" or not isinstance(selected, str) or selected not in candidates:
                raise ValueError("Sentinel bloqueou: Atlas indicou uma sessão desconhecida.")
            hub.send_probe(selected)
            self.notice.emit("Atlas selecionou uma sessão. Diagnóstico enfileirado.")

        self.call("recommend_device", {"capability": "session_probe", "required_ram_mib": 512,
                                       "devices": nodes}, recommend)

    def close(self):
        if self.busy:
            self.callback = self.failure_callback = None
            self.abort("Operação encerrada pelo Studio.")
            self.process.waitForFinished(1000)
