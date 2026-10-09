from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from pasajes_accesibles_cnrt import updater


class FakeResponse:
    def __init__(self, payload: bytes):
        self._stream = io.BytesIO(payload)

    def read(self, size=-1):
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def update_info(channel: str, payload: bytes = b"payload", version: str = "1.2.15") -> updater.UpdateInfo:
    name = updater.PORTABLE_ASSET if channel == updater.CHANNEL_PORTABLE else updater.INSTALLER_ASSET
    return updater.UpdateInfo(
        version=version,
        tag=f"v{version}",
        release_url="",
        notes="",
        channel=channel,
        asset_name=name,
        asset_url=f"https://github.com/example/repo/releases/download/v{version}/{name}",
        asset_size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


class UpdaterTests(unittest.TestCase):
    def test_semantic_version_comparison(self):
        self.assertTrue(updater.is_newer_version("1.2.15", "1.2.14"))
        self.assertTrue(updater.is_newer_version("v2.0.0", "1.9.9"))
        self.assertFalse(updater.is_newer_version("1.2.14", "1.2.14"))
        self.assertFalse(updater.is_newer_version("1.2.13", "1.2.14"))

    def test_official_repository_cannot_be_overridden_by_environment(self):
        with patch.object(updater, "GITHUB_REPOSITORY", "martin/oficial"), patch.dict(
            os.environ, {"PASAJES_CNRT_UPDATE_REPOSITORY": "atacante/falso"}, clear=False
        ):
            self.assertEqual(updater.configured_repository(), "martin/oficial")

    def test_environment_repository_is_only_used_for_source_development(self):
        with patch.object(updater, "GITHUB_REPOSITORY", ""), patch.dict(
            os.environ, {"PASAJES_CNRT_UPDATE_REPOSITORY": "martin/pruebas"}, clear=False
        ):
            self.assertEqual(updater.configured_repository(), "martin/pruebas")

    def test_portable_channel_is_detected_only_with_marker_next_to_frozen_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / updater.APP_EXECUTABLE
            exe.write_bytes(b"")
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(exe)):
                self.assertEqual(updater.detect_update_channel(), updater.CHANNEL_INSTALLER)
                (Path(tmp) / updater.PORTABLE_MARKER).write_text("channel=portable", encoding="utf-8")
                self.assertEqual(updater.detect_update_channel(), updater.CHANNEL_PORTABLE)

    def test_latest_release_requires_expected_installer_and_sha256(self):
        data = b"installer-content"
        digest = hashlib.sha256(data).hexdigest()
        name = updater.INSTALLER_ASSET
        release = {
            "tag_name": "v1.2.15",
            "draft": False,
            "prerelease": False,
            "html_url": "https://github.com/example/repo/releases/tag/v1.2.15",
            "body": "Cambios",
            "assets": [{
                "name": name,
                "browser_download_url": f"https://github.com/example/repo/releases/download/v1.2.15/{name}",
                "size": len(data),
                "digest": "sha256:" + digest,
            }],
        }
        with patch.object(updater, "urlopen", return_value=FakeResponse(json.dumps(release).encode())):
            info = updater.GitHubUpdateService(
                "example/repo", current_version="1.2.14", channel=updater.CHANNEL_INSTALLER
            ).latest()
        self.assertIsNotNone(info)
        self.assertEqual(info.version, "1.2.15")
        self.assertEqual(info.asset_name, updater.INSTALLER_ASSET)
        self.assertEqual(info.channel, updater.CHANNEL_INSTALLER)
        self.assertEqual(info.sha256, digest)

    def test_latest_release_selects_portable_zip_for_portable_channel(self):
        data = b"portable-content"
        digest = hashlib.sha256(data).hexdigest()
        name = updater.PORTABLE_ASSET
        release = {
            "tag_name": "v1.2.15",
            "draft": False,
            "prerelease": False,
            "assets": [{
                "name": name,
                "browser_download_url": f"https://github.com/example/repo/releases/download/v1.2.15/{name}",
                "size": len(data),
                "digest": "sha256:" + digest,
            }],
        }
        with patch.object(updater, "urlopen", return_value=FakeResponse(json.dumps(release).encode())):
            info = updater.GitHubUpdateService(
                "example/repo", current_version="1.2.14", channel=updater.CHANNEL_PORTABLE
            ).latest()
        self.assertIsNotNone(info)
        self.assertEqual(info.asset_name, name)
        self.assertEqual(info.channel, updater.CHANNEL_PORTABLE)

    def test_latest_release_returns_none_when_not_newer(self):
        release = {"tag_name": "v1.2.14", "draft": False, "prerelease": False, "assets": []}
        with patch.object(updater, "urlopen", return_value=FakeResponse(json.dumps(release).encode())):
            info = updater.GitHubUpdateService(
                "example/repo", current_version="1.2.14", channel=updater.CHANNEL_INSTALLER
            ).latest()
        self.assertIsNone(info)

    def test_latest_release_rejects_asset_from_another_host_or_repository(self):
        digest = hashlib.sha256(b"x").hexdigest()
        release = {
            "tag_name": "v1.2.15",
            "draft": False,
            "prerelease": False,
            "assets": [{
                "name": updater.INSTALLER_ASSET,
                "browser_download_url": f"https://evil.example/{updater.INSTALLER_ASSET}",
                "size": 1,
                "digest": "sha256:" + digest,
            }],
        }
        with patch.object(updater, "urlopen", return_value=FakeResponse(json.dumps(release).encode())):
            with self.assertRaises(updater.UpdateError):
                updater.GitHubUpdateService(
                    "example/repo", current_version="1.2.14", channel=updater.CHANNEL_INSTALLER
                ).latest()

    def test_latest_release_rejects_checksum_from_another_repository(self):
        release = {
            "tag_name": "v1.2.15",
            "draft": False,
            "prerelease": False,
            "assets": [
                {
                    "name": updater.INSTALLER_ASSET,
                    "browser_download_url": f"https://github.com/example/repo/releases/download/v1.2.15/{updater.INSTALLER_ASSET}",
                    "size": 1,
                },
                {
                    "name": updater.INSTALLER_ASSET + ".sha256",
                    "browser_download_url": f"https://github.com/attacker/repo/releases/download/v1.2.15/{updater.INSTALLER_ASSET}.sha256",
                    "size": 80,
                },
            ],
        }
        with patch.object(updater, "urlopen", return_value=FakeResponse(json.dumps(release).encode())):
            with self.assertRaises(updater.UpdateError):
                updater.GitHubUpdateService(
                    "example/repo", current_version="1.2.14", channel=updater.CHANNEL_INSTALLER
                ).latest()

    def test_release_without_digest_or_checksum_is_rejected(self):
        release = {
            "tag_name": "v1.2.15",
            "draft": False,
            "prerelease": False,
            "assets": [{
                "name": updater.INSTALLER_ASSET,
                "browser_download_url": f"https://github.com/example/repo/releases/download/v1.2.15/{updater.INSTALLER_ASSET}",
                "size": 100,
            }],
        }
        with patch.object(updater, "urlopen", return_value=FakeResponse(json.dumps(release).encode())):
            with self.assertRaises(updater.UpdateError):
                updater.GitHubUpdateService(
                    "example/repo", current_version="1.2.14", channel=updater.CHANNEL_INSTALLER
                ).latest()

    def test_download_rejects_tampered_asset(self):
        payload = b"tampered"
        info = update_info(updater.CHANNEL_INSTALLER, payload)
        info = updater.UpdateInfo(**{**info.__dict__, "sha256": "0" * 64})
        with tempfile.TemporaryDirectory() as tmp, patch.object(updater, "APP_DIR", Path(tmp)), patch.object(
            updater, "urlopen", return_value=FakeResponse(payload)
        ):
            with self.assertRaises(updater.UpdateError):
                updater.GitHubUpdateService("example/repo", channel=updater.CHANNEL_INSTALLER).download(info)
            self.assertFalse((Path(tmp) / "updates" / info.asset_name).exists())

    def test_download_accepts_matching_sha256(self):
        payload = b"valid-installer"
        info = update_info(updater.CHANNEL_INSTALLER, payload)
        with tempfile.TemporaryDirectory() as tmp, patch.object(updater, "APP_DIR", Path(tmp)), patch.object(
            updater, "urlopen", return_value=FakeResponse(payload)
        ):
            path = updater.GitHubUpdateService("example/repo", channel=updater.CHANNEL_INSTALLER).download(info)
            self.assertEqual(path.read_bytes(), payload)

    def test_download_rejects_cross_channel_info(self):
        info = update_info(updater.CHANNEL_PORTABLE, b"portable")
        with self.assertRaises(updater.UpdateError):
            updater.GitHubUpdateService("example/repo", channel=updater.CHANNEL_INSTALLER).download(info)

    def test_prepare_portable_update_extracts_valid_package_next_to_current_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            current = base / "current"
            current.mkdir()
            (current / updater.PORTABLE_MARKER).write_text("channel=portable", encoding="utf-8")
            (current / updater.PORTABLE_HELPER).write_bytes(b"helper")
            payload = b"zip-placeholder"
            info = update_info(updater.CHANNEL_PORTABLE, payload)
            archive = base / info.asset_name
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("Pasajes Accesibles CNRT/.portable", "channel=portable\nversion=1.2.15")
                zf.writestr("Pasajes Accesibles CNRT/Pasajes Accesibles CNRT.exe", b"exe")
                zf.writestr("Pasajes Accesibles CNRT/PasajesPortableUpdater.exe", b"helper2")
                zf.writestr("Pasajes Accesibles CNRT/.portable-manifest.json",
                            json.dumps({"version": "1.2.15", "files": [
                                ".portable", "Pasajes Accesibles CNRT.exe", "PasajesPortableUpdater.exe", "_internal/example.txt"
                            ]}))
                zf.writestr("Pasajes Accesibles CNRT/_internal/example.txt", b"x")
            service = updater.GitHubUpdateService("example/repo", channel=updater.CHANNEL_PORTABLE)
            prepared = service.prepare_portable_update(archive, info, portable_dir=current)
            try:
                self.assertEqual(prepared.portable_root, current.resolve())
                self.assertEqual(prepared.staging_root.parent, current.parent.resolve())
                self.assertEqual((prepared.staging_root / "_internal" / "example.txt").read_bytes(), b"x")
            finally:
                import shutil
                shutil.rmtree(prepared.staging_root, ignore_errors=True)

    def test_prepare_portable_update_rejects_zip_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            current = base / "current"
            current.mkdir()
            (current / updater.PORTABLE_MARKER).write_text("channel=portable", encoding="utf-8")
            (current / updater.PORTABLE_HELPER).write_bytes(b"helper")
            info = update_info(updater.CHANNEL_PORTABLE, b"zip-placeholder")
            archive = base / info.asset_name
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("Pasajes Accesibles CNRT/.portable", "channel=portable")
                zf.writestr("Pasajes Accesibles CNRT/../escape.txt", b"bad")
            service = updater.GitHubUpdateService("example/repo", channel=updater.CHANNEL_PORTABLE)
            with self.assertRaises(updater.UpdateError):
                service.prepare_portable_update(archive, info, portable_dir=current)
            self.assertFalse((base / "escape.txt").exists())

    def test_prepare_portable_update_rejects_duplicate_files_case_insensitively(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            current = base / "current"
            current.mkdir()
            (current / updater.PORTABLE_MARKER).write_text("channel=portable", encoding="utf-8")
            (current / updater.PORTABLE_HELPER).write_bytes(b"helper")
            info = update_info(updater.CHANNEL_PORTABLE, b"zip-placeholder")
            archive = base / info.asset_name
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("Root/.portable", "channel=portable")
                zf.writestr("Root/Pasajes Accesibles CNRT.exe", b"exe")
                zf.writestr("Root/PasajesPortableUpdater.exe", b"helper")
                zf.writestr("Root/.portable-manifest.json", json.dumps({"files": [
                    ".portable", "Pasajes Accesibles CNRT.exe", "PasajesPortableUpdater.exe", "Test.txt", "test.TXT"
                ]}))
                zf.writestr("Root/Test.txt", b"1")
                zf.writestr("Root/test.TXT", b"2")
            service = updater.GitHubUpdateService("example/repo", channel=updater.CHANNEL_PORTABLE)
            with self.assertRaises(updater.UpdateError):
                service.prepare_portable_update(archive, info, portable_dir=current)


if __name__ == "__main__":
    unittest.main()
