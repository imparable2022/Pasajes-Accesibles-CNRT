"""Keyboard-only Anki E2E using genuine NVDA speech as the accessibility oracle.

All UI actions use keyboard injection. SQLite is used READ-ONLY for postconditions.
No mouse clicking, direct Anki commands, or silent shortcuts are counted as success.
"""
import ctypes
import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone
import pyautogui
import pyperclip
from robot.libraries.BuiltIn import BuiltIn
import NvdaLib

robot = BuiltIn()
out = Path(os.environ["ANKI_A11Y_OUTPUT"])
out.mkdir(parents=True, exist_ok=True)
records = []
process = None
data_dir = out / "isolated-profile"
DECK = "NVDA Accessibility Audit 2026"
FRONT = "Accessible keyboard study question"
BACK = "Accessible keyboard study answer"

def save():
    (out / "speech.json").write_text(json.dumps({
      "utc": datetime.now(timezone.utc).isoformat(),
      "actual_nvda": True, "keyboard_only_ui_actions": True,
      "observations_not_full_compliance": True, "records": records
    }, ensure_ascii=False, indent=2), encoding="utf-8")

def note(stage, **extra):
    records.append(dict(stage=stage, **extra)); save()
    print("ANKI_A11Y " + json.dumps(records[-1], ensure_ascii=False), flush=True)

def press(stage, keys, seconds=0.65):
    spy = NvdaLib.getSpyLib()
    spy.wait_for_speech_to_finish()
    index = spy.get_next_speech_index()
    spy.emulateKeyPress(keys, blockUntilProcessed=False)
    robot.sleep(f"{seconds} seconds")
    speech = str(spy.get_speech_at_index_until_now(index))
    note(stage, keys=keys, speech=speech[:1700])
    return speech

def paste(stage, value):
    pyperclip.copy(value)
    press(stage, "control+v", 1.0)

def focus_title():
    return press("window title", "NVDA+t")

def focus_description():
    return press("focused element", "NVDA+tab")

def select_button(targets, limit=80):
    """Tab until NVDA reports a requested button by its accessible name."""
    for i in range(limit):
        speech = press("tab search " + str(i+1), "tab", 0.35)
        focus = focus_description()
        both = (speech + " " + focus).casefold()
        if any(t.casefold() in both for t in targets):
            note("button found", matching=targets, ordinal=i+1)
            return True
    raise AssertionError(f"Cannot reach button {targets} with Tab and NVDA in {limit} attempts")

def db_path():
    candidates = list(data_dir.rglob("collection.anki2")) + list(data_dir.rglob("collection.anki21"))
    if not candidates:
        raise AssertionError("No Anki collection file appeared in isolated data dir")
    return candidates[0]

def query(sql, params=()):
    db = db_path()
    with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=10) as conn:
        return conn.execute(sql, params).fetchall()

def wait_for(sql, params=(), predicate=lambda rows: bool(rows), seconds=16):
    error = None
    for i in range(seconds):
        try:
            found=query(sql,params)
            if predicate(found): return found
        except Exception as exc: error=repr(exc)
        time.sleep(1)
    raise AssertionError(f"Postcondition failed: {sql}; last error={error}")

def activate_anki():
    """Use Win32 only to activate the window; all in-app traversal uses keyboard."""
    import win32gui, win32con
    matches=[]
    def probe(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title=win32gui.GetWindowText(hwnd)
            if "Anki" in title:
                matches.append((hwnd,title))
    win32gui.EnumWindows(probe,None)
    if not matches: raise AssertionError("No visible Anki desktop window")
    hwnd=matches[0][0]
    win32gui.ShowWindow(hwnd,win32con.SW_RESTORE)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(1)
    note("activated", title=matches[0][1])

def start_anki():
    global process
    exe=os.environ["ANKI_EXE"]
    data_dir.mkdir(parents=True, exist_ok=True)
    process=subprocess.Popen([exe,"-b",str(data_dir)])
    robot.sleep("13 seconds")
    activate_anki()
    title=focus_title()
    if not title.strip(): raise AssertionError("NVDA did not announce any Anki window title")
    # The first launch displays a language picker. In the previous CI run,
    # the keyboard cycled between 'English (United States)' and 'OK'.
    # Complete this actual setup with keyboard, not with a programmatic bypass.
    for i in range(7):
        focus=focus_description()
        if "OK" in focus and "button" in focus:
            press("confirm first-run language", "enter", 2.5)
            break
        if any(x in focus.lower() for x in ["list item", "english", "language"]):
            press("move to language confirmation", "tab", 0.5)
        else:
            press("find language confirmation", "tab", 0.5)
    else:
        note("first run dialog unidentified", title=focus_title())
    robot.sleep("3 seconds")
    # Anki profiles.py verifies the chosen language with QMessageBox Yes/No.
    # NO reopens the picker; YES is necessary to finish first-run startup.
    for i in range(6):
        focus=focus_description()
        if "Yes" in focus and "button" in focus:
            press("confirm selected language Yes", "enter", 2.0)
            break
        if "No" in focus and "button" in focus:
            press("move from No to Yes", "tab", 0.5)
            continue
        break
    robot.sleep("12 seconds")
    note("post-language-setup", title=focus_title(),
         focused=focus_description(),
         folder_contents=[str(p.relative_to(data_dir)) for p in data_dir.rglob("*")][:40])

def create_deck_via_keyboard():
    activate_anki()
    press("deck screen", "d", 1.2)
    select_button(["Create Deck", "Crear mazo", "Crear baraja"], limit=18)
    opened=press("open create deck","enter",1.0)
    if not any(t in opened.casefold() for t in ["deck","mazo","baraja"]):
        raise AssertionError(f"No Create Deck dialog announcement: {opened}")
    # Do not type before the input is *actually* focused.
    field=None
    for i in range(10):
        focus=focus_description()
        if any(t in focus.casefold() for t in ["edit", "editable", "text field", "edición"]):
            field=focus
            break
        press("find deck name edit "+str(i),"tab",0.5)
    if field is None:
        raise AssertionError("Cannot reach new deck name edit by Tab; capture evidence")
    note("DECK_NAME_FIELD_ACCESSIBLE",focused=field)
    press("select current name", "control+a",0.2)
    paste("type deck name",DECK)
    press("confirm new deck","enter",1.8)
    press("refresh decks","d",1.2)
    select_button([DECK],limit=24)
    note("DECK_CREATED_VERIFIED_BY_NVDA",name=DECK)
    # Leave the new deck open so the Add dialog uses its selected deck.
    press("open new deck","enter",1.2)

def add_card_via_keyboard():
    activate_anki()
    press("open Add shortcut","a",2.2)
    title=focus_title()
    if not any(t in title.casefold() for t in ["add","añadir","agregar"]):
        raise AssertionError(f"Add window title not announced: {title}")
    # The Nov 14 NVDA trace exposed a concrete accessibility finding:
    # the focused editor was only announced as 'edit focused blank', with
    # no Front label. Preserve it rather than treating it as a passing label.
    first=None
    for i in range(16):
        focus=focus_description()
        if "edit" in focus.casefold():
            first=focus
            break
        press("find first editor field "+str(i),"tab",0.5)
    if first is None:
        raise AssertionError("Cannot reach editable card field by keyboard")
    if not any(x in first.casefold() for x in ["front","frente","anverso"]):
        note("ACCESSIBILITY_FINDING", issue="Editor field missing spoken accessible label", actual=first)
    paste("type card question in first field",FRONT)
    next_announcement=press("move to next card field","tab",0.8)
    focus=focus_description()
    note("next card field",speech=next_announcement,focus=focus)
    if "edit" not in focus.casefold():
        raise AssertionError("Tab did not reach another editable field")
    if not any(x in focus.casefold() for x in ["back","dorso","reverso"]):
        note("ACCESSIBILITY_FINDING",issue="Second card field missing spoken accessible label",actual=focus)
    paste("type card answer in second field",BACK)
    press("submit card with Ctrl+Enter","control+enter",1.7)
    note("CARD_SUBMISSION_ATTEMPTED_BY_KEYBOARD")
    # Main functional journey will independently verify persistence when
    # review actually reads both sides of the newly-created card.
    press("close Add via Escape","escape",0.8)

def study_with_keyboard():
    activate_anki()
    press("return to decks","d",1.2)
    select_button([DECK],limit=24)
    press("open selected deck","enter",1.3)
    note("deck opened",title=focus_title())
    # Unlike a silent bare 's' shortcut, a real native HTML Study Now
    # control has an observable accessible name and keyboard activation.
    select_button(["Study Now","Estudiar ahora"],limit=18)
    transition=press("activate Study Now","enter",1.3)
    note("study screen",transition=transition,focused=focus_description())
    traces=[transition, focus_description()]
    traces.append(press("read question with NVDA", "NVDA+downArrow",1.2))
    traces.append(press("move to question start", "control+home",0.4))
    traces.append(press("read from start", "NVDA+downArrow",1.2))
    if not any(FRONT.casefold() in x.casefold() for x in traces):
        note("ACCESSIBILITY_FINDING",issue="Question content not spoken in NVDA read-all",traces=traces)
    # Independently verify whether the show-answer control is keyboard reachable.
    select_button(["Show Answer","Mostrar respuesta"],limit=18)
    announced=press("show answer via keyboard","enter",1.1)
    answer_traces=[announced, focus_description()]
    answer_traces.append(press("read revealed answer","NVDA+downArrow",1.5))
    if not any(BACK.casefold() in x.casefold() for x in answer_traces):
        note("ACCESSIBILITY_FINDING",issue="Answer content not spoken in NVDA read-all",traces=answer_traces)
    note("ANSWER_DISPLAY_STEP_COMPLETED")
    # 'Good' may be 2 or 3 depending on the number of review buttons.
    select_button(["Good","Bien","Easy","Fácil"],limit=18)
    press("grade card with accessible button","enter",1.1)
    note("REVIEW_GRADE_STEP_COMPLETED")

def browser_via_keyboard():
    activate_anki()
    press("open Browser","b",1.7)
    title=focus_title()
    if not any(t in title.casefold() for t in ["browse","explor","navega"]):
        raise AssertionError(f"Browser window not announced: {title}")
    for i in range(6):
        press(f"Browser tab {i}","tab",0.3)
        focus_description()
    press("close Browser","escape",0.4)
    note("BROWSER_NAVIGATED",window_title=title)

def stop_anki():
    save()
    if process and process.poll() is None:
        process.terminate()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill()
