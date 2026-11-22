"""Run real Repeater inside a Windows console with NVDA's system-test speech spy.

No faked spoken announcements: all speech claims come from NvdaLib's actual
NVDA synthesizer spy. Collect diagnostics even when the accessibility gate fails.
"""
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import NvdaLib
from robot.libraries.BuiltIn import BuiltIn

robot = BuiltIn()
out = Path(os.environ["REPEATER_NVDA_OUTPUT"])
out.mkdir(parents=True, exist_ok=True)
exe = Path(os.environ["REPEATER_EXE"]).resolve()
cards = out / "matematicas.md"
proc = None
events = []


def record(stage, **values):
    obj = dict(stage=stage, utc=datetime.now(timezone.utc).isoformat(), **values)
    events.append(obj)
    (out / "repeater-speech.json").write_text(
        json.dumps({"actual_nvda": True, "events": events}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("REPEATER_NVDA " + json.dumps(obj, ensure_ascii=False), flush=True)


def key(stage, combo, seconds=1.5):
    spy = NvdaLib.getSpyLib()
    spy.wait_for_speech_to_finish()
    index = spy.get_next_speech_index()
    spy.emulateKeyPress(combo, blockUntilProcessed=False)
    robot.sleep(f"{seconds} seconds")
    speech = str(spy.get_speech_at_index_until_now(index))
    record(stage, key=combo, speech=speech[:3500])
    return speech


def focus_console():
    import win32con
    import win32gui

    matches = []
    def visit(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "Repeater NVDA Audit" in title:
                matches.append((hwnd, title))

    win32gui.EnumWindows(visit, None)
    if not matches:
        raise AssertionError("No visible Repeater Windows console; NVDA test cannot start.")
    hwnd, title = matches[-1]
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    record("CONSOLE_WINDOW", title=title)
    robot.sleep("2 seconds")


def start_repeater():
    global proc
    assert exe.is_file(), f"Missing compiled Repeater: {exe}"
    cards.write_text(
        "Q: What is the accessibility audit question?\\n"
        "A: The accessible answer is forty two.\\n",
        encoding="utf-8",
    )
    command = (
        f"$Host.UI.RawUI.WindowTitle = 'Repeater NVDA Audit'; "
        f"& '{exe}' drill '{cards}'"
    )
    proc = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-NoExit", "-Command", command],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    robot.sleep("8 seconds")
    focus_console()
    speech = key("NVDA_WINDOW_TITLE", "NVDA+t")
    if "Repeater NVDA Audit" not in speech:
        record("WINDOW_TITLE_NOT_SPOKEN", speech=speech)


def read_question_with_nvda():
    # Ask NVDA to read the actual console, as an end user would.
    result = []
    result.append(key("QUESTION_SAY_ALL", "NVDA+downArrow", 4.0))
    result.append(key("QUESTION_FOCUS_REPORT", "NVDA+tab", 1.5))
    combined = " ".join(result).casefold()
    if "accessibility audit question" not in combined:
        record("QUESTION_NOT_SPOKEN", observed=combined[:2500])
        raise AssertionError("NVDA did not speak Repeater's question; inspect speech evidence.")
    record("QUESTION_SPOKEN", passed=True)


def reveal_answer_with_keyboard():
    key("REVEAL_ANSWER", "space", 1.5)
    spoken = key("ANSWER_SAY_ALL", "NVDA+downArrow", 4.0).casefold()
    if "accessible answer is forty two" not in spoken:
        record("ANSWER_NOT_SPOKEN", observed=spoken[:2500])
        raise AssertionError("NVDA did not speak the revealed answer.")
    record("ANSWER_SPOKEN", passed=True)


def grade_and_exit_with_keyboard():
    key("GRADE_PASS", "enter", 2.0)
    key("WINDOW_AFTER_GRADE", "NVDA+t", 1.0)
    record("GRADE_INPUT_SENT", note="Keys sent; no database success assumed")


def stop_repeater():
    global proc
    if proc is not None and proc.poll() is None:
        try:
            key("EXIT", "escape", 0.5)
        except Exception as exc:
            record("EXIT_KEY_ERROR", error=repr(exc))
        proc.terminate()
        try:
            proc.wait(timeout=7)
        except subprocess.TimeoutExpired:
            proc.kill()
