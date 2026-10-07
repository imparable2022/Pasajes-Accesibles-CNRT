from __future__ import annotations

import ctypes
import json
import locale
import os
import platform
import queue
import sys
import threading
import uuid
from ctypes import wintypes
from datetime import datetime
from typing import Any
from urllib import request

from . import __version__

APP_NAME = "Pasajes Accesibles CNRT"
# El project token de PostHog (phc_...) es público y solo sirve para captura.
# Esta distribución trae configurado el proyecto oficial de Pasajes Accesibles CNRT.
# Las variables de entorno se conservan para pruebas o para rotar la configuración.
DEFAULT_POSTHOG_PROJECT_TOKEN = "phc_mbpeKc3GpbuB5zD8mUJo4PYHCF2oCWsyPxvvvbwGMCXm"
DEFAULT_POSTHOG_HOST = "https://us.i.posthog.com"
POSTHOG_PROJECT_TOKEN = os.getenv(
    "PASAJES_ACCESIBLES_CNRT_POSTHOG_TOKEN", DEFAULT_POSTHOG_PROJECT_TOKEN
).strip()
POSTHOG_HOST = os.getenv(
    "PASAJES_ACCESIBLES_CNRT_POSTHOG_HOST", DEFAULT_POSTHOG_HOST
).rstrip("/")


def _windows_build() -> int | None:
    if sys.platform != "win32":
        return None
    try:
        return int(sys.getwindowsversion().build)
    except Exception:
        return None


def _windows_name(build: int | None) -> str:
    if sys.platform != "win32":
        return platform.system() or "desconocido"
    if build is not None and build >= 22000:
        return "Windows 11"
    return "Windows 10"


def _ram_bucket() -> str:
    if sys.platform != "win32":
        return "desconocida"
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        state = MEMORYSTATUSEX()
        state.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            return "desconocida"
        gb = state.ullTotalPhys / (1024**3)
        if gb < 4:
            return "menos de 4 GB"
        if gb < 8:
            return "4 a menos de 8 GB"
        if gb < 16:
            return "8 a menos de 16 GB"
        if gb < 32:
            return "16 a menos de 32 GB"
        return "32 GB o más"
    except Exception:
        return "desconocida"


def _cpu_bucket() -> str:
    count = os.cpu_count()
    if not count:
        return "desconocido"
    if count <= 2:
        return "1-2"
    if count <= 4:
        return "3-4"
    if count <= 8:
        return "5-8"
    if count <= 16:
        return "9-16"
    return "17+"


def _running_process_names() -> set[str]:
    """Enumera solo nombres de ejecutables en Windows; nunca se envía la lista completa."""
    if sys.platform != "win32":
        return set()
    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    MAX_PATH = 260

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * MAX_PATH),
        ]

    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        return set()
    names: set[str] = set()
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return set()
        while True:
            names.add(entry.szExeFile.casefold())
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                break
        return names
    except Exception:
        return set()
    finally:
        kernel32.CloseHandle(snapshot)


def _spi_bool(action: int) -> bool | None:
    if sys.platform != "win32":
        return None
    try:
        value = wintypes.BOOL()
        ok = ctypes.windll.user32.SystemParametersInfoW(action, 0, ctypes.byref(value), 0)
        return bool(value.value) if ok else None
    except Exception:
        return None


def _accessibility_key_state(action: int, structure_type: type[ctypes.Structure], enabled_flag: int) -> bool | None:
    if sys.platform != "win32":
        return None
    try:
        info = structure_type()
        info.cbSize = ctypes.sizeof(structure_type)
        ok = ctypes.windll.user32.SystemParametersInfoW(action, info.cbSize, ctypes.byref(info), 0)
        return bool(info.dwFlags & enabled_flag) if ok else None
    except Exception:
        return None


def collect_accessibility_properties(high_contrast: bool) -> dict[str, Any]:
    processes = _running_process_names()
    readers: list[str] = []
    if "nvda.exe" in processes:
        readers.append("NVDA")
    if "jfw.exe" in processes or "jfw64.exe" in processes:
        readers.append("JAWS")
    if "narrator.exe" in processes:
        readers.append("Narrador")

    spi_reader = _spi_bool(0x0046)  # SPI_GETSCREENREADER
    if not readers and spi_reader:
        readers.append("otro/desconocido")

    class STICKYKEYS(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("dwFlags", wintypes.DWORD)]

    class FILTERKEYS(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
            ("iWaitMSec", wintypes.DWORD), ("iDelayMSec", wintypes.DWORD),
            ("iRepeatMSec", wintypes.DWORD), ("iBounceMSec", wintypes.DWORD),
        ]

    class TOGGLEKEYS(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("dwFlags", wintypes.DWORD)]

    class MOUSEKEYS(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
            ("iMaxSpeed", wintypes.DWORD), ("iTimeToMaxSpeed", wintypes.DWORD),
            ("iCtrlSpeed", wintypes.DWORD), ("dwReserved1", wintypes.DWORD),
            ("dwReserved2", wintypes.DWORD),
        ]

    return {
        "screen_reader": ", ".join(readers) if readers else "ninguno detectado",
        "screen_reader_flag": spi_reader,
        "windows_magnifier": "magnify.exe" in processes,
        "high_contrast": bool(high_contrast),
        "sticky_keys": _accessibility_key_state(0x003A, STICKYKEYS, 0x00000001),
        "filter_keys": _accessibility_key_state(0x0032, FILTERKEYS, 0x00000001),
        "toggle_keys": _accessibility_key_state(0x0034, TOGGLEKEYS, 0x00000001),
        "mouse_keys": _accessibility_key_state(0x0036, MOUSEKEYS, 0x00000001),
    }


def collect_technical_properties(*, high_contrast: bool, app_text_scale: float, screen_size: tuple[int, int] | None = None, dpi: tuple[int, int] | None = None) -> dict[str, Any]:
    build = _windows_build()
    try:
        language = locale.getlocale()[0] or "desconocido"
    except Exception:
        language = "desconocido"
    try:
        timezone = str(datetime.now().astimezone().tzinfo or "desconocida")
    except Exception:
        timezone = "desconocida"

    props: dict[str, Any] = {
        "app_name": APP_NAME,
        "app_version": __version__,
        "operating_system": _windows_name(build),
        "windows_build": build,
        "platform_release": platform.release(),
        "architecture": platform.machine() or "desconocida",
        "python_version": platform.python_version(),
        "cpu_logical_bucket": _cpu_bucket(),
        "ram_bucket": _ram_bucket(),
        "system_language": language,
        "timezone": timezone,
        "app_text_scale_percent": int(round(app_text_scale * 100)),
    }
    if screen_size:
        props["screen_width"] = int(screen_size[0])
        props["screen_height"] = int(screen_size[1])
    if dpi:
        props["dpi_x"] = int(dpi[0])
        props["dpi_y"] = int(dpi[1])
    props.update(collect_accessibility_properties(high_contrast))
    return props


class TelemetryClient:
    """Captura mínima y no bloqueante. Nunca interfiere con el uso de la aplicación."""

    def __init__(self, installation_id: str = "", enabled: bool = False):
        self.installation_id = installation_id
        self.enabled = bool(enabled)
        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="pasajes-telemetry", daemon=True)
        self._thread.start()

    @property
    def configured(self) -> bool:
        return bool(POSTHOG_PROJECT_TOKEN and POSTHOG_HOST)

    def configure(self, *, enabled: bool, installation_id: str = ""):
        self.enabled = bool(enabled)
        if installation_id:
            self.installation_id = installation_id

    def capture_technical(self, properties: dict[str, Any]):
        if not self.enabled or not self.configured or not self.installation_id:
            return
        self._enqueue("app_started", self.installation_id, properties)

    def capture_reservation(
        self,
        event: str,
        *,
        tracking_id: str,
        company: str,
        origin: str,
        destination: str,
        travel_date: str,
        state: str,
        extra: dict[str, Any] | None = None,
    ):
        if not self.enabled or not self.configured or not tracking_id.startswith("reservation-"):
            return
        properties: dict[str, Any] = {
            "app_name": APP_NAME,
            "app_version": __version__,
            "company": company.strip(),
            "origin": origin.strip(),
            "destination": destination.strip(),
            "travel_date": travel_date.strip(),
            "reservation_state": state.strip(),
            # Se reutiliza solo dentro del ciclo de ESTA reserva anónima.
            # Nunca se mezcla con installation_id ni con el identificador real de CNRT.
            "$process_person_profile": False,
        }
        if extra:
            properties.update(extra)
        self._enqueue(event, tracking_id, properties)

    def _enqueue(self, event: str, distinct_id: str, properties: dict[str, Any]):
        payload = {
            "api_key": POSTHOG_PROJECT_TOKEN,
            "event": event,
            "distinct_id": distinct_id,
            "properties": {"$process_person_profile": False, **properties},
        }
        self._queue.put(payload)

    def _run(self):
        while True:
            payload = self._queue.get()
            if payload is None:
                return
            try:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                req = request.Request(
                    f"{POSTHOG_HOST}/i/v0/e/",
                    data=body,
                    headers={"Content-Type": "application/json", "User-Agent": f"{APP_NAME}/{__version__}"},
                    method="POST",
                )
                with request.urlopen(req, timeout=4):
                    pass
            except Exception:
                # La telemetría nunca debe impedir ni molestar el uso del programa.
                pass

    def shutdown(self):
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass
