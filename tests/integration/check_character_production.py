"""Aceitação local com Atlas, Blender, revisão, transferência e restauro por hash."""
from argparse import ArgumentParser
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from shutil import copyfile
from struct import pack
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from zlib import compress, crc32

from check_asset_package import ROOT, write_image
from fixture_glb import write_fixture


def run(blender, agents, artifacts, baseline=None):
    with TemporaryDirectory(prefix="arvertes-character-check-") as directory:
        root = Path(directory)
        image = root / "reference.png"
        other = root / "detail.png"
        write_image(image)

        def chunk(kind, data):
            return pack(">I", len(data)) + kind + data + pack(">I", crc32(kind + data))

        other.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", pack(">IIBBBBB", 16, 16, 8, 2, 0, 0, 0))
                          + chunk(b"IDAT", compress((b"\0" + b"\x23\x7a\xc7" * 16) * 16)) + chunk(b"IEND", b""))
        brief = root / "brief.json"
        images = [image, other]
        original = root / "provided.glb"
        write_fixture(original, mesh_count=4)
        inputs = {path: sha256(path.read_bytes()).hexdigest() for path in (*images, original)}
        library = root / "library.json"
        entry = {"id": "paleta-boreal", "revision": 1, "category": "materials", "source": "fixture",
                 "license": "validação interna", "sha256": inputs[other], "usage": "reference_only",
                 "credit": "Fixture Arvertes", "title": "Paleta sintética", "status": "approved",
                 "keywords": ["azul"]}
        library.write_text(json.dumps({"schema": 1, "entries": [entry]}), encoding="utf-8")
        workspace = root / "production"
        store = root / "storage"
        command = [sys.executable, "-m", "arvertes_desktop.character_production", "--workspace", str(workspace)]

        def call(*values, ok=True):
            result = subprocess.run([*command, *map(str, values)], cwd=ROOT, capture_output=True, timeout=100)
            assert (result.returncode == 0) == ok, (result.stdout, result.stderr)
            return json.loads(result.stdout) if ok else None

        def start(source="synthetic_fixture", requirements=(), approval=True):
            brief.write_text(json.dumps({
                "name": "Manequim Boreal", "description": "Manequim de laboratório com roupa neutra.",
                "quality": "lite" if source != "base_glb" else "medium", "source": source,
                "traits": {"clothes": "Vestuário de teste neutro"},
                "dossier": {"id": "68a95108-834d-4a18-84b1-617b5fa42759", "revision": 1},
                "reference_revisions": [{"id": entry["id"], "revision": 1}],
                "requirements": list(requirements), "license": "Criação sintética para validação interna.",
                **({"proportions":[1.02,.99,1]} if source == "synthetic_fixture" else {})
            }), encoding="utf-8")
            return call("start", "--blender", blender, "--agents", agents, "--brief", brief,
                        "--image", image, "--image", other, "--library", library,
                        *(("--base", original) if source == "base_glb" else ()),
                        *(("--approved",) if approval else ()))

        assert start("image_guided")["reason"] == "image_guided_generator_unavailable"
        assert start(approval=False)["reason"] == "local_execution_requires_operator"
        incomplete = start("base_glb", ["animations", "pbr_maps", "unreal_import"])
        assert incomplete["state"] == "blocked", incomplete
        assert incomplete["missing_required"] == ["animations", "pbr_maps", "unreal_import"], incomplete
        call("review", incomplete["job"], incomplete["sha256"], "accept", ok=False)
        with ZipFile(workspace / incomplete["job"] / "personagem.zip") as outer:
            assert outer.read("original.glb") == original.read_bytes()

        active = start(requirements=["rig", "animations", "materials", "lods"])
        assert active["state"] == "awaiting_human_review", active
        identifier, digest = active["job"], active["sha256"]
        call("publish", identifier, "--store", store, ok=False)
        call("review", identifier, "0" * 64, "accept", ok=False)
        assert call("status", identifier) == active
        assert call("review", identifier, digest, "accept")["ready_for_production"] is False
        call("review", identifier, digest, "reject", ok=False)
        assert call("status", identifier)["review"]["decision"] == "accept"
        folder = store / identifier
        folder.mkdir(parents=True, exist_ok=True)
        generated = workspace / identifier / "personagem.zip"
        partial = folder / (digest + ".part")
        partial.write_bytes(b"divergente")
        call("publish", identifier, "--store", store, ok=False)
        assert partial.read_bytes() == b"divergente"
        partial.write_bytes(generated.read_bytes()[:1024])
        delivered = Path(call("publish", identifier, "--store", store)["path"])
        assert not partial.exists()
        assert Path(call("recover", identifier, digest, "--store", store)["path"]) == delivered
        assert Path(call("publish", identifier, "--store", store)["path"]) == delivered
        assert sha256(delivered.read_bytes()).hexdigest() == digest

        with ZipFile(delivered) as archive:
            manifest = json.loads(archive.read("manifest.sha256.json"))
            assert set(manifest) == set(archive.namelist()) - {"manifest.sha256.json"}
            for name, row in manifest.items():
                content = archive.read(name)
                assert row == {"bytes":len(content), "sha256":sha256(content).hexdigest()}
            assert archive.read("references/concept-1.png") == image.read_bytes()
            assert archive.read("references/concept-2.png") == other.read_bytes()
            plan = json.loads(archive.read("plan.json"))
            assert plan["traits"]["clothes"]["origin"] == "operator"
            assert plan["traits"]["anatomy"]["state"] == "missing"
            assert plan["visual_analysis"]["state"] == "blocked"
            assert plan["library_references"][0]["sha256"] == inputs[other]
            inventory = json.loads(archive.read("inventory.json"))
            assert inventory["ready_for_production"] is False
            assert inventory["dossier"]["revision"] == 1
            assert inventory["components"]["unreal_import"] == "blocked"
            assert inventory["preflight"]["status"] == "ready_for_human_review"
            inner_bytes = archive.read("asset.zip")
        imports = {}
        with ZipFile(BytesIO(inner_bytes)) as inner:
            quality = json.loads(inner.read("reports/quality.json"))
            motion = json.loads(inner.read("reports/motion.json"))
            lods = json.loads(inner.read("reports/deformable-lods.json"))
            assert len(motion["clips"]) == 11 and {"Reach","TalkGesture","Reaction"} <= motion["clips"].keys()
            assert motion["unweighted"] == 0 and motion["max_weight_sum_error"] < 1e-5
            assert lods["accepted_count"] >= 1
            assert all(len(item["poses"]) == 6 for item in lods["attempts"])
            for relative, count in (("models/preview.glb", quality["base"]["triangles"]),
                                    ("models/asset.fbx", quality["base"]["triangles"]),
                                    *((item["preview"], item["triangles"]) for item in quality["lods"]),
                                    *((item["path"], item["triangles"]) for item in quality["lods"])):
                imports[str(Path(inner.extract(relative, root)))] = count

        expression = f'''
import bpy
for path, expected_triangles in {imports!r}.items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = (bpy.ops.import_scene.gltf(filepath=path, disable_bone_shape=True) if path.endswith(".glb")
              else bpy.ops.import_scene.fbx(filepath=path))
    assert "FINISHED" in result
    arm = next(item for item in bpy.context.scene.objects if item.type == "ARMATURE")
    assert {{bone.name: bone.parent.name if bone.parent else None for bone in arm.data.bones}} == {motion["parents"]!r}
    meshes = [item for item in bpy.context.scene.objects if item.type == "MESH"]
    for mesh in meshes:
        mesh.data.calc_loop_triangles()
        assert mesh.data.uv_layers and mesh.data.materials
        assert all(vertex.groups and abs(sum(group.weight for group in vertex.groups)-1)<1e-4 for vertex in mesh.data.vertices)
    assert sum(len(mesh.data.loop_triangles) for mesh in meshes) == expected_triangles
    for clip in {list(motion["clips"])!r}:
        assert any(action.name == clip or action.name.endswith("|"+clip) for action in bpy.data.actions), (path, clip)
'''
        subprocess.run([blender, "--background", "--factory-startup", "--offline-mode", "--disable-autoexec",
                        "--threads", "2", "--python-exit-code", "1", "--python-expr", expression], cwd=root,
                       check=True, timeout=90)
        assert {path: sha256(path.read_bytes()).hexdigest() for path in inputs} == inputs
        if artifacts:
            artifacts.mkdir(parents=True, exist_ok=True)
            copyfile(delivered, artifacts / "arvertes-sprint6-personagem.zip")
            for relative in imports:
                path = Path(relative)
                if path.suffix == ".glb":
                    copyfile(path, artifacts / f"arvertes-sprint6-{path.name}")
            evidence = {"sha256": digest, "quality":quality, "motion":motion, "lods":lods, "inventory":inventory,
                        "reimported_in_blender":sorted(Path(path).name for path in imports)}
            if baseline:
                bundle = root / "inner.zip"
                bundle.write_bytes(inner_bytes)
                comparison = subprocess.check_output([sys.executable, "-m", "arvertes_desktop.asset_package",
                                                     "compare-motion", baseline, bundle], cwd=ROOT, timeout=20)
                evidence["comparison"] = json.loads(comparison)
            (artifacts / "arvertes-sprint6-evidencias.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps({"verified": digest, "triangles": quality["base"]["triangles"],
                          "lods": [item["triangles"] for item in quality["lods"]], "clips": len(motion["clips"])}))


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("blender")
    parser.add_argument("--agents", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    run(args.blender, args.agents.resolve(), args.artifacts, args.baseline)
