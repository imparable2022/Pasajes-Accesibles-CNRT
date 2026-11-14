"""CI-only mitigation for NVDA 2026.3.1 MathCAT with the speech spy synth.

MathCAT's SSML converter in 2026.3.1 divides by twice the current synth
rate. NVDA's test speech spy advertises no rate setting, and returns zero.
This causes ZeroDivisionError even for valid native MathML in Chrome.
The fix belongs to the test synthesizer only, not Anki or MathML markup.
"""
from pathlib import Path
import sys

ANCHOR = "\tsupportedSettings = []  # noqa: RUF012"
INJECTION = (
    "\tdef _get_rate(self):\n"
    "\t\t# Test synthesizer: return a nonzero default for MathCAT 2026.3.1.\n"
    "\t\treturn 50\n\n"
)

def patch(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    if INJECTION in original:
        print("Speech spy MathCAT rate workaround already installed")
        return
    if original.count(ANCHOR) != 1 or "class SpeechSpySynthDriver(" not in original:
        raise RuntimeError("Unexpected NVDA test synth driver; refusing unsafe change")
    updated = original.replace(ANCHOR, INJECTION + ANCHOR, 1)
    compile(updated, str(path), "exec")
    path.write_text(updated, encoding="utf-8", newline="\n")
    assert updated.count(INJECTION) == 1
    print("Applied MathCAT speech spy rate workaround (50)")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_nvda_spy_rate.py path/to/speechSpySynthDriver.py")
    patch(Path(sys.argv[1]))
