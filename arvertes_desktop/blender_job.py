"""Admissão local de uma referência GLB explícita para análise em cópia."""
from hashlib import sha256
import json
from pathlib import Path
from struct import Struct
import os
import stat

from arvertes_studio.core.imports import validate_import_path

MAX_INPUT = 16 * 1024 * 1024
MAX_REPORT = 8 * 1024 * 1024
MAX_COPY = 128 * 1024 * 1024
HEADER = Struct("<4sIII4s")


def read_source(path):
    path = Path(path)
    if not path.is_absolute() or path.suffix.casefold() != ".glb" or path.drive.startswith("\\"):
        raise ValueError("Selecione um GLB de um disco local.")
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("A referência deve ser um arquivo GLB regular.")
    with path.open("rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError("A referência não é um arquivo regular.")
        raw = source.read(MAX_INPUT + 1)
    if len(raw) < HEADER.size or len(raw) > MAX_INPUT:
        raise ValueError("O GLB precisa caber no limite de 16 MiB.")
    magic, version, size, length, kind = HEADER.unpack_from(raw)
    if magic != b"glTF" or version != 2 or size != len(raw) or kind != b"JSON" or length > 2097152:
        raise ValueError("Cabeçalho do GLB fora do limite.")
    try:
        doc = json.loads(raw[HEADER.size:HEADER.size + length])
    except (ValueError, RecursionError) as error:
        raise ValueError("Metadados GLB inválidos.") from error
    if not isinstance(doc, dict) or len(raw) < HEADER.size + length:
        raise ValueError("Documento GLB incompatível.")
    stack = [doc]
    while stack:
        obj = stack.pop()
        if isinstance(obj, dict):
            if "uri" in obj and not (isinstance(obj["uri"], str) and obj["uri"].startswith("data:")):
                raise ValueError("A inspeção exige GLB sem recursos externos.")
            stack.extend(obj.values())
        elif isinstance(obj, list):
            stack.extend(obj)
    nodes, accessors = doc.get("nodes", []), doc.get("accessors", [])
    if (not isinstance(nodes, list) or len(nodes) > 5000 or not isinstance(accessors, list)
            or any(not isinstance(item, dict) or type(item.get("count")) is not int or item["count"] <= 0
                   for item in accessors) or sum(item["count"] for item in accessors) > 3_000_000):
        raise ValueError("A geometria excede o limite da análise local.")
    return raw


def fingerprint(raw):
    return sha256(raw).hexdigest()


def stage(source, expected_hash, folder):
    raw = read_source(source)
    if fingerprint(raw) != expected_hash:
        raise ValueError("A referência mudou desde a autorização. Crie outra inspeção.")
    folder.mkdir(parents=True, exist_ok=False)
    copy = folder / "source.glb"
    with copy.open("xb") as target:
        target.write(raw)
    validate_import_path(copy)
    return copy


def validated_summary(report):
    if not isinstance(report, dict) or type(report.get("schema_version")) is not int or report["schema_version"] != 1:
        raise ValueError("Relatório Blender fora do protocolo.")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("Relatório Blender sem resumo.")
    result = {}
    for key in ("mesh_count", "meshes_without_uv", "meshes_without_materials"):
        value = summary.get(key)
        if type(value) is not int or not 0 <= value <= 10_000:
            raise ValueError("Contagem Blender inválida.")
        result[key] = value
    if (result["meshes_without_uv"] > result["mesh_count"]
            or result["meshes_without_materials"] > result["mesh_count"]):
        raise ValueError("Contagem Blender inconsistente.")
    if type(summary.get("has_armature")) is not bool:
        raise ValueError("Indicador de armadura inválido.")
    result["has_armature"] = summary["has_armature"]
    materials = summary.get("materials")
    if not isinstance(materials, list) or len(materials) > 10000 or any(not isinstance(name, str) for name in materials):
        raise ValueError("Inventário Blender de materiais inválido.")
    result["material_count"] = len(set(materials))
    for key in ("geometry_original", "geometry_evaluated"):
        item = summary.get(key)
        if key == "geometry_evaluated" and item is None:
            result[key] = None
            continue
        value = item.get("triangles") if isinstance(item, dict) else None
        if type(value) is not int or not 0 <= value <= 50_000_000:
            raise ValueError("Total de triângulos inválido.")
        result[key] = {"triangles": value}
    technical = summary.get("technical")
    if technical is not None:
        counts = {"loose_vertices", "loose_edges", "overlapping_edges", "degenerate_faces",
                  "materials", "principled", "armatures", "bones", "actions"}
        if (not isinstance(technical, dict) or set(technical) != counts | {"topology_measured"}
                or type(technical["topology_measured"]) is not bool
                or any(type(technical[key]) is not int or not 0 <= technical[key] <= 10_000_000 for key in counts)
                or technical["materials"] != result["material_count"]
                or technical["principled"] > technical["materials"]):
            raise ValueError("Medição técnica Blender incompatível.")
        result["technical"] = technical
    return {"schema_version": 1, "summary": result}


def checked_digest(path, limit=MAX_COPY):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Cópia inexistente ou acima do limite.")
    checksum = sha256()
    remaining = limit
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            remaining -= len(chunk)
            if remaining < 0:
                raise ValueError("Cópia acima do limite.")
            checksum.update(chunk)
    return checksum.hexdigest()


def stage_export(origin, expected, folder):
    if checked_digest(origin) != expected:
        raise ValueError("Sentinel bloqueou: a cópia foi alterada após a inspeção.")
    folder.mkdir(mode=0o700, exist_ok=False)
    target = folder / "working.blend"
    with origin.open("rb") as stream, target.open("xb") as copy:
        remaining = MAX_COPY
        while chunk := stream.read(1024 * 1024):
            remaining -= len(chunk)
            if remaining < 0:
                raise ValueError("Cópia acima do limite.")
            copy.write(chunk)
    if checked_digest(target) != expected:
        raise ValueError("Sentinel bloqueou: a cópia foi alterada durante a leitura.")


def checked_fbx(folder):
    artifact = folder / "asset.fbx"
    digest = checked_digest(artifact)
    with artifact.open("rb") as stream:
        if not stream.read(24).startswith(b"Kaydara FBX Binary"):
            raise ValueError("O Blender retornou um arquivo FBX incompatível.")
    return digest


def read_result(folder, organize):
    report_path = folder / "report.json"
    with report_path.open("rb") as stream:
        raw = stream.read(MAX_REPORT + 1)
    if len(raw) > MAX_REPORT:
        raise ValueError("Relatório Blender excedeu 8 MiB.")
    report = validated_summary(json.loads(raw))
    if organize:
        result = folder / "working.blend"
        if result.is_symlink() or not result.is_file() or not 0 < result.stat().st_size <= MAX_COPY:
            raise ValueError("Cópia Blender não foi produzida dentro do limite.")
    return report
