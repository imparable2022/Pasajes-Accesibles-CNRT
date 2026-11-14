"""Editor-field names only; never changes focus or reviewer HTML."""
from __future__ import annotations
from . import HERE, OPTIONS, CI_MODE, gui_hooks

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


def _editor_note_loaded(editor) -> None:
    if not OPTIONS["label_editor_fields"]:
        return
    if CI_MODE:
        HERE.joinpath("editor-hook.marker").write_text("called", encoding="utf-8")
    editor.web.eval(EDITOR_JS)


def register_editor_hooks():
    gui_hooks.editor_did_load_note.append(_editor_note_loaded)
