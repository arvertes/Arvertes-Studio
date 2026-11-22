"""Executa o worker fixo com o Blender verdadeiro em uma cópia sintética."""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fixture_glb import write_fixture
from arvertes_desktop.blender_job import (checked_digest, checked_fbx, fingerprint, read_result,
                                         read_source, stage, stage_export)


def main(blender):
    worker = Path(__file__).resolve().parents[2] / "arvertes_desktop" / "blender_worker.py"
    with TemporaryDirectory(prefix="arvertes-worker-") as directory:
        root = Path(directory)
        source = root / "original.glb"
        write_fixture(source, mesh_count=4)
        original = fingerprint(read_source(source))
        work = root / "run"
        stage(source, original, work)
        subprocess.run([blender, "--background", "--factory-startup", "--offline-mode", "--disable-autoexec",
                        "--python-exit-code", "1", "--python", str(worker), "--", str(work), "organize"],
                       cwd=work, check=True, timeout=90)
        assert read_result(work, True)["summary"]["mesh_count"] == 4
        assert fingerprint(read_source(source)) == original
        subprocess.run([blender, "--background", "--factory-startup", "--offline-mode", "--disable-autoexec",
                        "--python-exit-code", "1", str(work / "working.blend"), "--python-expr",
                        "import bpy; assert sum(o.type == 'MESH' for o in bpy.context.scene.objects) == 4"],
                       cwd=work, check=True, timeout=30)
        delivery = work / "delivery"
        copy_hash = checked_digest(work / "working.blend")
        stage_export(work / "working.blend", copy_hash, delivery)
        subprocess.run([blender, "--background", "--factory-startup", "--offline-mode", "--disable-autoexec",
                        "--python-exit-code", "1", "--python", str(worker), "--", str(delivery), "export"],
                       cwd=delivery, check=True, timeout=90)
        assert len(checked_fbx(delivery)) == 64
        assert checked_digest(work / "working.blend") == copy_hash
        assert fingerprint(read_source(source)) == original
        print("Blender 5.3.0: importação, cópia organizada, relatório, FBX e origem intacta.")


if __name__ == "__main__":
    main(sys.argv[1])
