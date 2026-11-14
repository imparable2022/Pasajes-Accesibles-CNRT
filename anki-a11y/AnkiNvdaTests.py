"""Keyboard-only Anki E2E using genuine NVDA speech as the accessibility oracle.

All UI actions use keyboard injection. SQLite is used READ-ONLY for postconditions.
No mouse clicking, direct Anki commands, or silent shortcuts are counted as success.
"""
import ctypes
import json
import os
import sqlite3
import shutil
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
    recent = []
    for i in range(limit):
        speech = press("tab search " + str(i+1), "tab", 0.35)
        focus = focus_description()
        recent.append(focus[:180])
        both = (speech + " " + focus).casefold()
        # NVDA inserts spaces into CamelCase names when speaking them.
        # E.g. "MathExponent" is announced as "Math Exponent".
        canonical = "".join(char for char in both if char.isalnum())
        if any("".join(char for char in t.casefold() if char.isalnum())
               in canonical for t in targets):
            note("button found", matching=targets, ordinal=i+1)
            return True
    note("BUTTON_SEARCH_FAILED",targets=targets,limit=limit,last_focus=recent[-16:])
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
    src = Path(os.environ["ANKI_A11Y_ADDON_SOURCE"])
    target = data_dir / "addons21" / "anki_ci_review_announcer"
    shutil.copytree(src, target, dirs_exist_ok=True)
    fixture_src = Path(os.environ["ANKI_A11Y_FIXTURE_SOURCE"])
    fixture_target = data_dir / "addons21" / "anki_ci_fixtures"
    shutil.copytree(fixture_src, fixture_target, dirs_exist_ok=True)
    note("FIXTURE_LOADER_INSTALLED", path=str(fixture_target))
    # Isolated test profile explicitly opts into automatic narration.
    rich_focus_enabled = os.environ.get("ANKI_A11Y_RICH_FOCUS", "false").lower() == "true"
    settings = {"announce_review_cards": True, "announce_questions": True,
                "announce_answers": True, "max_auto_speech_characters": 800,
                "label_editor_fields": True,
                "focus_noninteractive_rich_cards": rich_focus_enabled,
                "experimental_mathml_focus": rich_focus_enabled,
                "enable_audio_replay_button": True}
    (target / "config.json").write_text(json.dumps(settings), encoding="utf-8")
    note("TEST_ADDON_INSTALLED", path=str(target), options=settings)
    logfile = out / "anki-startup.log"
    logfp = logfile.open("w", encoding="utf-8")
    process=subprocess.Popen([exe,"-b",str(data_dir)], stdout=logfp,
                             stderr=subprocess.STDOUT)
    logfp.close()
    start = time.monotonic()
    while True:
        robot.sleep("2 seconds")
        try:
            activate_anki()
            break
        except AssertionError:
            if process.poll() is not None or time.monotonic()-start > 40:
                log = logfile.read_text(encoding="utf-8", errors="replace")[-5000:]
                note("ANKI_STARTUP_FAILURE", process_exit=process.poll(), log=log)
                raise AssertionError(f"Anki did not show a window; exit={process.poll()}, log={log!r}")
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
    marker = data_dir / "addons21" / "anki_ci_review_announcer" / "loaded.marker"
    if not marker.exists():
        log = logfile.read_text(encoding="utf-8", errors="replace")[-12000:]
        note("ADDON_LOAD_FAILURE", log=log, paths=[str(p) for p in target.rglob("*")],
             process_exit=process.poll())
        raise AssertionError("Experimental accessibility add-on did not load; inspect ADDON_LOAD_FAILURE")
    note("TEST_ADDON_LOADED", marker=str(marker))
    fixture_report = fixture_target / "fixtures.json"
    if not fixture_report.exists():
        raise AssertionError("Native Anki fixture loader did not execute")
    fixture_result = json.loads(fixture_report.read_text(encoding="utf-8"))
    note("FIXTURE_CREATION_REPORT", report=fixture_result)
    failed = [x for x in fixture_result.get("cases", [])
              if x.get("status") not in ("created","already-present")]
    if failed:
        raise AssertionError("Anki fixture generation not completely successful: " + repr(failed))

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
    front_labeled = any(x in first.casefold() for x in ["front","frente","anverso"])
    note("EDITOR_FRONT_LABEL_VERIFIED", speech=first, success=front_labeled)
    paste("type card question in first field",FRONT)
    next_announcement=press("move to next card field","tab",0.8)
    focus=focus_description()
    note("next card field",speech=next_announcement,focus=focus)
    if "edit" not in focus.casefold():
        raise AssertionError("Tab did not reach another editable field")
    back_labeled = any(x in focus.casefold() for x in ["back","dorso","reverso"])
    note("EDITOR_BACK_LABEL_VERIFIED", speech=focus, success=back_labeled)
    if not (front_labeled and back_labeled):
        raise AssertionError(f"Editor field labels were not announced: first={first!r}, second={focus!r}")
    paste("type card answer in second field",BACK)
    press("submit card with Ctrl+Enter","control+enter",1.7)
    note("CARD_SUBMISSION_ATTEMPTED_BY_KEYBOARD")
    # Main functional journey will independently verify persistence when
    # review actually reads both sides of the newly-created card.
    press("close Add via Escape","escape",0.8)

def read_card_content_strict(stage, expected):
    """Prove NVDA can independently speak the specified card text using
    ordinary keyboard review / browse gestures, not Anki internals.

    Speech must include the exact known test content. A green workflow without
    this evidence would not establish accessible studying.
    """
    observations = []
    def capture(label, keys, sec=0.5):
        spoken = press(f"{stage}: {label}", keys, sec)
        observations.append((label, spoken))
        return expected.casefold() in spoken.casefold()

    # Anki sets focus to a Qt webview after updating the review card; its
    # virtual cursor may not be positioned at the question/answer.
    # These are the same browse-mode gestures a screen-reader user can use.
    for label, keys, sec in [
        ("report focus", "NVDA+tab", 0.5),
        ("move to document start", "control+home", 0.6),
        ("read first line", "downArrow", 0.7),
        ("read second line", "downArrow", 0.7),
        ("read current line", "NVDA+upArrow", 0.7),
        ("read all from cursor", "NVDA+downArrow", 1.5),
        ("move to document top again", "control+home", 0.4),
    ]:
        if capture(label, keys, sec):
            note(f"{stage}_CONTENT_SPOKEN_BY_NVDA", expected=expected, gesture=keys)
            return True
    for i in range(15):
        if capture(f"browse next line {i+1}", "downArrow", 0.45):
            note(f"{stage}_CONTENT_SPOKEN_BY_NVDA", expected=expected, gesture="downArrow")
            return True

    # Some QWebEngine views start NVDA in focus mode. Explicitly toggle to
    # browse mode, then navigate document text; keep raw mode speech evidence.
    mode = press(f"{stage}: toggle NVDA mode", "NVDA+space", 0.8)
    observations.append(("toggle mode", mode))
    for label, keys, sec in [
        ("browse document start", "control+home", 0.6),
        ("browse first line", "downArrow", 0.8),
        ("browse second line", "downArrow", 0.8),
        ("browse read line", "NVDA+upArrow", 0.6),
        ("browse read all", "NVDA+downArrow", 1.5),
    ]:
        if capture(label, keys, sec):
            note(f"{stage}_CONTENT_SPOKEN_BY_NVDA", expected=expected, gesture=keys, mode=mode)
            return True
    for i in range(15):
        if capture(f"browse subsequent line {i+1}", "downArrow", 0.45):
            note(f"{stage}_CONTENT_SPOKEN_BY_NVDA", expected=expected, gesture="downArrow", mode=mode)
            return True

    # Re-enter the main review document with Tab / Shift+Tab (no mouse) and
    # sample the first lines again. This tests whether focus positioning,
    # rather than actual document semantics, caused the apparent silence.
    for k in ["tab", "shift+tab", "NVDA+tab", "control+home", "downArrow", "NVDA+upArrow"]:
        capture("refocus document " + k, k, 0.55)

    # NVDA browse-mode Find searches the virtual-buffer *accessibility* text,
    # not the Anki HTML implementation. A successful match is supporting
    # evidence only; user-readable speech is still the passing requirement.
    capture("open NVDA find", "NVDA+control+f", 0.7)
    capture("dismiss NVDA find", "escape", 0.5)
    # NVDA object navigation is a second, independent screen-reader path.
    # QWebEngine often exposes an accessibility object tree even when NVDA's
    # browse mode does not start. The name must still be spoken by real NVDA.
    for label, gesture in [
        ("move navigator to focus", "NVDA+numpadMinus"),
        ("read current navigator object", "NVDA+numpad5"),
        ("enter first child", "NVDA+numpad2"),
    ]:
        try:
            if capture(label, gesture, 0.7):
                note(f"{stage}_CONTENT_SPOKEN_BY_NVDA",expected=expected,gesture=gesture,source="object_navigation")
                return True
        except Exception as error:
            note("object navigation unavailable", gesture=gesture,error=repr(error))
    # The first child of Anki's outer grouping is the top toolbar. Move to
    # its *next sibling* (the main webview) and then enter the main webview's
    # children. This differs from mistakenly enumerating only the root level.
    try:
        if capture("move to main webview sibling", "NVDA+numpad6", 0.7):
            note(f"{stage}_CONTENT_SPOKEN_BY_NVDA",expected=expected,source="object_navigation")
            return True
        for depth in range(1,5):
            if capture("enter main webview child depth "+str(depth),"NVDA+numpad2",0.6):
                note(f"{stage}_CONTENT_SPOKEN_BY_NVDA",expected=expected,
                     gesture="NVDA+numpad2",source="object_navigation")
                return True
            for idx in range(8):
                spoken=press(f"{stage}: explore sibling depth {depth} index {idx}","NVDA+numpad6",0.38)
                observations.append((f"object sibling depth {depth} index {idx}",spoken))
                if expected.casefold() in spoken.casefold():
                    note(f"{stage}_CONTENT_SPOKEN_BY_NVDA",expected=expected,
                         gesture="NVDA+numpad6",source="object_navigation")
                    return True
                if "no next" in spoken.casefold(): break
            # Return to first child at current depth, to drill into descendants
            # of the main webview instead of moving to sibling toolbars.
            for i in range(8):
                back=press(f"{stage}: rewind object sibling {i}","NVDA+numpad4",0.22)
                observations.append(("object rewind",back))
                if "no previous" in back.casefold():break
    except Exception as error:
        note("object navigation traversal error",error=repr(error))

    note("NVDA_CARD_READING_FAILURE", phase=stage, expected=expected, mode=mode,
         samples=[{"gesture":k,"speech":v[:500]} for k,v in observations])
    return False

def study_with_keyboard():
    activate_anki()
    press("return to decks", "d", 1.2)
    select_button([DECK], limit=24)
    press("open selected deck", "enter", 1.3)
    note("deck opened", title=focus_title())
    select_button(["Study Now", "Estudiar ahora"], limit=18)
    spy = NvdaLib.getSpyLib()
    idx = spy.get_next_speech_index()
    transition = press("activate Study Now", "enter", 1.6)
    robot.sleep("2 seconds")
    question_auto = spy.get_speech_at_index_until_now(idx)
    addon_root = data_dir / "addons21" / "anki_ci_review_announcer"
    note("REVIEW_ADDON_HOOK_STATUS",
         webview_hook=(addon_root / "webview-hook.marker").exists(),
         card_hook=(addon_root / "card-hook.marker").exists())
    question_auto_ok = FRONT.casefold() in question_auto.casefold()
    note("QUESTION_AUTOMATIC_NVDA", spoken=question_auto[:1500], success=question_auto_ok)
    note("study screen", focused=focus_description())

    # Strict assertions: test only passes if NVDA genuinely voices each side.
    question_spoken = read_card_content_strict("QUESTION", FRONT)
    select_button(["Show Answer", "Mostrar respuesta"], limit=18)
    idx = spy.get_next_speech_index()
    transition = press("show answer via keyboard", "enter", 1.4)
    robot.sleep("2 seconds")
    answer_auto = spy.get_speech_at_index_until_now(idx)
    for side in ("question", "answer"):
        report = data_dir / "addons21" / "anki_ci_review_announcer" / ("reviewer-debug-" + side + ".json")
        note("REVIEWER_DOM_STATE", side=side,
             data=report.read_text(encoding="utf-8") if report.exists() else "(not captured)")
    answer_auto_ok = BACK.casefold() in answer_auto.casefold()
    note("ANSWER_AUTOMATIC_NVDA", spoken=answer_auto[:1500], success=answer_auto_ok)
    answer_spoken = read_card_content_strict("ANSWER", BACK)
    select_button(["Good", "Bien"], limit=18)
    press("grade card with accessible button", "enter", 1.0)
    note("REVIEW_GRADED_AFTER_STRICT_NVDA_READING", question_spoken=question_spoken, answer_spoken=answer_spoken)
    if not question_spoken or not answer_spoken:
        raise AssertionError(f"NVDA text-reading strict criterion failed: question={question_spoken}, answer={answer_spoken}")
    if not question_auto_ok or not answer_auto_ok:
        raise AssertionError(f"Automatic NVDA announcement failed: question={question_auto_ok}, answer={answer_auto_ok}")

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

SEMANTIC_CHECKS = {}

def _semantic_check(kind, criterion, passed, evidence, note_text=""):
    key = kind + ":" + criterion
    SEMANTIC_CHECKS[key] = {
        "kind": kind,
        "criterion": criterion,
        "passed": bool(passed),
        "evidence": str(evidence)[:3200],
        "note": note_text,
    }
    (out / "semantic-audit.json").write_text(
        json.dumps({"actual_nvda": True, "tests": list(SEMANTIC_CHECKS.values())},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    note("SEMANTIC_AUDIT_CHECK", **SEMANTIC_CHECKS[key])

def _speech_probe(kind):
    """Read through ordinary NVDA gestures without inspecting HTML/ARIA.
    Anki's UIA/DOM observation is recorded elsewhere, never used to satisfy
    these checks. Preserves the full raw utterance evidence for failed cases.
    """
    samples = []
    gestures = [
        ("announce focused control", "NVDA+tab", .5),
        ("switch browse/focus mode", "NVDA+space", .6),
        ("start virtual document", "control+home", .6),
        ("read first line", "downArrow", .65),
        ("read next line", "downArrow", .65),
        ("read current line", "NVDA+upArrow", .55),
        ("read all", "NVDA+downArrow", 1.4),
        ("graphic quick navigation", "g", .55),
        ("announce graphic focus", "NVDA+tab", .55),
        ("move navigator to focused object", "NVDA+numpadMinus", .5),
        ("first navigation child", "NVDA+numpad2", .5),
    ]
    for step,gesture,delay in gestures:
        try:
            speech=press(f"{kind} semantics: {step}", gesture,delay)
            samples.append({"gesture":gesture, "speech":speech})
        except Exception as err:
            samples.append({"gesture":gesture, "error":repr(err)})
    # NVDA object navigation can expose a MathML/graphic node even if the
    # QWebEngine virtual document does not expose a browse-mode cursor.
    for idx in range(14):
        for gesture in ("NVDA+numpad6", "NVDA+numpad2"):
            try:
                speech=press(f"{kind} semantics: object {idx} {gesture}",gesture,.30)
                samples.append({"gesture":gesture,"speech":speech})
            except Exception as err:
                samples.append({"gesture":gesture,"error":repr(err)})
                break
    if kind.startswith("Math"):
        # MathCAT is the NVDA 2026 mathematical interaction engine.
        # This is a user gesture, not a DOM/MathML read from Python.
        for step, gesture in [
            ("focus current object", "NVDA+numpadMinus"),
            ("enter document", "NVDA+numpad2"),
            ("move to mathematical child", "NVDA+numpad6"),
            ("descend into equation", "NVDA+numpad2"),
            ("MathCAT: interact", "NVDA+alt+m"),
            ("MathCAT: read current", "space"),
            ("MathCAT: zoom in", "downArrow"),
            ("MathCAT: move right", "rightArrow"),
            ("MathCAT: read fraction/exponent piece", "space"),
            ("MathCAT: exit", "escape"),
        ]:
            try:
                spoken=press(f"{kind} {step}",gesture,.6)
                samples.append({"gesture":gesture,"speech":spoken})
            except Exception as err:
                samples.append({"gesture":gesture,"error":repr(err)})
    note("NVDA_SEMANTIC_SPEECH_PROBE",kind=kind,samples=samples[-40:])
    return " ".join(s.get("speech", "") for s in samples).casefold()

def _check_image_semantics(kind, speech):
    expected="green square on white background"
    _semantic_check(kind, "image_alt_spoken", expected in speech, speech,
                    "Real NVDA must actually announce the image's alt text")

def _check_math_semantics(kind, speech):
    expected = {
        "Math": ("fraction", "half", "quarter", "one over", "numerator", "denominator"),
        "MathExponent": ("square", "squared", "cube", "cubed", "power", "superscript"),
        "MathEquation": ("equal", "equals", "is equal to"),
    }[kind]
    found=any(x in speech for x in expected)
    _semantic_check(kind,"mathematical_structure_spoken",found,speech,
                    "A mathematical relation must be announced as speech, not merely present in DOM")

def _check_audio_replay(kind):
    fixture = data_dir / "addons21" / "anki_ci_fixtures" / "audio-events.json"
    before = json.loads(fixture.read_text(encoding="utf-8")) if fixture.exists() else []
    # Anki documents 'r' as a reviewer shortcut for replaying sound.
    # This input is injected to the genuine Anki window, not a backend call.
    press(f"{kind}: replay existing audio using keyboard", "r", .9)
    robot.sleep("1 second")
    after = json.loads(fixture.read_text(encoding="utf-8")) if fixture.exists() else []
    new = after[len(before):]
    requested = any(ev.get("event") == "user_replay" for ev in new)
    queued = any(ev.get("event") == "play_request" for ev in new)
    _semantic_check(kind,"audio_replay_keyboard_hook",requested,new,
                    "Anki's audio_will_replay hook confirms the keyboard action")
    _semantic_check(kind,"audio_playback_requested",queued,new,
                    "Playback was requested, not proof of audible device output")

def study_fixture_decks_via_keyboard():
    """Exercise actual Anki-generated media/complex cards and review controls.

    Fixture note creation uses Anki's collection API (setup only). Every
    interaction with the rendered reviewer remains keyboard + real NVDA.
    The test makes *no* claim that media/math content was understood unless
    the actual speech trace supplies that evidence.
    """
    fixture_file = data_dir / "addons21" / "anki_ci_fixtures" / "fixtures.json"
    report = json.loads(fixture_file.read_text(encoding="utf-8"))
    cases = [item for item in report.get("cases", [])
             if item.get("status") in ("created", "already-present")]
    if len(cases) < 6:
        raise AssertionError("Insufficient actual Anki fixture cards: " + repr(cases))
    note("MULTIFORMAT_REVIEW_START", cases=[item["case"] for item in cases])
    for item in cases:
        kind = item["case"]
        deck = "NVDA Fixture - " + kind
        activate_anki()
        press(f"{kind}: leave any editable review field", "escape", 0.4)
        press(f"{kind}: return to decks", "d", 0.8)
        try:
            select_button([deck], limit=34)
        except AssertionError:
            note("FIXTURE_DECK_SEARCH_RECOVERY", kind=kind)
            press(f"{kind}: escape focus or active editor", "escape", 0.8)
            press(f"{kind}: reopen decks", "d", 1.0)
            press(f"{kind}: restart keyboard scan from top", "control+home", 0.5)
            select_button([deck], limit=65)
        press(f"{kind}: open deck", "enter", 0.7)
        select_button(["Study Now","Estudiar ahora"], limit=22)
        spy = NvdaLib.getSpyLib()
        start_index = spy.get_next_speech_index()
        press(f"{kind}: start study", "enter", 1.2)
        robot.sleep("2 seconds")
        spoken = spy.get_speech_at_index_until_now(start_index)
        focus = focus_description()
        note("MULTIFORMAT_QUESTION", kind=kind,
             automatic_speech=spoken[:600], focused=focus[:600])
        if kind in ("Image","Math","MathExponent","MathEquation","Audio"):
            sample = _speech_probe(kind)
            if kind == "Image":
                _check_image_semantics(kind, sample)
            elif kind.startswith("Math"):
                _check_math_semantics(kind, sample)
            elif kind == "Audio":
                # Separate voice exposure and activation from the existing R
                # shortcut: a proper labeled button must be Tab-reachable.
                select_button(["Replay audio (R)", "Replay audio"], limit=55)
                button_focus = focus_description()
                announce = "replay audio" in button_focus.casefold() and "button" in button_focus.casefold()
                _semantic_check(kind, "audio_control_named_by_nvda", announce,
                                button_focus,
                                "NVDA must announce a labeled replay button")
                events = data_dir / "addons21" / "anki_ci_fixtures" / "audio-events.json"
                before_events = json.loads(events.read_text(encoding="utf-8")) if events.exists() else []
                press("Activate replay button with Enter", "enter", 1.0)
                robot.sleep(".8 seconds")
                after_events = json.loads(events.read_text(encoding="utf-8")) if events.exists() else []
                marker = data_dir / "addons21" / "anki_ci_review_announcer" / "replay-button-invoked.marker"
                clicked = marker.exists() and any(
                    ev.get("event") == "user_replay" for ev in after_events[len(before_events):]
                )
                _semantic_check(kind, "audio_replay_button_activated", clicked,
                                after_events[len(before_events):],
                                "Real accessible control must dispatch Anki's existing replay action")
                _check_audio_replay(kind)

        if kind == "Typed":
            # Anki's native type-answer editor must retain focus.
            if not any(k in focus.casefold() for k in ["edit","text field","editable"]):
                note("MULTIFORMAT_FINDING", kind=kind,
                     problem="Typed-answer input not focused", focused=focus)
                raise AssertionError("Typing field unexpectedly lost focus")

        addon = data_dir / "addons21" / "anki_ci_review_announcer"
        domfile = addon / "reviewer-debug-question.json"
        if domfile.exists():
            dom = json.loads(domfile.read_text(encoding="utf-8"))
            note("MULTIFORMAT_RENDERED_QUESTION", kind=kind,
                 aria=dom.get("aria"), active=dom.get("active"),
                 text_excerpt=(dom.get("text") or "")[:120])
            if kind.startswith("Math"):
                note("RENDERED_MATHML_DIAGNOSTICS",kind=kind,
                     math=dom.get("math"),mathjax=dom.get("mathjax"))
            if kind in ("Image", "Math", "Audio", "Long", "Table", "Interactive"):
                aria = dom.get("aria")
                rich_enabled = os.environ.get("ANKI_A11Y_RICH_FOCUS", "false").lower() == "true"
                if rich_enabled and kind in ("Image", "Long", "Table"):
                    # These noninteractive rich cards may be focused as an
                    # explicitly labeled region but their content must remain
                    # structurally navigable, not flattened into a huge name.
                    if aria != "Question content":
                        raise AssertionError(f"{kind} missing semantic focus region: {aria!r}")
                    note("COMPLEX_CARD_REGION_FOCUSED",kind=kind,aria=aria,
                         focused=focus[:320])
                elif aria:
                    # Audio controls and interactive buttons must remain
                    # independent of the reviewer focus workaround.
                    raise AssertionError(f"{kind} was flattened into an ARIA name: {aria!r}")
        select_button(["Show Answer","Mostrar respuesta"], limit=32)
        reveal_index = spy.get_next_speech_index()
        press(f"{kind}: reveal answer", "enter", 1.3)
        robot.sleep("1.2 seconds")
        answer_utterance = spy.get_speech_at_index_until_now(reveal_index)
        note("MULTIFORMAT_ANSWER", kind=kind, speech=answer_utterance[:800],
             focused=focus_description()[:600])
        if kind == "Cloze":
            recognized = "telescope" in answer_utterance.casefold()
            note("CLOZE_REVEAL_NARRATED", success=recognized,
                 actual=answer_utterance[:600])
            if not recognized:
                raise AssertionError("NVDA did not automatically announce the revealed cloze text")
        select_button(["Good","Bien"], limit=32)
        press(f"{kind}: grade via keyboard", "enter", 0.9)
        note("MULTIFORMAT_REVIEW_COMPLETE", kind=kind)
    note("MULTIFORMAT_REVIEW_DONE", count=len(cases))
    report = list(SEMANTIC_CHECKS.values())
    note("REAL_NVDA_SEMANTIC_SUMMARY",tested=len(report),
         passed=sum(x["passed"] for x in report),
         unverified=[x["kind"]+":"+x["criterion"] for x in report if not x["passed"]])


def stop_anki():
    save()
    if process and process.poll() is None:
        process.terminate()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill()
