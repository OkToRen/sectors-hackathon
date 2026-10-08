"""Read local settings from the environment or a .env file, treated as data only."""

import os
from collections.abc import Mapping
from pathlib import Path


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip("'\"")
    return values


def setting(name: str, env_file: Path, environ: Mapping[str, str] = os.environ) -> str:
    return environ.get(name) or read_env_file(env_file).get(name, "")
