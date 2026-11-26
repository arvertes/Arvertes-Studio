"""Importação no Unreal Editor 5.6. Use um projeto descartável e o FBX legado."""
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re

DIGEST = re.compile(r"[a-f0-9]{64}")
PACKAGE_PATH = re.compile(r"/Game/ArvertesAcceptance/[a-f0-9]{32}")
TEXTURE = re.compile(r"textures/(?:pbr-(?:skin|cloth|leather|hair|metal)-(?:basecolor|normal|orm)-(?:32|64|128|256)|"
                     r"basecolor-[0-9]{1,4}x[0-9]{1,4})\.png")
LIMIT = 96 * 1024**2


def _digest(file, size):
    if file.is_symlink() or not file.is_file() or file.stat().st_size != size:
        raise ValueError("Arquivo da importação ausente ou alterado.")
    checksum = sha256()
    with file.open("rb") as stream:
        remaining = size
        while data := stream.read(1024**2):
            remaining -= len(data)
            if remaining < 0:
                raise ValueError("Arquivo cresceu durante a verificação.")
            checksum.update(data)
    if remaining:
        raise ValueError("Arquivo truncado durante a verificação.")
    return checksum.hexdigest()


def load_plan(directory, digest):
    path = directory / "import-plan.json"
    if directory.is_symlink() or path.is_symlink() or not path.is_file() or path.stat().st_size > 64*1024:
        raise ValueError("Plano de importação inválido.")
    raw = path.read_bytes()
    if not DIGEST.fullmatch(digest) or sha256(raw).hexdigest() != digest:
        raise ValueError("SHA-256 do plano divergente.")
    plan = json.loads(raw)
    if (plan["schema"] != 1 or plan["state"] != "unreal_import_pending"
            or not DIGEST.fullmatch(plan["package_sha256"]) or not PACKAGE_PATH.fullmatch(plan["destination"])
            or plan["base"] != "models/asset.fbx" or plan["units"] != "cm"
            or plan["fbx_axes"] != {"forward":"-Y","up":"Z"} or not math.isfinite(plan["height_cm"])
            or not 30 <= plan["height_cm"] <= 500 or not 0 <= plan["minimum_materials"] <= 40
            or not 1 <= len(plan["lods"]) <= 3
            or plan["lods"] != [f"models/lod{i}.fbx" for i in range(1, len(plan["lods"])+1)]
            or len(plan["textures"]) > 30 or not all(TEXTURE.fullmatch(name) for name in plan["textures"])
            or not 1 <= len(plan["clips"]) <= 50
            or not all(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_]{1,64}", name) for name in plan["clips"])
            or len(set(plan["clips"])) != len(plan["clips"])):
        raise ValueError("Metadados de importação fora do contrato.")
    expected = {plan["base"], *plan["lods"], *plan["textures"]}
    if (len(expected) != len(plan["files"]) or {row["path"] for row in plan["files"]} != expected
            or sum(row["bytes"] for row in plan["files"]) > LIMIT):
        raise ValueError("Inventário de importação divergente.")
    for row in plan["files"]:
        artifact = directory / row["path"]
        if (artifact.parent.is_symlink() or type(row["bytes"]) is not int or not 0 < row["bytes"] <= LIMIT
                or _digest(artifact, row["bytes"]) != row["sha256"]):
            raise ValueError("SHA-256 divergente durante a aceitação.")
    return plan


def execute(unreal, directory, plan):
    assets = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)
    target = plan["destination"]
    if assets.does_directory_exist(target) or assets.list_assets(target, recursive=True):
        raise ValueError("Escolha um projeto de teste com destino vazio.")
    mesh_editor = unreal.get_editor_subsystem(unreal.SkeletalMeshEditorSubsystem)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(directory / plan["base"]))
    task.set_editor_property("destination_path", target)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", False)
    task.set_editor_property("replace_existing_settings", False)
    task.set_editor_property("save", False)
    task.set_editor_property("factory", unreal.FbxFactory())
    ui = unreal.FbxImportUI()
    for key, value in {"automated_import_should_detect_type":False, "import_mesh":True, "import_as_skeletal":True,
                       "mesh_type_to_import":unreal.FBXImportType.FBXIT_SKELETAL_MESH,
                       "import_animations":True, "import_materials":True, "import_textures":True}.items():
        ui.set_editor_property(key, value)
    data = ui.get_editor_property("skeletal_mesh_import_data")
    for key, value in {"convert_scene":True, "convert_scene_unit":True, "force_front_x_axis":False,
                       "import_uniform_scale":1., "import_mesh_lods":False}.items():
        data.set_editor_property(key, value)
    task.set_editor_property("options", ui)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported = task.get_objects()
    meshes = [obj for obj in imported if isinstance(obj, unreal.SkeletalMesh)]
    if len(meshes) != 1:
        raise ValueError("A importação precisa produzir exatamente uma malha esquelética.")
    mesh = meshes[0]
    skeleton = mesh.get_editor_property("skeleton")
    actual_clips = [obj for obj in imported if isinstance(obj, unreal.AnimSequence)
                    and obj.get_editor_property("skeleton") == skeleton]
    names = [item.get_name() for item in actual_clips]
    missing = [name for name in plan["clips"] if not any(
        current == name or current.endswith("_" + name) for current in names)]
    checks = {"skeleton": skeleton is not None, "expected_animations_found": not missing,
              "material_slots": len(mesh.get_editor_property("materials")) >= plan["minimum_materials"]}
    for index, lod in enumerate(plan["lods"], 1):
        if mesh_editor.import_lod(mesh, index, str(directory / lod)) != index:
            raise ValueError(f"O editor recusou o LOD {index}.")
    checks["lod_count"] = mesh_editor.get_lod_count(mesh) == len(plan["lods"]) + 1
    height = 2 * mesh.get_bounds().box_extent.z
    checks["height_cm"] = abs(height - plan["height_cm"]) <= max(4, plan["height_cm"] * .05)
    texture_tasks = []
    for name in plan["textures"]:
        texture = unreal.AssetImportTask()
        for key, value in {"filename":str(directory / name), "destination_path":target + "/Maps",
                           "automated":True, "replace_existing":False, "save":False}.items():
            texture.set_editor_property(key, value)
        texture_tasks.append((name, texture))
    if texture_tasks:
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task for _, task in texture_tasks])
    textures = {}
    for name, texture in texture_tasks:
        objects = texture.get_objects()
        if len(objects) != 1 or not isinstance(objects[0], unreal.Texture2D):
            continue
        item = objects[0]
        is_normal, is_orm = "-normal-" in name, "-orm-" in name
        item.set_editor_property("srgb", not (is_normal or is_orm))
        if is_normal or is_orm:
            item.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP
                                     if is_normal else unreal.TextureCompressionSettings.TC_MASKS)
        textures[name] = item.get_name()
    checks["texture_files"] = set(textures) == set(plan["textures"])
    return {"schema":1, "engine":unreal.SystemLibrary.get_engine_version(),
            "package_sha256":plan["package_sha256"], "destination":target, "checks":checks,
            "missing_animations":missing, "observed_animations":names,
            "expected_height_cm":plan["height_cm"], "observed_height_cm":height, "imported_textures":textures,
            "state":"import_observed_human_review_required" if all(checks.values()) else "import_findings",
            "manual_checks":["altura e orientação no nível", "ligações PBR e espaço de cor",
                             "poses, transições e contato", "qualidade visual dos LODs"]}


def main():
    import unreal

    if os.environ.get("ARVERTES_UNREAL_ACCEPTANCE") != "DISPOSABLE_PROJECT":
        raise ValueError("Autorize explicitamente um projeto Unreal descartável.")
    directory = Path(os.environ["ARVERTES_UNREAL_STAGING"]).absolute()
    receipt = directory / "unreal-result.json"
    if receipt.exists() or receipt.is_symlink():
        raise ValueError("Use um diretório de ensaio novo.")
    plan = load_plan(directory, os.environ["ARVERTES_UNREAL_PLAN_SHA256"])
    result = execute(unreal, directory, plan)
    with receipt.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    unreal.log("Arvertes acceptance result: " + result["state"])


if __name__ == "__main__":
    main()
