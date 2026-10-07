from __future__ import annotations

import base64
import ctypes
import json
import os
import sqlite3
from ctypes import wintypes
from pathlib import Path
from typing import Optional

from .models import Locality

APP_DIR = Path(os.getenv("APPDATA", Path.home())) / "Pasajes Accesibles CNRT"
APP_DIR.mkdir(parents=True, exist_ok=True)


class LocalityCache:
    def __init__(self, path: Path | None = None):
        self.path = path or APP_DIR / "localidades.sqlite3"
        self._init()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _init(self):
        with self._connect() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS localidades (id TEXT PRIMARY KEY, texto TEXT NOT NULL, texto_norm TEXT NOT NULL)"
            )

    def add_many(self, localities: list[Locality]):
        with self._connect() as con:
            con.executemany(
                "INSERT INTO localidades(id,texto,texto_norm) VALUES(?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET texto=excluded.texto, texto_norm=excluded.texto_norm",
                [(x.id, x.text, x.text.casefold()) for x in localities],
            )

    def search(self, query: str, limit: int = 30) -> list[Locality]:
        q = f"%{query.casefold()}%"
        with self._connect() as con:
            rows = con.execute(
                "SELECT id,texto FROM localidades WHERE texto_norm LIKE ? ORDER BY texto LIMIT ?",
                (q, limit),
            ).fetchall()
        return [Locality(id=r[0], text=r[1]) for r in rows]


class CredentialStore:
    """Almacenamiento opcional. En Windows usa DPAPI vinculada al usuario actual."""

    def __init__(self, path: Path | None = None):
        self.path = path or APP_DIR / "credenciales.dat"

    def save(self, payload: dict):
        if os.name != "nt":
            raise RuntimeError("El guardado seguro de credenciales solo está habilitado en Windows.")
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        encrypted = _dpapi_protect(raw)
        self.path.write_bytes(base64.b64encode(encrypted))

    def load(self) -> Optional[dict]:
        if os.name != "nt" or not self.path.exists():
            return None
        encrypted = base64.b64decode(self.path.read_bytes())
        raw = _dpapi_unprotect(encrypted)
        return json.loads(raw.decode("utf-8"))

    def clear(self):
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes):
    buf = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf


def _local_free(ptr):
    fn = ctypes.windll.kernel32.LocalFree
    fn.argtypes = [ctypes.c_void_p]
    fn.restype = ctypes.c_void_p
    fn(ctypes.cast(ptr, ctypes.c_void_p))


def _dpapi_protect(data: bytes) -> bytes:
    in_blob, in_buf = _blob(data)
    out_blob = DATA_BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData
    fn.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(in_blob), "Pasajes Accesibles CNRT", None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        _local_free(out_blob.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    in_blob, in_buf = _blob(data)
    out_blob = DATA_BLOB()
    fn = ctypes.windll.crypt32.CryptUnprotectData
    fn.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        _local_free(out_blob.pbData)
