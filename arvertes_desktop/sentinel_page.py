"""Central local de evidências. Não autentica alegações nem libera operações."""
import json
from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout
from .sentinel import evaluate_release, REQUIRED

SCOPES = {"desktop_diagnostic": "Windows — diagnóstico",
          "android_diagnostic": "Android — diagnóstico",
          "usb_processing": "USB — processamento",
          "wifi_processing": "Wi-Fi local — processamento"}
LABELS = {"missing": "ausente", "stale": "outra revisão", "fail": "falha", "pending": "pendente"}


def current_revision():
    try:
        value = Path(__file__).with_name("build_revision.txt").read_text(encoding="ascii").strip()
        if len(value) == 40 and all(c in "0123456789abcdef" for c in value):
            return value
    except (OSError, UnicodeError):
        pass
    return ""


def build_sentinel(layout, hub=None, bridge=None):
    panel = QFrame()
    panel.setObjectName("panel")
    box = QVBoxLayout(panel)

    def label(value):
        item = QLabel(value)
        item.setTextFormat(Qt.TextFormat.PlainText)
        item.setWordWrap(True)
        box.addWidget(item)
        return item

    label("SENTINEL — segurança e validação independente")
    label("Revisão do pacote: " + (current_revision() or "não identificada (código-fonte)"))
    label("Nenhuma instalação ou execução é autorizada por este painel. Evidências coladas são declarações não autenticadas.")
    runtime = label("Monitoramento de sessões locais em espera.")
    if hub is not None:
        timer = QTimer(panel)
        timer.timeout.connect(lambda: runtime.setText(hub.notice) if hub.notice else None)
        timer.start(2000)
    if bridge is not None:
        def agent_notice(message):
            if message.startswith("Sentinel bloqueou:"):
                if hub is not None:
                    hub.alert(message)
                runtime.setText(message)
        bridge.notice.connect(agent_notice)
    scope = QComboBox()
    for key, title in SCOPES.items():
        scope.addItem(title, key)
    box.addWidget(scope)
    commit = QLineEdit(current_revision())
    commit.setMaxLength(40)
    commit.setPlaceholderText("SHA completo da revisão que será avaliada")
    box.addWidget(commit)
    label("Evidências JSON: lista de objetos check, commit, status e reference. Use [] para nenhuma evidência.")
    evidence = QPlainTextEdit("[]")
    evidence.setMaximumHeight(170)
    box.addWidget(evidence)
    feedback = label("BLOQUEADO — faltam evidências verificadas.")
    feedback.setObjectName("sentinelFeedback")
    detail = label("")
    def reset():
        feedback.setText("BLOQUEADO — avaliação pendente.")
        detail.setText("Verificações exigidas: " + ", ".join(REQUIRED[scope.currentData()]))

    def evaluate():
        try:
            raw = evidence.toPlainText()
            if len(raw) > 65536:
                raise ValueError("Evidências excedem o limite.")
            result = evaluate_release(scope.currentData(), commit.text().strip(), json.loads(raw))
            feedback.setText("BLOQUEADO — evidências insuficientes." if result["status"] == "blocked"
                             else "REVISÃO HUMANA NECESSÁRIA — nenhuma autorização concedida.")
            detail.setText("\n".join(f'{item["check"]}: {LABELS[item["reason"]]}' for item in result["blockers"])
                           or "Todas as verificações foram declaradas como concluídas; autenticidade não verificada.")
        except (ValueError, RecursionError) as error:
            feedback.setText("BLOQUEADO — dados inválidos.")
            detail.setText(str(error))
    for control in (scope.currentIndexChanged, commit.textChanged, evidence.textChanged):
        control.connect(reset)
    button = QPushButton("Avaliar evidências")
    button.clicked.connect(evaluate)
    box.addWidget(button)
    reset()
    layout.addWidget(panel)
    layout.addStretch()
