"""Experimental Anki/Windows-NVDA accessible review-content focus prototype.

The reviewer webview itself receives Qt focus, but the card text does not.
When Anki finishes rendering a card, this prototype focuses the visible card
content as a named group, which makes NVDA announce the card without object
navigation. It is NOT a finished general-purpose accessibility solution:
formatted cards, very long content, images/alt text, cloze, MathJax, media,
other screen readers and focus regressions still need separate validation.
"""
from pathlib import Path
from aqt import gui_hooks

Path(__file__).with_name("loaded.marker").write_text("loaded", encoding="utf-8")

def prepare_card(html, card, context):
    if context not in ("reviewQuestion", "reviewAnswer"):
        return html
    Path(__file__).with_name("card-hook.marker").write_text(context, encoding="utf-8")
    return html + """
<script>
onShownHook.push(() => {
    const content = document.getElementById("qa");
    if (!content) return;
    const text = content.innerText.trim();
    if (!text) return;
    // Trial solution for plain-text cards only. Preserve the existing DOM.
    content.tabIndex = -1;
    content.setAttribute("role", "group");
    content.setAttribute("aria-label", text.slice(0, 1000));
    content.focus({ preventScroll: true });
});
</script>
"""

gui_hooks.card_will_show.append(prepare_card)
