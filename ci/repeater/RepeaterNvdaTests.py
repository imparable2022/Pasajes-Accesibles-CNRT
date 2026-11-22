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


def run_plain_console_control():
    """Control test: if even plain PowerShell is unreadable, runner may be limiting NVDA."""
    marker = "PLAIN CONSOLE SCREEN READER CONTROL"
    cmd = (
        "$Host.UI.RawUI.WindowTitle = 'Repeater NVDA Audit'; "
        "Write-Output '" + marker + "'"
    )
    baseline = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-NoExit", "-Command", cmd],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    try:
        robot.sleep("3 seconds")
        try:
            focus_console()
        except AssertionError as exc:
            record("PLAIN_CONSOLE_CONTROL_UNAVAILABLE", error=str(exc))
            return
        observed = [key("CONTROL_FOCUS", "NVDA+tab", .4),
                    key("CONTROL_TOP", "shift+numpad7", .4),
                    key("CONTROL_CURRENT", "numpad8", .4)]
        for i in range(15):
            observed.append(key(f"CONTROL_NEXT_{i:02d}", "numpad9", .2))
            if marker.casefold() in " ".join(observed).casefold():
                break
        record("PLAIN_CONSOLE_CONTROL_RESULT",
               passed=marker.casefold() in " ".join(observed).casefold(),
               excerpts=" ".join(observed)[-2000:])
    finally:
        baseline.terminate()
        try:
            baseline.wait(timeout=6)
        except subprocess.TimeoutExpired:
            baseline.kill()
        robot.sleep("1 second")


def start_repeater():
    global proc
    assert exe.is_file(), f"Missing compiled Repeater: {exe}"
    run_plain_console_control()
    cards.write_text(
        "Q: What is the accessibility audit question?\n"
        "A: The accessible answer is forty two.\n",
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


def probe_console_uia(stage):
    """Inspect actual UI Automation children and text patterns independently."""
    import win32gui
    try:
        import uiautomation as auto
        matches = []
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and "Repeater NVDA Audit" in win32gui.GetWindowText(hwnd):
                matches.append(hwnd)
        win32gui.EnumWindows(callback, None)
        if not matches:
            record("UIA_PROBE", stage_name=stage, error="Console hwnd not found")
            return
        root = auto.ControlFromHandle(matches[-1])
        nodes = [(root, 0)]
        report = []
        while nodes and len(report) < 30:
            ctrl, depth = nodes.pop(0)
            item = dict(depth=depth, name=ctrl.Name, control_type=ctrl.ControlTypeName)
            try:
                pat = ctrl.GetPattern(auto.PatternId.TextPattern)
                if pat:
                    item["text"] = pat.DocumentRange.GetText(-1)[:3500]
            except Exception as exc:
                item["text_error"] = repr(exc)[:200]
            try:
                val = ctrl.GetPattern(auto.PatternId.ValuePattern)
                if val:
                    item["value"] = str(val.Value)[:3500]
            except Exception:
                pass
            report.append(item)
            if depth < 4:
                try:
                    nodes.extend((child, depth + 1) for child in ctrl.GetChildren()[:18])
                except Exception as exc:
                    item["children_error"] = repr(exc)[:200]
        record("UIA_PROBE", stage_name=stage, controls=report)
    except Exception as exc:
        record("UIA_PROBE", stage_name=stage, error=repr(exc))


def review_console(stage, needle):
    """Try genuine NVDA desktop/laptop review commands independently.

    Previous run only tried Say All and one Next Line while positioned at
    the bottom border of the console, which cannot prove text inaccessible.
    """
    observed = []
    for name, combo in [
        ("FOCUS", "NVDA+tab"),
        ("OBJECT_REVIEW_CURRENT", "numpad8"),
        ("OBJECT_REVIEW_TOP", "shift+numpad7"),
        ("OBJECT_REVIEW_FIRST", "numpad8"),
    ]:
        observed.append(key(stage + "_" + name, combo, .4))
    for n in range(28):
        observed.append(key(f"{stage}_REVIEW_NEXT_{n+1:02d}", "numpad9", .22))
        if needle in " ".join(observed).casefold():
            break
    # Also test reverse review, laptop mappings and a separate say-all.
    if needle not in " ".join(observed).casefold():
        for name, combo in [
            ("BOTTOM", "shift+numpad9"),
            ("PREVIOUS", "numpad7"),
            ("LAPTOP_TOP", "NVDA+control+home"),
            ("LAPTOP_NEXT", "NVDA+downArrow"),
            ("LAPTOP_CURRENT", "NVDA+shift+."),
            ("SAY_ALL_REVIEW", "numpadPlus"),
        ]:
            observed.append(key(stage + "_" + name, combo, .8))
    passed = needle in " ".join(observed).casefold()
    record(stage + "_RESULT", passed=passed, tested="NVDA review cursor and laptop alternatives",
           searched=needle, speech_excerpt=" ".join(observed)[-2500:])
    return passed


def read_question_with_nvda():
    global question_read
    probe_console_uia("QUESTION")
    question_read = review_console("QUESTION", "accessibility audit question")
    if not question_read:
        record("QUESTION_NOT_SPOKEN", reason="Question absent from all recorded real-NVDA review speech")


def reveal_answer_with_keyboard():
    global answer_read
    key("REVEAL_ANSWER", "space", 1.2)
    probe_console_uia("ANSWER")
    answer_read = review_console("ANSWER", "accessible answer is forty two")
    if not answer_read:
        record("ANSWER_NOT_SPOKEN", reason="Answer absent from all recorded real-NVDA review speech")


def grade_and_exit_with_keyboard():
    key("GRADE_PASS", "enter", 1.0)
    record("GRADE_INPUT_SENT", note="Key sent; no database success assumed")
    if not question_read or not answer_read:
        raise AssertionError(
            f"NVDA accessibility gate failed: question_read={question_read} "
            f"answer_read={answer_read}. Inspect actual speech and UIA evidence."
        )


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
