"""Accessibility prototype for Anki desktop (Windows + NVDA).

The opt-in reviewer feature names and focuses short, noninteractive content
once it has rendered. Complex/long cards retain their DOM and are NOT flattened
into a truncated accessible name. Editor labels are derived from the visible
field names, including notetypes with custom field names.

This is still a test prototype, not a verified universal solution.
"""
from __future__ import annotations

import json
from pathlib import Path
from aqt import gui_hooks, mw

HERE = Path(__file__).resolve().parent
HERE.joinpath("loaded.marker").write_text("loaded", encoding="utf-8")

DEFAULTS = {
    "announce_review_cards": False,
    "announce_questions": True,
    "announce_answers": True,
    "max_auto_speech_characters": 800,
    "label_editor_fields": True,
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
    // Only an explicit opt-in changes focus behavior. 'type in the answer',
    // cloze filters and other interactive templates must retain control.
    if (!__ENABLED__) return;
    const side = __SIDE__;
    if ((side === "question" && !__QUESTION_ENABLED__) ||
        (side === "answer" && !__ANSWER_ENABLED__)) return;
    const disallowed = [
        "input", "textarea", "select", "button", "audio[controls]",
        "video[controls]", "[contenteditable='true']",
        "a[href]", "[role='textbox']", "[role='application']",
        "[tabindex]:not([tabindex='-1'])"
    ];
    if (qa.querySelector(disallowed.join(","))) return;
    // Skip rich visual/mathematical/media content rather than flattening it
    // into an incomplete label. It remains reachable via Anki's normal DOM.
    if (qa.querySelector("img, svg, math, canvas, iframe, object, video, audio")) return;

    // For answers, use the text *after* <hr id="answer">, so NVDA does
    // not read the question again. A missing marker means the card has an
    // unusual template; do not guess the answer boundary.
    let text = "";
    if (side === "answer") {
        const marker = qa.querySelector("#answer");
        if (!marker) return;
        const doc = qa.ownerDocument;
        const range = doc.createRange();
        range.setStartAfter(marker);
        range.setEnd(qa, qa.childNodes.length);
        const holder = doc.createElement("div");
        holder.appendChild(range.cloneContents());
        text = holder.textContent || "";
    } else {
        text = qa.innerText || "";
    }
    text = text.replace(/\s+/g, " ").trim();
    if (!text || text.length > __LIMIT__) return;

    // Preserve the actual card DOM for object navigation and review actions.
    // A focusable named group produces NVDA speech in Qt WebEngine.
    qa.setAttribute("tabindex", "-1");
    qa.setAttribute("role", "group");
    qa.setAttribute("aria-label", text);
    // Calling focus synchronously in onShownHook follows Anki's render queue.
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
    side = "question" if context == "reviewQuestion" else "answer"
    HERE.joinpath("card-hook.marker").write_text(side, encoding="utf-8")
    script = (
        REVIEW_JS.replace("__ENABLED__", json.dumps(bool(OPTIONS["announce_review_cards"])))
        .replace("__QUESTION_ENABLED__", json.dumps(bool(OPTIONS["announce_questions"])))
        .replace("__ANSWER_ENABLED__", json.dumps(bool(OPTIONS["announce_answers"])))
        .replace("__SIDE__", json.dumps(side))
        .replace("__LIMIT__", str(OPTIONS["max_auto_speech_characters"]))
    )
    return html + "<script>onShownHook.push(() => {\n" + script + "\n});</script>"

def _editor_note_loaded(editor) -> None:
    if not OPTIONS["label_editor_fields"]:
        return
    HERE.joinpath("editor-hook.marker").write_text("called", encoding="utf-8")
    editor.web.eval(EDITOR_JS)

gui_hooks.card_will_show.append(_card_hook)
gui_hooks.editor_did_load_note.append(_editor_note_loaded)
