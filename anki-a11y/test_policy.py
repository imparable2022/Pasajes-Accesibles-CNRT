"""Fast policy/syntax checks for the isolated accessibility prototype.

They complement the real NVDA/Qt Windows test, not replace it.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ADDON_FILE = Path(__file__).parent / "anki-accessibility-prototype" / "__init__.py"


def load_addon(options=None):
    hooks = types.SimpleNamespace(**{
        key: [] for key in (
            "card_will_show", "editor_did_load_note",
            "reviewer_did_show_question", "reviewer_did_show_answer"
        )
    })
    mw = types.SimpleNamespace(addonManager=types.SimpleNamespace(
        getConfig=lambda name: options or {}
    ))
    fake_aqt = types.ModuleType("aqt")
    fake_aqt.gui_hooks = hooks
    fake_aqt.mw = mw
    fake_qt = types.ModuleType("aqt.qt")
    fake_qt.QTimer = types.SimpleNamespace(singleShot=lambda ms, fn: None)
    previous = (sys.modules.get("aqt"), sys.modules.get("aqt.qt"))
    oldenv = os.environ.pop("ANKI_A11Y_CI", None)
    try:
        sys.modules["aqt"] = fake_aqt
        sys.modules["aqt.qt"] = fake_qt
        spec = importlib.util.spec_from_file_location("anki_ci_review_announcer", ADDON_FILE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, hooks
    finally:
        for k, prior in zip(("aqt", "aqt.qt"), previous):
            if prior is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = prior
        if oldenv is not None:
            os.environ["ANKI_A11Y_CI"] = oldenv


class AnkiAccessibilityPolicyTests(unittest.TestCase):
    def test_default_does_not_move_focus(self):
        addon, hooks = load_addon()
        self.assertFalse(addon.OPTIONS["announce_review_cards"])
        html = hooks.card_will_show[0]("<div>Question</div>", None, "reviewQuestion")
        self.assertIn("if (!false) return;", html)

    def test_unknown_context_unchanged(self):
        addon, hooks = load_addon()
        html = "<p>keep me</p>"
        self.assertEqual(html, hooks.card_will_show[0](html, None, "previewQuestion"))

    def test_opt_in_and_independent_sides(self):
        addon, hooks = load_addon({
            "announce_review_cards": True,
            "announce_questions": False,
            "announce_answers": True,
            "max_auto_speech_characters": 1200
        })
        q = hooks.card_will_show[0]("", None, "reviewQuestion")
        a = hooks.card_will_show[0]("", None, "reviewAnswer")
        self.assertIn('const side = "question"', q)
        self.assertIn('const side = "answer"', a)
        self.assertIn("&& !false", q)
        self.assertIn("&& !true", a)
        self.assertIn("text.length > 1200", a)

    def test_prevents_long_content_truncation_and_unsafe_interactions(self):
        addon, hooks = load_addon({"announce_review_cards": True})
        js = hooks.card_will_show[0]("", None, "reviewQuestion")
        self.assertIn("text.length > 800", js)
        self.assertNotIn("text.slice(0, 1000)", js)
        self.assertIn("input", js)
        self.assertIn("img, svg, math", js)
        self.assertIn('content.focus({ preventScroll: true })', js.replace('qa.focus', 'content.focus'))

    def test_editor_labels_can_be_disabled_independently(self):
        addon, hooks = load_addon({"label_editor_fields": False})
        self.assertEqual(len(hooks.editor_did_load_note), 1)
        call_count = []
        fake_editor = types.SimpleNamespace(web=types.SimpleNamespace(eval=lambda js: call_count.append(js)))
        hooks.editor_did_load_note[0](fake_editor)
        self.assertEqual(call_count, [])

    def test_editor_label_hook_includes_shadow_dom_and_codemirror(self):
        addon, hooks = load_addon({"label_editor_fields": True})
        outputs = []
        fake_editor = types.SimpleNamespace(web=types.SimpleNamespace(eval=lambda js: outputs.append(js)))
        hooks.editor_did_load_note[0](fake_editor)
        self.assertEqual(len(outputs), 1)
        self.assertIn("shadowRoot", outputs[0])
        self.assertIn("anki-editable", outputs[0])
        self.assertIn(".CodeMirror textarea", outputs[0])
        self.assertIn("MutationObserver", outputs[0])

    def test_javascript_is_valid(self):
        addon, hooks = load_addon({"announce_review_cards": True})
        programs = [
            hooks.card_will_show[0]("", None, "reviewQuestion"),
            hooks.card_will_show[0]("", None, "reviewAnswer"),
            addon.EDITOR_JS,
        ]
        with tempfile.TemporaryDirectory() as temp:
            for index, source in enumerate(programs):
                script = source.removeprefix("<script>").removesuffix("</script>")
                output = Path(temp) / f"check{index}.js"
                output.write_text(script, encoding="utf-8")
                check = subprocess.run(["node", "--check", str(output)],
                                       capture_output=True, text=True)
                self.assertEqual(check.returncode, 0, check.stderr)


if __name__ == "__main__":
    unittest.main()
