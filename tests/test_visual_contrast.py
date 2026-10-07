import re
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "pasajes_accesibles_cnrt" / "app.py"
SOURCE = APP.read_text(encoding="utf-8")


def colour(name: str):
    match = re.search(rf"^{name} = wx\.Colour\((\d+), (\d+), (\d+)\)", SOURCE, re.MULTILINE)
    if not match:
        raise AssertionError(f"No se encontró {name}")
    return tuple(int(v) for v in match.groups())


def channel(value: int) -> float:
    c = value / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    la, lb = luminance(a), luminance(b)
    light, dark = max(la, lb), min(la, lb)
    return (light + 0.05) / (dark + 0.05)


class VisualContrastTests(unittest.TestCase):
    def test_text_palettes_keep_wcag22_numeric_contrast_floor(self):
        self.assertGreaterEqual(contrast(colour("COLOR_TEXT"), colour("COLOR_BG")), 4.5)
        self.assertGreaterEqual(contrast(colour("COLOR_MUTED"), colour("COLOR_BG")), 4.5)
        self.assertGreaterEqual(contrast(colour("COLOR_WHITE"), colour("COLOR_PRIMARY")), 4.5)
        self.assertGreaterEqual(contrast(colour("COLOR_SUCCESS"), colour("COLOR_SUCCESS_BG")), 4.5)
        self.assertGreaterEqual(contrast(colour("COLOR_DANGER"), colour("COLOR_DANGER_BG")), 4.5)
        self.assertGreaterEqual(contrast(colour("COLOR_WARNING"), colour("COLOR_WARNING_BG")), 4.5)

    def test_reference_border_contrast_is_at_least_three_to_one(self):
        self.assertGreaterEqual(contrast(colour("COLOR_BORDER"), colour("COLOR_SURFACE")), 3.0)


if __name__ == "__main__":
    unittest.main()
