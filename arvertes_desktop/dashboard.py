"""Painel inicial: contagens reais do workspace, sem simular produção."""
import sqlite3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


def label(value, style=""):
    widget = QLabel(str(value))
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setObjectName(style)
    return widget


def card(name="panel"):
    frame = QFrame()
    frame.setObjectName(name)
    box = QVBoxLayout(frame)
    box.setContentsMargins(18, 16, 18, 16)
    box.setSpacing(8)
    return frame, box


def action(text, navigate, key, *, primary=False, enabled=True):
    button = QPushButton(text)
    if primary:
        button.setObjectName("primary")
    button.setEnabled(enabled)
    button.clicked.connect(lambda checked=False: navigate(key))
    return button


def build_dashboard(layout, workspace, navigate):
    hero, hb = card("hero")
    hb.addWidget(label("WORKSPACE   /   VISÃO GERAL", "eyebrow"))
    hb.addWidget(label("Sua central de criação", "heroTitle"))
    hb.addWidget(label("Organize projetos, prepare ativos e planeje a produção em um só lugar.", "muted"))
    actions = QHBoxLayout()
    actions.addWidget(action("Abrir projetos", navigate, "projects", primary=True, enabled=workspace is not None))
    actions.addWidget(action("Fila de produção", navigate, "tasks", enabled=workspace is not None))
    actions.addStretch()
    hb.addLayout(actions)
    layout.addWidget(hero)

    grid = QGridLayout()
    grid.setSpacing(10)
    metrics = []
    for index, (title, description) in enumerate((
        ("PROJETOS", "Espaços de trabalho locais"),
        ("REFERÊNCIAS", "Arquivos registrados"),
        ("RASCUNHOS", "Tarefas aguardando execução"),
    )):
        frame, box = card()
        box.addWidget(label(title, "eyebrow"))
        value = label("—", "metric")
        metrics.append(value)
        box.addWidget(value)
        box.addWidget(label(description, "muted"))
        grid.addWidget(frame, 0, index)
        grid.setColumnStretch(index, 1)
    layout.addLayout(grid)

    row = QHBoxLayout()
    row.setSpacing(10)
    production, pb = card()
    pb.addWidget(label("Produção", "networkTitle"))
    pb.addWidget(label("Planejamento ativo · execução indisponível", "muted"))
    recent = label("Nenhum rascunho registrado.")
    pb.addWidget(recent)
    pb.addStretch()
    pb.addWidget(action("Gerenciar biblioteca", navigate, "library", enabled=workspace is not None))
    pb.addWidget(action("Ver tarefas", navigate, "tasks", enabled=workspace is not None))
    row.addWidget(production, 3)

    team, tb = card()
    tb.addWidget(label("Equipe & infraestrutura", "networkTitle"))
    tb.addWidget(label("26 especialistas · 5 departamentos", "muted"))
    tb.addWidget(label("ATLAS   /   Planejamento", "eyebrow"))
    tb.addWidget(label("Agentes de produção ainda não conectados.", "muted"))
    tb.addWidget(action("Abrir escritório", navigate, "office", primary=True))
    tb.addWidget(action("Explorar agentes", navigate, "agents"))
    tb.addWidget(action("Dispositivos · USB / Wi-Fi", navigate, "network"))
    tb.addStretch()
    row.addWidget(team, 2)
    layout.addLayout(row)

    security, sb = card("security")
    sb.addWidget(label("SENTINEL   /   SEGURANÇA", "eyebrow"))
    sb.addWidget(label("Produção bloqueada até validação", "networkTitle"))
    sb.addWidget(label("Avaliação local de evidências disponível. Nenhuma autorização automática.", "muted"))
    security_row = QHBoxLayout()
    security_row.addWidget(action("Revisar evidências", navigate, "sentinel"))
    security_row.addWidget(action("Configurar Blender", navigate, "settings"))
    security_row.addStretch()
    sb.addLayout(security_row)
    layout.addWidget(security)
    layout.addStretch()

    def refresh():
        if workspace is None:
            recent.setText("Workspace indisponível.")
            return
        try:
            counts, drafts = workspace.dashboard_summary()
            for widget, count in zip(metrics, counts):
                widget.setText(str(count))
            recent.setText("\n".join(f"{project[:45]}  /  {title[:70]}" for project, title in drafts)
                           or "Nenhum rascunho registrado. Crie uma tarefa para começar.")
        except sqlite3.Error:
            for widget in metrics:
                widget.setText("—")
            recent.setText("Não foi possível consultar o workspace.")
    refresh()
    return refresh
