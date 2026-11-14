# Anki Windows/NVDA reviewer — experimental automatic card reading

Test environment: Anki 26.09.4, NVDA 2026.3.1, Windows Server 2025, Robot Framework.

## Reproduction and control

Without a reviewer accessibility add-on, the keyboard E2E could create a deck,
add a note, show its answer, grade it, and browse cards. NVDA announced the
reviewer toolbar buttons, but **did not speak the card question/answer** through
ordinary document navigation or 'say all'. It *could* read the text through
the multi-step navigator-object hierarchy. See runs 43555291340
(functional success) and 43554096185 (strict automatic speech failure).

A preliminary add-on using only an ARIA live region did not cause the expected
automatic announcement (run 43556488507). The experimental add-on in this
directory takes a different approach:

1. A `card_will_show` hook attaches a callback to Anki's `onShownHook`.
2. After the new card finishes rendering, it gives the actual `#qa` element a
   programmatic focus target (`tabindex=-1`), the accessible role `group`,
   and an accessible name derived from its visible plain text (test cap 1,000).
3. Focus moves to that element, causing NVDA to announce the visible card text
   without requiring the user's object navigation gestures.
4. Tab still reaches the normal Show Answer / rating controls.

Both automatic announcements and the original complete keyboard journey passed
in run 43557599539, even after the ARIA live region was removed. The recording
reports `QUESTION_AUTOMATIC_NVDA.success=true` and
`ANSWER_AUTOMATIC_NVDA.success=true`.

## Experimental status — do not ship as a general-purpose add-on

This is a proof of concept for one *plain text* Basic card, not a safe upstream
patch. Other scenarios require testing: images and their alt text, audio, long
content, HTML layout and CSS hidden elements, MathJax and cloze deletions,
cards with their own interactive controls, and other screen readers/platforms.
A 1,000-character accessible name truncates long cards, and setting the whole
visible text as a group's accessible name can degrade structural exploration or
repeat question text when revealing an answer. Moving focus can also interfere
with active typing on special templates. A production solution should preserve
semantic navigation, be sensitive to screen reader preferences, and avoid
unwanted interruptions or automatic narration.

## Implementation

`experimental-review-announcer/__init__.py` is copied to an isolated
`addons21` directory in CI. No production installation or upstream modification
occurs. The CI test **fails** if either automatic announcement is missing;
the navigator-object fallback is a separate, supplementary assertion.

All changes are restricted to the audit branch.
