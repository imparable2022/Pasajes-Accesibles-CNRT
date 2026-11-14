"""Reviewer-only opt-in focus and speech, separate from note-editor labels."""
from __future__ import annotations
import json
from . import HERE, OPTIONS, CI_MODE, gui_hooks, mw, QTimer

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
    // MathJax can still be asynchronously typesetting when a card appears.
    // Do not take focus away from its accessible equation structure, even
    // when optional rich-region focusing is enabled.
    if (qa.querySelector("mjx-container, math, svg, .MathJax")) return;

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
        // For cloze deletions the answer changes text *within* the question.
        // Anki renders revealed deletions in .cloze elements, so recognize
        // those explicitly instead of incorrectly expecting an unchanged
        // question prefix. Preserve surrounding HTML for further navigation.
        const clozes = Array.from(qa.querySelectorAll(".cloze"));
        if (clozes.length && (!question || !visible.startsWith(question))) {
            text = normalize(clozes.map(el => el.innerText).join(" "));
            if (text === "[...]" || text === "...") text = "";
        }
        // Basic cards preserve the question and add an answer beneath it.
        if (!text && question && visible.startsWith(question)) {
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
        // Qt WebEngine/NVDA exposed "region" as an unknown role during the
        // image experiment; the same named-group role used by Basic cards is
        // announced correctly without hiding nested content.
        qa.setAttribute("role", "group");
        qa.setAttribute("aria-label", side === "question" ?
            "Question content" : "Answer content");
    }
    qa.focus({ preventScroll: true });
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



def register_reviewer_hooks():
    gui_hooks.card_will_show.append(_card_hook)
    if CI_MODE:
        gui_hooks.reviewer_did_show_question.append(lambda card: _debug_state("question"))
        gui_hooks.reviewer_did_show_answer.append(lambda card: _debug_state("answer"))
