# Anki/NVDA real semantic reading audit — 14 Nov 2026

**Evidence:** [GitHub Actions run 43632280136](https://github.com/imparable2022/Pasajes-Accesibles-CNRT/actions/runs/43632280136), both Windows/NVDA configurations completed with success. The test journey completed ten native Anki fixture decks. **Workflow success does not imply semantic accessibility success:** the semantic validator was deliberately configured as a separate `continue-on-error` measurement, recording unverified speech in `semantic-audit.json`.

## Observed NVDA results

| Content | Automatic focus OFF | Experimental rich focus ON | Meaning |
|---|---|---|---|
| Image with alt `Green square on white background` | Not spoken in the tested gestures | **Spoken as part of NVDA's graphic description** | Demonstrates image is reachable with experimental focus in this setup; more templates still untested. |
| MathJax fraction `\\frac{1}{2}+\\frac{1}{4}` | Not verified in speech | Not verified in speech | Rendered HTML has math symbols but NVDA did not announce fraction structure in the tested gestures. |
| MathJax exponent `x^2+y^3` | Not verified in speech | Not verified in speech | Same issue. |
| MathJax equation `2x+3=7` | Not verified in speech | Not verified in speech | Same issue. |
| Audio in note | Playback request verified on both | Playback request verified on both | Pressing Anki reviewer `r` created both `user_replay` and `play_request` callback records. The keyboard shortcut is functional; no assertion is made that the CI machine emitted audible audio. |
| NVDA accessible media-control label | Not verified | Not verified | No named play/pause control was read through the tested card navigation. |
| Cloze revealed text `telescope` | **Spoken** | **Spoken** | Correct incremental announcement worked. |

**Machine-readable evidence:**

- Rich focus on: `anki-real-nvda-evidence-rich-true`, artifact 14129605592. The semantic audit recorded **3 verified of 7 criteria**: image description, audio shortcut received, playback requested.
- Rich focus off: `anki-real-nvda-evidence-rich-false`, artifact 14128854125. The semantic audit recorded **2 verified of 7 criteria**: audio shortcut received, playback requested.

### Important limits

The `NVDA_SEMANTIC_SPEECH_PROBE` used screen-reader keyboard gestures, including virtual cursor and object navigation. A missing phrase is **a failure to prove accessibility in this journey**, not necessarily a proof that no alternative NVDA route works. The MathJax source was rendered (visible `1, 2, +, 1, 4` or superscript numerals), but rendering does not prove semantic speech. Audio replay events demonstrate the Anki API dispatch only, not sound device output or perceptual audibility. The MathCAT gesture exploration was added in a later experiment and should be evaluated independently.

## Upstream implementation track

An independent patch covering **only editor field accessible names** is in
`upstream-ready/0001-editor-fields-accessible-names.patch`. The dedicated
[syntax workflow 43631380836](https://github.com/imparable2022/Pasajes-Accesibles-CNRT/actions/runs/43631380836) succeeded. It checked `git apply` against exact upstream commit `827f4aa42681f1d60ab0fe4ad76eb75d767a385e`, parsed the four changed components using upstream Svelte compiler, and verified the changed-file list. **Full Svelte type-check is unverified**: invoking it without first generating Anki's backend/FTL modules produced hundreds of dependency errors, unrelated to this patch. No actual build of patched Anki and no PR were performed.

Reviewer and editor functionality are now split into separate Python modules in the experimental add-on, keeping the reviewer’s focus modification off by default. Before proposing a reviewer PR, resolve mathematical semantics and document audio controls, then execute tests with the actual upstream changes.

### Relevant prior upstream discussion

Official [Anki PR 4511](https://github.com/ankitects/anki/pull/4511) proposed automatic focus management and announcing card content. Maintainers suggested separating concerns, verifying on screen readers and card types, and waiting for reviewer refactoring. The PR was closed without merge; the maintainer pointed to [issue 4661](https://github.com/ankitects/anki/issues/4661) as the accessibility tracker. This is relevant upstream feedback; avoid submitting another large, undifferentiated PR.
