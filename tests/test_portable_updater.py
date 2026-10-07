from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import portable_updater


class PortableUpdaterHelperTests(unittest.TestCase):
    def _make_tree(self, root: Path, label: str) -> None:
        root.mkdir()
        (root / portable_updater.PORTABLE_MARKER).write_text("channel=portable", encoding="utf-8")
        (root / "Pasajes Accesibles CNRT.exe").write_text(label, encoding="utf-8")
        (root / "version.txt").write_text(label, encoding="utf-8")
        (root / portable_updater.PORTABLE_MANIFEST).write_text(
            json.dumps({"files": [portable_updater.PORTABLE_MARKER, "Pasajes Accesibles CNRT.exe", "version.txt"]}),
            encoding="utf-8",
        )

    def test_replacement_swaps_complete_directory_and_removes_backup_after_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "Pasajes Accesibles CNRT"
            source = base / ".update"
            self._make_tree(target, "old")
            self._make_tree(source, "new")
            process = Mock()
            process.poll.return_value = None
            with patch.object(portable_updater.subprocess, "Popen", return_value=process), patch.object(
                portable_updater.time, "sleep", return_value=None
            ):
                portable_updater._replace_portable(source, target, "Pasajes Accesibles CNRT.exe")
            self.assertEqual((target / "version.txt").read_text(encoding="utf-8"), "new")
            self.assertFalse((base / ".Pasajes Accesibles CNRT.previous").exists())

    def test_user_file_not_in_manifest_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "Pasajes Accesibles CNRT"
            source = base / ".update"
            self._make_tree(target, "old")
            self._make_tree(source, "new")
            (target / "mis_notas.txt").write_text("guardar", encoding="utf-8")
            process = Mock()
            process.poll.return_value = None
            with patch.object(portable_updater.subprocess, "Popen", return_value=process), patch.object(
                portable_updater.time, "sleep", return_value=None
            ):
                portable_updater._replace_portable(source, target, "Pasajes Accesibles CNRT.exe")
            self.assertEqual((target / "mis_notas.txt").read_text(encoding="utf-8"), "guardar")
            self.assertEqual((target / "version.txt").read_text(encoding="utf-8"), "new")

    def test_launch_failure_rolls_back_previous_portable(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "Pasajes Accesibles CNRT"
            source = base / ".update"
            self._make_tree(target, "old")
            self._make_tree(source, "new")
            with patch.object(portable_updater.subprocess, "Popen", side_effect=OSError("cannot start")), patch.object(
                portable_updater.time, "sleep", return_value=None
            ):
                with self.assertRaises(OSError):
                    portable_updater._replace_portable(source, target, "Pasajes Accesibles CNRT.exe")
            self.assertEqual((target / "version.txt").read_text(encoding="utf-8"), "old")
            self.assertTrue((base / ".Pasajes Accesibles CNRT.failed").exists())

    def test_rejects_replacement_without_portable_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "target"
            source = base / "source"
            target.mkdir()
            source.mkdir()
            with self.assertRaises(RuntimeError):
                portable_updater._replace_portable(source, target, "Pasajes Accesibles CNRT.exe")


if __name__ == "__main__":
    unittest.main()
