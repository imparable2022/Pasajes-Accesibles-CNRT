"""Patch NVDA's system-test global plugin with an Anki Qt MathML bridge.

This is deliberately test-only. It proves whether restoring Role.MATH and the
exact MathML lost by Qt's Windows UIA bridge is sufficient for native MathCAT
navigation. The selector is the unique ANKI_MATHML marker added only by the
opt-in wrapper experiment.
"""
from pathlib import Path
import ast
import sys

CLASS_ANCHOR = "class SystemTestSpyServer(globalPluginHandler.GlobalPlugin):"
CLASS_TERMINATE_ANCHOR = """\n\tdef terminate(self):
\t\tlog.debug("Terminating the SystemTestSpyServer")"""

BRIDGE_CLASS = '''
_ANKI_MATH_MARKER = "ANKI_MATHML:"


class _AnkiQtMathBridge:
\t"""Test-only overlay for a Qt UIA object carrying exact MathML."""

\trole = None  # replaced after imports below

\tdef _get_mathMl(self):
\t\tfrom urllib.parse import unquote
\t\tdesc = self.description or ""
\t\tif not desc.startswith(_ANKI_MATH_MARKER):
\t\t\traise LookupError("No Anki MathML marker")
\t\treturn unquote(desc[len(_ANKI_MATH_MARKER):])
'''

METHOD = '''
\tdef chooseNVDAObjectOverlayClasses(self, obj, clsList):
\t\t# The marker only exists on the opt-in audit wrapper, so it is a safer
\t\t# causal selector than relying on process environment propagation or
\t\t# a particular UIA control type.
\t\ttry:
\t\t\timport controlTypes
\t\t\tfrom NVDAObjects.UIA import UIA
\t\t\tif not isinstance(obj, UIA):
\t\t\t\treturn
\t\t\tdesc = obj.description or ""
\t\t\tif not desc.startswith(_ANKI_MATH_MARKER):
\t\t\t\treturn
\t\t\t_AnkiQtMathBridge.role = controlTypes.Role.MATH
\t\t\tclsList.insert(0, _AnkiQtMathBridge)
\t\t\tlog.warning("ANKI_QT_MATH_BRIDGE applied to marked Qt UIA object")
\t\texcept Exception:
\t\t\tlog.error("ANKI_QT_MATH_BRIDGE overlay selection failed", exc_info=True)
'''


def _verify_method_is_on_global_plugin(source: str) -> None:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "SystemTestSpyServer":
            methods = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if "chooseNVDAObjectOverlayClasses" in methods:
                return
            raise RuntimeError(
                "Patched chooser is not a method of SystemTestSpyServer; refusing patch"
            )
    raise RuntimeError("SystemTestSpyServer class not found after patch")


def patch(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    if "ANKI_QT_MATH_BRIDGE applied" in original:
        print("Anki Qt MathML bridge already installed")
        return
    if original.count(CLASS_ANCHOR) != 1 or original.count(CLASS_TERMINATE_ANCHOR) != 1:
        raise RuntimeError("Unexpected SystemTestSpy source layout; refusing patch")

    # Put the mixin before the concrete GlobalPlugin class.
    updated = original.replace(CLASS_ANCHOR, BRIDGE_CLASS + "\n\n" + CLASS_ANCHOR, 1)

    # Insert the chooser inside SystemTestSpyServer, immediately before its
    # terminate() method. Do not insert near module-level GlobalPlugin assignment:
    # doing that can accidentally nest the chooser inside another function.
    updated = updated.replace(
        CLASS_TERMINATE_ANCHOR,
        METHOD + CLASS_TERMINATE_ANCHOR,
        1,
    )

    compile(updated, str(path), "exec")
    _verify_method_is_on_global_plugin(updated)
    path.write_text(updated, encoding="utf-8", newline="\n")
    print("Applied test-only Anki Qt MathML -> NVDA Role.MATH bridge")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_nvda_qt_math_bridge.py path/to/speechSpyGlobalPlugin.py")
    patch(Path(sys.argv[1]))
