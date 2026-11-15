# Anki / Qt WebEngine / NVDA MathCAT on Windows — root-cause note

Status: causal diagnosis verified in real NVDA CI, 15 Nov 2026. This note
separates observed behavior, diagnostic proof and upstream draft work.

## User-facing criterion

A screen-reader user studying a MathJax card should be able to reach the
mathematical expression, press NVDA+Alt+M, and use MathCAT's structural
navigation (arrows and Space) to explore fractions, powers and equations.
Visible glyphs or a linearized accessible name do not satisfy this criterion.

## Positive control: NVDA + MathCAT works

The audit uses NVDA 2026.3.1 on Windows and direct native MathML in Chrome.
After correcting a CI-only zero-rate bug in NVDA's speech-spy synthesizer,
MathCAT successfully enters and structurally explores fractions, powers and
equations. Therefore the original Anki failure is not caused by MathCAT being
unavailable in the tested NVDA build.

## Unmodified Qt transport result

Anki 26.09.4 renders the fixtures with MathJax 3.2.2 and the reviewer DOM
contains real assistive MathML. Native, detached and wrapper experiments do not
make that MathML usable by NVDA on their own. Without the diagnostic bridge,
NVDA+Alt+M reports "Not math".

Qt WebEngine maps Chromium kMath / kMathMLMath to QAccessible::Equation, but
Qt Base's Windows UIA bridge maps that equation to UIA_CustomControlTypeId and
does not transport the MathML property that NVDA's MathCAT path needs.

## Causal bridge proof

A test-only audit bridge transports the exact existing Anki MathML through a
marked UIA description and overlays the marked UIA object inside NVDA as
Role.MATH with a real mathMl property. This is deliberately not production
behavior.

With only that missing semantic transport restored, the real NVDA system test
passes structural MathCAT navigation inside Anki for all three independent
fixtures:

- fraction: MathCAT enters and moves between the fraction expression and its
  structural siblings;
- exponent: MathCAT announces structures such as "x squared" and "y cubed";
- equation: MathCAT moves from the left side to "is equal to".

The semantic audit reports zero unverified criteria in the causal run. This
proves that Anki's existing mathematical content is sufficient for MathCAT when
the Qt -> Windows UIA -> NVDA transport supplies both math identity and MathML.

## Accessibility transport chain

The production gap is therefore between Qt WebEngine / Qt Base's Windows UIA
provider and NVDA, not in MathJax's visible rendering.

The upstream-oriented draft uses two machine-readable signals:

1. QAccessible::Equation is exposed as invariant UIA_AriaRole "math" rather
   than relying only on a localized control-type string.
2. MathML is exposed through the same custom UIA MathML property GUID used by
   Microsoft Word and Chromium:
   {FA170AB3-3229-4E7C-827F-DD05EE0481D9}.

NVDA can then classify that UIA object as Role.MATH and reuse its existing
MathCAT interaction path.

## What this does and does not prove

Proven:
- Anki produces usable structured MathML.
- MathCAT works in the same NVDA CI environment.
- Restoring Role.MATH plus the exact MathML is sufficient for MathCAT
  interaction inside Anki.
- The saved Qt and NVDA draft patches apply cleanly to the exact source
  versions used for validation.

Not yet proven:
- a full Qt Base + Qt WebEngine C++ build with the draft patches;
- runtime behavior of binaries rebuilt from those upstream drafts;
- upstream acceptance by Qt, NVDA or Anki maintainers.

Do not replace equations with plain aria-label text as the final solution:
that would make speech possible while discarding MathCAT's structural
navigation.
