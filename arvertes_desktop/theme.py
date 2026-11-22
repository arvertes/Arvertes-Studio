DARK_THEME = """
QWidget { background: #181c24; color: #e3e8ef; font-size: 13px; }
QFrame#panel, QWidget#panel { background: #222833; border: 1px solid #343e4b; border-radius: 8px; }
QFrame#topbar { background: #202631; border-bottom: 1px solid #343e4b; }
QLabel { background: transparent; }
QLabel#heading { font-size: 23px; font-weight: bold; }
QLabel#brand { font-size: 19px; font-weight: bold; color: #72d6ca; }
QLabel#muted { color: #a1aebd; }
QLabel#networkTitle { font-size: 16px; font-weight: bold; }
QLabel#networkTag { color: #72d6ca; font-weight: bold; }
QCheckBox { spacing: 8px; }
QListWidget { background: #202631; border: 0; outline: none; padding: 5px; }
QListWidget::item { min-height: 34px; padding-left: 10px; border-radius: 5px; }
QListWidget::item:selected { background: #284640; color: #a0eee3; }
QListWidget::item:hover:!selected { background: #303946; }
QPushButton { background: #303b49; border: 1px solid #435364; padding: 8px 13px; border-radius: 5px; }
QPushButton:hover { background: #3d5061; }
QPushButton#primary { background: #27675f; border-color: #38847a; }
QPushButton:disabled { color: #8391a0; background: #292e38; }
QLineEdit { background: #121821; border: 1px solid #435364; border-radius: 5px; padding: 8px; }
QLineEdit:focus { border-color: #72d6ca; }
QTableWidget { background: #202631; border: 1px solid #343e4b; gridline-color: #343e4b; selection-background-color: #284640; }
QHeaderView::section { background: #303b49; color: #e3e8ef; padding: 8px; border: 0; border-bottom: 1px solid #435364; }
QComboBox, QPlainTextEdit { background: #121821; border: 1px solid #435364; border-radius: 5px; padding: 8px; }
QComboBox QAbstractItemView { background: #202631; selection-background-color: #284640; }
QScrollArea { border: 0; }
QSplitter::handle { background: #343e4b; width: 3px; }
"""
