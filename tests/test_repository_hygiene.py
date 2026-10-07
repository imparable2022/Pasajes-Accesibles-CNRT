from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositoryHygieneTests(unittest.TestCase):
    def test_gitignore_protects_common_local_files(self):
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        required = [
            ".venv/",
            "__pycache__/",
            ".env",
            "*.log",
            "*.sqlite",
            "*.sqlite3",
            "*.dat",
            "*.pem",
            "*.key",
            "*.p12",
            "*.pfx",
        ]
        for pattern in required:
            self.assertIn(pattern, text)

    def test_installer_uses_current_product_name(self):
        text = (ROOT / "instalar.bat").read_text(encoding="utf-8")
        self.assertIn("INSTALADOR DE PASAJES ACCESIBLES CNRT", text)
        self.assertNotIn("INSTALADOR DE CNRT ACCESIBLE", text)

    def test_no_real_private_posthog_keys_in_executable_sources(self):
        # El token phc_ del proyecto es intencionalmente público. Estos prefijos,
        # en cambio, corresponden a credenciales que nunca deben ir en el cliente.
        private_patterns = {
            "phx": re.compile(r"phx_[A-Za-z0-9_-]{12,}"),
            "phs": re.compile(r"phs_[A-Za-z0-9_-]{12,}"),
            "pha": re.compile(r"pha_[A-Za-z0-9_-]{12,}"),
            "phr": re.compile(r"phr_[A-Za-z0-9_-]{12,}"),
        }
        files = list((ROOT / "pasajes_accesibles_cnrt").glob("*.py"))
        files += [ROOT / "instalar.bat", ROOT / "ejecutar.bat", ROOT / "probar.bat"]
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            for name, pattern in private_patterns.items():
                self.assertIsNone(pattern.search(text), f"Posible clave privada {name}_ en {path}")

    def test_no_private_key_material_in_repository_text_files(self):
        marker = "-----BEGIN " + "PRIVATE KEY-----"
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() in {".pyc", ".zip"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            self.assertNotIn(marker, text, f"Material de clave privada en {path}")


if __name__ == "__main__":
    unittest.main()
