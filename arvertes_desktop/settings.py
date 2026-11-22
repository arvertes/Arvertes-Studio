"""Configuração local, sem dependências de Qt ou Blender."""
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile


@dataclass(frozen=True)
class Settings:
    blender_path: str = ""


def load_settings(path: Path) -> Settings:
    if not path.exists():
        return Settings()
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or type(data.get("version")) is not int
            or data["version"] != 1 or not isinstance(data.get("blender_path"), str)):
        raise ValueError("Configuração inválida ou incompatível.")
    return Settings(blender_path=data["blender_path"])


def save_settings(path: Path, settings: Settings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as handle:
            temporary = Path(handle.name)
            json.dump({"version": 1, **asdict(settings)}, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_blender_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.name.lower() not in {"blender", "blender.exe"}:
        raise ValueError("Selecione o executável Blender instalado no computador.")
    if not path.is_file():
        raise ValueError("Executável do Blender não encontrado.")
    return path
