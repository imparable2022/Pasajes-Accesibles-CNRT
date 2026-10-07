from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InternalIdentityTests(unittest.TestCase):
    def test_package_and_runtime_identity_use_pasajes_accesibles_cnrt(self):
        old_package = "cnrt" + "_accessible"
        self.assertTrue((ROOT / "pasajes_accesibles_cnrt").is_dir())
        self.assertFalse((ROOT / old_package).exists())

        app = (ROOT / "pasajes_accesibles_cnrt" / "app.py").read_text(encoding="utf-8")
        storage = (ROOT / "pasajes_accesibles_cnrt" / "storage.py").read_text(encoding="utf-8")
        runner = (ROOT / "ejecutar.bat").read_text(encoding="utf-8")

        self.assertIn('wx.Config("Pasajes Accesibles CNRT")', app)
        self.assertIn('/ "Pasajes Accesibles CNRT"', storage)
        self.assertIn('"Pasajes Accesibles CNRT", None, None, None, 0', storage)
        self.assertIn('-m pasajes_accesibles_cnrt.app', runner)

    def test_no_legacy_product_or_package_identity_remains(self):
        forbidden = (
            "CNRT" + " Accesible",
            "cnrt" + "_accessible",
            "CNRT" + "_Accesible",
            "_pasajes" + "_visual_header",
        )
        hits = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix == ".pyc":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for token in forbidden:
                if token in text:
                    hits.append(f"{path.relative_to(ROOT)}: {token}")
        self.assertEqual([], hits)


if __name__ == "__main__":
    unittest.main()
