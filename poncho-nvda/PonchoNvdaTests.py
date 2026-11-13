"""Robot keywords: exercise the real Poncho snippets through installed NVDA + Chrome.

Uses the same ChromeLib / NvdaLib / speech spy that nvaccess/nvda runs in CI.
"""
from pathlib import Path
import json
from robot.libraries.BuiltIn import BuiltIn
from SystemTestSpy import _getLib
from ChromeLib import ChromeLib
import NvdaLib

_chrome: ChromeLib = _getLib("ChromeLib")
_builtin = BuiltIn()
_repo = Path.cwd().parent  # Robot always runs from the NVDA checkout
_out = _repo / "poncho-nvda" / "speech-results"
_out.mkdir(parents=True, exist_ok=True)

def _record(component, phase, steps):
    output = _out / f"{component}-{phase}.json"
    output.write_text(json.dumps(steps, indent=2, ensure_ascii=False), encoding="utf-8")
    _builtin.log(f"{component} {phase}: {steps}", level="INFO")
    for name, speech in steps.items():
        print(f"NVDA {component} {phase} {name}: {speech}", flush=True)

def _page(component, phase):
    html = (_repo / "poncho-nvda" / "fixtures" / phase / f"{component}.html").read_text("utf-8")
    _chrome.prepareChrome(html)

def verify_svg(phase):
    _page("svg", phase)
    speech = _chrome.getSpeechAfterTab()
    _record("svg", phase, {"tab_to_svg": speech})
    if phase == "after":
        assert "Santa Fe" in speech, f"NVDA did not announce the shape label: {speech}"
    else:
        assert "Santa Fe" not in speech, f"Unpatched NVDA unexpectedly announced label: {speech}"

def verify_breadcrumb(phase):
    _page("breadcrumb", phase)
    expand = _chrome.getSpeechAfterTab()
    following = _chrome.getSpeechAfterTab()
    _record("breadcrumb", phase, {"expand_control": expand, "next_focus": following})
    if phase == "before":
        assert "Inicio" in following or "Tomates" in following, (
            f"Expected offscreen link to receive Tab before patch: {following}")
    else:
        assert "Inicio" not in following and "Tomates" not in following, (
            f"Hidden link still in NVDA Tab sequence after patch: {following}")
        assert following.strip(), "Expected NVDA speech for visible link"

def verify_panel(phase):
    _page("panel", phase)
    summary = _chrome.getSpeechAfterTab()
    opened = NvdaLib.getSpeechAfterKey("space")
    menu_link = _chrome.getSpeechAfterTab()
    resize_button = _chrome.getSpeechAfterTab()
    NvdaLib.getSpyLib().emulateKeyPress("enter")
    after_resize = NvdaLib.getSpeechAfterKey("NVDA+tab")
    all_steps = dict(summary=summary, opened=opened, menu_link=menu_link,
                     resize_button=resize_button, after_resize=after_resize)
    _record("panel", phase, all_steps)
    expected = "abierto" if phase == "after" else "cerrado"
    assert expected in after_resize.lower(), (
        f"Expected menu {expected} on resize, got {after_resize}")

def verify_combobox(phase):
    _page("combobox", phase)
    input_speech = _chrome.getSpeechAfterTab()
    option_speech = NvdaLib.getSpeechAfterKey("downArrow")
    _record("combobox", phase, {
        "input": input_speech, "arrow_down": option_speech
    })
    # The browser tests validate the ARIA association; this one confirms
    # real NVDA speech, without claiming the whole combobox pattern is fixed.
    assert input_speech.strip(), "No NVDA announcement for combobox input"
    assert option_speech.strip(), "No NVDA announcement after ArrowDown"
