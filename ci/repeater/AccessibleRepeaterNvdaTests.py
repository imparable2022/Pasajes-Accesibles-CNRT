"""Real NVDA speech trial of the opt-in ordinary-console accessible study mode.

Unlike the TUI diagnostic this verifies persisted FSRS review_count through
SQLite, not merely that Robot sent a key press.
"""
import os
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from robot.libraries.BuiltIn import BuiltIn
import NvdaLib

robot = BuiltIn()
root = Path(os.environ["REPEATER_NVDA_OUTPUT"]).resolve()
root.mkdir(parents=True, exist_ok=True)
exe = Path(os.environ["REPEATER_EXE"]).resolve()
deck = root / "accessible-mode.md"
db_dir = root / "db-accessible"
db_dir.mkdir(parents=True, exist_ok=True)
proc = None
events = []
def note(stage, **kwargs):
    entry = dict(stage=stage, utc=datetime.now(timezone.utc).isoformat(), **kwargs)
    events.append(entry)
    (root / "accessible-nvda.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    print("REPEATER_ACCESSIBLE_NVDA " + json.dumps(entry, ensure_ascii=False), flush=True)

def speech_step(stage, key, pause="1.5 seconds"):
    spy = NvdaLib.getSpyLib()
    spy.wait_for_speech_to_finish()
    i = spy.get_next_speech_index()
    spy.emulateKeyPress(key, blockUntilProcessed=False)
    robot.sleep(pause)
    spoken = str(spy.get_speech_at_index_until_now(i))
    note(stage, key=key, speech=spoken[:4000])
    return spoken

def start_accessible_repeater():
    global proc
    deck.write_text("Q: What is the accessible study question?\nA: The accessible study answer is blue.\n", encoding="utf-8")
    cmd = (
        "$Host.UI.RawUI.WindowTitle = 'Repeater Accessible Mode Audit'; "
        f"$env:REPEATER_DATA_DIR = '{db_dir}'; "
        f"& '{exe}' drill --accessible '{deck}'"
    )
    spy = NvdaLib.getSpyLib()
    spy.wait_for_speech_to_finish()
    i = spy.get_next_speech_index()
    proc = subprocess.Popen(["powershell.exe", "-NoProfile", "-NoExit", "-Command", cmd],
                            creationflags=subprocess.CREATE_NEW_CONSOLE)
    robot.sleep("6 seconds")
    spoken = str(spy.get_speech_at_index_until_now(i))
    note("QUESTION_AUTOMATIC_SPEECH", speech=spoken[:4000])
    import win32gui, win32con
    handles=[]
    def visit(hwnd,_):
        if win32gui.IsWindowVisible(hwnd) and "Repeater Accessible Mode Audit" in win32gui.GetWindowText(hwnd):
            handles.append(hwnd)
    win32gui.EnumWindows(visit,None)
    if not handles:
        raise AssertionError("Accessible Repeater console was not found")
    win32gui.ShowWindow(handles[0],win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(handles[0])
    robot.sleep("1 second")
    note("CONSOLE_FOCUS", speech=speech_step("TITLE", "NVDA+t"))
    # An automatic announcement is desirable, but console focus announcements
    # are separately captured rather than silently treated as equivalent.
    if "accessible study question" not in spoken.casefold():
        note("AUTO_QUESTION_NOT_PROVEN", spoken=spoken)

def reveal_accessible_answer():
    # Normal line mode: Enter submits a blank line to reveal the answer.
    note("REVEAL_SPEECH", speech=speech_step("REVEAL", "enter", "2 seconds"))

def grade_and_verify_db():
    note("PASS_SPEECH", speech=speech_step("GRADE_PASS", "enter", "3 seconds"))
    database = db_dir / "cards.db"
    if not database.exists():
        raise AssertionError("Accessible study did not create its SQLite database")
    with sqlite3.connect(database) as con:
        records = con.execute("SELECT review_count FROM cards").fetchall()
    note("DATABASE_REVIEW_COUNT", rows=records)
    if not any(count >= 1 for (count,) in records):
        raise AssertionError("Accessible mode did not persist FSRS review")
    # Distinguish the reliable persistence check from automatic NVDA narration.
    note("PERSISTED_REVIEW", passed=True)

def stop_accessible_repeater():
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()
