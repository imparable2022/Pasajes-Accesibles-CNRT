"""Isolated behavioral regression for the proposed upstream Anki audio patch.

Run in a checkout where patch 0002 has been applied:
    python ../anki-a11y/upstream-ready/test_audio_patch.py
Only the one function's AST is executed with benign stub dependencies. It
does not require an installed Anki profile or any Qt audio device.
"""
import ast
import re
from html import escape
from pathlib import Path
from types import SimpleNamespace

source = Path("qt/aqt/sound.py").read_text(encoding="utf-8")
parsed = ast.parse(source)
definition = next(
    node for node in parsed.body
    if isinstance(node, ast.FunctionDef) and node.name == "av_refs_to_play_icons"
)
function_code = compile(ast.Module(body=[definition], type_ignores=[]),
                        "qt/aqt/sound.py", "exec")

def render(translated):
    fake_tr = SimpleNamespace(actions_replay_audio=lambda: translated)
    scope = {
        "re": re,
        "escape": escape,
        "tr": fake_tr,
        "AV_REF_RE": re.compile(r"\{\{(play:[qa]:\d+)\}\}"),
    }
    exec(function_code, scope)
    return scope["av_refs_to_play_icons"]("Before {{play:q:0}} and {{play:a:2}}")

standard = render("Replay Audio")
assert standard.count('aria-label="Replay Audio"') == 2, standard
assert standard.count('focusable="false"') == 2, standard
assert standard.count('aria-hidden="true"') == 2, standard
assert "pycmd('play:q:0')" in standard and "pycmd('play:a:2')" in standard
assert standard.count('href=#') == 2, standard
assert standard.count("return false") == 2
special = render('Reproducir <audio> "ahora" & antes')
assert 'aria-label="Reproducir &lt;audio&gt; &quot;ahora&quot; &amp; antes"' in special
print("Audio icon labels: localized, HTML-escaped, keyboard-focusable, original pycmd preserved")
