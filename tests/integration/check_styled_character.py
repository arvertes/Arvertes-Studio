"""Produz duas identidades procedurais e verifica pacote, revisão, mapas e adaptações."""
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

from check_asset_package import ROOT
from fixture_glb import write_fixture

sys.path.insert(0, str(ROOT))
from arvertes_studio.core.character_style import study_presets


def sketch(path, design):
    """Estudo esquemático em pixels, com silhueta e paleta declaradas pelo teste."""
    edge = 144
    colors = {key: bytes.fromhex(value[1:]) for key, value in design["palette"].items()}
    broad = design["silhouette"] == "stocky"
    pixels = bytearray()
    for y in range(edge):
        pixels.append(0)
        for x in range(edge):
            dx = abs(x - edge//2)
            color = b"\x22\x29\x32"
            if 19 <= y < 48 and dx < (18 if broad else 14):
                color = colors["hair"] if y < 28 else colors["skin"]
                if broad and y > 42:
                    color = colors["hair"]
            if 48 <= y < 89 and dx < (33 if broad else 23):
                color = colors["cloth"]
            if 76 <= y < 79 and dx < (33 if broad else 25):
                color = colors["leather"]
            if not broad and 54 <= y < 63 and dx + abs(59-y) < 8:
                color = colors["metal"]
            if 89 <= y < 130 and 5 <= dx < (24 if broad else 17):
                color = colors["leather"]
            pixels.extend(color)

    def chunk(kind, data):
        return pack(">I", len(data)) + kind + data + pack(">I", crc32(kind + data))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", pack(">IIBBBBB", edge, edge, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", compress(pixels)) + chunk(b"IEND", b""))


def read_zip(archive, filename):
    return json.loads(archive.read(filename))


def exercise(blender, agents, artifacts, baseline):
    with TemporaryDirectory(prefix="arvertes-sprint7-") as folder:
        root = Path(folder)
        command = [sys.executable, "-m", "arvertes_desktop.character_production", "--workspace", str(root / "jobs")]

        def invoke(*args, ok=True):
            result = subprocess.run([*command, *map(str, args)], cwd=ROOT, capture_output=True, timeout=100)
            assert (result.returncode == 0) == ok, (result.stdout, result.stderr)
            return json.loads(result.stdout) if ok else None

        def produce(brief, image, *options):
            path = root / "brief.json"
            path.write_text(json.dumps(brief), encoding="utf-8")
            return invoke("start", "--blender", blender, "--agents", agents, "--brief", path,
                          "--image", image, "--approved", *options)

        takes, metrics = [], {}
        for slug, name, design in zip(("coral", "cobre"), ("Guia do Coral", "Mecânico do Cobre"),
                                      study_presets().values(), strict=True):
            reference = root / (slug + "-referencia.png")
            sketch(reference, design)
            digest = sha256(reference.read_bytes()).hexdigest()
            brief = {"name": name, "description": "Personagem fictício de validação procedural offline.",
                     "quality": "lite", "source": "procedural", "design": design, "views": ["front"],
                     "traits": {"silhouette": design["silhouette"], "clothes": design["outfit"]},
                     "hypotheses": {"style": "Estilo de bancada ainda em revisão."},
                     "requirements": ["rig", "animations", "lods", "materials", "pbr_maps"],
                     "license": "Peças sintéticas criadas na bancada. Uso oficial aguarda decisão do proprietário."}
            active = produce(brief, reference)
            assert active["state"] == "awaiting_human_review", active
            identifier, key = active["job"], active["sha256"]
            invoke("review", identifier, key, "accept", ok=False)
            fidelity = root / "fidelity.json"
            fidelity.write_text(json.dumps({
                "references": [digest], "verdict": "enough_for_local_review",
                "notes": "Fixture de aceitação. Estudo frontal esquemático, revisado para entrega de bancada.",
            }), encoding="utf-8")
            invoke("review", identifier, key, "accept", "--fidelity-report", fidelity)
            store = root / "store"
            final = Path(invoke("publish", identifier, "--store", store)["path"])
            assert final == Path(invoke("recover", identifier, key, "--store", store)["path"])
            assert sha256(final.read_bytes()).hexdigest() == key
            target = root / slug if not artifacts else artifacts / slug
            target.mkdir(parents=True, exist_ok=True)
            with ZipFile(final) as outer:
                for filename, entry in read_zip(outer, "manifest.sha256.json").items():
                    payload = outer.read(filename)
                    assert entry == {"bytes": len(payload), "sha256": sha256(payload).hexdigest()}
                plan = read_zip(outer, "plan.json")
                assert plan["tool_selection"]["executor"] == "blender_procedural"
                assert plan["traits"]["clothes"]["origin"] == "operator"
                assert plan["hypotheses"][0]["origin"] == "unverified_hypothesis"
                assert plan["reference_views"] == [{"sha256":digest,"view":"front","origin":"operator"}]
                inventory = read_zip(outer, "inventory.json")
                assert inventory["components"]["pbr_maps"] == "produced"
                assert inventory["visual_analysis"]["state"] == "blocked"
                assert not inventory["ready_for_production"]
                inner = outer.read("asset.zip")
            with ZipFile(BytesIO(inner)) as asset:
                quality = read_zip(asset, "reports/quality.json")
                motion = read_zip(asset, "reports/motion.json")
                style = read_zip(asset, "reports/style.json")
                lod = read_zip(asset, "reports/deformable-lods.json")
                assert 3000 <= quality["base"]["triangles"] <= design["triangle_budget"]
                assert not quality["findings"] and lod["accepted_count"]
                assert len(quality["texture_variants"]) == 30 and len(motion["clips"]) == 11
                for clip in ("Walk", "Run"):
                    before = motion["contact"]["same_geometry_before"][clip]["indicative_foot_drift_m"]
                    after = motion["clips"][clip]["indicative_foot_drift_m"]
                    assert after < before * .15 and motion["clips"][clip]["closure_error_m"] < .01
                assert set(style["meshes"]) >= {"Corpo", "Vestuário", "Cabelo"}
                assert len(lod["attempts"][0]["poses"][0]["by_component_m"]) == len(style["meshes"])
                for rel, count in (("models/preview.glb", quality["base"]["triangles"]),
                                   ("models/asset.fbx", quality["base"]["triangles"]),
                                   *((item["preview"], item["triangles"]) for item in quality["lods"]),
                                   *((item["path"], item["triangles"]) for item in quality["lods"])):
                    path = Path(asset.extract(rel, target))
                    takes.append((str(path), count, list(motion["clips"])))
                if artifacts:
                    asset.extract("scene/working.blend", target)
                    copyfile(final, target / (slug + "-personagem.zip"))
                    copyfile(reference, target / reference.name)
            evidence = {"package_sha256": key, "quality": quality, "lods": lod, "motion": motion, "style": style,
                        "preflight": inventory["preflight"]}
            if baseline:
                inner_path = root / (slug + "-asset.zip")
                inner_path.write_bytes(inner)
                comparison = subprocess.check_output([sys.executable, "-m", "arvertes_desktop.asset_package",
                                                      "compare-motion", baseline, inner_path], cwd=ROOT, timeout=20)
                evidence["comparison_to_sprint6"] = json.loads(comparison)
            metrics[slug] = evidence
        assert metrics["coral"]["quality"]["dimensions_m"] != metrics["cobre"]["quality"]["dimensions_m"]

        # The valid local-authored handoff deliberately has an incompatible humanoid rig.
        original = root / "external.glb"
        write_fixture(original, 3)
        payload = original.read_bytes()
        receipt = root / "handoff.json"
        receipt.write_text(json.dumps({"schema": 1, "provider": "local_authored", "license": "Sintético de teste",
                                       "version": "fixture-1", "model_sha256": sha256(payload).hexdigest(),
                                       "references": [digest], "cost_centavos": 0}), encoding="utf-8")
        result = produce({"name": "Fixture externa", "description": "Checar rig e materiais", "quality": "medium",
                          "source": "external_glb", "requirements": ["rig"],
                          "adaptation": {"front": "+X", "height_m": 1.7, "require_humanoid": True}},
                         reference, "--base", original, "--handoff", receipt)
        assert result["state"] == "blocked", result
        assert {"incompatible_humanoid_rig", "missing_materials", "missing_uv"} <= {
            item["finding"] for item in result["referrals"]}, result
        invoke("review", result["job"], result["sha256"], "accept", ok=False)
        bundled = root / "jobs" / result["job"] / "personagem.zip"
        with ZipFile(bundled) as outer:
            assert outer.read("original.glb") == payload == original.read_bytes()
            assert read_zip(outer, "handoff.json")["inference_verified_by_studio"] is False
            with ZipFile(BytesIO(outer.read("asset.zip"))) as inner:
                external_quality = read_zip(inner, "reports/quality.json")
                assert external_quality["dimensions_m"][2] == 1.7
                assert external_quality["adaptation"]["output_front"] == "-Y"
        original.write_bytes(b"invalid")
        refused = subprocess.run([*command, "start", "--agents", str(agents), "--blender", str(blender),
                                  "--image", str(reference), "--brief", str(root / "brief.json"),
                                  "--base", str(original), "--handoff", str(receipt), "--approved"],
                                 cwd=ROOT, capture_output=True, timeout=15)
        assert refused.returncode == 2

        check = f"""
import bpy
for path, triangles, clips in {takes!r}:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    glb = path.endswith(".glb")
    result = (bpy.ops.import_scene.gltf(filepath=path, disable_bone_shape=True) if glb
              else bpy.ops.import_scene.fbx(filepath=path))
    assert "FINISHED" in result, path
    rig = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    assert len(rig) == 1 and len(rig[0].data.bones) == 16, path
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    for mesh in meshes:
        mesh.data.calc_loop_triangles()
        assert mesh.data.uv_layers and mesh.data.materials
        assert all(abs(sum(g.weight for g in v.groups)-1) < 1e-4 for v in mesh.data.vertices)
    assert sum(len(obj.data.loop_triangles) for obj in meshes) == triangles
    assert all(any(a.name == clip or a.name.endswith("|"+clip) for a in bpy.data.actions) for clip in clips)
    if glb:
        for material in bpy.data.materials:
            bsdf = next((node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
            assert bsdf and all(bsdf.inputs[key].is_linked for key in ("Base Color","Roughness","Metallic","Normal"))
"""
        subprocess.run([blender,"--background","--factory-startup","--offline-mode","--disable-autoexec","--threads","2",
                        "--python-exit-code","1","--python-expr",check], cwd=root, check=True, timeout=100)
        if artifacts:
            (artifacts / "evidencias-sprint7.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(json.dumps({key: {"triangles": item["quality"]["base"]["triangles"],
                                "lods": [row["triangles"] for row in item["quality"]["lods"]]}
                          for key, item in metrics.items()}))


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("blender", type=Path)
    parser.add_argument("--agents", required=True, type=Path)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    exercise(args.blender.resolve(), args.agents.resolve(), args.artifacts, args.baseline)
