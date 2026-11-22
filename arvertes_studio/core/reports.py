"""Gravação local do formato versionado de relatórios."""

import json
import os
from pathlib import Path
import tempfile


SCHEMA_VERSION = 1


class ReportError(ValueError):
    """Falha ao validar ou gravar um relatório."""


def write_report(report, filepath):
    """Grava o JSON em UTF-8 e substitui o destino somente após o sucesso."""
    if not isinstance(report, dict):
        raise ReportError("Informe um relatório com o formato esperado.")
    version = report.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        raise ReportError("A versão do formato do relatório não é suportada.")

    try:
        raw_path = os.fspath(filepath)
    except TypeError as error:
        raise ReportError("Informe o caminho do relatório JSON.") from error
    if not isinstance(raw_path, str) or not raw_path.strip() or "\x00" in raw_path:
        raise ReportError("Informe um caminho válido para o relatório JSON.")

    temporary_path = None
    try:
        destination = Path(raw_path).expanduser()
        if destination.suffix.lower() != ".json":
            raise ReportError("O relatório deve ter a extensão .json.")
        if destination.is_dir():
            raise ReportError("O destino do relatório é uma pasta.")
        if not destination.parent.is_dir():
            raise ReportError("A pasta de destino do relatório não existe.")

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=destination.parent,
            prefix=".arvertes-relatorio-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(report, temporary_file, ensure_ascii=False, indent=2, allow_nan=False)
            temporary_file.write("\n")
        os.replace(temporary_path, destination)
        temporary_path = None
    except ReportError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise ReportError(f"Falha ao gravar o relatório JSON: {error}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return destination
