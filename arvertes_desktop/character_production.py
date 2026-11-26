"""Fluxo local de personagens. Atlas só recebe dados normalizados e evidências."""
import argparse
from functools import partial
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from shutil import disk_usage
import subprocess
import sys
from typing import Protocol
from tempfile import NamedTemporaryFile
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZIP_STORED, ZipFile

from arvertes_studio.core.asset_package import MAX_FILE, MAX_IMAGE, MAX_PACKAGE, image_info, json_bytes, library_pins
from arvertes_studio.core.unreal_preflight import preflight
from arvertes_studio.core.character_style import reference_views, validate_adaptation, validate_style
from .generation_adapter import run_triposr, validate_handoff
from .process_runtime import system_dll_search
from .production_tools import inventory, read_config
from .visual_executor import analyze as analyze_visual
from . import asset_package
from .blender_job import checked_digest, read_source

IDENTIFIER = re.compile(r"[0-9a-f]{32}")
DIGEST = re.compile(r"[0-9a-f]{64}")
MAX_DELIVERY = MAX_PACKAGE + MAX_FILE + 4 * MAX_IMAGE + 256 * 1024
BLOCK = 1024 * 1024


def _atomic(path, data):
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        temporary.write_bytes(data)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _json(path, limit=256 * 1024):
    return json.loads(asset_package.read_local(path, limit))


def _directory(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("Área local inválida.")
    return path


def _job(workspace, identifier):
    if not IDENTIFIER.fullmatch(identifier):
        raise ValueError("Identificador de produção inválido.")
    path = workspace / identifier
    if workspace.is_symlink() or path.is_symlink() or not path.is_dir():
        raise ValueError("Produção local não encontrada.")
    return path


def _atlas(repository, action, *, python=None, **payload):
    request = {"version": 1, "action": action, **payload}
    repository = repository.resolve(strict=True)
    if not (repository / "arvertes_agents" / "__main__.py").is_file():
        raise ValueError("Selecione um checkout local confiável do Agents.")
    if python is None and getattr(sys, "frozen", False):
        raise ValueError("Informe o Python local configurado para o Agents.")
    interpreter = Path(python or sys.executable)
    if python is not None and (not interpreter.is_absolute() or not interpreter.is_file()
                               or interpreter.name.lower() not in {"python", "python3", "python.exe", "python3.exe"}):
        raise ValueError("Selecione um executável Python local confiável para o Agents.")
    environment = {key: os.environ[key] for key in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG")
                   if key in os.environ}
    bootstrap = ("import sys; sys.path.insert(0, sys.argv[1]); "
                 "from arvertes_agents.__main__ import main; sys.exit(main())")
    data = (json.dumps(request, allow_nan=False) + "\n").encode()
    if len(data) > 65536:
        raise ValueError("A consulta do Atlas ultrapassa 64 KiB.")
    with system_dll_search():
        result = subprocess.run([str(interpreter), "-I", "-B", "-c", bootstrap, str(repository)], cwd=repository,
                                env=environment, input=data, capture_output=True, timeout=15)
    if result.returncode or not 0 < len(result.stdout) <= 64 * 1024:
        raise ValueError("Atlas recusou o contrato ou está indisponível.")
    response = json.loads(result.stdout)
    kind = list if action == "pin_asset_references" else dict
    if response.get("ok") is not True or not isinstance(response.get("result"), kind):
        raise ValueError("Resposta do Atlas incompatível.")
    return response["result"]


def _inputs(args):
    brief = _json(args.brief, 24 * 1024)
    if not isinstance(brief, dict) or set(brief) - {
            "name", "description", "quality", "source", "traits", "requirements", "proportions", "license", "reference_revisions", "dossier", "design", "views", "hypotheses", "adaptation"} or (
            {"name", "description", "quality"} - set(brief)):
        raise ValueError("Campos do briefing incompatíveis.")
    brief.setdefault("traits", {})
    brief.setdefault("requirements", [])
    brief.setdefault("source", "base_glb" if args.base else "image_guided")
    if bool(args.base) != (brief["source"] in ("base_glb", "external_glb")):
        raise ValueError("Informe um GLB local somente para origem fornecida ou externa.")
    if bool(getattr(args, "handoff", None)) != (brief["source"] == "external_glb"):
        raise ValueError("Um artefato externo exige um handoff com revisão e licença.")
    if "adaptation" in brief:
        if not args.base:
            raise ValueError("A adaptação exige um GLB local.")
        validate_adaptation(brief["adaptation"])
    if brief["source"] == "procedural":
        validate_style(brief.get("design"))
    elif "design" in brief:
        raise ValueError("A receita visual só se aplica ao modo procedural.")
    if not 1 <= len(args.image) <= 4:
        raise ValueError("Selecione de uma a quatro imagens de referência.")
    proportions = brief.get("proportions")
    if proportions is not None and (brief["source"] != "synthetic_fixture"
            or not isinstance(proportions, list) or len(proportions) != 3
            or any(type(value) not in (int, float) or not .85 <= value <= 1.15 for value in proportions)):
        raise ValueError("Proporções devem conter três escalas entre 0,85 e 1,15 para o manequim.")
    license_note = brief.get("license")
    if license_note is not None and (not isinstance(license_note, str)
            or not 1 <= len(license_note.strip()) <= 300 or any(ord(c) < 32 for c in license_note)):
        raise ValueError("Declaração de licença inválida.")
    dossier = brief.get("dossier")
    if dossier is not None:
        if (not isinstance(dossier, dict) or set(dossier) != {"id", "revision"}
                or type(dossier["revision"]) is not int or not 1 <= dossier["revision"] <= 2**31 - 1):
            raise ValueError("Vínculo de dossiê inválido.")
        try:
            identifier = UUID(dossier["id"])
        except (TypeError, ValueError, AttributeError) as error:
            raise ValueError("Identificador de dossiê inválido.") from error
        if dossier["id"] != str(identifier):
            raise ValueError("Use o identificador canônico do dossiê.")
    images = []
    for path in args.image:
        data = asset_package.read_local(path, MAX_IMAGE)
        images.append((data, image_info(data)))
    if "views" in brief:
        brief["views"] = reference_views(brief["views"], len(images))
    request = {key: value for key, value in brief.items()
               if key not in {"proportions", "license", "reference_revisions", "dossier", "design", "adaptation"}}
    request["references"] = [sha256(data).hexdigest() for data, _ in images]
    return brief, images, request


def _evidence(path):
    review = preflight(path)
    with ZipFile(path) as archive:
        quality = json.loads(archive.read("reports/quality.json"))
        names = set(archive.namelist())
        lod_report = (json.loads(archive.read("reports/deformable-lods.json"))
                      if "reports/deformable-lods.json" in names else None)
    base = quality["base"]
    components = ["model", "master"]
    skin = (quality.get("adaptation") or {}).get("skin")
    if review["glb"]["skins"] and base["bones"] and (skin is None or skin["weighted_vertices"] > 0):
        components.append("rig")
    if review["clips"]:
        components.append("animations")
    if review["glb"]["materials"]:
        components.append("materials")
    if review["pbr_status"] in ("opaque_maps_verified", "embedded_opaque_maps_verified"):
        components.append("pbr_maps")
    if lod_report and lod_report["accepted_count"] and lod_report["accepted_count"] == len(review["lods"]):
        components.append("lods")
    findings = set(review["findings"]) | set(quality["findings"])
    return {"components": components, "findings": sorted(findings),
            "lods": [item["mechanically_accepted"] for item in lod_report["attempts"]] if lod_report else []}, review


def _delivery(job, brief, plan, evidence, assessment, preflight_report):
    files = {"asset.zip": job / "asset.zip", "brief.json": job / "brief.json", "plan.json": job / "plan.json",
             **{f"references/{item.name}": item for item in (job / "references").iterdir()}}
    if (job / "original.glb").is_file():
        files["original.glb"] = job / "original.glb"
    if (job / "visual.json").is_file():
        files["visual.json"] = job / "visual.json"
    if (job / "handoff.json").is_file():
        files["handoff.json"] = job / "handoff.json"
    documented = set(evidence["components"])
    visual_status = plan["visual_analysis"]
    if "visual.json" in files:
        measured = _json(files["visual.json"])
        confirmed = sum(row["state"] == "observations_pending_human_confirmation" for row in measured["analyses"])
        visual_status = {"state":"observations_pending_human_confirmation" if confirmed else "blocked",
                         "images_observed":confirmed, "report":"visual.json"}
    inventory = {
        "scope": "isolated_local_review",
        "state": assessment["state"],
        "ready_for_production": False,
        "components": {component: "produced" if component in documented else (
            "blocked" if component in {"pbr_maps", "unreal_import"} or component in assessment["missing_required"]
            else "absent") for component in ("model", "master", "rig", "animations", "materials", "lods",
                                             "pbr_maps", "unreal_import")},
        "original": "preserved_glb" if "original.glb" in files else "synthetic_master_in_asset",
        "license": brief.get("license"),
        "dossier": brief.get("dossier"),
        "reference_usage": "provenance_and_human_comparison" if brief["source"] in ("procedural", "base_glb", "external_glb", "image_guided")
        else "provenance_and_scaled_copy",
        "fidelity_review": plan.get("fidelity_review", "human_required"),
        "external_handoff": "handoff.json" if "handoff.json" in files else None,
        "visual_analysis": visual_status,
        "assessment": assessment,
        "preflight": preflight_report,
    }
    records = {"inventory.json": json_bytes(inventory), "IMPORTAR-NA-UNREAL.txt": (
        "Pré-validação local. Importe models/asset.fbx de asset.zip em um projeto de teste.\n"
        "Confira escala em centímetros, eixo vertical, esqueleto, clipes e materiais.\n"
        "Importe os FBX de LOD como níveis da malha esquelética, se presentes.\n"
        "Compare poses, mapeamento, deformação, aparência e desempenho antes de liberar.\n"
    ).encode("utf-8")}
    manifest = {name: {"sha256": checked_digest(path, MAX_DELIVERY), "bytes": path.stat().st_size}
                for name, path in files.items()}
    manifest.update({name: {"sha256": sha256(data).hexdigest(), "bytes": len(data)} for name, data in records.items()})
    if sum(item["bytes"] for item in manifest.values()) > MAX_DELIVERY:
        raise ValueError("Entrega excede a reserva local.")
    with ZipFile(job / "personagem.zip", "x", ZIP_STORED) as archive:
        for name, path in sorted(files.items()):
            archive.write(path, name)
        for name, data in sorted(records.items()):
            archive.writestr(name, data)
        archive.writestr("manifest.sha256.json", json_bytes(manifest))
    return checked_digest(job / "personagem.zip", MAX_DELIVERY)


def start(args):
    def stage(name):
        if getattr(args, "progress", False):
            print(f"ARVERTES_STAGE {name}", file=sys.stderr, flush=True)

    stage("references")
    brief, images, request = _inputs(args)
    stage("planning")
    atlas = partial(_atlas, args.agents, python=getattr(args, "agents_python", None))
    plan = atlas("plan_character", brief=request)
    selections = brief.get("reference_revisions", [])
    if not isinstance(selections, list) or len(selections) > 12 or (selections and not args.library):
        raise ValueError("Informe revisões específicas e o catálogo local de referências.")
    pins = []
    if selections:
        pins = library_pins(atlas("pin_asset_references",
                                 library=_json(args.library, 48 * 1024), selections=selections))
    plan["library_references"] = pins
    config = read_config(getattr(args, "executor_config", None))
    mode = brief["source"]
    wants_vision = getattr(args, "analyze_visual", False)
    reports, probe_details = inventory(args.blender, config, approved=args.approved,
                                       wants_generation=mode == "image_guided", wants_vision=wants_vision)
    task, input_format, output_format = {
        "image_guided": ("image_3d", images[0][1]["extension"], "glb"),
        "base_glb": ("reuse", "glb", "zip"), "external_glb": ("reuse", "glb", "zip"),
        "synthetic_fixture": ("procedural", "json", "zip"), "procedural": ("procedural", "json", "zip"),
    }[mode]
    choice = atlas("select_production_executor", demand={
        "task": task, "quality": brief["quality"], "input": input_format, "output": output_format,
        "views": len(images), "complexity": getattr(args, "complexity", "simple")}, reports=reports)
    plan["tool_selection"] = choice
    plan["executor_inventory"] = probe_details
    if wants_vision:
        visual_choice = atlas("select_production_executor", demand={
            "task":"vision", "quality":brief["quality"], "input":images[0][1]["extension"], "output":"json",
            "views":len(images), "complexity":"simple"}, reports=reports)
        plan["visual_analysis"] = {"state":"planned" if visual_choice["executor"] else "blocked",
                                   "selection":visual_choice, "details":probe_details["ollama"]}
    fatal_plan = next((step["reason"] for step in plan["steps"]
                       if step["id"] == "mesh" and step["state"] == "blocked"), None)
    if fatal_plan == "image_guided_generator_unavailable" and choice["executor"] == "triposr" and (
            brief["quality"] in ("lite", "low", "medium")):
        fatal_plan = None
        for step in plan["steps"]:
            if step["state"] == "blocked":
                step["state"] = "planned"
                step.pop("reason", None)
        plan["executor"] = "triposr"
    original = read_source(args.base.absolute()) if args.base else None
    handoff = validate_handoff(_json(args.handoff, 8192), original, request["references"]) if args.handoff else None
    root = _directory(args.workspace)
    if disk_usage(root).free < 3 * MAX_DELIVERY:
        raise ValueError("Sentinel bloqueou a produção por reserva de armazenamento.")
    identifier = uuid4().hex
    job = root / identifier
    job.mkdir(mode=0o700)
    _atomic(job / "brief.json", json_bytes(brief))
    _atomic(job / "plan.json", json_bytes(plan))
    source = _directory(job / "references")
    paths = []
    for index, (data, meta) in enumerate(images, 1):
        path = source / f"concept-{index}.{meta['extension']}"
        _atomic(path, data)
        paths.append(path)
    _atomic(source / "library.json", json_bytes(pins))
    if original is not None:
        _atomic(job / "original.glb", original)
    if handoff is not None:
        _atomic(job / "handoff.json", json_bytes(handoff))
    status = {"job": identifier, "state": "blocked", "ready_for_production": False, "cost_brl": 0,
              "plan": "plan.json"}
    if fatal_plan:
        status["reason"] = fatal_plan
    elif not args.approved:
        status["reason"] = "local_execution_requires_operator"
    elif not choice["executor"] or not probe_details["blender_reuse"]["available"]:
        status["reason"] = "executor_or_sentinel_blocked"
    else:
        try:
            if wants_vision:
                stage("vision")
                vision = config.get("ollama")
                visual = [analyze_visual(path, vision["model"], vision["port"], approved=True,
                                         license_reviewed=vision["license_reviewed"]) for path in paths] if (
                                             vision and plan["visual_analysis"]["selection"]["executor"] == "ollama") else []
                _atomic(job / "visual.json", json_bytes({
                    "analyses": visual, "probe": probe_details["ollama"], "review": "human_required",
                    "operator_traits": plan["traits"], "operator_hypotheses": plan["hypotheses"]}))
            if choice["executor"] == "triposr":
                stage("generation")
                entry = config["triposr"]
                target = job / "original.glb"
                result = run_triposr(argparse.Namespace(**{
                    key: Path(entry[key]) for key in ("checkout", "weights", "python")},
                    license_reviewed=entry["license_reviewed"], approved=True, version=entry["version"],
                    image=paths[0], output=target))
                original = read_source(target)
                receipt = _json(target.with_suffix(".handoff.json"), 8192)
                proof = validate_handoff(receipt, original, request["references"])
                _atomic(job / "handoff.json", json_bytes({**proof, "inference_verified_by_studio": True,
                                                         "artifact_generated": result["artifact_generated"]}))
            fixture = brief["source"] == "synthetic_fixture"
            procedural = brief["source"] == "procedural"
            inner = job / "asset.zip"
            stage("blender")
            asset_package.build(argparse.Namespace(
                approved=True, quality=brief["quality"], blender=args.blender, output=inner,
                description=brief["description"], image=paths[0], references=source / "library.json",
                model=job / "original.glb" if original is not None else None,
                recipe="procedural" if procedural else "humanoid", design=brief.get("design"),
                adaptation=brief.get("adaptation"),
                motion_revision=3 if fixture else 1, requirements=None, deformable_lods=fixture,
                proportions=dict(zip(("width", "depth", "height"), brief["proportions"]))
                if brief.get("proportions") is not None else None))
            stage("checking")
            evidence, review = _evidence(inner)
            assessment = atlas("assess_character_result", plan=plan, evidence=evidence)
            stage("packaging")
            digest = _delivery(job, brief, plan, evidence, assessment, review)
            status.update(assessment, sha256=digest)
        except (OSError, ValueError, BadZipFile, subprocess.TimeoutExpired) as error:
            status["reason"] = str(error)
    _atomic(job / "status.json", json_bytes(status))
    return status


def _confirm_visual(job, value):
    if not isinstance(value, list) or len(value) > 32:
        raise ValueError("Lista de observações confirmadas fora do limite.")
    if not value:
        return []
    evidence = _json(job / "visual.json")
    eligible = {(row["reference_sha256"], trait): row["model_sha256"]
                for row in evidence["analyses"] if row.get("state") == "observations_pending_human_confirmation"
                for trait, data in row["traits"].items() if data["state"] == "observed"}
    confirmed = []
    for row in value:
        if (not isinstance(row, dict) or row.keys() != {"reference", "trait"}
                or not all(isinstance(row[key], str) for key in row)
                or (row["reference"], row["trait"]) not in eligible):
            raise ValueError("Confirme apenas observações vinculadas ao modelo e à imagem analisada.")
        selected = {**row, "model_sha256":eligible.pop((row["reference"],row["trait"])),
                    "origin":"operator_confirmation"}
        confirmed.append(selected)
    return confirmed


def review(job, digest, decision, fidelity=None):
    state = _json(job / "status.json")
    if (state["state"] != "awaiting_human_review" or not DIGEST.fullmatch(digest)
            or state.get("sha256") != digest or checked_digest(job / "personagem.zip", MAX_DELIVERY) != digest):
        raise ValueError("A decisão exige um pacote apto à revisão e o SHA-256 exato.")
    brief = _json(job / "brief.json")
    if fidelity is not None and (not isinstance(fidelity, dict)
            or not isinstance(fidelity.get("notes"), str) or not 1 <= len(fidelity["notes"].strip()) <= 1500):
        raise ValueError("Registre uma observação de revisão entre 1 e 1.500 caracteres.")
    if decision == "accept" and brief["source"] in ("procedural", "base_glb", "external_glb", "image_guided"):
        reference_hashes = _json(job / "plan.json")["references"]
        required = {"references", "notes", "verdict"}
        if (not isinstance(fidelity, dict) or not required <= fidelity.keys()
                or fidelity.keys() - required - {"confirmed_observations"}
                or fidelity["references"] != reference_hashes or fidelity["verdict"] != "enough_for_local_review"):
            raise ValueError("Confirme a comparação humana para todas as referências desta revisão.")
        if "confirmed_observations" in fidelity:
            fidelity = {**fidelity, "confirmed_observations":
                        _confirm_visual(job, fidelity["confirmed_observations"])}
    if decision not in ("accept", "reject"):
        raise ValueError("Decisão fora do contrato.")
    result = {"decision": decision, "sha256": digest, "scope": "local_review", "ready_for_production": False}
    if fidelity is not None:
        result["fidelity"] = fidelity
    _atomic(job / "review.json", json_bytes(result))
    return result


class PackageStorage(Protocol):
    def put(self, identifier: str, source: Path, digest: str) -> Path: ...
    def get(self, identifier: str, digest: str) -> Path: ...


class LocalPackages:
    """Implementação local do contrato de publicação e recuperação por revisão imutável."""

    def __init__(self, root):
        self.root = _directory(root)

    def put(self, identifier, source, digest):
        if not IDENTIFIER.fullmatch(identifier) or not DIGEST.fullmatch(digest):
            raise ValueError("Identificador de revisão inválido.")
        folder = _directory(self.root / identifier)
        target = folder / f"{digest}.zip"
        partial = folder / f"{digest}.part"
        with asset_package.package_slot():
            if target.is_symlink() or partial.is_symlink():
                raise ValueError("Destino de transferência inválido.")
            if not target.exists():
                if checked_digest(source, MAX_DELIVERY) != digest:
                    raise ValueError("A origem diverge do SHA-256 aprovado.")
                length = source.stat().st_size
                if ((partial.exists() and (not partial.is_file() or partial.stat().st_size > length))
                        or disk_usage(folder).free < length):
                    raise ValueError("Sentinel bloqueou a transferência local.")
                with source.open("rb") as expected, partial.open("a+b") as copied:
                    copied.seek(0)
                    while chunk := copied.read(BLOCK):
                        if chunk != expected.read(len(chunk)):
                            raise ValueError("Transferência parcial diverge da revisão aprovada.")
                    while chunk := expected.read(BLOCK):
                        copied.write(chunk)
                    copied.flush()
                    os.fsync(copied.fileno())
                if checked_digest(partial, MAX_DELIVERY) != digest:
                    raise ValueError("SHA-256 divergente durante a transferência.")
                os.link(partial, target)
                partial.unlink()
            return self.get(identifier, digest)

    def get(self, identifier, digest):
        if not IDENTIFIER.fullmatch(identifier) or not DIGEST.fullmatch(digest):
            raise ValueError("Identificador de revisão inválido.")
        target = _job(self.root, identifier) / f"{digest}.zip"
        if checked_digest(target, MAX_DELIVERY) != digest:
            raise ValueError("Revisão armazenada falhou na conferência de integridade.")
        return target


def publish(job, store: PackageStorage):
    state = _json(job / "status.json")
    decision = _json(job / "review.json")
    digest = decision.get("sha256")
    source = job / "personagem.zip"
    if (decision["decision"] != "accept" or digest != state.get("sha256")
            or state["state"] != "awaiting_human_review" or checked_digest(source, MAX_DELIVERY) != digest):
        raise ValueError("A revisão precisa ser aprovada localmente e manter a integridade.")
    return store.put(job.name, source, digest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    begin = commands.add_parser("start")
    for key in ("agents", "brief", "blender"):
        begin.add_argument("--" + key, required=True, type=Path)
    begin.add_argument("--agents-python", type=Path, help="Python local do checkout do Agents")
    for key in ("base", "library", "handoff", "executor_config"):
        begin.add_argument("--" + key.replace("_", "-"), type=Path)
    begin.add_argument("--image", required=True, action="append", type=Path)
    begin.add_argument("--approved", action="store_true", help="autoriza a execução local")
    begin.add_argument("--analyze-visual", action="store_true")
    begin.add_argument("--complexity", choices=("simple","detailed"), default="simple")
    begin.add_argument("--progress", action="store_true", help="emite etapas observadas em stderr")
    for command in ("status", "review", "publish", "recover"):
        operation = commands.add_parser(command)
        operation.add_argument("job")
        if command in ("publish", "recover"):
            operation.add_argument("--store", required=True, type=Path)
        if command in ("review", "recover"):
            operation.add_argument("sha256")
        if command == "review":
            operation.add_argument("decision", choices=("accept", "reject"))
            operation.add_argument("--fidelity-report", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            result = start(args)
        elif args.command == "recover":
            result = {"path": str(LocalPackages(args.store).get(args.job, args.sha256)), "sha256": args.sha256}
        else:
            job = _job(args.workspace, args.job)
            if args.command == "review":
                result = review(job, args.sha256, args.decision,
                                _json(args.fidelity_report, 8192) if args.fidelity_report else None)
            elif args.command == "publish":
                result = {"path": str(publish(job, LocalPackages(args.store)))}
            else:
                result = _json(job / "status.json")
                if (job / "review.json").is_file():
                    result["review"] = _json(job / "review.json")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, ValueError, BadZipFile, subprocess.TimeoutExpired) as error:
        parser.exit(2, f"Produção local bloqueada. {error}\n")


if __name__ == "__main__":
    main()
