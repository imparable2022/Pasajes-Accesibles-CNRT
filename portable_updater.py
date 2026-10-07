from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

PORTABLE_MARKER = ".portable"
PORTABLE_MANIFEST = ".portable-manifest.json"
WAIT_TIMEOUT_MS = 120_000
RETRY_SECONDS = 45


def _wait_for_process(pid: int) -> None:
    if os.name != "nt" or pid <= 0:
        return
    SYNCHRONIZE = 0x00100000
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        return
    try:
        kernel32.WaitForSingleObject(handle, WAIT_TIMEOUT_MS)
    finally:
        kernel32.CloseHandle(handle)


def _retry(action, description: str) -> None:
    deadline = time.monotonic() + RETRY_SECONDS
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            action()
            return
        except OSError as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"No se pudo {description}: {last_error}")


def _safe_remove_tree(path: Path) -> None:
    if not path.exists():
        return
    if not (path / PORTABLE_MARKER).is_file():
        raise RuntimeError("Se rechazó borrar una carpeta que no pertenece a Pasajes Accesibles CNRT portable.")
    _retry(lambda: shutil.rmtree(path), "eliminar la copia anterior")


def _managed_files(root: Path) -> set[str]:
    manifest_path = root / PORTABLE_MANIFEST
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = data.get("files") if isinstance(data, dict) else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("La versión portable actual no tiene un manifiesto válido.") from exc
    if not isinstance(files, list) or not all(isinstance(item, str) and item for item in files):
        raise RuntimeError("La versión portable actual no tiene un manifiesto válido.")
    return {item.replace("\\", "/").casefold() for item in files}


def _preserve_user_files(backup: Path, target: Path, managed: set[str]) -> None:
    for source in backup.rglob("*"):
        if not source.is_file() or source.is_symlink():
            continue
        relative = source.relative_to(backup)
        key = relative.as_posix().casefold()
        if key in managed or relative.name == PORTABLE_MANIFEST:
            continue
        destination = target / relative
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _replace_portable(source: Path, target: Path, app_name: str) -> None:
    source = source.resolve()
    target = target.resolve()
    if source.parent != target.parent:
        raise RuntimeError("La actualización portable no está en la misma unidad que la aplicación.")
    if not (source / PORTABLE_MARKER).is_file() or not (target / PORTABLE_MARKER).is_file():
        raise RuntimeError("No se reconoció una carpeta portable válida.")
    if not (source / app_name).is_file():
        raise RuntimeError("La nueva versión no contiene el ejecutable principal.")
    if not (source / PORTABLE_MANIFEST).is_file():
        raise RuntimeError("La nueva versión no contiene su manifiesto portable.")
    managed = _managed_files(target)

    backup = target.parent / f".{target.name}.previous"
    _safe_remove_tree(backup)

    _retry(lambda: os.replace(target, backup), "guardar temporalmente la versión anterior")
    try:
        _retry(lambda: os.replace(source, target), "activar la nueva versión")
        _preserve_user_files(backup, target, managed)
    except Exception:
        try:
            if target.exists():
                failed = target.parent / f".{target.name}.failed"
                _safe_remove_tree(failed)
                os.replace(target, failed)
            if backup.exists():
                os.replace(backup, target)
        finally:
            raise

    try:
        process = subprocess.Popen([str(target / app_name)], cwd=str(target), close_fds=True)
    except OSError:
        failed = target.parent / f".{target.name}.failed"
        try:
            _safe_remove_tree(failed)
            os.replace(target, failed)
            os.replace(backup, target)
        finally:
            try:
                subprocess.Popen([str(target / app_name)], cwd=str(target), close_fds=True)
            except OSError:
                pass
        raise

    # Si Windows pudo iniciar la nueva aplicación, ya no necesitamos la copia
    # anterior. Se deja un pequeño margen para que el proceso termine de cargar.
    time.sleep(3)
    if process.poll() is None:
        try:
            _safe_remove_tree(backup)
        except Exception:
            # Una copia anterior que no pudo borrarse no invalida la actualización.
            pass


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--wait-pid", type=int, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--app", required=True)
    args = parser.parse_args()

    try:
        _wait_for_process(args.wait_pid)
        _replace_portable(Path(args.source), Path(args.target), args.app)
        return 0
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
