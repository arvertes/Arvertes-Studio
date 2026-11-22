"""Operações fixas chamadas pelo Blender local com um GLB de trabalho."""
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arvertes_studio.blender.analysis import analyze_asset
from arvertes_studio.blender.assets import import_asset, organize_meshes
from arvertes_studio.core.reports import write_report


def main():
    if bpy.app.version[:3] != (5, 3, 0):
        raise ValueError("A inspeção requer Blender 5.3.0.")
    folder_arg, operation = sys.argv[sys.argv.index("--") + 1:]
    folder = Path(folder_arg).resolve(strict=True)
    if operation not in ("inspect", "organize"):
        raise ValueError("Operação fora do contrato.")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if bpy.app.online_access or bpy.context.preferences.filepaths.use_scripts_auto_execute:
        raise ValueError("O executor requer Blender offline e scripts automáticos desabilitados.")
    collection = import_asset(bpy.context, folder / "source.glb")
    if operation == "organize":
        organize_meshes(collection)
        bpy.ops.wm.save_as_mainfile(filepath=str(folder / "working.blend"))
    report = analyze_asset(bpy.context, collection, evaluated=True)
    write_report(report, folder / "report.json")


if __name__ == "__main__":
    main()
