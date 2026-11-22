"""Gera o ZIP local do add-on usando apenas a biblioteca padrão."""

from pathlib import Path
from runpy import run_path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    root = Path(__file__).resolve().parents[1]
    package = root / "arvertes_studio"
    metadata = run_path(str(package / "__init__.py"))["bl_info"]
    version = ".".join(str(part) for part in metadata["version"])
    destination = root / "dist" / f"{package.name}-{version}-dev.zip"
    destination.parent.mkdir(exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for source in sorted(package.rglob("*.py")):
            if "__pycache__" not in source.parts:
                archive.write(source, source.relative_to(root))
    print(destination)


if __name__ == "__main__":
    main()
