"""Teste local das duas bases e do Blender. Executar com QT_QPA_PLATFORM=offscreen."""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from arvertes_desktop.blender_job import fingerprint, read_source
from arvertes_desktop.settings import Settings
from arvertes_desktop.status_snapshot import snapshot
from arvertes_desktop.window import StudioWindow
from fixture_glb import write_fixture


def wait_for(predicate, timeout_ms):
    if predicate():
        return
    loop, timer = QEventLoop(), QTimer()
    timer.timeout.connect(lambda: loop.quit() if predicate() else None)
    timer.start(25)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    timer.stop()
    assert predicate(), "A etapa não terminou no tempo esperado."


def main(blender, agents, python):
    app = QApplication([])
    with TemporaryDirectory() as directory:
        root = Path(directory)
        window = StudioWindow(config_dir=root / "config")
        try:
            window.settings = Settings(blender_path=str(Path(blender).resolve(strict=True)))
            window.show()
            production = window.production
            production.notice.connect(print)
            bridge = window.agent_bridge
            bridge.configure(str(Path(python).absolute()), str(Path(agents).absolute()))
            wait_for(lambda: bridge.connected, 8000)
            write_fixture(root / "fixture.glb", mesh_count=5)
            original = root / "fixture.glb"
            source_hash = fingerprint(read_source(original))
            project = window.workspace.create_project("Fixture pipeline")
            asset = window.workspace.add_reference(project, str(original))
            production.queue(project, asset, True, 1000)
            wait_for(lambda: bool(production.runs.list(project)), 8000)
            run = production.runs.list(project)[0]["id"]
            production.start(run)
            # Interrompe a execução do Blender depois que Nexus já gravou seu checkpoint.
            wait_for(lambda: bool(production.process.processId()), 12000)
            production.halt("Pausa do teste de integração.")
            wait_for(lambda: not production.process.processId(), 5000)
            assert set(production.runs.checkpoints(run)) == {"catalog"}
            production.start(run)
            wait_for(lambda: production.active is None, 90000)
            assert production.runs.get(run)["status"] == "blocked"
            assert set(production.runs.checkpoints(run)) == {
                "catalog", "blender", "budget", "materials", "inspect", "audit", "gate"}
            assert (production.directory(run) / "report.json").is_file()
            assert (production.directory(run) / "working.blend").is_file()
            assert fingerprint(read_source(original)) == source_hash
            assert snapshot(window.workspace, window.network, bridge)["sentinel"][0]["status"] == "blocked"
            print("Fluxo Studio/Agents/Blender com pausa e retomada validado.")
        finally:
            window.close()
            app.processEvents()


if __name__ == "__main__":
    main(*sys.argv[1:])
