"""Accessibility prototype for Anki desktop (Windows + NVDA).

The opt-in reviewer feature names and focuses short, noninteractive content
once it has rendered. Complex/long cards retain their DOM and are NOT flattened
into a truncated accessible name. Editor labels are derived from the visible
field names, including notetypes with custom field names.

This is still a test prototype, not a verified universal solution.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from aqt import gui_hooks, mw
from aqt.qt import QTimer

HERE = Path(__file__).resolve().parent
CI_MODE = os.environ.get("ANKI_A11Y_CI") == "1"
if CI_MODE:
    HERE.joinpath("loaded.marker").write_text("loaded", encoding="utf-8")

DEFAULTS = {
    "announce_review_cards": False,
    "announce_questions": True,
    "announce_answers": True,
    "max_auto_speech_characters": 800,
    "label_editor_fields": True,
    "focus_noninteractive_rich_cards": False,
}
try:
    config = mw.addonManager.getConfig(__name__) or {}
except (AttributeError, ValueError):
    config = {}
OPTIONS = {**DEFAULTS, **config}
OPTIONS["max_auto_speech_characters"] = max(40, min(3000, int(OPTIONS["max_auto_speech_characters"])))

REVIEW_JS = r"""
(function () {
    const qa = document.getElementById("qa");
    if (!qa) return;

    // The reviewer reuses #qa for the next card. Restore the original
    // semantics before inspecting new content so stale question labels never
    // remain on an answer, long card, image or interactive card.
    const previousState = window.__ankiA11yReviewFocusState;
    if (previousState && previousState.node === qa) {
        for (const [name, value] of Object.entries(previousState.attrs)) {
            if (value === null) qa.removeAttribute(name);
            else qa.setAttribute(name, value);
        }
        window.__ankiA11yReviewFocusState = null;
    }

    if (!__ENABLED__) return;
    const side = __SIDE__;
    if ((side === "question" && !__QUESTION_ENABLED__) ||
        (side === "answer" && !__ANSWER_ENABLED__)) return;

    const interactive = [
        "input", "textarea", "select", "button", "audio[controls]",
        "video[controls]", "[contenteditable='true']",
        "a[href]", "[role='textbox']", "[role='application']",
        "[tabindex]:not([tabindex='-1'])"
    ];
    // In particular, Anki's type-in-answer box MUST retain focus.
    if (qa.querySelector(interactive.join(","))) return;

    const normalize = value => (value || "").replace(/\s+/g, " ").trim();
    const visible = normalize(qa.innerText);
    const rich = qa.querySelector(
        "img, svg, math, canvas, iframe, object, video, audio, table, " +
        "ul, ol, pre, code, h1, h2, h3, h4, h5, h6, blockquote"
    );
    let text = "";
    if (side === "question") {
        text = visible;
        window.__ankiA11yPreviousQuestion = visible;
    } else {
        const question = normalize(window.__ankiA11yPreviousQuestion);
        // Only remove an exact visible prefix from the answer side.
        if (question && visible.startsWith(question)) {
            text = normalize(visible.slice(question.length));
        }
        if (!text && qa.querySelector("#answer")) {
            // Some templates include markup between question and answer.
            // textContent contains injected scripts, so remove them first.
            try {
                const marker = qa.querySelector("#answer");
                const range = qa.ownerDocument.createRange();
                range.setStartAfter(marker);
                range.setEnd(qa, qa.childNodes.length);
                const fragment = range.cloneContents();
                fragment.querySelectorAll("script,style,template,noscript")
                    .forEach(node => node.remove());
                text = normalize(fragment.textContent);
            } catch (_) {}
        }
    }
    qa.dataset.ankiA11yLastSide = side;
    qa.dataset.ankiA11yLastDerived = text.slice(0, 120);

    const ordinary = Boolean(text) && !rich && text.length <= __LIMIT__;
    const focusRich = !ordinary && __RICH_FOCUS__;
    if (!ordinary && !focusRich) return;

    const snapshot = {};
    for (const attribute of ["role", "tabindex", "aria-label"]) {
        snapshot[attribute] = qa.getAttribute(attribute);
    }
    window.__ankiA11yReviewFocusState = {node: qa, attrs: snapshot};

    qa.setAttribute("tabindex", "-1");
    if (ordinary) {
        qa.setAttribute("role", "group");
        qa.setAttribute("aria-label", text);
    } else {
        // Optional structural navigation: focus the region without flattening
        // images, mathematics, headings or long text into an aria-label.
        qa.setAttribute("role", "region");
        qa.setAttribute("aria-label", side === "question" ?
            "Question content" : "Answer content");
    }
    qa.focus({ preventScroll: true });
})();
"""
EDITOR_JS = r"""
(function () {
    if (window.__ankiA11yEditorLabels) {
        window.__ankiA11yEditorLabels.refresh();
        return;
    }
    const observed = new WeakSet();
    let scheduled = false;
    const allowed = (el) => el instanceof Element;

    function updateLabels() {
        if (!document.body) return;
        const containers = document.querySelectorAll(".field-container[data-index]");
        containers.forEach((container) => {
            const name = container.querySelector(".label-name")?.textContent?.trim();
            if (!name) return;

            // Rich text inputs reside in open shadow DOM. The real focusable
            // <anki-editable> is inside that shadow root, not on its host.
            container.querySelectorAll(".rich-text-editable").forEach((host) => {
                const root = host.shadowRoot;
                if (!root) return;
                watch(root);
                root.querySelectorAll("anki-editable[contenteditable='true']").forEach((el) => {
                    if (el.getAttribute("aria-label") !== name) {
                        el.setAttribute("aria-label", name);
                    }
                });
            });

            // CodeMirror's active textarea is generated dynamically. Do not
            // label the hidden source textarea or modify editor semantics.
            container.querySelectorAll(".CodeMirror textarea").forEach((el) => {
                if (el.getAttribute("aria-label") !== name) {
                    el.setAttribute("aria-label", name);
                }
            });
        });
    }

    const observer = new MutationObserver((records) => {
        // Ignore our own aria-label changes: only re-scan if fields are added,
        // removed or their visible name changes.
        if (records.some(r => r.type === "childList" ||
            (r.type === "characterData") ||
            (r.type === "attributes" && r.attributeName === "data-index"))) {
            schedule();
        }
    });

    function watch(root) {
        if (observed.has(root)) return;
        observed.add(root);
        observer.observe(root, {
            subtree: true,
            childList: true,
            characterData: true,
        });
    }
    function schedule() {
        if (scheduled) return;
        scheduled = true;
        requestAnimationFrame(() => {
            scheduled = false;
            updateLabels();
        });
    }
    window.__ankiA11yEditorLabels = { refresh: schedule };
    watch(document.body);
    updateLabels();
})();
"""

def _card_hook(html: str, card, context: str) -> str:
    if context not in ("reviewQuestion", "reviewAnswer"):
        return html
    # No review HTML, runtime script, or focus changes at all when disabled.
    if not OPTIONS["announce_review_cards"]:
        return html
    if context == "reviewQuestion" and not OPTIONS["announce_questions"]:
        return html
    if context == "reviewAnswer" and not OPTIONS["announce_answers"]:
        return html
    side = "question" if context == "reviewQuestion" else "answer"
    if CI_MODE:
        HERE.joinpath("card-hook.marker").write_text(side, encoding="utf-8")
    script = (
        REVIEW_JS.replace("__ENABLED__", json.dumps(bool(OPTIONS["announce_review_cards"])))
        .replace("__QUESTION_ENABLED__", json.dumps(bool(OPTIONS["announce_questions"])))
        .replace("__ANSWER_ENABLED__", json.dumps(bool(OPTIONS["announce_answers"])))
        .replace("__SIDE__", json.dumps(side))
        .replace("__LIMIT__", str(OPTIONS["max_auto_speech_characters"]))
        .replace("__RICH_FOCUS__", json.dumps(bool(OPTIONS["focus_noninteractive_rich_cards"])))
    )
    return html + "<script>onShownHook.push(() => {\n" + script + "\n});</script>"

def _editor_note_loaded(editor) -> None:
    if not OPTIONS["label_editor_fields"]:
        return
    if CI_MODE:
        HERE.joinpath("editor-hook.marker").write_text("called", encoding="utf-8")
    editor.web.eval(EDITOR_JS)

gui_hooks.card_will_show.append(_card_hook)
gui_hooks.editor_did_load_note.append(_editor_note_loaded)

# Optional CI diagnostics. This reads the rendered UI state after updates;
# it does not alter Anki's collection or the accessible experience.
def _debug_state(side):
    def capture():
        if not mw or not mw.reviewer:
            return
        code = r'''(() => {
            const qa=document.querySelector("#qa");
            const hr=qa?.querySelector("#answer");
            return JSON.stringify({
                answerMarker: !!hr, side:qa?.dataset.ankiA11yLastSide,
                derived:qa?.dataset.ankiA11yLastDerived,
                text:qa?.innerText?.slice(0,500),
                aria:qa?.getAttribute("aria-label"),
                active:document.activeElement?.id,
                previous:window.__ankiA11yPreviousQuestion,
            });
        })()'''
        def callback(value):
            HERE.joinpath("reviewer-debug-" + side + ".json").write_text(str(value), encoding="utf-8")
        mw.reviewer.web.evalWithCallback(code, callback)
    QTimer.singleShot(1800, capture)

if CI_MODE:
    gui_hooks.reviewer_did_show_question.append(lambda card: _debug_state("question"))
    gui_hooks.reviewer_did_show_answer.append(lambda card: _debug_state("answer"))
