"""Copy our adapter into a pinned checkout. Build-time only; no upstream server."""
from pathlib import Path
from shutil import copyfile
import subprocess
import sys

PIN = "faa1a012b5fbf632c66dc6801c5383e53a542406"
HERE = Path(__file__).resolve().parent

def prepare(upstream):
    upstream = Path(upstream).resolve(strict=True)
    actual = subprocess.check_output(["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True).strip()
    if actual != PIN:
        raise ValueError("Revisão Habblaud não autorizada.")
    copyfile(HERE / "index.html", upstream / "client/index.html")
    copyfile(HERE / "arvertes-preview.ts", upstream / "client/src/arvertes-preview.ts")
    copyfile(HERE / "roster.json", upstream / "client/src/arvertes-roster.json")

if __name__ == "__main__":
    prepare(sys.argv[1])
