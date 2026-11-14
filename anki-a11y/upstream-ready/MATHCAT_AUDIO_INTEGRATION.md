# NVDA MathCAT + audio replay + upstream Anki patches

## Math in NVDA 2026.3.1

NVDA 2026.3.1 includes MathCAT. MathCAT can navigate **real MathML**,
enter mathematical interaction with **NVDA+Alt+M**, move inside a fraction
using Down Arrow, explore terms with Left/Right Arrow, and read the
current subexpression with Space. As documented in NV Access's user guide,
this requires the mathematical object to be available in NVDA's cursor.

Anki 26.09.4 uses MathJax 3, with a `tex-chtml-full` renderer in the
reviewer. Simply having MathJax render visible formula glyphs does
**not** establish access to an interactive mathematical structure in
NVDA, particularly inside Qt WebEngine.

`anki-accessibility-prototype/review_mathml.py` is an **opt-in experiment**:
it first reuses the MathML node already emitted by MathJax, if any;
if none exists, it tries to serialize the original MathJax mathematical
expression tree into MathML and add a small, visually-clipped MathML
sibling. It makes the MathML node keyboard-focusable and focuses the
first expression in an opt-in test mode; it does **not** add an
`aria-label` containing a linearized formula, and it does **not**
overwrite Anki's original visual expression. The expected next step is
to verify native MathCAT speech and arrow-key exploration in actual
Anki/Qt NVDA. The feature is disabled by default.

The Windows Robot suite has separate fixtures for a fraction, powers and
an equation; it records a spoken transcript from real NVDA, attempts
NVDA+Alt+M and semantic arrow-key exploration, and stores the actual
MathJax DOM/MathML diagnostics. Semantic success is **not** equated
with a green test harness unless the expected content is spoken.

## Existing audio replay controls (not a new audio player)

Anki already converts `[sound:...]` into a focusable
`<a class="replay-button soundLink"...>` containing a decorative SVG
in `aqt.sound.av_refs_to_play_icons()`. The link itself did not carry
an accessible name and so could appear as an unnamed link/graphic to
NVDA. The **separate** proposed upstream patch
`0002-audio-replay-button-accessible-label.patch`:
1. Labels that *existing* anchor with Anki's translated
   `tr.actions_replay_audio()` label, HTML-escaped;
2. Marks only its decorative SVG as `aria-hidden=true` and
   `focusable=false`;
3. Preserves the original `pycmd('play:q:n')` bridge, keyboard Enter
   activation, CSS classes and the independent **R/F5** shortcut.

`test_audio_patch.py` checks correct localized markup, escaping,
original link focusability and playback commands. This source patch is
preferable for upstream to adding a second duplicate replay button.
An alternate add-on-only button experiment is isolated in
`anki-accessibility-prototype/review_audio.py` and opt-in.

Our previous NVDA recordings verified that R dispatched
`audio_will_replay` and a player request. This proves Anki requested
playback; it does **not** prove that the CI sound device produced audible
sound.

## Editor patch and complete build

`0001-editor-fields-accessible-names.patch` changes only four Svelte
editor components. It passes the note type's true field label to the
actual focusable rich-text or CodeMirror input, and does not change
focus. It is separate from all reviewer/MathML/audio work.

`.github/workflows/anki-upstream-editor-build.yml` checks out
an exact upstream Anki commit, applies both **independent** patches,
runs an isolated Python regression for replay markup, installs the
official source build dependencies, and runs **just build** followed by
**just lint**. Unlike a JS parser-only check, success would establish
a complete source build and project lint. No claim of completion should
be made until the run is green and the installed Windows application has
also been regression tested.

## Upstream discussion

Anki PR #4511 proposed broad reviewer focus/announcements, but was closed
after maintainers requested narrow changes, review of different screen
readers and card types, and coordination with ongoing reviewer work.
Accessibility tracker: ankitects/anki#4661. Do not present the
reviewer/math experiment as an upstream-ready universal fix without
evidence for complex cards.
