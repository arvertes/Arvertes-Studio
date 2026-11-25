"""Verifica pacote portátil sem extrair, executar ou substituir arquivos."""
from hashlib import sha256
from pathlib import Path
import json
import re
from zipfile import BadZipFile, ZipFile

VERSION = "0.2.4"
REVISION = re.compile(r"[a-f0-9]{40}")
SEMVER = re.compile(r"(?:0|[1-9][0-9]{0,4})\.(?:0|[1-9][0-9]{0,4})\.(?:0|[1-9][0-9]{0,4})")
MAX_ARCHIVE = 750 * 1024 * 1024
MEMBER = "ArvertesStudio/_internal/arvertes_desktop/portable-version.json"


def read_small(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Selecione um manifesto regular.")
    with path.open("rb") as stream:
        return stream.read(4097)


def verify(archive, manifest, cancelled=lambda: False):
    archive = Path(archive)
    if archive.suffix.lower() != ".zip" or archive.is_symlink() or not archive.is_file() or not 0 < archive.stat().st_size <= MAX_ARCHIVE:
        raise ValueError("Selecione um ZIP portátil de até 750 MiB.")
    raw = read_small(manifest)
    if len(raw) > 4096:
        raise ValueError("Manifesto acima do limite.")
    record = json.loads(raw)
    if (not isinstance(record, dict) or set(record) != {"platform", "version", "revision", "sha256"}
            or record["platform"] != "windows-x64" or not all(isinstance(item, str) for item in record.values())
            or not SEMVER.fullmatch(record["version"]) or not REVISION.fullmatch(record["revision"])
            or not re.fullmatch(r"[a-f0-9]{64}", record["sha256"])):
        raise ValueError("Manifesto de atualização incompatível.")
    checksum = sha256()
    with archive.open("rb") as stream:
        remaining = MAX_ARCHIVE
        while chunk := stream.read(1024 * 1024):
            if cancelled():
                raise ValueError("Verificação interrompida.")
            remaining -= len(chunk)
            if remaining < 0:
                raise ValueError("ZIP acima do limite.")
            checksum.update(chunk)
        if checksum.hexdigest() != record["sha256"]:
            raise ValueError("O SHA-256 do ZIP diverge do manifesto.")
        try:
            stream.seek(0)
            with ZipFile(stream) as archive_file:
                members = [item for item in archive_file.infolist() if item.filename == MEMBER]
                if len(members) != 1 or members[0].file_size > 4096:
                    raise ValueError("Metadados internos ausentes ou ambíguos.")
                with archive_file.open(members[0]) as source:
                    embedded = json.loads(source.read(4097))
        except BadZipFile as error:
            raise ValueError("ZIP portátil inválido.") from error
    if embedded != {key: record[key] for key in ("platform", "version", "revision")}:
        raise ValueError("Os metadados internos divergem do manifesto.")
    current, candidate = (tuple(map(int, value.split("."))) for value in (VERSION, record["version"]))
    comparison = "mais recente" if candidate > current else "anterior (retorno manual)" if candidate < current else "igual"
    return f"Integridade conferida. Versão {record['version']} {comparison}, revisão {record['revision'][:7]}."
