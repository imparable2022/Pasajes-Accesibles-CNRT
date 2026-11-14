"""Opt-in semantic MathML focus: preserve math nodes for NVDA MathCAT.

This intentionally does NOT flatten a formula into a text/ARIA label.
If MathJax has already emitted assistive MathML we reuse that node;
otherwise we request MathML from MathJax's own parsed expression tree.
"""
import json
from . import HERE, OPTIONS, CI_MODE, gui_hooks

MATH_FOCUS_JS = r"""
(function () {
  const qa = document.getElementById("qa");
  if (!qa) return;
  const containers = [...qa.querySelectorAll("mjx-container")];
  const report = {containers: containers.length, nativeMath: 0,
    injectedMath: 0, focusedMath: 0, mathjaxVersion: window.MathJax?.version || "",
    sample: "", errors: []};
  window.__ankiA11yMathReport = report;
  if (!containers.length) return;
  const startup = window.MathJax?.startup;
  const items = startup?.document?.math ? [...startup.document.math] : [];
  const results = [];

  for (const visual of containers) {
    // MathJax 3 ships with an assistive-MathML output extension.
    // A node is only useful when it is exposed in the accessibility tree.
    let math = visual.querySelector("mjx-assistive-mml math, math[xmlns], math");
    if (math) {
      report.nativeMath++;
    } else if (startup?.toMML) {
      const item = items.find(entry => entry.typesetRoot === visual);
      if (item?.root) {
        try {
          const serialized = startup.toMML(item.root);
          const parsed = new DOMParser().parseFromString(serialized, "application/xml");
          if (parsed.querySelector("parsererror")) throw new Error("Invalid generated MathML");
          math = document.importNode(parsed.documentElement, true);
          const wrapper = document.createElement("span");
          wrapper.className = "anki-a11y-assistive-math";
          wrapper.style.cssText =
            "position:absolute;width:1px;height:1px;padding:0;overflow:hidden;" +
            "clip-path:inset(50%);white-space:nowrap;";
          wrapper.appendChild(math);
          visual.after(wrapper);
          report.injectedMath++;
        } catch (error) {
          report.errors.push(String(error).slice(0,250));
        }
      }
    }
    if (!math) continue;
    if (math.localName !== "math") continue;
    // Controlled Qt WebEngine experiment: clone the unmodified MathML
    // outside MathJax's assistive wrapper, keeping its native structure.
    if (__DETACHED__) {
      const clone = math.cloneNode(true);
      const host = document.createElement("span");
      host.className = "anki-a11y-mathml-isolation-test";
      host.style.cssText = "position:absolute;width:1px;height:1px;" +
        "overflow:hidden;clip-path:inset(50%);white-space:nowrap;";
      host.appendChild(clone);
      visual.after(host);
      math = clone;
      report.injectedMath++;
    }
    // Qt WebEngine exposes the native MathML as role "unknown" to NVDA.
    // Try an explicit ARIA math role without linearizing or duplicating
    // the equation. This is a controlled experiment, not an upstream fix.
    math.setAttribute("role", "math");
    math.setAttribute("tabindex", "0");
    results.push(math);
    report.sample = math.outerHTML.slice(0,1200);
  }
  if (results.length > 0) {
    // Move focus only in the explicit opt-in mode. Ordinary keyboard users
    // and any typed-answer field retain the existing Anki focus behavior.
    if (!qa.querySelector("input,textarea,select,[contenteditable='true']")) {
      results[0].focus({preventScroll:true});
      report.focusedMath = document.activeElement === results[0] ? 1 : 0;
    }
  }
})();
"""

def add_math_navigation(html, card, context):
    if context not in ("reviewQuestion", "reviewAnswer"):
        return html
    if not OPTIONS.get("experimental_mathml_focus", False):
        return html
    # Append after the normal reviewer body (and its existing hooks).
    code = MATH_FOCUS_JS.replace("__DETACHED__", json.dumps(bool(OPTIONS.get("experimental_mathml_detached", False))))
    return html + "<script>onShownHook.push(() => {\n" + code + "\n});</script>"

def register_math_hooks():
    gui_hooks.card_will_show.append(add_math_navigation)
