"""Validação dos formatos de origem, sem acesso à API do Blender."""

import json
import os
from pathlib import Path
from struct import Struct


class ImportValidationError(ValueError):
    """O caminho ou o contêiner do modelo não é compatível."""


_GLB_HEADER = Struct("<4sII")
_CHUNK_HEADER = Struct("<I4s")


def _decode_glb_document(raw: bytes) -> dict:
    try:
        document = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError) as exc:
        raise ImportValidationError("A seção JSON do GLB é inválida.") from exc
    asset = document.get("asset") if isinstance(document, dict) else None
    if not isinstance(asset, dict) or asset.get("version") != "2.0":
        raise ImportValidationError("O documento GLB precisa declarar a versão glTF 2.0.")

    nodes = document.get("nodes", [])
    meshes = document.get("meshes", [])
    if not isinstance(nodes, list) or not isinstance(meshes, list):
        raise ImportValidationError("As listas de nós e malhas do GLB são inválidas.")
    for node in nodes:
        if not isinstance(node, dict):
            raise ImportValidationError("O GLB contém um nó inválido.")
        if "mesh" in node:
            mesh = node["mesh"]
            if type(mesh) is not int or not 0 <= mesh < len(meshes):
                raise ImportValidationError("O GLB contém um nó que referencia uma malha inexistente.")

    return document


def inspect_glb_stream(source, size, *, max_json=None):
    """Lê um contêiner sem alocar a seção geométrica. O chamador controla o size."""
    header = source.read(_GLB_HEADER.size)
    if len(header) != _GLB_HEADER.size:
        raise ImportValidationError("Cabeçalho GLB incompleto.")
    magic, version, declared = _GLB_HEADER.unpack(header)
    if magic != b"glTF" or version != 2:
        raise ImportValidationError("O arquivo precisa ser um GLB 2.0 válido.")
    if size != declared or size < 24:
        raise ImportValidationError("Tamanho inválido no cabeçalho do GLB.")

    document = None
    while source.tell() < size:
        chunk = source.read(_CHUNK_HEADER.size)
        if len(chunk) != _CHUNK_HEADER.size:
            raise ImportValidationError("Cabeçalho de seção GLB incompleto.")
        length, kind = _CHUNK_HEADER.unpack(chunk)
        if length % 4 or source.tell() + length > size:
            raise ImportValidationError("Tamanho inválido em uma seção do GLB.")
        if document is None:
            if kind != b"JSON" or length == 0:
                raise ImportValidationError("A primeira seção do GLB deve conter JSON.")
            if max_json is not None and length > max_json:
                raise ImportValidationError("Metadados GLB acima do limite.")
            document = _decode_glb_document(source.read(length))
        else:
            source.seek(length, os.SEEK_CUR)
    return document


def _validate_glb(path: Path) -> None:
    with path.open("rb") as source:
        inspect_glb_stream(source, os.fstat(source.fileno()).st_size)


_VALIDATORS = {".glb": _validate_glb}


def validate_import_path(filepath: str | os.PathLike) -> Path:
    """Valida um arquivo local e retorna seu caminho absoluto."""
    try:
        path = Path(filepath).expanduser().absolute()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ImportValidationError("Informe um caminho de arquivo válido.") from exc

    validator = _VALIDATORS.get(path.suffix.casefold())
    if validator is None:
        raise ImportValidationError("Formato não suportado. Selecione um arquivo GLB (.glb).")
    try:
        if not path.is_file():
            raise ImportValidationError("O arquivo informado não existe ou não é um arquivo regular.")
        validator(path)
    except OSError as exc:
        raise ImportValidationError("Não foi possível ler o arquivo informado.") from exc
    return path
