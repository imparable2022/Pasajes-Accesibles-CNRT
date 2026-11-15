# Qt WebEngine → UIA → NVDA MathML interoperability draft

This directory keeps the upstream-facing part of the Anki accessibility audit
separate from Anki-specific experiments.

## Confirmed transport gap

For web mathematics, Qt WebEngine already maps Chromium `kMath` and
`kMathMLMath` nodes to `QAccessible::Equation`. On Windows, Qt Base exposes
that role as a UIA Custom control, but currently does not provide the two
signals used by Chromium/assistive technology for structured mathematics:

- localized control type `math`;
- the registered UIA `MathML` string property.

Microsoft Word and Chromium use the same MathML custom-property GUID:

`{FA170AB3-3229-4E7C-827F-DD05EE0481D9}`

NVDA already registers and consumes this GUID for Word.

## Proposed generic path

1. Qt WebEngine exposes Chromium's `kMathContent` through a Qt accessibility
   attribute for the root equation object.
2. Qt Base registers the established MathML UIA property and returns that
   attribute for `QAccessible::Equation`; it also reports localized control
   type `math`.
3. NVDA recognizes a UIA object identified as `math` when the shared MathML
   property is available, exposes `Role.MATH`, and reuses its existing
   MathCAT implementation.

No Anki-specific code is needed in the final NVDA path, and equations are not
linearized into an `aria-label`.

## Acceptance test

Using real Anki/Qt WebEngine on Windows with real NVDA:

- fraction, power and equation objects are recognized as math;
- NVDA+Alt+M enters MathCAT;
- arrows and Space navigate the structure;
- the visible MathJax rendering is unchanged;
- ordinary reviewer keyboard navigation remains unchanged.

The audit branch's temporary FullDescription bridge is only a causal experiment
for proving that restoring `Role.MATH + MathML` is sufficient.
