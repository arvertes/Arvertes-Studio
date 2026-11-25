"""Exercita o comando com Blender real e entradas sintéticas."""
from hashlib import sha256
from pathlib import Path
from struct import pack
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from zlib import compress, crc32
import argparse
import json
import shutil
import subprocess
import sys

from fixture_glb import write_fixture

ROOT = Path(__file__).resolve().parents[2]


def write_image(path):
    def chunk(kind, data):
        return pack(">I", len(data)) + kind + data + pack(">I", crc32(kind + data))

    width, height = 384, 256
    rows = b"".join(b"\0" + bytes((x // 2 + y // 4) % 256 for x in range(width * 3)) for y in range(height))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", compress(rows)) + chunk(b"IEND", b""))


def main(blender, artifacts=None, agents=None):
    with TemporaryDirectory(prefix="arvertes-package-check-") as directory:
        root = Path(directory)
        image = root / "reference.png"
        model = root / "origin.glb"
        write_image(image)
        write_fixture(model, mesh_count=4)
        originals = {path: sha256(path.read_bytes()).hexdigest() for path in (image, model)}
        command = [sys.executable, "-m", "arvertes_desktop.asset_package"]
        pins = root / "pins.json"
        pin = {"id": "paleta-teste", "revision": 1, "category": "materials", "source": "fixture",
               "license": "uso-teste", "sha256": originals[image], "usage": "reference_only",
               "credit": "Fixture Arvertes Studio"}
        selected = [pin]
        if agents:
            request = {"version": 1, "action": "pin_asset_references",
                       "library": {"schema": 1, "entries": [{**pin, "status": "approved", "title": "Paleta",
                                                             "keywords": ["fixture"]}]},
                       "selections": [{"id": pin["id"], "revision": 1}]}
            response = subprocess.run([sys.executable, "-m", "arvertes_agents"], cwd=agents,
                                      input=json.dumps(request), capture_output=True, text=True, check=True, timeout=15)
            selected = json.loads(response.stdout)["result"]
            assert selected == [pin]
        pins.write_text(json.dumps(selected), encoding="utf-8")
        cases = (("static", "lite", ["--recipe", "static"]), ("rigged", "low", ["--recipe", "rigged"]),
                 ("imported_glb", "medium", ["--model", str(model)]))
        for mode, quality, source in cases:
            output = root / (mode + ".zip")
            result = subprocess.run([*command, "build", "--blender", blender, "--image", str(image),
                    "--description", "Corpo geométrico sintético para validar esta produção.",
                    "--output", str(output), "--approved", "--quality", quality, "--references", str(pins), *source],
                    cwd=ROOT, capture_output=True, text=True, timeout=100)
            assert result.returncode == 0, result.stdout + result.stderr
            manifest = json.loads(subprocess.check_output([*command, "verify", str(output)], cwd=ROOT, timeout=15))
            assert manifest["mode"] == mode and manifest["quality"] == quality
            with ZipFile(output) as archive:
                report = json.loads(archive.read("reports/quality.json"))
                brief = json.loads(archive.read("brief.json"))
                assert brief["image"]["sha256"] == originals[image]
                assert json.loads(archive.read("references/library.json"))[0]["revision"] == 1
                assert report["unreal_import"] == "pending"
                assert report["base"]["triangles"] > 0
                if mode == "static":
                    assert len(report["lods"]) == 2
                    assert [item["size"][0] for item in report["texture_variants"]] == [256, 128, 64]
                    assert report["base"]["uv_meshes"] == 1
                elif mode == "rigged":
                    assert report["base"]["bones"] == 1 and report["actions"] == ["FixtureTurn"]
                    assert report["lods"] == [] and report["lod_status"] == "deforming_asset_requires_lod_review"
                else:
                    assert brief["model_sha256"] == originals[model]
                    assert report["base"]["mesh_objects"] == 4
                    assert report["lod_status"] == "invalid_lod_topology"
                    assert [lod["triangles"] for lod in report["lods"]] == [24]
                for item in ("models/asset.fbx", "models/preview.glb", "scene/working.blend",
                             *(lod["path"] for lod in report["lods"])):
                    archive.extract(item, root / mode)
            for extension, importer in (("asset.fbx", "fbx"), ("preview.glb", "gltf")):
                path = root / mode / "models" / extension
                options = ", disable_bone_shape=True" if importer == "gltf" else ""
                expression = (f"import bpy; assert 'FINISHED' in bpy.ops.import_scene.{importer}(filepath={str(path)!r}{options}); "
                              f"assert sum(o.type=='MESH' for o in bpy.context.scene.objects)=={4 if mode == 'imported_glb' else 1}; "
                              + ("assert any(o.type=='ARMATURE' for o in bpy.context.scene.objects); assert len(bpy.data.actions)>0"
                                 if mode == "rigged" else "assert len(bpy.data.meshes)>0"))
                if mode != "imported_glb":
                    expression += "; assert any(image.size[0] > 0 for image in bpy.data.images)"
                subprocess.run([blender, "--background", "--factory-startup", "--offline-mode", "--disable-autoexec",
                                "--threads", "2", "--python-exit-code", "1", "--python-expr",
                                "import bpy; bpy.ops.wm.read_factory_settings(use_empty=True); " + expression],
                               check=True, timeout=30, cwd=root)
            if report["lods"]:
                lod_paths = [(str(root / mode / lod["path"]), lod["triangles"]) for lod in report["lods"]]
                check_lods = f"""
import bpy
for path, expected in {lod_paths!r}:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    assert 'FINISHED' in bpy.ops.import_scene.fbx(filepath=path)
    meshes = [o.data for o in bpy.context.scene.objects if o.type == 'MESH']
    for mesh in meshes:
        mesh.calc_loop_triangles()
    assert sum(len(mesh.loop_triangles) for mesh in meshes) == expected
"""
                subprocess.run([blender, "--background", "--factory-startup", "--offline-mode", "--disable-autoexec",
                                "--threads", "2", "--python-exit-code", "1", "--python-expr", check_lods],
                               check=True, timeout=30, cwd=root)
            if mode == "static":
                scene = root / mode / "scene/working.blend"
                subprocess.run([blender, "--background", "--factory-startup", "--offline-mode", "--disable-autoexec",
                                "--threads", "2", "--python-exit-code", "1", str(scene), "--python-expr",
                                "import bpy; assert any(i.packed_file for i in bpy.data.images); "
                                "assert len(bpy.data.materials)==1"], check=True, timeout=30, cwd=root)
            if artifacts:
                shutil.copyfile(output, artifacts / output.name)
            print(mode, report["base"]["triangles"], [item["triangles"] for item in report["lods"]], report["actions"])
        assert originals == {path: sha256(path.read_bytes()).hexdigest() for path in originals}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("blender")
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--agents", type=Path)
    args = parser.parse_args()
    main(args.blender, args.artifacts, args.agents)
