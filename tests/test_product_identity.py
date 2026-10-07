from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProductIdentityTests(unittest.TestCase):
    def test_visible_product_identity_is_pasajes_accesibles_cnrt(self):
        app = (ROOT / "pasajes_accesibles_cnrt" / "app.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        license_text = (ROOT / "LICENSE.txt").read_text(encoding="utf-8")
        installer = (ROOT / "instalar.bat").read_text(encoding="utf-8")

        self.assertIn('title="Pasajes Accesibles CNRT"', app)
        self.assertIn('"Acerca de Pasajes Accesibles CNRT"', app)
        self.assertTrue(readme.startswith("# Pasajes Accesibles CNRT\n"))
        self.assertTrue(license_text.startswith("Pasajes Accesibles CNRT\n"))
        self.assertIn("title Instalador de Pasajes Accesibles CNRT", installer)
        self.assertIn("abrir Pasajes Accesibles CNRT", installer)


if __name__ == "__main__":
    unittest.main()
