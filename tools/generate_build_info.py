from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "pasajes_accesibles_cnrt" / "build_info.py"
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()
    repository = args.repository.strip()
    if not REPOSITORY_RE.fullmatch(repository):
        parser.error("repository debe tener el formato owner/repo")
    TARGET.write_text(
        '"""Información inyectada durante el empaquetado oficial."""\n\n'
        f'GITHUB_REPOSITORY = {repository!r}\n'
        'UPDATE_CHANNEL = "stable"\n',
        encoding="utf-8",
    )
    print(f"Repositorio de actualizaciones: {repository}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
