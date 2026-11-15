# Anki / Qt WebEngine / NVDA MathCAT on Windows — root-cause note

Status: experimental audit, 15 Nov 2026. This note records evidence; it is not
an upstream fix proposal yet.

## User-facing criterion

A screen-reader user studying a MathJax card should be able to reach the
mathematical expression, press NVDA+Alt+M, and use MathCAT's structural
navigation (arrows and Space) to explore fractions, powers and equations.
Visible glyphs or a linearized accessible name do not satisfy this criterion.

## Positive control: NVDA + MathCAT works

The audit uses NVDA 2026.3.1 on Windows and direct native MathML in Chrome.
After correcting a CI-only zero-rate bug in NVDA's speech-spy synthesizer,
MathCAT successfully enters and structurally explores:

- fractions, spoken naturally as expressions such as “1 half” and “1 fourth”;
- powers, including “x squared” and “y cubed”;
- equations, including “is equal to”.

Therefore a failure inside Anki cannot be attributed to MathCAT being
unavailable in the tested NVDA build.

## Real Anki result

Anki 26.09.4 renders the fixtures with MathJax 3.2.2. The reviewer DOM contains
real assistive MathML. In the opt-in experiment the <math> element can receive
DOM focus, and cloning the same MathML outside MathJax's assistive wrapper does
not change the NVDA result. NVDA+Alt+M reports “Not math”.

A separate HTML role=math wrapper is also tested so that MathJax's wrapper and
native MathML focus are not assumed to be the cause.

## Accessibility transport chain

Current Qt WebEngine maps Chromium accessibility roles kMath and kMathMLMath to
QAccessible::Equation in src/core/browser_accessibility_qt.cpp. Qt WebEngine
also has tests asserting that native <math> receives QAccessible::Equation.

On Windows, Qt Base maps QAccessible::Equation to UIA_CustomControlTypeId in
src/plugins/platforms/windows/uiautomation/qwindowsuiautils.cpp.

NVDA maps UIA_CustomControlTypeId to controlTypes.Role.UNKNOWN. Its
NVDA+Alt+M command requires a controlTypes.Role.MATH object (or an equivalent
math control field) plus retrievable MathML. The IA2/Chromium web path has a
dedicated Math overlay that can retrieve native MathML; Qt's Windows UIA
provider does not expose an equivalent MathML property.

This explains the observed Anki speech (“unknown” / “Not math”) even though the
page DOM contains valid MathML.

## Consequence

An Anki-only change that merely adds role=math, tabindex or another copy of the
same MathML is unlikely to solve structural MathCAT navigation on Windows if
Qt's UIA bridge still publishes the target as a generic Custom control and
does not transport MathML to NVDA.

The next useful work is to verify the exact UIA properties of the focused Qt
math object in the real NVDA run and then choose between:

1. a coordinated Qt/NVDA upstream solution that transports equation identity
   and MathML over Windows accessibility APIs; or
2. a clearly isolated bridge proof-of-concept, used only to demonstrate that
   handing Anki's existing MathML to MathCAT restores native structural
   navigation.

Do not replace equations with plain aria-label text as the final solution:
that would make speech possible while discarding MathCAT's structural
navigation.
