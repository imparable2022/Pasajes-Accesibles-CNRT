from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LicenseContractTests(unittest.TestCase):
    def test_polyform_noncommercial_license_is_declared(self):
        text = (ROOT / "LICENSE.txt").read_text(encoding="utf-8")
        self.assertIn("PolyForm Noncommercial License 1.0.0", text)
        self.assertIn("https://polyformproject.org/licenses/noncommercial/1.0.0", text)
        self.assertIn("Required Notice: Copyright 2026 Martín Ortiz.", text)
        self.assertIn("independent and unofficial project", text)

    def test_third_party_licenses_are_kept_separate(self):
        text = (ROOT / "docs" / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("wxWindows Library Licence", text)
        self.assertIn("Apache License 2.0", text)
        self.assertIn("MIT License", text)
        self.assertIn("Python Software Foundation License", text)


if __name__ == "__main__":
    unittest.main()
