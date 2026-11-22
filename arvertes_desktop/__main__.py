import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
        from .window import StudioWindow
    except ModuleNotFoundError as error:
        if error.name and error.name.startswith("PySide6"):
            print("Instale requirements-desktop.txt no ambiente virtual.", file=sys.stderr)
            return 1
        raise

    app = QApplication(sys.argv)
    app.setApplicationName("Arvertes Studio")
    app.setOrganizationName("Arvertes")
    if sys.argv[1:] == ['--self-test']:
        return smoke_test(app, StudioWindow)
    window = StudioWindow()
    window.show()
    return app.exec()

def smoke_test(app, window_type):
    """Executa diagnóstico em pasta temporária, sem os dados reais do usuário."""
    from tempfile import TemporaryDirectory
    from PySide6.QtWidgets import QLabel, QPushButton
    from .navigation import SECTIONS
    with TemporaryDirectory(prefix="arvertes-smoke-") as directory:
        window = window_type(config_dir=directory)
        try:
            window.show()
            app.processEvents()
            assert window.workspace is not None
            assert window.pages.count() == len(SECTIONS)
            for index in range(len(SECTIONS)):
                window.menu.setCurrentRow(index)
                app.processEvents()
                assert window.pages.currentIndex() == index
            window._navigate("sentinel")
            page = window.pages.currentWidget()
            feedback = page.findChild(QLabel, "sentinelFeedback")
            assert feedback is not None and feedback.text().startswith("BLOQUEADO")
            button = next(b for b in page.findChildren(QPushButton) if b.text() == "Avaliar evidências")
            button.click()
            assert feedback.text().startswith("BLOQUEADO")
            assert window.process.state() == window.process.ProcessState.NotRunning
        finally:
            window.close()
            app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
