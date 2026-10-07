from __future__ import annotations

import argparse
import json
from pathlib import Path

MANIFEST_NAME = ".portable-manifest.json"


def build_manifest(root: Path, version: str) -> dict:
    root = root.resolve()
    files = []
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix().casefold()):
        if not path.is_file() or path.name == MANIFEST_NAME:
            continue
        files.append(path.relative_to(root).as_posix())
    return {"version": version, "files": files}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    root = Path(args.root)
    manifest = build_manifest(root, args.version)
    (root / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
