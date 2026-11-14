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
        self.assertEqual(html, "<div>Question</div>")

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
        self.assertEqual(q, "")
        self.assertIn('const side = "answer"', a)
        self.assertIn("&& !true", a)
        self.assertIn("text.length <= 1200", a)

    def test_prevents_long_content_truncation_and_unsafe_interactions(self):
        addon, hooks = load_addon({"announce_review_cards": True})
        js = hooks.card_will_show[0]("", None, "reviewQuestion")
        self.assertIn("text.length <= 800", js)
        self.assertNotIn("text.slice(0, 1000)", js)
        self.assertIn("input", js)
        self.assertIn("img, svg, math", js)
        self.assertIn("Question content", js)
        self.assertIn("previousState.attrs", js)
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

    def test_default_does_not_inject_or_mutate_review_html(self):
        addon, hooks = load_addon()
        before = '<div class="card"><img src="test.png" alt="diagram"></div>'
        for context in ("reviewQuestion", "reviewAnswer"):
            self.assertEqual(before, hooks.card_will_show[0](before, None, context))

    def test_interactive_content_opt_in_is_not_enforced_by_removing_controls(self):
        addon, hooks = load_addon({"announce_review_cards": True})
        html = '<input id="typeans" aria-label="Type your answer">'
        output = hooks.card_will_show[0](html, None, "reviewQuestion")
        self.assertTrue(output.startswith(html))
        self.assertIn("if (qa.querySelector(interactive.join", output)

    def _run_dom_cases(self, cases):
        harness = Path(__file__).parent / "review_dom_harness.js"
        run = subprocess.run(["node", str(harness)], input=json.dumps({"cases": cases}),
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(run.returncode, 0, run.stderr)
        return {row["name"]: row for row in json.loads(run.stdout)}

    def test_real_javascript_question_answer_short_and_complex_content(self):
        addon, hooks = load_addon({"announce_review_cards": True})
        question = hooks.card_will_show[0]("", None, "reviewQuestion")
        answer = hooks.card_will_show[0]("", None, "reviewAnswer")
        cases = [
            {"name":"plain-question", "source":question, "text":"Sample question"},
            {"name":"plain-answer", "source":answer, "text":"Sample question New answer",
             "previousQuestion":"Sample question", "answerMarker":True},
            {"name":"answer-with-no-known-boundary", "source":answer,
             "text":"Standalone answer", "previousQuestion":"", "answerMarker":False},
            {"name":"long-question", "source":question, "text":"X"*900},
            {"name":"typed-answer", "source":question,
             "text":"Write the answer", "tags":["input"]},
            {"name":"link", "source":question, "text":"Follow a link",
             "tags":["a"]},
            {"name":"interactive-button", "source":question, "text":"Button",
             "tags":["button"]},
            {"name":"prior-focused-complex-card", "source":answer,
             "text":"Image on answer", "tags":["img"],"priorPatch":True,
             "initialAttrs":{"role":"group","tabindex":"-1","aria-label":"Old question"}},
        ]
        rich_types = ["img", "svg", "math", "canvas", "iframe", "object",
                      "audio", "video", "table", "ul", "ol", "pre", "code",
                      "h1", "h2", "blockquote"]
        for tag in rich_types:
            cases.append({"name":"rich-"+tag, "source":question,
                          "text":"Content with "+tag, "tags":[tag]})
        data = self._run_dom_cases(cases)
        for name, label in [
            ("plain-question", "Sample question"),
            ("plain-answer", "New answer"),
        ]:
            self.assertEqual(data[name]["focusCount"], 1, name)
            self.assertEqual(data[name]["active"], "card", name)
            self.assertEqual(data[name]["attrs"]["aria-label"], label, name)
            self.assertEqual(data[name]["attrs"]["role"], "group", name)
        self.assertEqual(data["plain-question"]["previousQuestion"], "Sample question")
        for name in ["answer-with-no-known-boundary", "long-question",
                     "typed-answer", "link", "interactive-button"]+[
                     "rich-"+tag for tag in rich_types]:
            with self.subTest(name=name):
                self.assertEqual(data[name]["focusCount"], 0)
                self.assertEqual(data[name]["active"], "unchanged")
                self.assertNotIn("aria-label", data[name]["attrs"])
        self.assertEqual(data["prior-focused-complex-card"]["focusCount"], 0)
        self.assertEqual(data["prior-focused-complex-card"]["attrs"], {},
                         "Stale question must not remain the accessible name of an image")

    def test_optional_rich_region_is_not_flattened_into_aria_text(self):
        addon, hooks = load_addon({
            "announce_review_cards":True, "focus_noninteractive_rich_cards":True})
        js = hooks.card_will_show[0]("", None, "reviewQuestion")
        data = self._run_dom_cases([
            {"name":"image-focus", "source":js, "tags":["img"], "text":"Description"},
            {"name":"long-focus", "source":js, "text":"D"*1400},
            {"name":"typed-answer-still-safe", "source":js, "tags":["input"],
             "text":"Please type"},
        ])
        for name in ["image-focus","long-focus"]:
            self.assertEqual(data[name]["focusCount"], 1)
            self.assertEqual(data[name]["attrs"]["role"], "region")
            self.assertEqual(data[name]["attrs"]["aria-label"], "Question content")
        self.assertEqual(data["typed-answer-still-safe"]["focusCount"], 0)

    def test_original_qa_semantics_are_restored(self):
        addon, hooks = load_addon({"announce_review_cards":True})
        answer = hooks.card_will_show[0]("", None, "reviewAnswer")
        original = {"role":"region","aria-label":"Original reviewer label","tabindex":"1"}
        data = self._run_dom_cases([{
            "name":"original-semantic-attributes", "source":answer,
            "text":"Image", "tags":["img"], "priorPatch":True,
            "initialAttrs":{"role":"group","aria-label":"Old question","tabindex":"-1"},
            "savedAttrs":original,
        }])["original-semantic-attributes"]
        self.assertEqual(data["attrs"], original)

    def test_editor_label_reacts_to_custom_field_names_without_moving_focus(self):
        addon, hooks = load_addon({"label_editor_fields":True})
        data = self._run_dom_cases([{
            "name":"renamed-field",
            "editorScript":addon.EDITOR_JS,
            "fieldName":"Front",
            "updatedFieldName":"Mi pregunta",
        }])["renamed-field"]
        self.assertEqual(data["initial"], {"rich":"Front","plain":"Front"})
        self.assertEqual(data["updated"], {"rich":"Mi pregunta","plain":"Mi pregunta"})
        self.assertGreaterEqual(data["observerCount"], 1)

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
