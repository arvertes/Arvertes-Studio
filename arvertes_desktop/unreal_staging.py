"""Gera uma entrada verificada para a aceitação Unreal, em diretório novo."""
import argparse
from hashlib import sha256
from pathlib import Path
from shutil import copyfileobj
from uuid import uuid4

from arvertes_studio.core.asset_package import MAX_PACKAGE, json_bytes, open_package
from arvertes_studio.core.unreal_preflight import preflight
from .blender_job import checked_digest


def prepare(package, output):
    source_hash = checked_digest(package, MAX_PACKAGE)
    report = preflight(package)
    if report["findings"] or not report["clips"] or not report["glb"]["skins"] or not report["lods"]:
        raise ValueError("A aceitação exige pacote com rig, clipes e LODs sem achados bloqueantes.")
    if not report["dimensions_m"] or report["dimensions_m"][2] <= 0:
        raise ValueError("A altura do personagem precisa estar documentada.")
    output.mkdir(mode=0o700, exist_ok=False)
    with open_package(package) as (archive, original):
        items = {entry["path"]: entry for entry in original["files"]}
        lods = [row["path"] for row in report["lods"]]
        textures = list(report["external_texture_dimensions"])
        selected = ["models/asset.fbx", *lods, *textures]
        for name in selected:
            path = output / name
            path.parent.mkdir(mode=0o700, exist_ok=True)
            with archive.open(name) as source, path.open("xb") as target:
                copyfileobj(source, target, 1024**2)
        if checked_digest(package, MAX_PACKAGE) != source_hash:
            raise ValueError("A revisão do pacote mudou durante a preparação.")
        plan = {"schema":1, "package_sha256":source_hash, "state":"unreal_import_pending",
                "destination":"/Game/ArvertesAcceptance/" + uuid4().hex,
                "units":"cm", "fbx_axes":{"forward":"-Y","up":"Z"}, "height_cm":report["dimensions_m"][2]*100,
                "base":"models/asset.fbx", "lods":lods, "textures":textures, "clips":report["clips"],
                "minimum_materials":report["glb"]["materials"], "files":[items[name] for name in selected]}
        data = json_bytes(plan)
        (output / "import-plan.json").write_bytes(data)
    return {"state":plan["state"], "plan":str(output / "import-plan.json"), "plan_sha256":sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="asset.zip interno")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json_bytes(prepare(args.package, args.output)).decode(), end="")
    except (OSError, ValueError) as error:
        parser.exit(2, f"Preparação bloqueada. {error}\n")


if __name__ == "__main__":
    main()
