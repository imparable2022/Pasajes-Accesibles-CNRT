"""Accessibility prototype for Anki desktop (Windows + NVDA).

The opt-in reviewer feature names and focuses short, noninteractive content
once it has rendered. Complex/long cards retain their DOM and are NOT flattened
into a truncated accessible name. Editor labels are derived from the visible
field names, including notetypes with custom field names.

This is still a test prototype, not a verified universal solution.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from aqt import gui_hooks, mw
from aqt.qt import QTimer

HERE = Path(__file__).resolve().parent
CI_MODE = os.environ.get("ANKI_A11Y_CI") == "1"
if CI_MODE:
    HERE.joinpath("loaded.marker").write_text("loaded", encoding="utf-8")

DEFAULTS = {
    "announce_review_cards": False,
    "announce_questions": True,
    "announce_answers": True,
    "max_auto_speech_characters": 800,
    "label_editor_fields": True,
    "experimental_mathml_focus": False,
    "experimental_mathml_detached": False,
    "enable_audio_replay_button": False,
    "focus_noninteractive_rich_cards": False,
}
try:
    config = mw.addonManager.getConfig(__name__) or {}
except (AttributeError, ValueError):
    config = {}
OPTIONS = {**DEFAULTS, **config}
OPTIONS["max_auto_speech_characters"] = max(40, min(3000, int(OPTIONS["max_auto_speech_characters"])))

# Deliberate separation: either feature can be disabled without mutating
# the other feature's HTML, focus, hooks or configuration.
from .reviewer_focus import REVIEW_JS, _card_hook, register_reviewer_hooks
from .editor_labels import EDITOR_JS, _editor_note_loaded, register_editor_hooks

from .review_mathml import register_math_hooks
from .review_audio import register_audio_hooks

register_reviewer_hooks()
register_editor_hooks()
register_math_hooks()
register_audio_hooks()
