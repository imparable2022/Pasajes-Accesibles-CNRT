from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
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


class UpdaterTests(unittest.TestCase):
    def test_semantic_version_comparison(self):
        self.assertTrue(updater.is_newer_version("1.2.14", "1.2.13"))
        self.assertTrue(updater.is_newer_version("v2.0.0", "1.9.9"))
        self.assertFalse(updater.is_newer_version("1.2.13", "1.2.13"))
        self.assertFalse(updater.is_newer_version("1.2.12", "1.2.13"))

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

    def test_latest_release_requires_expected_installer_and_sha256(self):
        data = b"installer-content"
        digest = hashlib.sha256(data).hexdigest()
        release = {
            "tag_name": "v1.2.14",
            "draft": False,
            "prerelease": False,
            "html_url": "https://github.com/example/repo/releases/tag/v1.2.14",
            "body": "Cambios",
            "assets": [{
                "name": "Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe",
                "browser_download_url": "https://github.com/example/repo/releases/download/v1.2.14/Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe",
                "size": len(data),
                "digest": "sha256:" + digest,
            }],
        }
        with patch.object(updater, "urlopen", return_value=FakeResponse(json.dumps(release).encode())):
            info = updater.GitHubUpdateService("example/repo", current_version="1.2.13").latest()
        self.assertIsNotNone(info)
        self.assertEqual(info.version, "1.2.14")
        self.assertEqual(info.sha256, digest)

    def test_latest_release_returns_none_when_not_newer(self):
        release = {"tag_name": "v1.2.13", "draft": False, "prerelease": False, "assets": []}
        with patch.object(updater, "urlopen", return_value=FakeResponse(json.dumps(release).encode())):
            info = updater.GitHubUpdateService("example/repo", current_version="1.2.13").latest()
        self.assertIsNone(info)

    def test_latest_release_rejects_installer_from_another_host_or_repository(self):
        digest = hashlib.sha256(b"x").hexdigest()
        release = {
            "tag_name": "v1.2.14",
            "draft": False,
            "prerelease": False,
            "assets": [{
                "name": "Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe",
                "browser_download_url": "https://evil.example/Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe",
                "size": 1,
                "digest": "sha256:" + digest,
            }],
        }
        with patch.object(updater, "urlopen", return_value=FakeResponse(json.dumps(release).encode())):
            with self.assertRaises(updater.UpdateError):
                updater.GitHubUpdateService("example/repo", current_version="1.2.13").latest()

    def test_latest_release_rejects_checksum_from_another_repository(self):
        release = {
            "tag_name": "v1.2.14",
            "draft": False,
            "prerelease": False,
            "assets": [
                {
                    "name": "Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe",
                    "browser_download_url": "https://github.com/example/repo/releases/download/v1.2.14/Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe",
                    "size": 1,
                },
                {
                    "name": "Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe.sha256",
                    "browser_download_url": "https://github.com/attacker/repo/releases/download/v1.2.14/Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe.sha256",
                    "size": 80,
                },
            ],
        }
        with patch.object(updater, "urlopen", return_value=FakeResponse(json.dumps(release).encode())):
            with self.assertRaises(updater.UpdateError):
                updater.GitHubUpdateService("example/repo", current_version="1.2.13").latest()

    def test_release_without_digest_or_checksum_is_rejected(self):
        release = {
            "tag_name": "v1.2.14",
            "draft": False,
            "prerelease": False,
            "assets": [{
                "name": "Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe",
                "browser_download_url": "https://github.com/example/repo/releases/download/v1.2.14/Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe",
                "size": 100,
            }],
        }
        with patch.object(updater, "urlopen", return_value=FakeResponse(json.dumps(release).encode())):
            with self.assertRaises(updater.UpdateError):
                updater.GitHubUpdateService("example/repo", current_version="1.2.13").latest()

    def test_download_rejects_tampered_installer(self):
        payload = b"tampered"
        info = updater.UpdateInfo(
            version="1.2.14",
            tag="v1.2.14",
            release_url="",
            notes="",
            installer_name="Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe",
            installer_url="https://github.com/example/repo/releases/download/v1.2.14/Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe",
            installer_size=len(payload),
            sha256="0" * 64,
        )
        with tempfile.TemporaryDirectory() as tmp, patch.object(updater, "APP_DIR", Path(tmp)), patch.object(
            updater, "urlopen", return_value=FakeResponse(payload)
        ):
            with self.assertRaises(updater.UpdateError):
                updater.GitHubUpdateService("example/repo").download(info)
            self.assertFalse((Path(tmp) / "updates" / info.installer_name).exists())

    def test_download_accepts_matching_sha256(self):
        payload = b"valid-installer"
        info = updater.UpdateInfo(
            version="1.2.14",
            tag="v1.2.14",
            release_url="",
            notes="",
            installer_name="Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe",
            installer_url="https://github.com/example/repo/releases/download/v1.2.14/Pasajes_Accesibles_CNRT_Setup_v1.2.14.exe",
            installer_size=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        )
        with tempfile.TemporaryDirectory() as tmp, patch.object(updater, "APP_DIR", Path(tmp)), patch.object(
            updater, "urlopen", return_value=FakeResponse(payload)
        ):
            path = updater.GitHubUpdateService("example/repo").download(info)
            self.assertEqual(path.read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
