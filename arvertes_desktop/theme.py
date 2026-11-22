DARK_THEME = """
QWidget { background: #10151e; color: #edf2f8; font-family: "Segoe UI"; font-size: 13px; }
QFrame#panel, QWidget#panel { background: #1a2330; border: 1px solid #2d3a4b; border-radius: 12px; }
QFrame#hero { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #203d46,stop:1 #1b2638); border: 1px solid #3b646b; border-radius: 12px; }
QFrame#security { background: #192c31; border: 1px solid #36545a; border-radius: 12px; }
QFrame#topbar { background: #141c27; border-bottom: 1px solid #2c3949; }
QLabel { background: transparent; }
QLabel#heading { font-size: 25px; font-weight: bold; color: #f2f6fb; }
QLabel#heroTitle { font-size: 29px; font-weight: bold; }
QLabel#brand { font-size: 20px; font-weight: bold; color: #79e4d2; }
QLabel#muted { color: #a9bbcf; }
QLabel#eyebrow { color: #90c6c8; font-weight: bold; font-size: 11px; }
QLabel#metric { font-size: 29px; font-weight: bold; color: #eef9ff; }
QLabel#networkTitle { font-size: 17px; font-weight: bold; }
QLabel#networkTag { color: #79e4d2; font-weight: bold; }
QLabel#sentinelFeedback { color: #ecc48b; font-weight: bold; }
QCheckBox { spacing: 8px; }
QListWidget#navigation { background: #141c27; border: 0; border-right: 1px solid #293746; outline: none; padding: 8px; }
QListWidget { background: #19222e; border: 1px solid #304052; border-radius: 8px; outline: none; padding: 4px; }
QListWidget::item { min-height: 29px; padding: 3px 9px; border-radius: 6px; }
QListWidget::item:selected { background: #214e4b; color: #b9fff2; font-weight: bold; }
QListWidget::item:hover:!selected { background: #243445; }
QPushButton { background: #273648; border: 1px solid #3d5065; padding: 9px 13px; border-radius: 7px; font-weight: 500; }
QPushButton:hover { background: #354b61; border-color: #5d7892; }
QPushButton#primary { background: #24786f; border-color: #49a99c; }
QPushButton#primary:hover { background: #308d82; }
QPushButton:disabled { color: #8291a2; background: #242b34; }
QLineEdit, QComboBox, QPlainTextEdit { background: #0e1722; border: 1px solid #3b4c60; border-radius: 7px; padding: 8px; }
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QPushButton:focus { border: 1px solid #79e4d2; }
QTableWidget { background: #19222e; border: 1px solid #304052; gridline-color: #2c3847; selection-background-color: #214e4b; border-radius: 8px; }
QHeaderView::section { background: #253347; color: #edf2f8; padding: 9px; border: 0; border-bottom: 1px solid #3d5065; font-weight: bold; }
QComboBox QAbstractItemView { background: #19222e; selection-background-color: #214e4b; }
QScrollArea { border: 0; }
QScrollBar:vertical { background: #141c27; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #43566a; min-height: 24px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QStatusBar { background: #141c27; color: #a9bbcf; }
"""
