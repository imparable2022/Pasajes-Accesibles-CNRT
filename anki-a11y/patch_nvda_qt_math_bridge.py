"""Patch NVDA's system-test global plugin with an Anki Qt MathML bridge.

This is deliberately test-only. It proves whether restoring Role.MATH and the
exact MathML lost by Qt's Windows UIA bridge is sufficient for native MathCAT
navigation. It is enabled only when ANKI_A11Y_MATH_VARIANT=wrapper.
"""
from pathlib import Path
import sys

CLASS_ANCHOR = "class SystemTestSpyServer(globalPluginHandler.GlobalPlugin):"
GLOBAL_ANCHOR = "\nGlobalPlugin = SystemTestSpyServer\n"

BRIDGE_CLASS = r'''
_ANKI_MATH_MARKER = "ANKI_MATHML:"


class _AnkiQtMathBridge:
	"""Test-only overlay for a Qt UIA Custom object carrying exact MathML."""

	role = None  # replaced after imports below

	def _get_mathMl(self):
		from urllib.parse import unquote
		desc = self.description or ""
		if not desc.startswith(_ANKI_MATH_MARKER):
			raise LookupError("No Anki MathML marker")
		return unquote(desc[len(_ANKI_MATH_MARKER):])
'''

METHOD = r'''
	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		# The marker only exists on the opt-in audit wrapper, so it is a safer
		# causal selector than relying on process environment propagation or
		# a particular UIA control type.
		try:
			import controlTypes
			from NVDAObjects.UIA import UIA
			if not isinstance(obj, UIA):
				return
			desc = obj.description or ""
			if not desc.startswith(_ANKI_MATH_MARKER):
				return
			_AnkiQtMathBridge.role = controlTypes.Role.MATH
			clsList.insert(0, _AnkiQtMathBridge)
			log.warning("ANKI_QT_MATH_BRIDGE applied to marked Qt UIA object")
		except Exception:
			log.error("ANKI_QT_MATH_BRIDGE overlay selection failed", exc_info=True)
'''

def patch(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    if "ANKI_QT_MATH_BRIDGE applied" in original:
        print("Anki Qt MathML bridge already installed")
        return
    if original.count(CLASS_ANCHOR) != 1 or original.count(GLOBAL_ANCHOR) != 1:
        raise RuntimeError("Unexpected SystemTestSpy source layout; refusing patch")

    # Put the mixin before the concrete GlobalPlugin class.
    updated = original.replace(CLASS_ANCHOR, BRIDGE_CLASS + "\n\n" + CLASS_ANCHOR, 1)

    # Insert the chooser inside SystemTestSpyServer immediately before module
    # level GlobalPlugin assignment.
    idx = updated.index(GLOBAL_ANCHOR)
    updated = updated[:idx] + METHOD + updated[idx:]

    compile(updated, str(path), "exec")
    path.write_text(updated, encoding="utf-8", newline="\n")
    print("Applied test-only Anki Qt MathML -> NVDA Role.MATH bridge")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_nvda_qt_math_bridge.py path/to/speechSpyGlobalPlugin.py")
    patch(Path(sys.argv[1]))
