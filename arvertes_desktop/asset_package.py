"""Comando offline para construir e verificar pacotes locais de assets."""
from argparse import ArgumentParser
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from shutil import disk_usage
import json
import os
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory, gettempdir
from time import monotonic, sleep
from zipfile import BadZipFile, ZIP_STORED, ZipFile

import psutil

from arvertes_studio.core.asset_package import (ACTIVE_QUALITY, MAX_FILE, MAX_IMAGE, MAX_PACKAGE, SAFE_ENTRY,
                                               QUALITY, image_info, json_bytes, library_pins, verify_package)
from .blender_job import checked_digest, fingerprint, read_source
from .resources import MIB, budget, reading, reserve, stop_children
from .settings import validate_blender_path

WORKER = Path(__file__).with_name("blender_worker.py").resolve()


def read_local(path, limit):
    path = path.absolute()
    if path.drive.startswith("\\") or path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("Use um arquivo regular em disco local.")
    with path.open("rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Use um arquivo regular.")
        data = stream.read(limit + 1)
    if not 0 < len(data) <= limit:
        raise ValueError("Entrada vazia ou acima do limite.")
    return data


@contextmanager
def package_slot():
    # OS releases the lock when a process dies. The directory is local to the user.
    if os.name == "nt":
        import msvcrt
        base = Path(os.environ.get("LOCALAPPDATA", gettempdir()))
    else:
        import fcntl
        base = Path(gettempdir()) / f"arvertes-{os.getuid()}"
    base.mkdir(mode=0o700, exist_ok=True)
    if base.is_symlink() or (os.name != "nt" and (
            base.stat().st_uid != os.getuid() or base.stat().st_mode & 0o077)):
        raise ValueError("A pasta de reserva local não é privada.")
    lock = base / "arvertes-blender-package.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    if lock.is_symlink():
        raise ValueError("Reserva de execução inválida.")
    with os.fdopen(os.open(lock, flags, 0o600), "r+b") as handle:
        if os.name == "nt" and not os.fstat(handle.fileno()).st_size:
            handle.write(b"0")
            handle.flush()
            handle.seek(0)
        try:
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError("Sentinel bloqueou: outro pacote Blender está em execução.") from error
        yield


def run_worker(blender, folder):
    ceiling = budget(reading(cpu_interval=0.25))
    log = folder / "blender.log"
    command = [str(blender), "--background", "--factory-startup", "--offline-mode", "--disable-autoexec",
               "--threads", "2", "--python-exit-code", "1", "--python", str(WORKER), "--", str(folder), "package"]
    with log.open("wb") as output, subprocess.Popen(command, cwd=folder, stdin=subprocess.DEVNULL,
                                                    stdout=output, stderr=subprocess.STDOUT) as worker:
        deadline = monotonic() + 90
        try:
            while worker.poll() is None:
                sample = reading()
                if monotonic() >= deadline or log.stat().st_size > 2 * MIB:
                    raise ValueError("Sentinel interrompeu por tempo ou log acima do limite.")
                if sample.available < reserve(sample):
                    raise ValueError("Sentinel interrompeu para preservar a reserva de RAM do sistema.")
                try:
                    process = psutil.Process(worker.pid)
                    processes = [process, *process.children(recursive=True)]
                    used = sum(item.memory_info().rss for item in processes)
                    if used > ceiling * MIB:
                        raise ValueError("Sentinel interrompeu por RAM acima da reserva da tarefa.")
                except psutil.NoSuchProcess:
                    pass
                sleep(0.12)
            if worker.returncode or log.stat().st_size > 2 * MIB:
                with log.open("rb") as stream:
                    stream.seek(max(0, log.stat().st_size - 1600))
                    excerpt = stream.read(1600).decode("utf-8", errors="replace").strip()
                raise ValueError("O Blender interrompeu a produção. " + excerpt)
        finally:
            if worker.poll() is None:
                stop_children(worker.pid)
                worker.kill()
                worker.wait(timeout=5)


def _outputs(folder, quality, mode):
    report = json.loads(read_local(folder / "reports/quality.json", 64 * 1024))
    if (report.get("schema") != 1 or report.get("quality") != quality or report.get("mode") != mode
            or report.get("unreal_import") != "pending" or report.get("artistic_review") != "pending"):
        raise ValueError("Relatório de qualidade incompatível.")
    files = {"models/asset.fbx", "models/preview.glb", "scene/working.blend", "reports/quality.json"}
    triangles = report["base"]["triangles"]
    if type(triangles) is not int or triangles <= 0:
        raise ValueError("Relatório de geometria inválido.")
    for level, lod in enumerate(report["lods"], 1):
        path = f"models/lod{level}.fbx"
        if level > len(QUALITY[quality].lod_ratios) or lod["path"] != path or not 0 < lod["triangles"] < triangles:
            raise ValueError("Um LOD não reduziu a geometria medida.")
        triangles = lod["triangles"]
        files.add(path)
    if len(report["texture_variants"]) > 3:
        raise ValueError("Quantidade de texturas incompatível.")
    for item in report["texture_variants"]:
        path = item["path"]
        if not SAFE_ENTRY.fullmatch(path) or not path.startswith("textures/"):
            raise ValueError("Caminho de textura incompatível.")
        info = image_info(read_local(folder / path, MAX_IMAGE))
        if [info["width"], info["height"]] != item["size"]:
            raise ValueError("Resolução de textura diverge do relatório.")
        files.add(path)
    read_source(folder / "models/preview.glb")
    for name in files:
        if name.endswith(".fbx"):
            with (folder / name).open("rb") as stream:
                if not stream.read(24).startswith(b"Kaydara FBX Binary"):
                    raise ValueError("Saída FBX incompatível.")
    return files


def build(args):
    if not args.approved:
        raise ValueError("Confirme explicitamente a execução local com --approved.")
    if args.quality not in ACTIVE_QUALITY:
        raise ValueError("O nível escolhido é um alvo de planejamento e excede a faixa homologada para execução.")
    blender = validate_blender_path(str(args.blender.absolute()))
    output = args.output.absolute()
    if output.suffix.lower() != ".zip" or output.exists() or output.is_symlink():
        raise ValueError("Escolha um novo arquivo .zip de destino.")
    if disk_usage(output.parent).free < 2 * MAX_PACKAGE:
        raise ValueError("Sentinel bloqueou: a área de trabalho exige pelo menos 192 MiB livres.")
    description = args.description.strip()
    if not 1 <= len(description) <= 2000 or any(ord(c) < 32 and c not in "\r\n\t" for c in description):
        raise ValueError("Informe uma descrição de até 2.000 caracteres.")
    concept = read_local(args.image, MAX_IMAGE)
    image = image_info(concept)
    pins = library_pins(json.loads(read_local(args.references, 32 * 1024))) if args.references else []
    mode = "imported_glb" if args.model else args.recipe
    with package_slot(), TemporaryDirectory(prefix="arvertes-asset-", dir=output.parent) as directory:
        folder = Path(directory)
        (folder / "references").mkdir()
        ref_path = "references/concept." + image["extension"]
        (folder / ref_path).write_bytes(concept)
        (folder / "references/library.json").write_bytes(json_bytes(pins))
        info = {"schema": 1, "description": description, "reference": ref_path, "image": image,
                "mode": mode, "quality": args.quality, "max_cost_centavos": 0}
        if args.model:
            original = read_source(args.model.absolute())
            info["model_sha256"] = fingerprint(original)
            (folder / "source.glb").write_bytes(original)
        (folder / "brief.json").write_bytes(json_bytes(info))
        run_worker(blender, folder)
        files = _outputs(folder, args.quality, mode) | {ref_path, "references/library.json", "brief.json"}
        entries = [{"path": item, "bytes": (folder / item).stat().st_size,
                    "sha256": checked_digest(folder / item, MAX_FILE)} for item in sorted(files)]
        if sum(item["bytes"] for item in entries) > MAX_PACKAGE:
            raise ValueError("Artefatos acima do limite de 96 MiB.")
        manifest = {"schema": 1, "mode": mode, "quality": args.quality, "unreal_import": "pending",
                    "max_cost_centavos": 0, "files": entries}
        temporary = folder / "ready.zip"
        with ZipFile(temporary, "x", ZIP_STORED) as archive:
            for item in entries:
                archive.write(folder / item["path"], item["path"])
            archive.writestr("manifest.json", json_bytes(manifest))
        verify_package(temporary)
        # An atomic, no-overwrite publication on the same filesystem.
        os.link(temporary, output)
    return manifest


def main(argv=None):
    parser = ArgumentParser(description="Produção local de pacotes de assets Arvertes.")
    sub = parser.add_subparsers(dest="action", required=True)
    make = sub.add_parser("build", help="processar no Blender e verificar o ZIP")
    for name in ("blender", "image", "output"):
        make.add_argument("--" + name, required=True, type=Path)
    make.add_argument("--description", required=True)
    make.add_argument("--quality", choices=tuple(QUALITY), default="lite")
    sources = make.add_mutually_exclusive_group(required=True)
    sources.add_argument("--recipe", choices=("static", "rigged"), help="receita sintética explícita")
    sources.add_argument("--model", type=Path, help="GLB local escolhido pelo operador")
    make.add_argument("--references", type=Path, help="lista JSON de revisões licenciadas")
    make.add_argument("--approved", action="store_true")
    check = sub.add_parser("verify", help="verificar inventário e hashes sem extrair")
    check.add_argument("package", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = build(args) if args.action == "build" else verify_package(args.package)
    except (OSError, ValueError, BadZipFile, RecursionError, KeyError, TypeError, psutil.Error) as error:
        print(f"Pacote bloqueado. {error}", file=sys.stderr)
        return 2
    print(json_bytes(manifest).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
