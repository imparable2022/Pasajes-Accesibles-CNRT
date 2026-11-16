"""Add read-only Qt/UIA math diagnostics to NVDA's system-test spy.

Unlike the earlier causal bridge, this patch does not add overlay classes,
change roles, or synthesize MathML. It only reports what NVDA and the raw UIA
provider already expose, so production transport tests cannot pass because of
the diagnostic itself.
"""
from pathlib import Path
import ast
import sys

SPY_DEVINFO_ANCHOR = "\n\tdef _devInfoToLog(self):"

SPY_DIAGNOSTIC = r'''
\tdef get_math_context(self):
\t\t"""Return raw and NVDA-level math state immediately before NVDA+Alt+M."""
\t\timport json
\t\timport threading
\t\timport core
\t\tresult = {}
\t\tdone = threading.Event()

\t\tdef collect():
\t\t\ttry:
\t\t\t\timport api
\t\t\t\timport controlTypes
\t\t\t\timport mathPres
\t\t\t\timport UIAHandler
\t\t\t\tfrom NVDAObjects.UIA import UIA
\t\t\t\tfrom xml.etree import ElementTree
\t\t\t\tfocus = api.getFocusObject()
\t\t\t\tnav = api.getNavigatorObject()
\t\t\t\treview = api.getReviewPosition()

\t\t\t\tdef inspectMathMl(prefix, value):
\t\t\t\t\tresult[prefix] = value
\t\t\t\t\ttry:
\t\t\t\t\t\troot = ElementTree.fromstring(value)
\t\t\t\t\t\tlocalName = root.tag.rsplit("}", 1)[-1]
\t\t\t\t\t\tresult[prefix + "_root"] = localName
\t\t\t\t\t\tresult[prefix + "_valid"] = localName == "math"
\t\t\t\t\texcept Exception as error:
\t\t\t\t\t\tresult[prefix + "_valid"] = False
\t\t\t\t\t\tresult[prefix + "_validation_error"] = repr(error)

\t\t\t\tfocusDesc = str(getattr(focus, "description", "") or "")
\t\t\t\tnavDesc = str(getattr(nav, "description", "") or "")
\t\t\t\tresult["focus_type"] = type(focus).__name__
\t\t\t\tresult["focus_role"] = str(getattr(focus, "role", None))
\t\t\t\tresult["focus_description"] = focusDesc[:1000]
\t\t\t\tresult["focus_marker_seen"] = focusDesc.startswith("ANKI_MATHML:")
\t\t\t\tresult["navigator_type"] = type(nav).__name__
\t\t\t\tresult["navigator_mro"] = [c.__name__ for c in type(nav).__mro__]
\t\t\t\tresult["navigator_role"] = str(getattr(nav, "role", None))
\t\t\t\tresult["navigator_description"] = navDesc[:1000]
\t\t\t\tresult["navigator_marker_seen"] = navDesc.startswith("ANKI_MATHML:")
\t\t\t\tresult["navigator_is_uia"] = isinstance(nav, UIA)
\t\t\t\tresult["navigator_bridge_overlay"] = "_AnkiQtMathBridge" in result["navigator_mro"]
\t\t\t\tresult["navigator_is_math_role"] = getattr(nav, "role", None) == controlTypes.Role.MATH
\t\t\t\tif isinstance(nav, UIA):
\t\t\t\t\ttry:
\t\t\t\t\t\tresult["raw_uia_control_type"] = nav._getUIACacheablePropertyValue(UIAHandler.UIA_ControlTypePropertyId)
\t\t\t\t\t\tresult["raw_uia_aria_role"] = nav._getUIACacheablePropertyValue(UIAHandler.UIA_AriaRolePropertyId)
\t\t\t\t\t\tresult["raw_uia_localized_control_type"] = nav._getUIACacheablePropertyValue(UIAHandler.UIA_LocalizedControlTypePropertyId)
\t\t\t\t\t\trawMathMl = nav._getUIACacheablePropertyValue(nav._UIACustomProps.word_mathml.id)
\t\t\t\t\t\tresult["raw_uia_mathml"] = rawMathMl
\t\t\t\t\t\tresult["raw_uia_mathml_present"] = bool(rawMathMl)
\t\t\t\t\t\tif rawMathMl:
\t\t\t\t\t\t\tinspectMathMl("raw_uia_mathml", rawMathMl)
\t\t\t\t\texcept Exception as error:
\t\t\t\t\t\tresult["raw_uia_probe_error"] = repr(error)
\t\t\t\tresult["raw_qt_transport_complete"] = (
\t\t\t\t\tstr(result.get("raw_uia_aria_role", "") or "").casefold() == "math"
\t\t\t\t\tand bool(result.get("raw_uia_mathml_valid"))
\t\t\t\t)
\t\t\t\tresult["review_type"] = type(review).__name__
\t\t\t\tresult["review_obj_type"] = type(getattr(review, "obj", None)).__name__
\t\t\t\tresult["review_obj_role"] = str(getattr(getattr(review, "obj", None), "role", None))
\t\t\t\ttry:
\t\t\t\t\tinspectMathMl("navigator_mathMl_property", nav.mathMl)
\t\t\t\texcept Exception as error:
\t\t\t\t\tresult["navigator_mathMl_property_error"] = repr(error)
\t\t\t\ttry:
\t\t\t\t\tgetter = getattr(nav, "_get_mathMl")
\t\t\t\t\tinspectMathMl("navigator_mathMl_getter", getter())
\t\t\t\texcept Exception as error:
\t\t\t\t\tresult["navigator_mathMl_getter_error"] = repr(error)
\t\t\t\tresult["navigator_mathMl_sources_match"] = (
\t\t\t\t\tresult.get("navigator_mathMl_property") is not None
\t\t\t\t\tand result.get("navigator_mathMl_property") == result.get("navigator_mathMl_getter")
\t\t\t\t)
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
\t\treturn json.dumps(result, ensure_ascii=False, default=str)
'''


def _verify(source: str) -> None:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "NVDASpyLib":
            methods = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if "get_math_context" in methods:
                return
    raise RuntimeError("get_math_context was not added to NVDASpyLib")


def patch(path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    if "Return raw and NVDA-level math state immediately before NVDA+Alt+M." in original:
        print("Read-only Qt/UIA math diagnostic already installed")
        return
    if original.count(SPY_DEVINFO_ANCHOR) != 1:
        raise RuntimeError("Unexpected NVDASpyLib source layout; refusing patch")
    updated = original.replace(SPY_DEVINFO_ANCHOR, SPY_DIAGNOSTIC + SPY_DEVINFO_ANCHOR, 1)
    compile(updated, str(path), "exec")
    _verify(updated)
    path.write_text(updated, encoding="utf-8", newline="\n")
    print("Applied read-only Qt/UIA math diagnostic")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_nvda_math_diagnostic.py path/to/speechSpyGlobalPlugin.py")
    patch(Path(sys.argv[1]))
