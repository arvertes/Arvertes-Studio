"""Escritório visual original do Arvertes, sem serviços, assets externos ou IA simulada."""
from shiboken6 import isValid

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPen, QFont, QPainter
from PySide6.QtWidgets import (
    QComboBox, QGraphicsItem, QGraphicsScene, QGraphicsView, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget,
)
from .roster import AGENTS, DEPARTMENTS
from .production_page import event_label, LABELS, NAMES
from .project_runs import FLOW, STEPS
from .office_preview import OfficePreview

PALETTE = {
    "Fundação": ("#3a5868", "#76d1cc"),
    "Visual": ("#59445f", "#d5a2ea"),
    "Movimento": ("#47596c", "#8ebaff"),
    "Áudio": ("#5c4b45", "#f1ba84"),
    "Qualidade": ("#415c54", "#9cdeb1"),
    "Convivência": ("#3c4d4e", "#b6d6a1"),
}


class OfficeView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setObjectName("officeMap")
        self.setMinimumHeight(410)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


def build_office(layout, navigate, bridge, production=None, auto=False):
    intro = QLabel("ARVERTES HQ  •  26 especialistas em cinco departamentos")
    intro.setObjectName("networkTag")
    layout.addWidget(intro)
    notice = QLabel("Selecione um personagem para acompanhar as consultas do Studio e a disponibilidade de suas ferramentas.")
    notice.setWordWrap(True)
    layout.addWidget(notice)
    preview = OfficePreview(auto)
    layout.addWidget(preview)
    fallback = QWidget()
    fallback_layout = QVBoxLayout(fallback)
    fallback_layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(fallback, 1)

    def switch_visual(active):
        fallback.setVisible(not active)
        layout.setStretchFactor(preview, int(active))

    preview.active_changed.connect(switch_visual)
    scene = QGraphicsScene(0, 0, 1060, 576)
    scene.setBackgroundBrush(QColor("#111d27"))

    def rect(x, y, w, h, color, outline=None):
        return scene.addRect(x, y, w, h,
                             QPen(QColor(outline)) if outline else QPen(Qt.PenStyle.NoPen),
                             QBrush(QColor(color)))

    def text(value, x, y, size=12, color="#edf2f8", bold=False):
        font = QFont("Segoe UI", size)
        font.setBold(bold)
        item = scene.addSimpleText(value, font)
        item.setBrush(QBrush(QColor(color)))
        item.setPos(x, y)
        return item

    seats, indicators = {}, {}
    by_id = {a.id: a for a in AGENTS}
    rooms = (*DEPARTMENTS, "Convivência")
    for index, name in enumerate(rooms):
        x, y = 12 + (index % 3) * 348, 14 + (index // 3) * 280
        floor, accent = PALETTE[name]
        rect(x, y, 340, 266, floor, "#60727e")
        rect(x, y, 340, 35, "#243340")
        text(name.upper(), x + 12, y + 7, 12, accent, True)
        # Linhas discretas do piso e tapete.
        for yy in range(y + 46, y + 257, 16):
            rect(x + 4, yy, 332, 1, "#303a48")
        rect(x + 7, y + 42, 326, 213, "#303d4d", "#647180")
        if name == "Convivência":
            rect(x + 35, y + 90, 115, 65, "#395c68", "#87a8b0")
            rect(x + 43, y + 98, 99, 12, "#5a8190")
            rect(x + 184, y + 90, 115, 65, "#395c68", "#87a8b0")
            rect(x + 192, y + 98, 99, 12, "#5a8190")
            rect(x + 124, y + 177, 91, 31, "#9b795c", "#c6ab82")
            text("Área de descanso", x + 93, y + 51, 12, accent)
            text("Espaço decorativo", x + 96, y + 223, 10, "#c7d3dd")
            continue
        members = [a for a in AGENTS if a.department == name]
        for seat, agent in enumerate(members):
            sx = x + 14 + (seat % 3) * 106
            sy = y + 46 + (seat // 3) * 104
            body = "#55b9ac" if agent.id == "seguranca" else accent
            # Formas em grade, desenhadas no próprio Qt: mesa, monitor e avatar.
            items = [
                rect(sx, sy, 100, 99, "#26313e", "#56697b"),
                rect(sx + 15, sy + 13, 70, 30, "#997d63", "#bda68b"),
                rect(sx + 27, sy + 6, 46, 23, "#18222a", "#71929d"),
                rect(sx + 31, sy + 10, 38, 15, "#2a5260"),
                rect(sx + 18, sy + 32, 19, 5, "#d5c1a6"),
                rect(sx + 36, sy + 46, 28, 22, body),
                rect(sx + 40, sy + 36, 20, 19, "#d8b393"),
                rect(sx + 38, sy + 34, 24, 7, "#242a35"),
                rect(sx + 44, sy + 45, 3, 3, "#28313a"),
                rect(sx + 53, sy + 45, 3, 3, "#28313a"),
                rect(sx + 38, sy + 67, 9, 6, "#171f2d"),
                rect(sx + 53, sy + 67, 9, 6, "#171f2d"),
                rect(sx + 85, sy + 7, 7, 7, "#67d8af" if agent.id == "seguranca" else "#8a98a6"),
            ]
            indicators[agent.id] = items[-1]
            title = text(agent.name, sx, sy + 76, 9, "#edf2f8", True)
            title.setX(sx + (100 - title.boundingRect().width()) / 2)
            items.append(title)
            group = scene.createItemGroup(items)
            group.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
            group.setData(0, agent.id)
            group.setToolTip(agent.name + " — " + agent.role)
            seats[agent.id] = group

    view = OfficeView(scene)
    fallback_layout.addWidget(view, 1)
    controls = QHBoxLayout()
    controls.addWidget(QLabel("Agente"))
    select = QComboBox()
    select.setObjectName("officeAgent")
    for agent in AGENTS:
        select.addItem(agent.name, agent.id)
    controls.addWidget(select, 1)
    team = QPushButton("Ver equipe")
    team.clicked.connect(lambda: navigate("agents"))
    controls.addWidget(team)
    guard = QPushButton("Abrir Sentinel")
    guard.clicked.connect(lambda: navigate("sentinel"))
    controls.addWidget(guard)
    fallback_layout.addLayout(controls)

    detail = QLabel()
    detail.setTextFormat(Qt.TextFormat.PlainText)
    detail.setObjectName("officeDetail")
    detail.setWordWrap(True)
    fallback_layout.addWidget(detail)
    progress = QLabel("Nenhuma inspeção ativa")
    progress.setWordWrap(True)
    fallback_layout.addWidget(progress)

    statuses, history = {}, {}

    def show_agent():
        agent = by_id[select.currentData()]
        status = statuses.get(agent.id, bridge.status(agent.id))
        recent = "\n".join(history.get(agent.id, [])[:3])
        detail.setText(f"{agent.name}  •  {agent.role}  •  {agent.department}\n{status}" +
                       (f"\n{recent}" if recent else ""))
        if not seats[agent.id].isSelected():
            scene.clearSelection()
            seats[agent.id].setSelected(True)

    def choose_from_scene():
        if not isValid(scene) or not isValid(select):
            return
        selected = scene.selectedItems()
        if selected:
            key = selected[0].data(0)
            index = select.findData(key)
            if index >= 0:
                select.setCurrentIndex(index)

    def update_status():
        colors = {"Trabalhando": "#f5ce66", "Disponível": "#67d8af", "Consulta concluída": "#67d8af",
                  "Consulta interrompida": "#f08a82", "Regras locais · monitoramento": "#67d8af"}
        statuses.update({key: (production.status(key) if production else None) or bridge.status(key)
                         for key in by_id})
        history.clear()
        if production:
            for event in production.runs.office_history():
                for key in dict.fromkeys((event["sender"], event["recipient"])):
                    if key in by_id and len(history.setdefault(key, [])) < 5:
                        history[key].append(event_label(event))
        for key, status in statuses.items():
            indicators[key].setBrush(QBrush(QColor(colors.get(status, "#8a98a6"))))
            seats[key].setToolTip(by_id[key].name + " · " + status)
        flow = ""
        if production and production.active:
            started = production.active[0]
            done = len(production.runs.checkpoints(started))
            step = production.step
            partner = {"budget": "Argus", "materials": "Argus", "audit": "Argus", "gate": "Aegis"}.get(step)
            team = NAMES[STEPS[step][0]] if step in STEPS else "Atlas"
            meeting = f" · colaboração {partner} ↔ {team}" if partner else f" · {team}"
            flow = f"{done}/{len(FLOW)} etapas · {LABELS.get(step, 'Preparando')}{meeting}"
        elif production and production.delivery_job:
            flow = "Bridge · gerando FBX aprovado"
        progress.setText(flow or "Nenhuma inspeção ativa")
        preview.update_states(statuses, history, flow)
        show_agent()

    bridge.changed.connect(update_status)
    if production:
        production.changed.connect(update_status)
    select.currentIndexChanged.connect(show_agent)
    scene.selectionChanged.connect(choose_from_scene)
    update_status()
    return preview
