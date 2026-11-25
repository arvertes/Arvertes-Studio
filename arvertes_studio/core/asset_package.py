"""Contrato offline para níveis de qualidade, referências e entregas verificáveis."""
from contextlib import contextmanager
from dataclasses import dataclass
from os import fstat
from stat import S_ISREG
from hashlib import sha256
import json
import re
from struct import unpack_from
from zipfile import ZIP_STORED, ZipFile

MIB = 1024 * 1024
MAX_FILE = 32 * MIB
MAX_PACKAGE = 96 * MIB
MAX_IMAGE = 8 * MIB
SHA = re.compile(r"[0-9a-f]{64}")
SAFE_ENTRY = re.compile(r"(?:models/(?:asset|lod[1-3])\.fbx|models/preview\.glb|scene/working\.blend|"
                        r"models/lod[1-3]\.glb|reports/deformable-lods\.json|reports/style\.json|"
                        r"textures/pbr-(?:skin|cloth|leather|hair|metal)-(?:basecolor|normal|orm)-(?:32|64|128|256)\.png|"
                        r"textures/basecolor-(?:[1-9][0-9]{0,3})x[1-9][0-9]{0,3}\.png|"
                        r"references/concept\.(?:png|jpg)|references/library\.json|"
                        r"reports/(?:quality|motion|environment|audio)\.json|audio/(?:cut|crossfade)\.wav|brief\.json)")


@dataclass(frozen=True)
class Quality:
    label: str
    triangle_target: int
    texture_edge: int
    lod_ratios: tuple[float, ...]


QUALITY = {
    "lite": Quality("Lite", 2_000, 256, (.5, .25)),
    "low": Quality("Baixa", 8_000, 512, (.5, .25)),
    "medium": Quality("Média", 25_000, 1024, (.5, .25, .125)),
    "high": Quality("Alta", 60_000, 2048, (.6, .35, .15)),
    "ultra": Quality("Ultra", 120_000, 4096, (.6, .35, .15)),
    "cinematic": Quality("Cinematográfica", 240_000, 8192, (.7, .4, .2)),
}
LEGACY_RECIPES = ("static", "rigged")
RIGGED_RECIPES = ("humanoid", "procedural", "quadruped", "tailed", "winged")
OTHER_RECIPES = ("environment", "materials", "effects")
RECIPES = (*LEGACY_RECIPES, *RIGGED_RECIPES, *OTHER_RECIPES)
ASSET_MODES = (*RECIPES, "imported_glb")
ACTIVE_QUALITY = frozenset(("lite", "low", "medium"))


def image_info(data):
    if not 0 < len(data) <= MAX_IMAGE:
        raise ValueError("A imagem precisa caber em 8 MiB.")
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24 and data[8:16] == b"\x00\x00\x00\rIHDR":
        width, height = unpack_from(">II", data, 16)
        extension = "png"
    elif data.startswith(b"\xff\xd8"):
        position = 2
        width = height = 0
        extension = "jpg"
        for _ in range(256):
            if position + 4 > len(data) or data[position] != 255:
                break
            marker = data[position + 1]
            size = int.from_bytes(data[position + 2:position + 4], "big")
            if marker in (0xDA, 0xD9) or size < 2 or position + 2 + size > len(data):
                break
            if marker in (0xC0, 0xC1, 0xC2) and size >= 8:
                height, width = unpack_from(">HH", data, position + 5)
                break
            position += size + 2
        else:
            raise ValueError("Metadados JPEG acima do limite.")
        if not width:
            raise ValueError("Imagem JPEG inválida.")
    else:
        raise ValueError("Selecione uma referência PNG ou JPEG.")
    if not (0 < width <= 4096 and 0 < height <= 4096 and width * height <= 8_000_000):
        raise ValueError("Resolução fora do limite de segurança.")
    return {"extension": extension, "width": width, "height": height, "sha256": sha256(data).hexdigest()}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")


def library_pins(items):
    fields = {"id", "revision", "category", "source", "license", "sha256", "credit", "usage"}
    if not isinstance(items, list) or len(items) > 16:
        raise ValueError("Selecione até 16 referências aprovadas.")
    seen = set()
    for item in items:
        if (not isinstance(item, dict) or item.keys() != fields
                or any(not isinstance(item[key], str) or not item[key].strip() or len(item[key]) > 200
                       for key in fields - {"revision"})
                or type(item["revision"]) is not int or not 1 <= item["revision"] <= 1000
                or not SHA.fullmatch(item["sha256"]) or item["id"] in seen
                or item["usage"] not in ("reference_only", "reusable")):
            raise ValueError("Referência da biblioteca incompatível ou repetida.")
        seen.add(item["id"])
    return items


def _digest(stream, declared):
    checksum = sha256()
    total = 0
    while chunk := stream.read(MIB):
        total += len(chunk)
        if total > declared:
            raise ValueError("Arquivo do pacote acima do tamanho declarado.")
        checksum.update(chunk)
    if total != declared:
        raise ValueError("Arquivo do pacote truncado.")
    return checksum.hexdigest()


@contextmanager
def open_package(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("O pacote precisa ser um arquivo local regular.")
    with path.open("rb") as stream:
        info = fstat(stream.fileno())
        if not S_ISREG(info.st_mode) or not 22 <= info.st_size <= MAX_PACKAGE + MIB:
            raise ValueError("Pacote incompleto ou acima do limite.")
        stream.seek(-22, 2)
        magic, disk, start, local, total, directory_size, directory_start, comment = unpack_from(
            "<4s4H2IH", stream.read(22))
        if (magic != b"PK\x05\x06" or disk or start or comment or local != total or not 1 <= total <= 56
                or directory_size > 8192 or directory_start + directory_size != stream.tell() - 22):
            raise ValueError("Diretório ZIP fora dos limites.")
        with ZipFile(stream) as archive:
            yield archive, _verify_archive(archive)


def verify_package(path):
    with open_package(path) as (_, manifest):
        return manifest


def _verify_archive(archive):
    entries = archive.infolist()
    names = [entry.filename for entry in entries]
    if (len(entries) > 56 or len(names) != len(set(names)) or
            any(entry.compress_type != ZIP_STORED or not 0 < entry.file_size <= MAX_FILE or
                (entry.filename != "manifest.json" and not SAFE_ENTRY.fullmatch(entry.filename))
                for entry in entries) or sum(entry.file_size for entry in entries) > MAX_PACKAGE):
        raise ValueError("Entradas inesperadas ou acima do limite.")
    if "manifest.json" not in names or archive.getinfo("manifest.json").file_size > 64 * 1024:
        raise ValueError("Manifesto ausente ou acima do limite.")
    manifest = json.loads(archive.read("manifest.json"))
    if (not isinstance(manifest, dict) or manifest.get("schema") != 1
            or type(manifest["schema"]) is not int or manifest.get("unreal_import") != "pending"
            or type(manifest.get("max_cost_centavos")) is not int or manifest["max_cost_centavos"] != 0
            or manifest.get("mode") not in ASSET_MODES
            or not isinstance(manifest.get("quality"), str) or manifest["quality"] not in ACTIVE_QUALITY
            or not isinstance(manifest.get("files"), list) or len(manifest["files"]) > 55):
        raise ValueError("Manifesto incompatível.")
    declared = {}
    for item in manifest["files"]:
        if (not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}
                or not isinstance(item["path"], str) or item["path"] in declared
                or type(item["bytes"]) is not int or not isinstance(item["sha256"], str)
                or not SHA.fullmatch(item["sha256"])):
            raise ValueError("Inventário inválido.")
        declared[item["path"]] = item
    required = {"brief.json", "models/asset.fbx", "models/preview.glb", "scene/working.blend", "reports/quality.json",
                "references/library.json"}
    references = {"references/concept.png", "references/concept.jpg"} & declared.keys()
    if manifest["mode"] in RIGGED_RECIPES:
        required.add("reports/motion.json")
    if manifest["mode"] == "procedural":
        required.add("reports/style.json")
    if manifest["mode"] in OTHER_RECIPES:
        required.add("reports/environment.json")
    if manifest["mode"] == "effects":
        required.update(("audio/cut.wav", "audio/crossfade.wav", "reports/audio.json"))
    if declared.keys() != set(names) - {"manifest.json"} or not required <= declared.keys() or len(references) != 1:
        raise ValueError("O inventário diverge do pacote.")
    for name, expected in declared.items():
        if archive.getinfo(name).file_size != expected["bytes"]:
            raise ValueError("Tamanho divergente em " + name)
        with archive.open(name) as stream:
            if _digest(stream, expected["bytes"]) != expected["sha256"]:
                raise ValueError("SHA-256 divergente em " + name)
    artwork = next(iter(references))
    if (archive.getinfo("brief.json").file_size > 16 * 1024
            or archive.getinfo("reports/quality.json").file_size > 64 * 1024
            or archive.getinfo("references/library.json").file_size > 32 * 1024):
        raise ValueError("Metadados do pacote acima do limite.")
    brief = json.loads(archive.read("brief.json"))
    report = json.loads(archive.read("reports/quality.json"))
    if (not isinstance(brief, dict) or not isinstance(report, dict)
            or any(brief.get(key) != manifest[key] or report.get(key) != manifest[key]
                   for key in ("mode", "quality")) or report.get("unreal_import") != "pending"
            or brief.get("reference") != artwork or not isinstance(brief.get("image"), dict)
            or brief["image"].get("sha256") != declared[artwork]["sha256"]):
        raise ValueError("Briefing, referência ou relatório incompatível com o manifesto.")
    library_pins(json.loads(archive.read("references/library.json")))
    return manifest
