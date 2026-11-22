"""Controles para as ferramentas locais sem efeitos de escrita."""
import json

from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QHBoxLayout,
                               QLineEdit, QPlainTextEdit, QSpinBox)
from .pages import button, plain


def build_agent_tools(layout, bridge, settings, save):
    status = plain("Selecione um checkout confiável do Agents e seu Python local.")
    python = QLineEdit(settings.agents_python)
    python.setPlaceholderText("Executável Python")
    checkout = QLineEdit(settings.agents_checkout)
    checkout.setPlaceholderText("Pasta do Agents")

    def choose_interpreter():
        path, _ = QFileDialog.getOpenFileName(python, "Selecionar Python")
        if path:
            python.setText(path)

    def choose_checkout():
        path = QFileDialog.getExistingDirectory(checkout, "Selecionar checkout do Agents")
        if path:
            checkout.setText(path)

    for field, callback in ((python, choose_interpreter), (checkout, choose_checkout)):
        row = QHBoxLayout()
        row.addWidget(field, 1)
        row.addWidget(button("Procurar", callback))
        layout.addLayout(row)

    def connect():
        try:
            bridge.configure(python.text().strip(), checkout.text().strip())
        except (OSError, ValueError) as error:
            status.setText(str(error))

    layout.addWidget(button("Conectar Agents", connect))
    layout.addWidget(status)
    tools = QComboBox()
    for title, action in (("Atlas · plano", "plan_production"),
                          ("Nexus · catalogar nome de arquivo", "catalog_file"),
                          ("Argus e Aegis · inspecionar e auditar", "inspect_and_review"),
                          ("Vector · comparar orçamento de triângulos", "assess_triangle_budget"),
                          ("Atlas · interpretar com Ollama local", "interpret_instruction")):
        tools.addItem(title, action)
    layout.addWidget(tools)
    workflow = QComboBox()
    for title, value in (("Pacote de modelo", "model_package"), ("Pacote de imagem", "image_package"),
                         ("Pacote de áudio", "audio_package")):
        workflow.addItem(title, value)
    layout.addWidget(workflow)
    source = QPlainTextEdit()
    source.setMaximumHeight(105)
    layout.addWidget(source)
    model = QLineEdit()
    model.setPlaceholderText("Nome do modelo local já instalado no Ollama")
    layout.addWidget(model)
    requirements = QHBoxLayout()
    flags = {key: QCheckBox(title) for key, title in (("require_uv", "UV"), ("require_materials", "Materiais"),
                                                      ("require_rig", "Armadura"))}
    for checkbox in flags.values():
        requirements.addWidget(checkbox)
    budget = QSpinBox()
    budget.setRange(1, 1_000_000_000)
    budget.setValue(100_000)
    attempt = QSpinBox()
    attempt.setRange(1, 3)
    captions = {"budget": plain("Triângulos"), "attempt": plain("Tentativa")}
    for key, widget in (("budget", budget), ("attempt", attempt)):
        requirements.addWidget(captions[key])
        requirements.addWidget(widget)
    layout.addLayout(requirements)

    output = QPlainTextEdit()
    output.setReadOnly(True)
    output.setPlaceholderText("Resultado da ferramenta")
    output.setMinimumHeight(160)

    def invoke():
        try:
            action = tools.currentData()
            if action == "plan_production":
                fields = {"workflow": workflow.currentData()}
            elif action == "catalog_file":
                fields = {"file_name": source.toPlainText().strip()}
            elif action in ("inspect_and_review", "assess_triangle_budget"):
                raw = source.toPlainText()
                if len(raw.encode("utf-8")) > 60000:
                    raise ValueError("Resumo JSON acima do limite de 60 KB.")
                fields = {"report": json.loads(raw)}
                if action == "inspect_and_review":
                    fields.update(attempt=attempt.value(), requirements={
                        **{key: widget.isChecked() for key, widget in flags.items()}, "triangle_budget": budget.value()})
                else:
                    fields["triangle_budget"] = budget.value()
            else:
                fields = {"instruction": source.toPlainText(), "model": model.text().strip()}
            bridge.call(action, fields)
        except (ValueError, RecursionError) as error:
            status.setText(str(error))

    execute = button("Consultar ferramenta", invoke)
    layout.addWidget(execute)
    layout.addWidget(output)

    def update():
        action = tools.currentData()
        auditing = action == "inspect_and_review"
        geometry = auditing or action == "assess_triangle_budget"
        workflow.setVisible(action == "plan_production")
        source.setVisible(action != "plan_production")
        model.setVisible(action == "interpret_instruction")
        source.setPlaceholderText({
            "catalog_file": "Nome e extensão, sem caminho",
            "inspect_and_review": "Cole um objeto JSON com schema_version e summary do relatório Studio",
            "assess_triangle_budget": "Cole um objeto JSON com schema_version e summary do relatório Studio",
            "interpret_instruction": "Descreva o fluxo de produção para o modelo local",
        }.get(action, ""))
        for widget in (*flags.values(), attempt, captions["attempt"]):
            widget.setVisible(auditing)
        budget.setVisible(geometry)
        captions["budget"].setVisible(geometry)
        execute.setEnabled(bridge.connected and not bridge.busy)

    def show_result(action, value):
        output.setPlainText(json.dumps(value, ensure_ascii=False, indent=2))
        status.setText("Consulta concluída.")

    def notice(message):
        status.setText(message)
        if bridge.connected and message.startswith("Catálogo conferido"):
            save(bridge.python, bridge.checkout)

    tools.currentIndexChanged.connect(update)
    bridge.changed.connect(update)
    bridge.notice.connect(notice)
    bridge.result.connect(show_result)
    update()
