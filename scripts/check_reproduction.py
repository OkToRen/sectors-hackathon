"""Rebuild the app in a clean copy with no network and no secrets: python scripts/check_reproduction.py

Copies only what a checkout plus the shared cache contains, strips SECTORS_* variables, blocks every socket
connection in the child process, and compares the generated pages with the ones in dist/."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPIED = ("sectors", "scripts", "app", "research", "cache")
BLOCK_NETWORK = """
import socket
def _refuse(*args, **kwargs):
    raise OSError("network blocked by the reproduction check")
socket.socket.connect = _refuse
socket.create_connection = _refuse
"""
# Only the build timestamp may differ between two builds of the same cache.
STAMP = re.compile(r'"generated_at": "[^"]*"|Snapshot generated <time>[^<]*</time>')


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp)
        for name in COPIED:
            shutil.copytree(ROOT / name, clean / name, ignore=shutil.ignore_patterns("__pycache__"))
        (clean / "sitecustomize.py").write_text(BLOCK_NETWORK)
        env = {k: v for k, v in os.environ.items() if not k.startswith("SECTORS_")}
        env["PYTHONPATH"] = str(clean)
        run = subprocess.run([sys.executable, "scripts/build_snapshot.py"], cwd=clean, env=env,
                             capture_output=True, text=True)
        if run.returncode != 0:
            print(f"Build failed:\n{run.stdout}{run.stderr}", file=sys.stderr)
            return 1
        built = sorted(p.name for p in (clean / "dist").iterdir())
        published = sorted(p.name for p in (ROOT / "dist").iterdir())
        different = [name for name in built if name.endswith((".html", ".json"))
                     and STAMP.sub("", (clean / "dist" / name).read_text())
                     != STAMP.sub("", (ROOT / "dist" / name).read_text())]
        members = len(json.loads((clean / "dist" / "roster.json").read_text())["members"])
        print(f"{run.stdout.strip()} No network, no SECTORS_* variables, no .env.")
        print(f"{members} members; {len(built)} files built, {len(published)} in dist/; "
              f"{len(different)} differ from dist/ beyond the timestamp{': ' + ', '.join(different) if different else ''}.")
        return 0 if built == published and not different else 1


if __name__ == "__main__":
    raise SystemExit(main())
