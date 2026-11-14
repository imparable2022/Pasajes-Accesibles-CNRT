"""Genuine NVDA speech capture in Anki Desktop, using NV Access' Robot harness.

This suite intentionally records evidence rather than claiming full E2E coverage.
"""
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from robot.libraries.BuiltIn import BuiltIn
import NvdaLib

robot = BuiltIn()
out = Path(os.environ["ANKI_A11Y_OUTPUT"])
out.mkdir(parents=True, exist_ok=True)
records = []
process = None

def save():
    (out / "speech.json").write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actual_nvda": True,
        "complete_e2e": False,
        "records": records,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

def press(label, keys, seconds=0.9):
    spy = NvdaLib.getSpyLib()
    index = spy.get_next_speech_index()
    spy.emulateKeyPress(keys, blockUntilProcessed=False)
    robot.sleep(f"{seconds} seconds")
    speech = str(spy.get_speech_at_index_until_now(index))
    records.append({"step": label, "keys": keys, "speech": speech})
    save()
    robot.log(f"{label}: {speech}")
    return speech

def start_anki_for_testing():
    global process
    exe = os.environ.get("ANKI_EXE", "")
    if not Path(exe).is_file():
        raise AssertionError(f"Missing Anki executable: {exe!r}")
    base = out / "isolated-profile"
    base.mkdir(exist_ok=True)
    process = subprocess.Popen([exe, "-b", str(base)])
    robot.sleep("18 seconds")
    title = press("first foreground window", "NVDA+t")
    if not title.strip():
        raise AssertionError("NVDA did not speak the foreground window title")

def inspect_keyboard_journey():
    failures = []
    keys = [("focus at start", "NVDA+tab")]
    keys += [(f"tab forward {i}", "tab") for i in range(1, 13)]
    keys += [(f"shift tab {i}", "shift+tab") for i in range(1, 7)]
    keys += [
        ("shortcut Add", "a"), ("Add title", "NVDA+t"),
        ("Add focus", "NVDA+tab"),
    ]
    keys += [(f"Add form tab {i}", "tab") for i in range(1, 13)]
    keys += [
        ("close Add", "escape"), ("focus after Add", "NVDA+tab"),
        ("shortcut Browse", "b"), ("Browse title", "NVDA+t"),
        ("Browse focus", "NVDA+tab"), ("escape Browse", "escape"),
        ("focus after Browse", "NVDA+tab")
    ]
    spoken = 0
    try:
        for label, key in keys:
            if press(label, key).strip():
                spoken += 1
    finally:
        records.append({"summary": {"steps": len(keys), "speech_nonempty": spoken,
                                     "complete_functional_journey": False}})
        save()
    if spoken < 5:
        raise AssertionError(f"Only {spoken} keyboard steps produced NVDA speech")

def stop_anki_for_testing():
    save()
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
