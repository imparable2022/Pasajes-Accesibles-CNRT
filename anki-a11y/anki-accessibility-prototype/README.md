# Anki accessibility — generalized, conservative prototype

This is a separate research branch for **Anki Desktop 26.09.4 / NVDA
2026.3.1 / Windows 2025**, extending the original Poncho-style Windows
screen-reader CI. It is not an upstream Anki change or a public release.

## What is fixed and has a real NVDA test

1. **Editor field labels**: NVDA formerly announced the first and second
   editing fields as "edit, focused, blank" with no indication which field
   was active. The add-on derives the visible field name (not hard-coded
   Front/Back) and associates it with rich text's real shadow-DOM
   `anki-editable` and CodeMirror's generated textarea. A MutationObserver
   updates labels on Svelte re-render/note-type changes. This does not move
   focus. In run 43618440801 NVDA reported "Front edit focused blank" and
   "Back edit focused blank".
2. **Automatic reviewer narration for short, noninteractive text cards**:
   with the explicit opt-in enabled in an isolated CI profile, the add-on
   focuses the rendered `#qa` element after Anki's `onShownHook`. The card
   is exposed as a named group, which NVDA announces without needing object
   navigation. For answers, visible content already read as the question is
   removed before announcing: no repeated question. In run 43618440801,
   NVDA spoke the exact test question and then **only the new answer**.
   Keyboard focus could still proceed to Show Answer, Good and Browse.

## Expanded validation (Nov 14, 2026)

[Windows GitHub Actions run 43623827708](https://github.com/imparable2022/Pasajes-Accesibles-CNRT/actions/runs/43623827708) is an important intermediate **green** run:

- **13 policy/DOM tests passed**. The runtime harness executes the actual
  reviewer JavaScript with simulated DOM states for images, math, audio, video,
  long texts, tables, links, interactive buttons, typed-answer controls and
  screen-reader-disabled defaults. It verifies focus remains unchanged for
  incompatible content, semantics are restored between cards and long text
  is not silently truncated. These are deterministic policy tests, **not**
  genuine NVDA assertions about media content.
- **One real Anki/NVDA journey passed**: create deck and note, read and grade a
  Basic card, then open **8 native fixture decks** produced through Anki's
  Collection API and complete keyboard study/answer/grading in each:
  Image, MathJax, Audio, Long, Typed answer, Cloze, Table and Interactive.
  Typed-answer focus was preserved; incompatible rich cards were not
  overridden with a false `aria-label`. The fixture loader is CI-only and
  never writes directly to SQLite.
- **A separate real Anki no-screen-reader keyboard smoke passed** after the
  NVDA tests shut down. It checks that NVDA, Narrator and JAWS processes are
  absent, disables review focus in the isolated profile, opens Browse and Add
  by keyboard, traverses 12 Tab stops with a Windows focus handle and exits.

**Scope of claims:** a green multimodal keyboard smoke means the screens,
controls and review transitions remain keyboard-operable. It does **not**
prove that NVDA understands the image alt text, speaks mathematical structure,
or can control audio without additional work. The tested non-AT keyboard
journey does not establish equivalence for JAWS, Narrator, VoiceOver or Orca;
those tools are not actually driving these tests.

The follow-on cloze assertion checks that NVDA announces the *revealed* cloze
deletion, rather than just repeating the question or ignoring a changed span.
See newer workflow runs for its outcome.

## Configuration

`config.json` has:

- `announce_review_cards`: `false` by default; enabling changes focus.
- `announce_questions`: `true` (relevant only if narration enabled).
- `announce_answers`: `true` (relevant only if narration enabled).
- `max_auto_speech_characters`: `800`; content longer than this is left alone
  rather than being silently truncated. Hard limit 3,000.
- `label_editor_fields`: `true`; independent of reviewer narration.
- `focus_noninteractive_rich_cards`: `false` by default; optional keyboard
  focus to a semantic Question/Answer region for complex noninteractive cards
  without replacing their accessible hierarchy with the full card text. This
  is not yet NVDA-validated across all content types.

For the CI E2E the test explicitly writes a configuration with narration
enabled into a disposable Anki profile. No other user profile is modified.

## Deliberate safety limits and known gaps

This prototype does **not** claim to handle all types of cards. It deliberately
does not force focus or flatten the card to a single spoken name when there are
images, audio, mathematical markup, video, embedded/interactive controls,
tables, lists, headings, code blocks, or more text than the chosen limit.
Those cards keep their original HTML but require a separate accessibility
solution and real NVDA tests. The current decision is safer than a false
claim that inaccessible content is read.

Even with short text cards, focus movement is opt-in because it may interfere
with unusual templates, browser cursor settings or other assistive technologies.
Editor label code for dynamically switching note types and CodeMirror is
implemented but needs separate end-to-end coverage. Other screen readers and
platforms are untested. No PR should be submitted upstream as "complete
accessibility" based on a single Basic card.

## What went wrong and what we learned

- `onShownHook` runs after the reviewer HTML is rendered.
- The first prototype set an `aria-label` to the entire rendered card text;
  revealing the answer repeated the question.
- Trying to derive answer text from `Range.cloneContents().textContent`
  accidentally pulled in the JavaScript code appended by our add-on; this
  exceeded the allowed length and suppressed narration.
- We corrected this by preferring `qa.innerText` (visible text only),
  removing the already-read question when the prefix matches, and filtering
  any script/style/template/noscript elements from the fallback DOM fragment.
- The strict Windows NVDA test validates the actual utterance instead of
  accepting keyboard clicks alone.

## Test infrastructure

`test_policy.py` checks preference defaults, hook registration, editor
injection, avoidance of truncation/unsafe markup, and JavaScript syntax.
The Windows GitHub Actions workflow additionally installs Anki and NVDA,
creates a deck and note through keyboard commands, verifies both editor names,
requires automatic announcements of the question **and the answer**, grades
the card, and browses the note. Robot and NVDA artifacts are collected.

All private card text in CI comes from a newly created dummy note. Optional
rendered-DOM diagnostics are emitted **only when `ANKI_A11Y_CI=1`**.

Relevant evidence:

- Working initial focus-and-label implementation (1 Basic text card):
  https://github.com/imparable2022/Pasajes-Accesibles-CNRT/actions/runs/43618440801
- Generalization/JS syntax policy tests: see branch workflow runs.

## Follow-up work required for upstream readiness

Build independent scenarios for long rich text, links, tables, images with
alt text, audio-only notes, formulas, cloze deletions, typed answer, note type
changes, and HTML source mode. For each, compare normal NVDA document/object
navigation and the fallback behavior with narration on and off. Test reading
order, focus restoration, rapid review, other readers, and localization.
Only then prepare focused upstream patches in
`ts/reviewer/index.ts` and Svelte editor controls, with regression coverage.

The long-term goal is to keep the HTML semantically navigable, not to solve
all accessibility by converting every card to a huge `aria-label`.
