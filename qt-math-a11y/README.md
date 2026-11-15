# Qt WebEngine → UIA → NVDA MathML interoperability draft

This directory keeps the upstream-facing part of the Anki accessibility audit
separate from Anki-specific experiments.

## Confirmed transport gap

For web mathematics, Qt WebEngine already maps Chromium `kMath` and
`kMathMLMath` nodes to `QAccessible::Equation`. On Windows, Qt Base exposes
that role as a UIA Custom control, but currently does not provide the complete
machine-readable transport NVDA needs for structured mathematics:

- invariant `UIA_AriaRolePropertyId = "math"`;
- the registered UIA `MathML` string property.

Microsoft Word and Chromium use the same MathML custom-property GUID:

`{FA170AB3-3229-4E7C-827F-DD05EE0481D9}`

NVDA already registers and consumes this GUID for Word.

## Proposed generic path

1. Qt WebEngine exposes Chromium's `kMathContent` through a Qt accessibility
   attribute for the root equation object.
2. Qt Base registers the established MathML UIA property and returns that
   attribute for `QAccessible::Equation`. It exposes invariant ARIA role
   `math`; a localized control type may also be supplied for parity, but is
   not the machine-readable selector.
3. NVDA identifies the object from the invariant UIA ARIA role, retrieves the
   shared MathML property, exposes `Role.MATH`, and reuses its existing
   MathCAT implementation.

No Anki-specific code is needed in the final NVDA path, and equations are not
linearized into an `aria-label`.

## Causal evidence

The audit's test-only bridge restores exactly the two missing inputs at runtime:
`Role.MATH` and the existing Anki MathML. With those supplied, real NVDA
2026.3.1 successfully enters MathCAT inside Anki 26.09.4 for independent
fraction, exponent and equation fixtures. The semantic audit reports zero
unverified criteria in that run.

This proves sufficiency of the missing semantic transport. The bridge itself is
not proposed for production.

## Draft validation status

The saved patches currently pass direct `git apply --check`, application and
repository diff checks against:

- NVDA `release-2026.3.1`;
- Qt Base `v6.11.2`;
- Qt WebEngine `v6.11.2`.

The NVDA draft also passes its lightweight Python syntax validation. A full Qt
Base + Qt WebEngine C++ build and a runtime test using rebuilt Qt binaries are
still required before calling the upstream implementation complete.

## Acceptance test

Using real Anki/Qt WebEngine on Windows with real NVDA:

- fraction, power and equation objects are recognized as math;
- NVDA+Alt+M enters MathCAT;
- arrows and Space navigate the structure, including nested components;
- the visible MathJax rendering is unchanged;
- ordinary reviewer keyboard navigation remains unchanged.
