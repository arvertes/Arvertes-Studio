"""Escritório visual original do Arvertes, sem serviços, assets externos ou IA simulada."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPen, QFont, QPainter
from PySide6.QtWidgets import (
    QComboBox, QGraphicsItem, QGraphicsScene, QGraphicsView, QHBoxLayout,
    QLabel, QPushButton,
)
from .roster import AGENTS, DEPARTMENTS

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


def build_office(layout, navigate):
    intro = QLabel("ARVERTES HQ  •  26 especialistas em cinco departamentos")
    intro.setObjectName("networkTag")
    layout.addWidget(intro)
    notice = QLabel("Mapa interativo de planejamento. As posições são ilustrativas; não há tarefas executadas nem agentes remotos conectados.")
    notice.setWordWrap(True)
    layout.addWidget(notice)
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

    seats = {}
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
            title = text(agent.name, sx, sy + 76, 9, "#edf2f8", True)
            title.setX(sx + (100 - title.boundingRect().width()) / 2)
            items.append(title)
            group = scene.createItemGroup(items)
            group.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
            group.setData(0, agent.id)
            group.setToolTip(agent.name + " — " + agent.role)
            seats[agent.id] = group

    view = OfficeView(scene)
    layout.addWidget(view, 1)
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
    layout.addLayout(controls)

    detail = QLabel()
    detail.setTextFormat(Qt.TextFormat.PlainText)
    detail.setObjectName("officeDetail")
    detail.setWordWrap(True)
    layout.addWidget(detail)

    def show_agent():
        agent = by_id[select.currentData()]
        status = ("Avaliação local disponível; nenhuma autorização automática."
                  if agent.id == "seguranca" else "Perfil cadastrado; não conectado à execução.")
        detail.setText(f"{agent.name}  •  {agent.role}  •  {agent.department}\n{status}")
        if not seats[agent.id].isSelected():
            scene.clearSelection()
            seats[agent.id].setSelected(True)

    def choose_from_scene():
        selected = scene.selectedItems()
        if selected:
            key = selected[0].data(0)
            index = select.findData(key)
            if index >= 0:
                select.setCurrentIndex(index)

    select.currentIndexChanged.connect(show_agent)
    scene.selectionChanged.connect(choose_from_scene)
    show_agent()
