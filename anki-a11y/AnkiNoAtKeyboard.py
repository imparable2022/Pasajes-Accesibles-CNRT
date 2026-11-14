"""Windows desktop keyboard smoke with NO running NVDA or other screen reader.

This exercises Anki's Qt UI with the review focus feature disabled, ensuring
the accessibility add-on doesn't prevent ordinary non-AT keyboard navigation.
The NVDA E2E suite runs separately. This test must not be described as
Narrator/JAWS coverage or as exhaustive visual regression testing.
"""
import json
import ctypes
from ctypes import wintypes
import os
import subprocess
import time
from pathlib import Path

import pyautogui
import win32con
import win32gui
import win32process

OUT = Path(os.environ["ANKI_A11Y_OUTPUT"])
PROFILE = OUT / "isolated-profile"
EXE = os.environ["ANKI_EXE"]
LOG = OUT / "no-at-keyboard.json"
results = []

def record(stage, **kwargs):
    results.append({"stage":stage, **kwargs})
    LOG.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ANKI_NO_AT " + json.dumps(results[-1], ensure_ascii=False), flush=True)

def visible_windows():
    windows = []
    def visit(hwnd, ignored):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            windows.append((hwnd, win32gui.GetWindowText(hwnd)))
    win32gui.EnumWindows(visit, None)
    return windows

def find_window(tokens, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches = [
            (hwnd, title) for hwnd,title in visible_windows()
            if any(x.casefold() in title.casefold() for x in tokens)
        ]
        if matches:
            return matches[0]
        time.sleep(.4)
    raise AssertionError("Window missing: " + str(tokens) +
                         "; visible=" + repr(visible_windows())[-1600:])

def activate(handle):
    win32gui.ShowWindow(handle, win32con.SW_RESTORE)
    try:
        win32gui.SetForegroundWindow(handle)
    except Exception:
        pyautogui.hotkey("alt", "tab")
    time.sleep(1)
    foreground = win32gui.GetForegroundWindow()
    record("window activated", target=win32gui.GetWindowText(handle),
           foreground=win32gui.GetWindowText(foreground))
    if foreground != handle:
        raise AssertionError("Could not focus expected window using keyboard")

def key(name, *args, pause=0.9):
    if len(args) > 1:
        pyautogui.hotkey(*args)
    else:
        pyautogui.press(args[0])
    time.sleep(pause)
    title = win32gui.GetWindowText(win32gui.GetForegroundWindow())
    record(name, title=title)

def assert_no_reader():
    p = subprocess.run(["tasklist", "/FI", "IMAGENAME eq nvda.exe"],
                       capture_output=True, text=True)
    if "nvda.exe" in p.stdout.casefold():
        raise AssertionError("NVDA is still running; cannot claim no-AT test")
    # Narrator and JAWS should not be running either.
    for name in ["Narrator.exe", "jfw.exe"]:
        p = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + name],
                           capture_output=True, text=True)
        if name.casefold() in p.stdout.casefold():
            raise AssertionError(name + " is running in non-AT scenario")
    record("NO_SCREEN_READER_RUNNING")

class GUIThreadInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]

def focused_window_handle(foreground):
    thread_id = win32process.GetWindowThreadProcessId(foreground)[0]
    info = GUIThreadInfo()
    info.cbSize = ctypes.sizeof(info)
    ok = ctypes.windll.user32.GetGUIThreadInfo(thread_id, ctypes.byref(info))
    if not ok:
        return 0
    return int(info.hwndFocus or 0)

def main():
    assert_no_reader()
    addon_config = PROFILE / "addons21" / "anki_ci_review_announcer" / "config.json"
    if not addon_config.exists():
        raise AssertionError("Anki test add-on installation is missing")
    opts = json.loads(addon_config.read_text(encoding="utf-8"))
    opts["announce_review_cards"] = False
    opts["label_editor_fields"] = True
    addon_config.write_text(json.dumps(opts), encoding="utf-8")
    record("REVIEW_FOCUS_DISABLED", actual_config=opts)

    log = (OUT / "no-at-anki-startup.log").open("w", encoding="utf-8")
    process = subprocess.Popen([EXE, "-b", str(PROFILE)], stdout=log,
                               stderr=subprocess.STDOUT)
    log.close()
    try:
        hwnd, title = find_window(["Anki"], timeout=45)
        activate(hwnd)
        record("MAIN_OPENED", title=title)
        key("OPEN_BROWSER_WITH_KEYBOARD", "b", pause=2)
        bhwnd, btitle = find_window(["Browse", "Browser", "Explor"], timeout=12)
        record("BROWSER_OPENED", title=btitle)
        activate(bhwnd)
        key("CLOSE_BROWSER_WITH_KEYBOARD", "escape", pause=1.4)
        activate(hwnd)
        key("OPEN_ADD_WITH_KEYBOARD", "a", pause=2)
        ahwnd, atitle = find_window(["Add", "Añadir", "Agregar"], timeout=12)
        record("ADD_DIALOG_OPENED", title=atitle)
        activate(ahwnd)
        seen = []
        for i in range(12):
            pyautogui.press("tab")
            time.sleep(.1)
            fg = win32gui.GetForegroundWindow()
            focused = focused_window_handle(fg)
            seen.append({"focused_hwnd":int(focused or 0),
                         "window":win32gui.GetWindowText(fg)})
        record("TAB_NAVIGATION", sequence=seen)
        if not any(x["focused_hwnd"] for x in seen):
            raise AssertionError("No keyboard focus exposed by Windows during Tab traversal")
        key("CLOSE_ADD_DIALOG_WITH_KEYBOARD", "escape", pause=1)
        record("NO_AT_PASS")
    finally:
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=12)
            except subprocess.TimeoutExpired: process.kill()

if __name__ == "__main__":
    main()
