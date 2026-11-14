"""Experimental Anki review speech prototype, not a general-release add-on.

It announces the rendered visible card text through an independent ARIA live
region when the question/answer becomes visible. This tests whether live region
notifications work in QWebEngine + NVDA, without requiring object navigation.
Only plain text cards are validated by the CI test. Avoid deploying generally
without testing audio cards, cloze, MathJax, very long cards, and focus behavior.
"""
from pathlib import Path
from aqt import gui_hooks
from aqt.reviewer import Reviewer

Path(__file__).with_name("loaded.marker").write_text("loaded", encoding="utf-8")

_HEAD = r"""
<script>
(function() {
  function initReviewLiveRegion() {
    if (document.getElementById('anki-ci-review-announcer')) return;
    const el = document.createElement('div');
    el.id = 'anki-ci-review-announcer';
    el.setAttribute('role', 'status');
    el.setAttribute('aria-live', 'polite');
    el.setAttribute('aria-atomic', 'true');
    el.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;' +
      'clip-path:inset(50%);white-space:nowrap;';
    document.body.appendChild(el);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReviewLiveRegion, {once:true});
  } else {
    initReviewLiveRegion();
  }
})();
</script>
"""

def on_webview_content(web_content, context):
    if isinstance(context, Reviewer):
        Path(__file__).with_name("webview-hook.marker").write_text("reviewer webview instrumented", encoding="utf-8")
        web_content.head += _HEAD

def prepare_card(html, card, context):
    if context not in ("reviewQuestion", "reviewAnswer"):
        return html
    side = "question" if context == "reviewQuestion" else "answer"
    Path(__file__).with_name("card-hook.marker").write_text(side, encoding="utf-8")
    return html + f"""
<script>
onShownHook.push(() => {{
    const content = document.getElementById('qa');
    const live = document.getElementById('anki-ci-review-announcer');
    if (!content) return;
    const text = content.innerText.trim();
    if (!text) return;
    // Focus rendered content as a named accessibility node. This is an
    // experimental workaround, not a recommended upstream change.
    content.tabIndex = -1;
    content.setAttribute('role', 'group');
    content.setAttribute('aria-label', text.slice(0, 1000));
    content.focus({{ preventScroll: true }});
    // A cleared, stable region avoids relying on focus moving to the text.
    if (live) {{
      live.textContent = '';
      setTimeout(() => {{
        if (document.getElementById('anki-ci-review-announcer') !== live) return;
        live.textContent = text;
      }}, 140);
    }}
}});
</script>
"""

gui_hooks.webview_will_set_content.append(on_webview_content)
gui_hooks.card_will_show.append(prepare_card)
