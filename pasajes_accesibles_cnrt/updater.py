from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import __version__
from .build_info import GITHUB_REPOSITORY
from .storage import APP_DIR

GITHUB_API = "https://api.github.com"
INSTALLER_ASSET = "Pasajes_Accesibles_CNRT_Setup.exe"
PORTABLE_ASSET = "Pasajes_Accesibles_CNRT_Portable.zip"
PORTABLE_MARKER = ".portable"
PORTABLE_HELPER = "PasajesPortableUpdater.exe"
PORTABLE_MANIFEST = ".portable-manifest.json"
APP_EXECUTABLE = "Pasajes Accesibles CNRT.exe"
CHANNEL_INSTALLER = "installer"
CHANNEL_PORTABLE = "portable"
MAX_UPDATE_BYTES = 1200 * 1024 * 1024
MAX_PORTABLE_UNPACKED_BYTES = 2500 * 1024 * 1024
MAX_PORTABLE_MEMBERS = 25000
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
    channel: str
    asset_name: str
    asset_url: str
    asset_size: int
    sha256: str


@dataclass(frozen=True)
class PortablePreparedUpdate:
    version: str
    staging_root: Path
    portable_root: Path


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


def portable_root() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    root = Path(sys.executable).resolve().parent
    return root if (root / PORTABLE_MARKER).is_file() else None


def detect_update_channel() -> str:
    return CHANNEL_PORTABLE if portable_root() is not None else CHANNEL_INSTALLER


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


def _fetch_checksum_asset(url: str, repository: str, tag: str, timeout: float) -> str:
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


def _expected_asset_name(channel: str) -> str:
    if channel == CHANNEL_PORTABLE:
        return PORTABLE_ASSET
    if channel == CHANNEL_INSTALLER:
        return INSTALLER_ASSET
    raise UpdateError("El canal de actualización no es válido.")


def _safe_zip_path(name: str) -> PurePosixPath:
    if not name or "\\" in name or "\x00" in name:
        raise UpdateError("El paquete portable contiene una ruta no válida.")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise UpdateError("El paquete portable contiene una ruta insegura.")
    if any(":" in part for part in path.parts):
        raise UpdateError("El paquete portable contiene una ruta incompatible con Windows.")
    return path


def _zip_member_is_symlink(member: zipfile.ZipInfo) -> bool:
    mode = (member.external_attr >> 16) & 0o170000
    return mode == stat.S_IFLNK


class GitHubUpdateService:
    def __init__(
        self,
        repository: str | None = None,
        current_version: str = __version__,
        timeout: float = 15.0,
        channel: str | None = None,
    ):
        self.repository = (repository or configured_repository()).strip()
        self.current_version = current_version
        self.timeout = timeout
        self.channel = channel or detect_update_channel()
        if self.channel not in (CHANNEL_INSTALLER, CHANNEL_PORTABLE):
            raise ValueError(f"Canal de actualización no válido: {self.channel!r}")

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

        asset_name = _expected_asset_name(self.channel)
        assets = data.get("assets") or []
        if not isinstance(assets, list):
            raise UpdateError("GitHub no devolvió una lista válida de archivos del release.")
        asset = next((a for a in assets if isinstance(a, dict) and a.get("name") == asset_name), None)
        if asset is None:
            label = "portable" if self.channel == CHANNEL_PORTABLE else "instalador"
            raise UpdateError(f"La versión {version} no contiene el {label} esperado {asset_name}.")
        asset_url = str(asset.get("browser_download_url") or "")
        prefix = _safe_release_download_prefix(self.repository, tag)
        if not asset_url.startswith(prefix) or not asset_url.startswith("https://"):
            raise UpdateError("La URL de la actualización no pertenece al release esperado.")
        try:
            asset_size = int(asset.get("size") or 0)
        except (TypeError, ValueError):
            asset_size = 0
        if asset_size <= 0 or asset_size > MAX_UPDATE_BYTES:
            raise UpdateError("El tamaño publicado de la actualización no es válido.")

        sha256 = _asset_sha256(asset)
        if not sha256:
            checksum_name = asset_name + ".sha256"
            checksum = next((a for a in assets if isinstance(a, dict) and a.get("name") == checksum_name), None)
            if checksum is None:
                raise UpdateError("El release no publica un SHA-256 verificable para esta actualización.")
            sha256 = _fetch_checksum_asset(
                str(checksum.get("browser_download_url") or ""),
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
            channel=self.channel,
            asset_name=asset_name,
            asset_url=asset_url,
            asset_size=asset_size,
            sha256=sha256,
        )

    def download(self, info: UpdateInfo, progress: Callable[[int, int], None] | None = None) -> Path:
        if info.channel != self.channel:
            raise UpdateError("La actualización descargada pertenece a otro canal de distribución.")
        updates_dir = APP_DIR / "updates"
        updates_dir.mkdir(parents=True, exist_ok=True)
        destination = updates_dir / info.asset_name
        part = destination.with_suffix(destination.suffix + ".part")
        try:
            part.unlink(missing_ok=True)
        except TypeError:  # Python 3.10 compatibility
            if part.exists():
                part.unlink()
        request = Request(info.asset_url, headers={"User-Agent": f"Pasajes-Accesibles-CNRT/{__version__}"})
        digest = hashlib.sha256()
        written = 0
        try:
            with urlopen(request, timeout=max(self.timeout, 30.0)) as response, part.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_UPDATE_BYTES or written > info.asset_size + 1024:
                        raise UpdateError("La descarga excedió el tamaño publicado para la actualización.")
                    digest.update(chunk)
                    handle.write(chunk)
                    if progress:
                        progress(written, info.asset_size)
        except UpdateError:
            part.unlink(missing_ok=True)
            raise
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            part.unlink(missing_ok=True)
            raise UpdateError("La descarga de la actualización no pudo completarse.") from exc

        if written != info.asset_size:
            part.unlink(missing_ok=True)
            raise UpdateError("La actualización descargada no tiene el tamaño publicado por GitHub.")
        actual = digest.hexdigest().lower()
        if actual != info.sha256.lower():
            part.unlink(missing_ok=True)
            raise UpdateError("El SHA-256 de la actualización no coincide. La descarga fue descartada.")
        os.replace(part, destination)
        return destination

    @staticmethod
    def launch_installer(installer: Path) -> None:
        installer = Path(installer).resolve()
        if os.name != "nt":
            raise UpdateError("La instalación automática solo está disponible en Windows.")
        if installer.suffix.lower() != ".exe" or installer.name != INSTALLER_ASSET:
            raise UpdateError("El archivo descargado no tiene el nombre de un instalador válido.")
        try:
            subprocess.Popen(
                [str(installer), "/SP-", "/CLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS"],
                cwd=str(installer.parent),
                close_fds=True,
            )
        except OSError as exc:
            raise UpdateError("Windows no pudo abrir el instalador descargado.") from exc

    def prepare_portable_update(
        self,
        archive: Path,
        info: UpdateInfo,
        portable_dir: Path | None = None,
    ) -> PortablePreparedUpdate:
        if info.channel != CHANNEL_PORTABLE or self.channel != CHANNEL_PORTABLE:
            raise UpdateError("Este paquete no corresponde al canal portable.")
        archive = Path(archive).resolve()
        if archive.suffix.lower() != ".zip" or archive.name != info.asset_name:
            raise UpdateError("El archivo descargado no tiene el nombre del paquete portable esperado.")
        root = Path(portable_dir).resolve() if portable_dir is not None else portable_root()
        if root is None or not (root / PORTABLE_MARKER).is_file():
            raise UpdateError("No se pudo identificar una instalación portable válida.")
        if not (root / PORTABLE_HELPER).is_file():
            raise UpdateError("La versión portable actual no contiene su actualizador auxiliar.")

        staging = Path(
            tempfile.mkdtemp(
                prefix=f".Pasajes_Accesibles_CNRT_update_{info.version}_{uuid.uuid4().hex[:8]}_",
                dir=str(root.parent),
            )
        ).resolve()
        try:
            with zipfile.ZipFile(archive, "r") as zf:
                members = zf.infolist()
                if not members or len(members) > MAX_PORTABLE_MEMBERS:
                    raise UpdateError("El paquete portable tiene una cantidad de archivos no válida.")
                total_unpacked = sum(max(0, int(member.file_size)) for member in members)
                if total_unpacked > MAX_PORTABLE_UNPACKED_BYTES:
                    raise UpdateError("El paquete portable excede el tamaño máximo permitido al descomprimirse.")

                parsed: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
                roots: set[str] = set()
                relative_names: set[str] = set()
                for member in members:
                    path = _safe_zip_path(member.filename.rstrip("/"))
                    if _zip_member_is_symlink(member):
                        raise UpdateError("El paquete portable contiene un enlace simbólico no permitido.")
                    roots.add(path.parts[0])
                    if len(path.parts) == 1:
                        continue
                    relative = PurePosixPath(*path.parts[1:])
                    key = relative.as_posix().casefold()
                    if key in relative_names and not member.is_dir():
                        raise UpdateError("El paquete portable contiene archivos duplicados.")
                    relative_names.add(key)
                    parsed.append((member, relative))
                if len(roots) != 1:
                    raise UpdateError("El paquete portable debe contener una única carpeta raíz.")

                for member, relative in parsed:
                    destination = staging.joinpath(*relative.parts)
                    if member.is_dir():
                        destination.mkdir(parents=True, exist_ok=True)
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    resolved_parent = destination.parent.resolve()
                    if os.path.commonpath([str(staging), str(resolved_parent)]) != str(staging):
                        raise UpdateError("El paquete portable intentó escribir fuera de su carpeta temporal.")
                    with zf.open(member, "r") as source, destination.open("wb") as target:
                        shutil.copyfileobj(source, target, length=1024 * 1024)

            required = [
                staging / PORTABLE_MARKER,
                staging / PORTABLE_MANIFEST,
                staging / APP_EXECUTABLE,
                staging / PORTABLE_HELPER,
            ]
            if not all(path.is_file() for path in required):
                raise UpdateError("El paquete portable no contiene todos los archivos requeridos.")
            marker = (staging / PORTABLE_MARKER).read_text(encoding="utf-8", errors="replace")
            if "channel=portable" not in marker:
                raise UpdateError("El paquete descargado no está marcado como versión portable.")
            try:
                manifest = json.loads((staging / PORTABLE_MANIFEST).read_text(encoding="utf-8"))
                managed = manifest.get("files") if isinstance(manifest, dict) else None
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise UpdateError("El manifiesto del paquete portable no es válido.") from exc
            if not isinstance(managed, list) or not all(isinstance(item, str) and item for item in managed):
                raise UpdateError("El manifiesto del paquete portable no contiene una lista válida de archivos.")
            required_names = {PORTABLE_MARKER, APP_EXECUTABLE, PORTABLE_HELPER}
            if not required_names.issubset({item.replace("\\", "/") for item in managed}):
                raise UpdateError("El manifiesto portable no declara los archivos esenciales del programa.")
            return PortablePreparedUpdate(info.version, staging, root)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    @staticmethod
    def launch_portable_update(prepared: PortablePreparedUpdate) -> None:
        if os.name != "nt":
            raise UpdateError("La actualización portable automática solo está disponible en Windows.")
        root = prepared.portable_root.resolve()
        staging = prepared.staging_root.resolve()
        if staging.parent != root.parent:
            raise UpdateError("La carpeta temporal portable no está en la ubicación esperada.")
        if not (root / PORTABLE_MARKER).is_file() or not (staging / PORTABLE_MARKER).is_file():
            raise UpdateError("No se pudo validar la carpeta portable antes de actualizar.")
        source_helper = root / PORTABLE_HELPER
        if not source_helper.is_file():
            raise UpdateError("No se encontró el actualizador auxiliar de la versión portable.")

        helper_dir = APP_DIR / "updates"
        helper_dir.mkdir(parents=True, exist_ok=True)
        helper_copy = helper_dir / f"PasajesPortableUpdater-{prepared.version}.exe"
        try:
            shutil.copy2(source_helper, helper_copy)
            subprocess.Popen(
                [
                    str(helper_copy),
                    "--wait-pid",
                    str(os.getpid()),
                    "--source",
                    str(staging),
                    "--target",
                    str(root),
                    "--app",
                    APP_EXECUTABLE,
                ],
                cwd=str(helper_dir),
                close_fds=True,
            )
        except OSError as exc:
            raise UpdateError("Windows no pudo iniciar el actualizador portable auxiliar.") from exc
