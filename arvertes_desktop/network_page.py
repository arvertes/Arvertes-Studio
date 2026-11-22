"""Central de dispositivos: interface de planejamento, sem transporte USB."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)


def text(value, style=""):
    label = QLabel(value)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    if style:
        label.setObjectName(style)
    return label


def card():
    frame = QFrame()
    frame.setObjectName("panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(7)
    return frame, layout


def device(title, connection, state, work):
    frame, layout = card()
    layout.addWidget(text(title, "networkTitle"))
    layout.addWidget(text(connection, "muted"))
    layout.addWidget(text(state, "networkTag"))
    layout.addWidget(text(work))
    layout.addWidget(text("RAM · Bateria · Temperatura: —", "muted"))
    return frame


def build_network(layout):
    banner, banner_layout = card()
    banner_layout.addWidget(text("ARVERTES NETWORK  /  USB EXCLUSIVO", "networkTag"))
    banner_layout.addWidget(text(
        "Distribua trabalhos entre dispositivos autorizados, com Atlas na coordenação. "
        "A comunicação e a execução distribuída ainda não estão implementadas."
    ))
    layout.addWidget(banner)

    stats = QGridLayout()
    for index, (title, value) in enumerate((
        ("Central de produção", "Este computador"),
        ("Celulares conectados", "Não verificado"),
        ("Tarefas distribuídas", "Indisponível"),
    )):
        frame, frame_layout = card()
        frame_layout.addWidget(text(title, "muted"))
        frame_layout.addWidget(text(value, "networkTitle"))
        stats.addWidget(frame, 0, index)
        stats.setColumnStretch(index, 1)
    layout.addLayout(stats)

    header = QHBoxLayout()
    header.addWidget(text("Dispositivos", "networkTitle"), 1)
    example = QCheckBox("Mostrar exemplo")
    example.setToolTip("Exibe somente um cenário ilustrativo, sem conexão ou métricas reais.")
    header.addWidget(example)
    layout.addLayout(header)

    real_view, real_layout = card()
    real_layout.addWidget(text("Computador principal", "networkTitle"))
    real_layout.addWidget(text("Exibição local · monitoramento ainda indisponível", "muted"))
    real_layout.addWidget(text(
        "Nenhuma sessão USB pode ser verificada nesta versão. "
        "O pareamento com o aplicativo Android será desenvolvido separadamente."
    ))
    layout.addWidget(real_view)

    demo = QWidget()
    demo_layout = QGridLayout(demo)
    demo_layout.setContentsMargins(0, 0, 0, 0)
    notice = text("EXEMPLO ILUSTRATIVO — não representa aparelhos conectados", "networkTag")
    demo_layout.addWidget(notice, 0, 0, 1, 3)
    for index, spec in enumerate((
        ("Computador", "Local", "Exemplo", "Forge · geometria e Blender"),
        ("Celular A", "USB", "Exemplo", "Atlas · planejamento"),
        ("Celular B", "USB", "Exemplo", "Echo · áudio"),
    )):
        demo_layout.addWidget(device(*spec), 1, index)
        demo_layout.setColumnStretch(index, 1)
    demo.hide()
    example.toggled.connect(demo.setVisible)
    layout.addWidget(demo)

    policies, policies_layout = card()
    policies_layout.addWidget(text("Política de distribuição", "networkTitle"))
    for rule in (
        "Celulares: somente cabo USB de dados. Sem Wi-Fi, Bluetooth ou internet.",
        "Pareamento e autorização explícita do proprietário; processamento desligado por padrão.",
        "Preservar o uso cotidiano do aparelho; respeitar limites de RAM, bateria e temperatura.",
        "Uma tarefa pesada por nó inicialmente; Atlas deve verificar compatibilidade.",
        "Ao desconectar, devolver tarefas interrompidas à fila e recuperar checkpoints quando disponíveis.",
    ):
        policies_layout.addWidget(text("• " + rule))
    help_button = QPushButton("Como será a conexão")
    help_button.setCheckable(True)
    help_details = text(
        "Fluxo previsto: instalar o aplicativo Android, conectar por cabo de dados, "
        "autorizar o pareamento nos dois aparelhos e optar pelo compartilhamento. "
        "O transporte USB e a verificação de identidade ainda precisam ser implementados e testados.",
        "muted",
    )
    help_details.hide()
    help_button.toggled.connect(help_details.setVisible)
    policies_layout.addWidget(help_button)
    policies_layout.addWidget(help_details)
    layout.addWidget(policies)
    layout.addStretch()
