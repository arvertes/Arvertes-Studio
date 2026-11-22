"""Telas de trabalho local. Nenhuma tarefa é executada nesta versão."""
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QPlainTextEdit, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView,
)
from .roster import AGENTS, DEPARTMENTS, filter_agents


def plain(text):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    return widget


def button(text, callback):
    widget = QPushButton(text)
    widget.clicked.connect(callback)
    return widget


def table(headers):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.verticalHeader().hide()
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return widget


def rows(widget, values):
    widget.setRowCount(len(values))
    for i, row in enumerate(values):
        for j, value in enumerate(row):
            widget.setItem(i, j, QTableWidgetItem(str(value)))


def build_agents(layout):
    layout.addWidget(plain("26 especialistas · 5 departamentos · Sentinel local; demais agentes não conectados"))
    filters = QHBoxLayout()
    department = QComboBox()
    department.addItem("Todos os departamentos", "")
    for name in DEPARTMENTS:
        department.addItem(name, name)
    search = QLineEdit()
    search.setPlaceholderText("Buscar nome ou especialidade...")
    filters.addWidget(department)
    filters.addWidget(search, 1)
    layout.addLayout(filters)
    view = table(["Nome", "Especialidade", "Departamento", "Estado"])
    layout.addWidget(view, 1)

    def refresh():
        rows(view, [(a.name, a.role, a.department, "Regras locais" if a.id == "seguranca" else "Não conectado")
                    for a in filter_agents(department.currentData(), search.text())])
    department.currentIndexChanged.connect(refresh)
    search.textChanged.connect(refresh)
    refresh()


class WorkspacePages:
    def __init__(self, parent, store):
        self.parent = parent
        self.store = store

    def protect(self, operation):
        try:
            operation()
        except (OSError, ValueError, sqlite3.Error) as error:
            QMessageBox.warning(self.parent, "Operação não concluída", str(error))

    def projects_page(self, layout):
        layout.addWidget(plain("Projetos locais — sem modificar arquivos de origem."))
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("Nome do novo projeto")
        row = QHBoxLayout()
        row.addWidget(self.project_name, 1)
        row.addWidget(button("Criar projeto", lambda: self.protect(self.create)))
        layout.addLayout(row)
        self.project_list = QListWidget()
        layout.addWidget(self.project_list, 1)

    def library_page(self, layout):
        layout.addWidget(plain("Registre referências a arquivos existentes. Não são movidos, copiados ou abertos."))
        self.library_project = QComboBox()
        self.library_project.currentIndexChanged.connect(self.refresh_library)
        layout.addWidget(self.library_project)
        self.add_file = button("Adicionar arquivos", lambda: self.protect(self.add_files))
        layout.addWidget(self.add_file)
        self.library_table = table(["Nome", "Localização"])
        layout.addWidget(self.library_table, 1)

    def tasks_page(self, layout):
        layout.addWidget(plain("Fila persistente de rascunhos. A execução pelos agentes ainda não está disponível."))
        self.task_project = QComboBox()
        self.task_project.currentIndexChanged.connect(self.refresh_tasks)
        layout.addWidget(self.task_project)
        self.task_title = QLineEdit()
        self.task_title.setPlaceholderText("Título da tarefa")
        self.instructions = QPlainTextEdit()
        self.instructions.setPlaceholderText("Descreva o resultado desejado, referências e requisitos.")
        self.instructions.setMaximumHeight(110)
        self.task_add = button("Adicionar à fila", lambda: self.protect(self.create_task))
        layout.addWidget(self.task_title)
        layout.addWidget(self.instructions)
        layout.addWidget(self.task_add)
        self.task_table = table(["Título", "Instruções", "Estado"])
        layout.addWidget(self.task_table, 1)
        actions = QHBoxLayout()
        for text, action in (
            ("Subir", lambda: self.reorder(-1)),
            ("Descer", lambda: self.reorder(1)),
            ("Cancelar rascunho", self.cancel),
        ):
            actions.addWidget(button(text, lambda checked=False, fn=action: self.protect(fn)))
        layout.addLayout(actions)

    def refresh(self):
        projects = self.store.projects()
        self.project_list.clear()
        for project in projects:
            self.project_list.addItem(project["name"])
        for combo in (self.library_project, self.task_project):
            previous = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for project in projects:
                combo.addItem(project["name"], project["id"])
            index = combo.findData(previous)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.blockSignals(False)
        self.refresh_library()
        self.refresh_tasks()

    def create(self):
        self.store.create_project(self.project_name.text())
        self.project_name.clear()
        self.refresh()

    def refresh_library(self):
        pid = self.library_project.currentData()
        self.add_file.setEnabled(pid is not None)
        data = self.store.assets(pid) if pid is not None else []
        rows(self.library_table, [(Path(row["path"]).name, row["path"]) for row in data])

    def add_files(self):
        pid = self.library_project.currentData()
        if pid is None:
            return
        files, _ = QFileDialog.getOpenFileNames(self.parent, "Registrar arquivos")
        errors = []
        for path in files:
            try:
                self.store.add_reference(pid, path)
            except (OSError, ValueError, sqlite3.Error) as error:
                errors.append(f"{Path(path).name}: {error}")
        self.refresh_library()
        if errors:
            QMessageBox.warning(self.parent, "Alguns arquivos não foram registrados", "\n".join(errors))

    def refresh_tasks(self):
        pid = self.task_project.currentData()
        self.task_add.setEnabled(pid is not None)
        self.task_rows = self.store.tasks(pid) if pid is not None else []
        rows(self.task_table, [(r["title"], r["instruction"],
             "Rascunho" if r["status"] == "draft" else "Cancelado") for r in self.task_rows])

    def create_task(self):
        pid = self.task_project.currentData()
        if pid is None:
            return
        self.store.add_task(pid, self.task_title.text(), self.instructions.toPlainText())
        self.task_title.clear()
        self.instructions.clear()
        self.refresh_tasks()

    def selected_task(self):
        row = self.task_table.currentRow()
        if 0 <= row < len(self.task_rows):
            return self.task_rows[row]["id"]
        return None

    def reorder(self, direction):
        task_id = self.selected_task()
        if task_id is not None:
            self.store.move_task(task_id, direction)
            self.refresh_tasks()
            for i, row in enumerate(self.task_rows):
                if row["id"] == task_id:
                    self.task_table.selectRow(i)
                    break

    def cancel(self):
        task_id = self.selected_task()
        if task_id is not None:
            self.store.cancel_task(task_id)
            self.refresh_tasks()
