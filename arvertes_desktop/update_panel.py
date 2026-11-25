from threading import Event

from PySide6.QtCore import QObject, QThreadPool, Signal
from PySide6.QtWidgets import QFileDialog

from .pages import button, plain
from .update_check import verify


class UpdateCheck(QObject):
    done = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.cancelled = Event()

    def check(self, archive, manifest):
        self.cancelled.clear()

        def work():
            try:
                result = verify(archive, manifest, self.cancelled.is_set)
            except (OSError, ValueError, RecursionError) as error:
                result = str(error)
            self.done.emit(result)

        QThreadPool.globalInstance().start(work)


def build_update_panel(layout, owner):
    checker = UpdateCheck(owner)
    owner.update_check = checker
    report = plain("Use o manifesto publicado no mesmo workflow do pacote.")
    layout.addWidget(plain("Atualização manual"))

    def choose():
        archive, _ = QFileDialog.getOpenFileName(owner, "Selecionar pacote portátil", "", "ZIP (*.zip)")
        if not archive:
            return
        manifest, _ = QFileDialog.getOpenFileName(owner, "Selecionar manifesto da CI", "", "JSON (*.json)")
        if manifest:
            action.setEnabled(False)
            report.setText("Verificando integridade e versão…")
            checker.check(archive, manifest)

    def finish(message):
        report.setText(message)
        action.setEnabled(True)

    action = button("Verificar pacote Windows", choose)
    checker.done.connect(finish)
    layout.addWidget(action)
    layout.addWidget(report)
