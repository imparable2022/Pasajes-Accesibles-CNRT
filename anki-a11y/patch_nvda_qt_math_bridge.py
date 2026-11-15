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
SPY_DEVINFO_ANCHOR = "\n\tdef _devInfoToLog(self):"

BRIDGE_CLASS = '''
_ANKI_MATH_MARKER = "ANKI_MATHML:"


class _AnkiQtMathBridge:
\t"""Test-only overlay for a Qt UIA object carrying exact MathML."""

\trole = None  # replaced after imports below

\tdef _decodeMathMl(self):
\t\tfrom urllib.parse import unquote
\t\tdesc = self.description or ""
\t\tif not desc.startswith(_ANKI_MATH_MARKER):
\t\t\traise LookupError("No Anki MathML marker")
\t\treturn unquote(desc[len(_ANKI_MATH_MARKER):])

\t@property
\tdef mathMl(self):
\t\t# NVDAObject.mathMl is an AutoProperty descriptor bound to the base
\t\t# getter when that class is created. A plain overlay mixin supplying
\t\t# only _get_mathMl does not replace that inherited descriptor.
\t\treturn self._decodeMathMl()

\tdef _get_mathMl(self):
\t\t# Keep the conventional getter for diagnostics/direct callers too.
\t\treturn self._decodeMathMl()
'''

OVERLAY_METHOD = '''
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

SPY_DIAGNOSTIC = '''
\tdef get_math_context(self):
\t\t"""Return the exact math state seen by NVDA immediately before NVDA+Alt+M."""
\t\timport json
\t\tresult = {}
\t\tdone = threading.Event()

\t\tdef collect():
\t\t\ttry:
\t\t\t\timport api
\t\t\t\timport mathPres
\t\t\t\tfocus = api.getFocusObject()
\t\t\t\tnav = api.getNavigatorObject()
\t\t\t\treview = api.getReviewPosition()
\t\t\t\tresult["focus_type"] = type(focus).__name__
\t\t\t\tresult["focus_role"] = str(getattr(focus, "role", None))
\t\t\t\tresult["focus_description"] = str(getattr(focus, "description", "") or "")[:1000]
\t\t\t\tresult["navigator_type"] = type(nav).__name__
\t\t\t\tresult["navigator_mro"] = [c.__name__ for c in type(nav).__mro__]
\t\t\t\tresult["navigator_role"] = str(getattr(nav, "role", None))
\t\t\t\tresult["navigator_description"] = str(getattr(nav, "description", "") or "")[:1000]
\t\t\t\tresult["review_type"] = type(review).__name__
\t\t\t\tresult["review_obj_type"] = type(getattr(review, "obj", None)).__name__
\t\t\t\tresult["review_obj_role"] = str(getattr(getattr(review, "obj", None), "role", None))
\t\t\t\ttry:
\t\t\t\t\tresult["navigator_mathMl_property"] = nav.mathMl
\t\t\t\texcept Exception as error:
\t\t\t\t\tresult["navigator_mathMl_property_error"] = repr(error)
\t\t\t\ttry:
\t\t\t\t\tgetter = getattr(nav, "_get_mathMl")
\t\t\t\t\tresult["navigator_mathMl_getter"] = getter()
\t\t\t\texcept Exception as error:
\t\t\t\t\tresult["navigator_mathMl_getter_error"] = repr(error)
\t\t\t\ttry:
\t\t\t\t\tresult["review_mathMl"] = mathPres.getMathMlFromTextInfo(review)
\t\t\t\texcept Exception as error:
\t\t\t\t\tresult["review_mathMl_error"] = repr(error)
\t\t\texcept Exception as error:
\t\t\t\tresult["collector_error"] = repr(error)
\t\t\tfinally:
\t\t\t\tdone.set()

\t\tcore.callLater(0, collect)
\t\tif not done.wait(self._minTimeout(5)):
\t\t\tresult["timeout"] = True
\t\tpayload = json.dumps(result, ensure_ascii=False, default=str)
\t\tlog.warning("ANKI_QT_MATH_CONTEXT " + payload)
\t\treturn payload
'''


def _verify_patch_layout(source: str) -> None:
    tree = ast.parse(source)
    found_global = False
    found_spy = False
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        methods = {
            child.name
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if node.name == "SystemTestSpyServer":
            found_global = "chooseNVDAObjectOverlayClasses" in methods
        elif node.name == "NVDASpyLib":
            found_spy = "get_math_context" in methods
    if not found_global:
        raise RuntimeError("Patched chooser is not a method of SystemTestSpyServer")
    if not found_spy:
        raise RuntimeError("Math diagnostic is not a method of NVDASpyLib")


def patch(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    if "ANKI_QT_MATH_CONTEXT " in original:
        print("Anki Qt MathML bridge and diagnostic already installed")
        return
    if (
        original.count(CLASS_ANCHOR) != 1
        or original.count(CLASS_TERMINATE_ANCHOR) != 1
        or original.count(SPY_DEVINFO_ANCHOR) != 1
    ):
        raise RuntimeError("Unexpected SystemTestSpy source layout; refusing patch")

    updated = original.replace(CLASS_ANCHOR, BRIDGE_CLASS + "\n\n" + CLASS_ANCHOR, 1)
    updated = updated.replace(
        CLASS_TERMINATE_ANCHOR,
        OVERLAY_METHOD + CLASS_TERMINATE_ANCHOR,
        1,
    )
    updated = updated.replace(
        SPY_DEVINFO_ANCHOR,
        SPY_DIAGNOSTIC + SPY_DEVINFO_ANCHOR,
        1,
    )

    compile(updated, str(path), "exec")
    _verify_patch_layout(updated)
    path.write_text(updated, encoding="utf-8", newline="\n")
    print("Applied test-only Anki Qt MathML -> NVDA Role.MATH bridge and diagnostic")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_nvda_qt_math_bridge.py path/to/speechSpyGlobalPlugin.py")
    patch(Path(sys.argv[1]))
