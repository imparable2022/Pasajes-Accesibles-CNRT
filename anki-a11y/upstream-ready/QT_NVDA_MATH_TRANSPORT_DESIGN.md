# Design sketch: transporting web MathML from Qt WebEngine to NVDA on Windows

This is a design note derived from the Anki/NVDA audit. It is intentionally
separate from Anki's editor/audio patches.

## Confirmed gap

The semantic chain currently loses mathematical identity and markup:

1. Chromium/Blink produces kMath / kMathMLMath and structured MathML nodes.
2. Qt WebEngine maps the root to QAccessible::Equation.
3. Qt Base's Windows UIA bridge maps QAccessible::Equation to
   UIA_CustomControlTypeId.
4. NVDA maps UIA_CustomControlTypeId to Role.UNKNOWN.
5. Qt's UIA_AriaRolePropertyId implementation only supplies an ARIA role for
   headings; it does not expose "math" for QAccessible::Equation.
6. NVDA 2026.3.1's ariaRolesToNVDARoles table does not currently contain
   "math" either.
7. Qt WebEngine's BrowserAccessibilityInterface does not implement
   QAccessibleAttributesInterface and therefore does not carry raw MathML
   through QAccessible custom attributes/UIA_AriaProperties.

Result: NVDA+Alt+M cannot obtain both Role.MATH and MathML, even when Anki's DOM
contains valid MathML.

## Why an Anki-only aria-label is not a solution

A spoken linear string can improve basic announcement but destroys the
structural navigation that MathCAT provides. Fractions, superscripts, roots,
matrices and nested expressions must remain MathML.

## Smallest coordinated direction worth prototyping

Qt side:
- Preserve QAccessible::Equation.
- Expose the invariant UIA_AriaRole value "math" for Equation. Do not use a
  localized control-type string as the only machine-readable selector.
- Transport structured MathML through a dedicated QAccessible attribute and
  the shared Word/Chromium custom UIA MathML property GUID
  {FA170AB3-3229-4E7C-827F-DD05EE0481D9}.
- Keep Name/Description free of raw MathML in production.

NVDA side:
- Recognize the invariant UIA ARIA role "math" as the candidate math object.
- Retrieve MathML from NVDA's already-registered Word MathML custom property.
- Expose controlTypes.Role.MATH only when MathML is actually retrievable.
- Reuse the existing MathCAT path; do not create a separate mathematics
  navigation implementation.

## Test acceptance criteria

A Windows test should use an actual QWebEngineView (Anki is a useful real-world
consumer) and real NVDA. For a fraction, exponent and equation independently:

- the object exposed to NVDA has Role.MATH;
- NVDA+Alt+M enters MathCAT rather than saying "Not math";
- Left/Right/Up/Down/Space produce structural speech;
- the visible MathJax rendering remains unchanged;
- ordinary keyboard focus and typed-answer cards are unaffected.

The independent Chrome control must run in the same job to prove MathCAT itself
is healthy.

## Diagnostic bridge

The audit branch includes a test-only bridge that transfers the exact MathML
through a marked UIA description and overlays that marked object as Role.MATH
with a real mathMl property inside NVDA's system-test plugin. This is
deliberately not proposed as production behavior.

The causal test now passes: real NVDA enters MathCAT inside Anki and navigates
the fraction, exponent and equation fixtures structurally. That confirms that
the rendering/content is valid and that restoring the missing Qt/UIA semantic
transport is sufficient.
