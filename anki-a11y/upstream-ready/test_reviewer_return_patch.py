"""Isolated behavior test for Return v. Space/R in the official Reviewer patch.

Read the patched upstream source, extract only _on_return_key() by AST, and
test it with fake Qt webviews. The real-NVDA scenario is separately checked.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

source = Path("qt/aqt/reviewer.py").read_text(encoding="utf-8")
tree = ast.parse(source)
reviewer = next(x for x in tree.body
                if isinstance(x, ast.ClassDef) and x.name == "Reviewer")
new_function = next(x for x in reviewer.body
                    if isinstance(x, ast.FunctionDef) and x.name == "_on_return_key")
scope = {}
exec(compile(ast.Module(body=[new_function], type_ignores=[]),
             "<reviewer return audio>", "exec"), scope)
handle = scope["_on_return_key"]

def make_case(audio: bool, focused: bool):
    actions = []
    view = SimpleNamespace(
        evalWithCallback=lambda js, callback: (actions.append(("evalWithCallback", js)), callback(focused)),
        eval=lambda js: actions.append(("eval", js)),
    )
    card = SimpleNamespace(
        question_av_tags=lambda: ["Sound"] if audio else [],
        answer_av_tags=lambda: [],
    )
    obj = SimpleNamespace(card=card, web=view,
                          onEnterKey=lambda: actions.append(("onEnterKey", None)))
    handle(obj)
    return actions

focused = make_case(True, True)
assert sum(x[0]=="eval" for x in focused)==1, focused
assert ("eval","document.activeElement.click();") in focused
assert not any(x[0]=="onEnterKey" for x in focused), focused
assert "document.hasFocus()" in focused[0][1],focused
assert "a.replay-button.soundLink" in focused[0][1],focused
not_focused = make_case(True, False)
assert ("onEnterKey",None) in not_focused,not_focused
assert not any(x[0]=="eval" for x in not_focused),not_focused
no_audio = make_case(False,True)
assert no_audio == [("onEnterKey",None)],no_audio
assert "(Qt.Key.Key_Return, self._on_return_key)" in source
assert "(Qt.Key.Key_Enter, self._on_return_key)" in source
assert '(" ", self.onEnterKey)' in source
assert '("r", self.replayAudio)' in source
assert '(Qt.Key.Key_F5, self.replayAudio)' in source
print("Reviewer's Return handles focused audio links and retains non-audio, Space and R/F5 behavior")
