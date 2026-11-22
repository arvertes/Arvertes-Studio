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
    if sys.argv[1:] == ["--self-test-habblaud"]:
        return smoke_habblaud(app, StudioWindow)
    if sys.argv[1:] == ['--self-test']:
        return smoke_test(app, StudioWindow)
    window = StudioWindow()
    window.show()
    return app.exec()

def smoke_test(app, window_type):
    """Executa diagnóstico em pasta temporária, sem os dados reais do usuário."""
    from contextlib import closing
    from hashlib import sha256
    from http.client import HTTPSConnection
    import ssl
    from tempfile import TemporaryDirectory
    from PySide6.QtWidgets import QLabel, QPushButton, QComboBox, QGraphicsView
    from .navigation import SECTIONS
    with TemporaryDirectory(prefix="arvertes-smoke-") as directory:
        window = window_type(config_dir=directory)
        try:
            window.show()
            app.processEvents()
            assert window.workspace is not None
            assert window.pages.count() == len(SECTIONS)
            project = window.workspace.create_project("Projeto smoke")
            window.workspace.add_task(project, "Rascunho smoke", "Diagnóstico")
            window.refresh_dashboard()
            values = [l.text() for l in window.pages.widget(0).findChildren(QLabel) if l.objectName() == "metric"]
            assert values == ["1", "0", "1"], values
            for index in range(len(SECTIONS)):
                window.menu.setCurrentRow(index)
                app.processEvents()
                assert window.pages.currentIndex() == index
            window._navigate("office")
            page = window.pages.currentWidget()
            view = page.findChild(QGraphicsView, "officeMap")
            selector = page.findChild(QComboBox, "officeAgent")
            detail = page.findChild(QLabel, "officeDetail")
            assert view is not None and selector.count() == 26
            selector.setCurrentIndex(selector.findData("seguranca"))
            app.processEvents()
            assert "Sentinel" in detail.text()
            assert "monitoramento" in detail.text()
            assert len(view.scene().selectedItems()) == 1
            assert view.scene().selectedItems()[0].data(0) == "seguranca"
            view.scene().clearSelection()
            atlas = next(i for i in view.scene().items() if i.data(0) == "coordenador")
            atlas.setSelected(True)
            app.processEvents()
            assert selector.currentData() == "coordenador"
            assert "Não conectado" in detail.text()
            window._navigate("network")
            network = window.pages.currentWidget()
            assert network.findChild(QLabel, "networkFeedback") is not None
            assert not window.network.listeners
            listener = window.network.start("127.0.0.1/8", "wifi_local", advertise=False, test_loopback=True)
            context = ssl.create_default_context(cadata=window.network.registry.identity()[0].decode("ascii"))
            context.check_hostname = False
            with closing(HTTPSConnection("127.0.0.1", listener.server_port, context=context, timeout=3)) as client:
                client.connect()
                assert sha256(client.sock.getpeercert(binary_form=True)).hexdigest() == window.network.fingerprint
                client.request("POST", "/v1/session", '{"version":1,"action":"poll"}',
                               {"Content-Type": "application/json"})
                response = client.getresponse()
                assert response.status == 401 and b"Sentinel" in response.read()
            window.network.stop("wifi_local")
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


def smoke_habblaud(app, window_type):
    """Confere renderização local e encerramento ao sair do escritório."""
    from tempfile import TemporaryDirectory
    from PySide6.QtCore import QEventLoop, QTimer
    with TemporaryDirectory(prefix="arvertes-office-smoke-") as directory:
        window = window_type(config_dir=directory)
        loop = QEventLoop()
        ready = []
        timer = QTimer()
        timer.setInterval(300)
        window.show()
        window._navigate("office")
        app.processEvents()
        preview = window.office_preview
        preview.toggle()
        if preview.view is None:
            window.close()
            return 2

        def result(count):
            if count == 26:
                ready.append(True)
                loop.quit()

        def poll():
            preview.page.runJavaScript("document.querySelectorAll('#agents option').length", result)

        timer.timeout.connect(poll)
        timer.start()
        QTimer.singleShot(20000, loop.quit)
        loop.exec()
        timer.stop()
        window._navigate("tasks")
        app.processEvents()
        suspended = preview.server is None and preview.view is None
        window.close()
        return 0 if ready and suspended else 3


if __name__ == "__main__":
    raise SystemExit(main())
