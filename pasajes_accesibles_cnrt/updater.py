from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import __version__
from .build_info import GITHUB_REPOSITORY
from .storage import APP_DIR

GITHUB_API = "https://api.github.com"
INSTALLER_PREFIX = "Pasajes_Accesibles_CNRT_Setup_v"
MAX_INSTALLER_BYTES = 900 * 1024 * 1024
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?$")


class UpdateError(RuntimeError):
    """Error controlado durante la comprobación o descarga de actualizaciones."""


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    tag: str
    release_url: str
    notes: str
    installer_name: str
    installer_url: str
    installer_size: int
    sha256: str


def _version_tuple(value: str) -> tuple[int, int, int]:
    match = VERSION_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Versión no válida: {value!r}")
    return tuple(int(group) for group in match.groups())


def is_newer_version(candidate: str, current: str = __version__) -> bool:
    return _version_tuple(candidate) > _version_tuple(current)


def configured_repository() -> str:
    # La compilación oficial debe quedar fijada al repositorio inyectado durante
    # el build. La variable de entorno solo existe como ayuda para ejecutar el
    # código fuente cuando todavía no hay un repositorio oficial incorporado.
    official = GITHUB_REPOSITORY.strip()
    value = official or os.getenv("PASAJES_CNRT_UPDATE_REPOSITORY", "").strip()
    return value if REPOSITORY_RE.fullmatch(value) else ""


def _request_json(url: str, timeout: float = 15.0) -> dict:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Pasajes-Accesibles-CNRT/{__version__}",
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read(2 * 1024 * 1024 + 1)
    except HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("Todavía no hay una versión publicada en GitHub Releases.") from exc
        raise UpdateError(f"GitHub respondió HTTP {exc.code} al buscar actualizaciones.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise UpdateError("No se pudo conectar con GitHub para buscar actualizaciones.") from exc
    if len(payload) > 2 * 1024 * 1024:
        raise UpdateError("La respuesta de actualización de GitHub fue demasiado grande.")
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError("GitHub devolvió una respuesta de actualización no válida.") from exc
    if not isinstance(data, dict):
        raise UpdateError("GitHub devolvió una respuesta de actualización inesperada.")
    return data


def _safe_release_download_prefix(repository: str, tag: str) -> str:
    return f"https://github.com/{repository}/releases/download/{tag}/"


def _asset_sha256(asset: dict) -> str:
    digest = str(asset.get("digest") or "").strip()
    if digest.lower().startswith("sha256:"):
        value = digest.split(":", 1)[1].strip()
        if SHA256_RE.fullmatch(value):
            return value.lower()
    return ""


def _fetch_checksum_asset(url: str, installer_name: str, repository: str, tag: str, timeout: float) -> str:
    prefix = _safe_release_download_prefix(repository, tag)
    if not url.startswith(prefix) or not url.startswith("https://"):
        raise UpdateError("La URL del archivo de comprobación no pertenece al release esperado.")
    request = Request(url, headers={"User-Agent": f"Pasajes-Accesibles-CNRT/{__version__}"})
    try:
        with urlopen(request, timeout=timeout) as response:
            text = response.read(4096).decode("utf-8", errors="strict").strip()
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError) as exc:
        raise UpdateError("No se pudo descargar el SHA-256 de la actualización.") from exc
    first = text.split()[0] if text else ""
    if not SHA256_RE.fullmatch(first):
        raise UpdateError("El SHA-256 publicado para la actualización no es válido.")
    return first.lower()


class GitHubUpdateService:
    def __init__(self, repository: str | None = None, current_version: str = __version__, timeout: float = 15.0):
        self.repository = (repository or configured_repository()).strip()
        self.current_version = current_version
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(REPOSITORY_RE.fullmatch(self.repository))

    def latest(self) -> UpdateInfo | None:
        if not self.configured:
            raise UpdateError(
                "El ejecutable todavía no tiene configurado el repositorio de actualizaciones. "
                "Al construirlo desde GitHub Actions se configura automáticamente."
            )
        data = _request_json(f"{GITHUB_API}/repos/{self.repository}/releases/latest", self.timeout)
        if bool(data.get("draft")) or bool(data.get("prerelease")):
            return None
        tag = str(data.get("tag_name") or "").strip()
        try:
            version_tuple = _version_tuple(tag)
        except ValueError as exc:
            raise UpdateError("El release más reciente de GitHub no usa una versión compatible.") from exc
        version = ".".join(str(x) for x in version_tuple)
        if not is_newer_version(version, self.current_version):
            return None

        installer_name = f"{INSTALLER_PREFIX}{version}.exe"
        assets = data.get("assets") or []
        if not isinstance(assets, list):
            raise UpdateError("GitHub no devolvió una lista válida de archivos del release.")
        installer = next((a for a in assets if isinstance(a, dict) and a.get("name") == installer_name), None)
        if installer is None:
            raise UpdateError(f"La versión {version} no contiene el instalador esperado {installer_name}.")
        installer_url = str(installer.get("browser_download_url") or "")
        prefix = _safe_release_download_prefix(self.repository, tag)
        if not installer_url.startswith(prefix) or not installer_url.startswith("https://"):
            raise UpdateError("La URL del instalador no pertenece al release esperado.")
        try:
            installer_size = int(installer.get("size") or 0)
        except (TypeError, ValueError):
            installer_size = 0
        if installer_size <= 0 or installer_size > MAX_INSTALLER_BYTES:
            raise UpdateError("El tamaño publicado del instalador no es válido.")

        sha256 = _asset_sha256(installer)
        if not sha256:
            checksum_name = installer_name + ".sha256"
            checksum = next((a for a in assets if isinstance(a, dict) and a.get("name") == checksum_name), None)
            if checksum is None:
                raise UpdateError("El release no publica un SHA-256 verificable para el instalador.")
            sha256 = _fetch_checksum_asset(
                str(checksum.get("browser_download_url") or ""),
                installer_name,
                self.repository,
                tag,
                self.timeout,
            )

        release_url = str(data.get("html_url") or "")
        if release_url and not release_url.startswith(f"https://github.com/{self.repository}/releases/"):
            release_url = ""
        notes = str(data.get("body") or "").strip()
        return UpdateInfo(
            version=version,
            tag=tag,
            release_url=release_url,
            notes=notes,
            installer_name=installer_name,
            installer_url=installer_url,
            installer_size=installer_size,
            sha256=sha256,
        )

    def download(self, info: UpdateInfo, progress: Callable[[int, int], None] | None = None) -> Path:
        updates_dir = APP_DIR / "updates"
        updates_dir.mkdir(parents=True, exist_ok=True)
        destination = updates_dir / info.installer_name
        part = destination.with_suffix(destination.suffix + ".part")
        try:
            part.unlink(missing_ok=True)
        except TypeError:  # Python 3.10 compatibility
            if part.exists():
                part.unlink()
        request = Request(info.installer_url, headers={"User-Agent": f"Pasajes-Accesibles-CNRT/{__version__}"})
        digest = hashlib.sha256()
        written = 0
        try:
            with urlopen(request, timeout=max(self.timeout, 30.0)) as response, part.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_INSTALLER_BYTES or written > info.installer_size + 1024:
                        raise UpdateError("La descarga excedió el tamaño publicado para el instalador.")
                    digest.update(chunk)
                    handle.write(chunk)
                    if progress:
                        progress(written, info.installer_size)
        except UpdateError:
            part.unlink(missing_ok=True)
            raise
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            part.unlink(missing_ok=True)
            raise UpdateError("La descarga de la actualización no pudo completarse.") from exc

        if written != info.installer_size:
            part.unlink(missing_ok=True)
            raise UpdateError("El instalador descargado no tiene el tamaño publicado por GitHub.")
        actual = digest.hexdigest().lower()
        if actual != info.sha256.lower():
            part.unlink(missing_ok=True)
            raise UpdateError("El SHA-256 del instalador no coincide. La actualización fue descartada.")
        os.replace(part, destination)
        return destination

    @staticmethod
    def launch_installer(installer: Path) -> None:
        installer = Path(installer).resolve()
        if os.name != "nt":
            raise UpdateError("La instalación automática solo está disponible en Windows.")
        if installer.suffix.lower() != ".exe" or not installer.name.startswith(INSTALLER_PREFIX):
            raise UpdateError("El archivo descargado no tiene el nombre de un instalador válido.")
        try:
            subprocess.Popen(
                [str(installer), "/SP-", "/CLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS"],
                cwd=str(installer.parent),
                close_fds=True,
            )
        except OSError as exc:
            raise UpdateError("Windows no pudo abrir el instalador descargado.") from exc
