"""Armazenamento experimental de arquivos em segmentos, em disco local."""
from argparse import ArgumentParser
from contextlib import closing, contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
from shutil import disk_usage
import sqlite3
import stat
from tempfile import NamedTemporaryFile

from arvertes_studio.core.asset_package import SHA, json_bytes

MIB = 1024*1024
BLOCK = MIB
MAX_SEGMENTS = 4096
DEFAULT_QUOTA = 256*MIB
APP_ID = 0x41525439


def _read_file(path):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
    if path.is_symlink():
        raise ValueError("Arquivo fora do armazenamento local.")
    stream = os.fdopen(os.open(path, flags), "rb")
    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
        stream.close()
        raise ValueError("Use um arquivo regular.")
    return stream


def _hash_bytes(stream, size, target=None, aggregate=None):
    checksum = sha256()
    while size:
        data = stream.read(min(BLOCK, size))
        if not data:
            raise ValueError("Segmento incompleto.")
        size -= len(data)
        checksum.update(data)
        if aggregate is not None:
            aggregate.update(data)
        if target is not None:
            target.write(data)
    return checksum.hexdigest()


def _manifest(value, quota):
    if (not isinstance(value, dict) or value.keys() != {"schema", "size", "sha256", "parts"}
            or type(value["schema"]) is not int or value["schema"] != 1 or type(value["size"]) is not int
            or not 0 < value["size"] <= quota or not isinstance(value["sha256"], str)
            or not SHA.fullmatch(value["sha256"]) or not isinstance(value["parts"], list)
            or not 1 <= len(value["parts"]) <= MAX_SEGMENTS):
        raise ValueError("Manifesto de transferência fora da cota.")
    if any(not isinstance(part, dict) or part.keys() != {"size", "sha256"}
           or type(part["size"]) is not int or not 0 < part["size"] <= 64*MIB
           or not isinstance(part["sha256"], str) or not SHA.fullmatch(part["sha256"]) for part in value["parts"]):
        raise ValueError("Manifesto contém segmento incompatível.")
    if sum(part["size"] for part in value["parts"]) != value["size"]:
        raise ValueError("Tamanho dos segmentos diverge do arquivo.")
    return json_bytes(value)


def describe(path, segment_size=4*MIB, quota=DEFAULT_QUOTA):
    if type(segment_size) is not int or not MIB <= segment_size <= 64*MIB:
        raise ValueError("Escolha segmentos de 1 a 64 MiB.")
    with _read_file(path) as stream:
        remaining = os.fstat(stream.fileno()).st_size
        if not 0 < remaining <= quota or (remaining+segment_size-1)//segment_size > MAX_SEGMENTS:
            raise ValueError("O arquivo ultrapassa a cota ou a quantidade de segmentos.")
        size = remaining
        parts, digest = [], sha256()
        while remaining:
            amount = min(segment_size, remaining)
            result = _hash_bytes(stream, amount, aggregate=digest)
            parts.append({"size":amount, "sha256":result})
            remaining -= amount
        if stream.read(1):
            raise ValueError("O arquivo mudou durante a leitura.")
    return {"schema":1, "size":size, "sha256":digest.hexdigest(), "parts":parts}


def _sync_folder(path):
    if os.name != "nt":
        handle = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(handle)
        finally:
            os.close(handle)


@contextmanager
def _stage(folder):
    with NamedTemporaryFile(prefix=".segment-", dir=folder, delete=False) as stream:
        path = Path(stream.name)
        try:
            yield stream, path
        finally:
            stream.close()
            path.unlink(missing_ok=True)


class Segments:
    def __init__(self, root, quota=DEFAULT_QUOTA):
        if type(quota) is not int or not MIB <= quota <= 2**53-1:
            raise ValueError("Cota deve ser um inteiro de pelo menos 1 MiB.")
        self.root, self.quota = root.absolute(), quota
        self.root.mkdir(mode=0o700, exist_ok=True, parents=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError("Selecione um diretório local de transferência.")
        self.db = self.root / "arvertes-parts.sqlite3"
        if self.db.is_symlink() or self.db.exists() and not self.db.is_file():
            raise ValueError("Banco de transferência fora do diretório local.")
        with self._transaction() as db:
            identifier = db.execute("PRAGMA application_id").fetchone()[0]
            if identifier != APP_ID:
                if identifier or db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone():
                    raise ValueError("O arquivo SQLite pertence a outro aplicativo.")
                db.execute(f"PRAGMA application_id = {APP_ID}")
            db.execute("""CREATE TABLE IF NOT EXISTS transfers(
                id TEXT PRIMARY KEY, manifest BLOB NOT NULL, budget INTEGER NOT NULL, done INTEGER NOT NULL DEFAULT 0
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS parts(
                id TEXT NOT NULL, part INTEGER NOT NULL, PRIMARY KEY(id,part),
                FOREIGN KEY(id) REFERENCES transfers(id)
            )""")

    @contextmanager
    def _transaction(self):
        with closing(sqlite3.connect(self.db, timeout=10)) as db, db:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("BEGIN IMMEDIATE")
            yield db

    def _folder(self, identifier):
        if not isinstance(identifier, str) or not SHA.fullmatch(identifier):
            raise ValueError("Identificador de transferência inválido.")
        folder = self.root / identifier
        if folder.is_symlink():
            raise ValueError("Diretório da transferência inválido.")
        return folder

    def begin(self, manifest):
        raw = _manifest(manifest, self.quota)
        identifier = sha256(raw).hexdigest()
        folder = self._folder(identifier)
        with self._transaction() as db:
            if not db.execute("SELECT 1 FROM transfers WHERE id=?", (identifier,)).fetchone():
                # Reserve space for segments and the assembled file during promotion.
                reservation = 2*manifest["size"]
                used = db.execute("SELECT COALESCE(SUM(budget),0) FROM transfers").fetchone()[0]
                if used + reservation > self.quota or disk_usage(self.root).free < reservation:
                    raise ValueError("Cota de armazenamento segmentado insuficiente.")
                folder.mkdir(mode=0o700, exist_ok=True)
                db.execute("INSERT INTO transfers(id,manifest,budget) VALUES (?,?,?)",
                           (identifier,raw,reservation))
        return identifier

    def _load(self, db, identifier):
        row = db.execute("SELECT manifest,done FROM transfers WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise ValueError("Transferência desconhecida.")
        return json.loads(row[0]), bool(row[1])

    def status(self, identifier):
        self._folder(identifier)
        with self._transaction() as db:
            manifest, done = self._load(db, identifier)
            received = {row[0] for row in db.execute("SELECT part FROM parts WHERE id=?", (identifier,))}
        return {"id":identifier, "state":"complete" if done else "receiving",
                "missing":[part for part in range(len(manifest["parts"])) if part not in received],
                "sha256":manifest["sha256"], "size":manifest["size"]}

    def _check(self, path, part, *, target=None, aggregate=None):
        with _read_file(path) as source:
            value = _hash_bytes(source, part["size"], target=target, aggregate=aggregate)
            if source.read(1) or value != part["sha256"]:
                raise ValueError("SHA-256 ou tamanho do segmento divergente.")

    def _receive(self, identifier, index, source, *, reject_suffix):
        folder = self._folder(identifier)
        with self._transaction() as db:
            manifest, done = self._load(db, identifier)
            if type(index) is not int or not 0 <= index < len(manifest["parts"]):
                raise ValueError("Índice de segmento fora do manifesto.")
            part = manifest["parts"][index]
            target = folder / f"{index:08d}.part"
            if target.is_symlink():
                raise ValueError("Destino do segmento inválido.")
            if target.exists():
                self._check(target, part)
            elif done:
                raise ValueError("Inventário concluído perdeu um segmento.")
            else:
                with _stage(folder) as (stream, temporary):
                    if (_hash_bytes(source, part["size"], target=stream) != part["sha256"]
                            or reject_suffix and source.read(1)):
                        raise ValueError("Bytes do segmento divergem do manifesto.")
                    stream.flush()
                    os.fsync(stream.fileno())
                    stream.close()
                    os.link(temporary, target)
                    _sync_folder(folder)
            db.execute("INSERT OR IGNORE INTO parts VALUES (?,?)", (identifier,index))

    def receive(self, identifier, index, path):
        with _read_file(path) as source:
            self._receive(identifier, index, source, reject_suffix=True)

    def copy_missing(self, identifier, path, *, max_parts=None):
        if max_parts is not None and (type(max_parts) is not int or not 1 <= max_parts <= MAX_SEGMENTS):
            raise ValueError("Limite de segmentos inválido.")
        status = self.status(identifier)
        with self._transaction() as db:
            manifest, _ = self._load(db, identifier)
        with _read_file(path) as source:
            if os.fstat(source.fileno()).st_size != manifest["size"]:
                raise ValueError("A origem deve ter o tamanho declarado.")
            offset = 0
            missing = set(status["missing"][:max_parts])
            for index, item in enumerate(manifest["parts"]):
                if index in missing:
                    source.seek(offset)
                    self._receive(identifier, index, source, reject_suffix=False)
                offset += item["size"]
        return self.status(identifier)

    def finalize(self, identifier):
        folder = self._folder(identifier)
        with self._transaction() as db:
            manifest, _ = self._load(db, identifier)
            final = folder / "artifact.bin"
            if final.is_symlink():
                raise ValueError("Destino final inválido.")
            if final.exists():
                self._check(final, manifest)
            else:
                if db.execute("SELECT COUNT(*) FROM parts WHERE id=?", (identifier,)).fetchone()[0] != len(manifest["parts"]):
                    raise ValueError("A transferência tem segmentos pendentes.")
                checksum = sha256()
                with _stage(folder) as (target, temporary):
                    for index, part in enumerate(manifest["parts"]):
                        self._check(folder / f"{index:08d}.part", part, target=target, aggregate=checksum)
                    if checksum.hexdigest() != manifest["sha256"]:
                        raise ValueError("O SHA-256 final diverge da revisão.")
                    target.flush()
                    os.fsync(target.fileno())
                    target.close()
                    os.link(temporary, final)
                    _sync_folder(folder)
            db.execute("UPDATE transfers SET done=1 WHERE id=?", (identifier,))
        return final


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--quota-mib", type=int, default=256)
    actions = parser.add_subparsers(dest="action", required=True)
    register = actions.add_parser("begin")
    register.add_argument("source", type=Path)
    register.add_argument("--segment-mib", type=int, default=4)
    for name in ("status","copy","put","finalize"):
        operation = actions.add_parser(name)
        operation.add_argument("id")
        if name in ("copy","put"):
            operation.add_argument("source", type=Path)
        if name == "copy":
            operation.add_argument("--max-parts", type=int)
        if name == "put":
            operation.add_argument("index", type=int)
    try:
        args = parser.parse_args()
        store = Segments(args.workspace, args.quota_mib*MIB)
        if args.action == "begin":
            manifest = describe(args.source, args.segment_mib*MIB, store.quota)
            result = {"id":store.begin(manifest), "manifest":manifest}
        elif args.action == "copy":
            result = store.copy_missing(args.id,args.source,max_parts=args.max_parts)
        elif args.action == "put":
            store.receive(args.id,args.index,args.source)
            result = store.status(args.id)
        elif args.action == "finalize":
            result = {"path":str(store.finalize(args.id)), **store.status(args.id)}
        else:
            result = store.status(args.id)
        print(json_bytes(result).decode(), end="")
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(2, f"Transferência bloqueada. {error}\n")


if __name__ == "__main__":
    main()
