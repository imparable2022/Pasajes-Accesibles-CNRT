"""CI-only Anki native collection fixtures.

Fixture creation uses Anki's public Collection API, never SQLite writes.
The tests still navigate the *real* rendered cards with keyboard and NVDA.
Not part of the user-facing accessibility add-on.
"""
from __future__ import annotations

import base64
import json
import math
import struct
import tempfile
import wave
from pathlib import Path

from aqt import gui_hooks, mw
from aqt.qt import QTimer

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "fixtures.json"
PREFIX = "NVDA Fixture - "
CASES = [
    ("Image", "Basic", "Accessible image: <img src='fixture-green.png' alt='Green square on white background'>", "Image answer"),
    ("Math", "Basic", r"Equation: \(\frac{1}{2} + \frac{1}{4}\)", "Three quarters"),
    ("MathExponent", "Basic", r"Exponent: \\(x^2 + y^3\\)", "Powers answer"),
    ("MathEquation", "Basic", r"Equation: \\(2x+3=7\\)", "x equals 2"),
    ("Audio", "Basic", "Listen: [sound:fixture-tone.wav]", "Audio answer"),
    ("Long", "Basic", "Read the full explanation. " + ("Many meaningful words are shown here. " * 42), "Long answer"),
    ("Typed", "Basic (type in the answer)", "Type the name of the animal", "cat"),
    ("Cloze", "Cloze", "The {{c1::telescope}} collects light.", "Astronomy"),
    ("Table", "Basic", "<table><tr><th>Country</th><th>Capital</th></tr><tr><td>France</td><td>Paris</td></tr></table>", "Paris"),
    ("Interactive", "Basic", '<button type="button">An interactive control</button>', "Button answer"),
]

def _create_media():
    """Generate benign media directly inside the disposable CI collection."""
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAF"
        "gAI/ScLytAAAAABJRU5ErkJggg=="
    )
    with tempfile.TemporaryDirectory() as tmp:
        image = Path(tmp) / "fixture-green.png"
        image.write_bytes(png)
        mw.col.media.add_file(str(image))
        wav = Path(tmp) / "fixture-tone.wav"
        with wave.open(str(wav), "wb") as fp:
            fp.setnchannels(1)
            fp.setsampwidth(2)
            fp.setframerate(22050)
            fp.writeframes(b"".join(
                struct.pack("<h", int(10000 * math.sin(2*math.pi*440*i/22050)))
                for i in range(2205)
            ))
        mw.col.media.add_file(str(wav))

def install_fixture_cards():
    if not mw.col:
        RESULTS.write_text(json.dumps({"error":"collection unavailable"}))
        return
    rows = []
    try:
        _create_media()
    except Exception as exc:
        rows.append({"case":"media-setup","error":repr(exc)})
    for kind, model_name, front, back in CASES:
        name = PREFIX + kind
        try:
            if mw.col.decks.id_for_name(name):
                rows.append({"case":kind,"status":"already-present"})
                continue
            model = mw.col.models.by_name(model_name)
            if not model:
                rows.append({"case":kind,"status":"notetype-unavailable",
                             "model":model_name})
                continue
            deck_id = mw.col.decks.add_normal_deck_with_name(name).id
            note = mw.col.new_note(model)
            if kind == "Cloze":
                note["Text"] = front
                note["Back Extra"] = back
            else:
                note["Front"] = front
                note["Back"] = back
            mw.col.add_note(note, deck_id)
            rows.append({"case":kind,"status":"created","deck":name})
        except Exception as exc:
            rows.append({"case":kind,"status":"failed","error":repr(exc)})
    RESULTS.write_text(json.dumps({"cases":rows},indent=2),encoding="utf-8")
    mw.reset()

AUDIO_EVENTS = HERE / "audio-events.json"
_audio_events = []

def _log_audio(kind, detail):
    _audio_events.append({"event": kind, "detail": str(detail)[:180]})
    AUDIO_EVENTS.write_text(json.dumps(_audio_events, indent=2), encoding="utf-8")

def _record_replay(webview, card, is_front_side):
    _log_audio("user_replay", {"card": int(card.id), "front": is_front_side})

def _record_play(tag):
    _log_audio("play_request", type(tag).__name__ + ": " + str(tag))

# Observe Anki's own playback hooks. A play request is not proof that audio
# reached a physical sound device in the GitHub runner.
gui_hooks.audio_will_replay.append(_record_replay)
gui_hooks.av_player_will_play.append(_record_play)
gui_hooks.profile_did_open.append(lambda: QTimer.singleShot(900, install_fixture_cards))
