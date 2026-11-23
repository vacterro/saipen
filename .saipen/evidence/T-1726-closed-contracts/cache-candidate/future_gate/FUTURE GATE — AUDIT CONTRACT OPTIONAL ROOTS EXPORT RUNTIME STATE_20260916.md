# FUTURE GATE — AUDIT CONTRACT `optional` ROOTS EXPORT RUNTIME STATE; PROJECT-LOCAL SCOPING IS ERASED BY REGENERATION

Status: RECORDED FOLLOW-UP WORK / NOT AUTHORIZED FOR IMPLEMENTATION

Recorded: 2026-09-16 by an opencode session bound to `_SAIPENVIEW`
(lineage `lineage-3d3c3d12923e46d5808f1545a72e3c6c`), during T-850 / SRC-007
(audit-artifact authority + runtime-leak repair).

This document is a record of an external, mechanically reproduced defect. It is
not a claim that anything here has been fixed, and it must not be cited as
evidence for any coverage disposition. Do not implement it while an active
ticket holds this repository's DOING seat.

## DEFECT

`tools/saipen_engine/audit_manifest.py` declares three broad RECURSIVE
`optional` roots and a three-entry `non_exportable` list. The `optional` roots
are whole live working trees that contain transient producer/crew coordination
state, staging directories and live sub-agent instance memory, none of which is
exportable audit evidence. A faithful consumer therefore packs machine-local
runtime state into the audit artifact while also reporting
`authoritative_state = true`, `required_evidence_omitted = false`.

The generator emits the declaration from a literal (`build()` ->
`OPTIONAL_DIRS`); it has no project-policy input. A project that narrows its own
`.saipen/MANIFEST.json` to durable surfaces has that narrowing erased by the
next canonical lifecycle mutation, because `ensure()` rewrites the document from
`build()`. The scoping therefore cannot be expressed on the project side at all.

## CURRENT DECLARATION (source truth, measured 2026-09-16)

```
CONDITIONAL_DIRS = (
    (LOGS_DIR, True, 4000),
    ("intake", True, 8000),
    ("archive/source", True, 8000),
    ("KNOWLEDGE", True, 4000),
    ("audit", False, 500),
    ("evidence", True, 4000),          # added by T-1373 / SRC-054 WIP
)

OPTIONAL_DIRS = (                      # audit_manifest.py:131-135
    ("extensions", True, 4000),
    ("kitchen", True, 500),
    ("saitranslate", True, 500),
)

NON_EXPORTABLE = (                     # audit_manifest.py:140-144
    f"{LOCKS_DIR}/",
    "recovery/",
    "LOCAL_STATE.json",
)
```

Source: `_SAIPEN/tools/saipen_engine/audit_manifest.py:131-144` (working tree;
`git status` shows `M tools/saipen_engine/audit_manifest.py` from the
T-1373/SRC-054 `evidence` + `references` work). Both installed homes
(`~/.agents/skills/saipen`, `~/.config/opencode/skills/saipen`) carry the same
broad `OPTIONAL_DIRS`; neither has any narrower variant.

The strings a project-side repair had hand-authored -- `kitchen/release_scope`,
`saitranslate/SETTLED`, `saitranslate/SUPERSEDED`, `extensions/subs/_shared`,
`extensions/subs/TEMPLATE`, and the transient `non_exportable` entries
`saitranslate/.prepare-staging/`, `saitranslate/READY/`, `saitranslate/kitchen/`,
`saitranslate/producer_epoch.json`, `kitchen/crew_epoch.json` -- do not exist
anywhere in this source. See the two packaged artifacts below.

## MECHANICAL PROOF (read-only, reproduced 2026-09-16)

Two archives of the SAME SAIPENVIEW project, one before and one after a
canonical `saipen continue`:

| Artifact | manifest | members | leak | subs live STATE/BOARD/LOG | saitranslate files | kitchen files |
|---|---|---:|---:|---:|---:|---:|
| `saipenview_16.09.26-T17-44-29.zip` | hand-authored, narrow | 1738 | 0 | 0 | 4 (SETTLED/SUPERSEDED only) | 9 (release_scope + receipt) |
| `_SAIPENVIEW_16.09.26-T23-41-20.zip` | regenerated, broad | 1870 | 8 | 21 | 84 | 13 |

"leak" = members matching `.prepare-staging` | `.in-flight` |
`producer_epoch` | `crew_epoch`.

Members present in the regenerated archive and not in the narrow one include:

```
.saipen/saitranslate/.prepare-staging/94f46884dc604e609df821192809a001/.in-flight
.saipen/saitranslate/.prepare-staging/94f46884dc604e609df821192809a001/staging.manifest.json
.saipen/saitranslate/.prepare-staging/94f46884dc604e609df821192809a001/payload/saipenview/ui/static/locale-*.js
.saipen/saitranslate/producer_epoch.json
.saipen/kitchen/crew_epoch.json
.saipen/kitchen/fix_log_dupes.py
.saipen/kitchen/fix_state.py
.saipen/kitchen/fix_t20.py
.saipen/extensions/subs/saihunt/STATE.md      (and BOARD/LOG for every live sub)
.saipen/extensions/subs/saipython/STATE.md
.saipen/saitranslate/STATE.md  BOARD.md  LOG.md
.saipen/saitranslate/kitchen/README.<40 locales>.md
```

All of these were packed while the consumer reported
`saipen_snapshot.status = COMPLETE`, `authoritative_state = true`,
`required_evidence_omitted = false`.

## ROOT CAUSE — REGENERATION ERASES PROJECT-LOCAL SCOPING

The narrow manifest was not generator output. It was a hand-authored document
on disk. The next canonical mutation regenerated it:

```
saipen continue --json  (2026-09-16, SAIPENVIEW)
  reconciliation.code = AUDIT_MANIFEST_UPGRADED
  audit_manifest.declared = STALE
  audit_manifest.detail = "an older or drifted declaration of a supported
    contract; rewritten deterministically from the current contract"
  path = V:/.../_SAIPENVIEW/.saipen/MANIFEST.json
```

`declared()` (`audit_manifest.py:~382`) marks a manifest `STALE` when
`is_current()` is False, and `is_current()` compares all non-timestamp content
against `build()`. So a project that narrows `optional`/`non_exportable` reads as
drifted and is overwritten from the literal. This is structural, not staleness:
the manifest's `generated_at` is irrelevant to the verdict.

Consequence: SAIPENVIEW's own written persistence contract
(`docs/saipen-persistence.md`) classifies `.saipen/saitranslate/`,
`.saipen/kitchen/` scratch and `.saipen/extensions/subs/*/` instances as
machine-local surfaces that "never" travel -- and the protocol generator
overrides that decision on every lifecycle run, with no way to express it.

The T-1373/SRC-054 `dropped_declarations` mechanism reports the case where a
regeneration NARROWS declared evidence. It does not cover the opposite: a
generator WIDENING past the project's intent, which is what this defect is.

## BOUNDED FOLLOW-UP OPTION (choose ONE, later, per its own red control)

Make the contract's declaration express durable evidence, not whole live trees:

* narrow `OPTIONAL_DIRS` to the durable subsurfaces actually worth exporting,
  e.g. `kitchen/release_scope`, `saitranslate/SETTLED`, `saitranslate/SUPERSEDED`,
  `extensions/subs` (non-recursive definitions) plus
  `extensions/subs/_shared` and `extensions/subs/TEMPLATE`;
* extend `NON_EXPORTABLE` with the transient classes: `saitranslate/.prepare-staging/`,
  `saitranslate/READY/`, `saitranslate/kitchen/`,
  `saitranslate/producer_epoch.json`, `saitranslate/STATE.md`,
  `saitranslate/BOARD.md`, `saitranslate/LOG.md`, `saitranslate/_prepare_k1.py`,
  `kitchen/crew_epoch.json`, and live sub-instance `STATE/BOARD/LOG` under
  `extensions/subs/*/`.

and, independently, decide whether a project may legitimately NARROW its own
declared evidence and have that survive regeneration (a policy input to
`build()`), rather than being silently rewritten from the literal.

Required hostile controls:

* a red control proves the pre-fix contract packs `.prepare-staging/**`,
  `.in-flight`, producer/crew epoch files and live sub-instance STATE/BOARD/LOG
  while the snapshot reports COMPLETE / authoritative;
* a project-scale fixture with both durable evidence and transient state proves
  durable evidence is present AND every transient class is absent;
* regeneration after a project-local narrowing either preserves the narrowing or
  reports the widening by name -- never silently widening;
* the `GLOBAL_FILE_CEILING` containment bound still holds for every narrowed
  root, and a symlinked root is still never descended.

NON-GOALS: do not widen `.gitignore`; do not delete project data; do not weaken
`authoritative_state`; do not drop durable authority receipts
(`intake/`, `archive/source/`, `kitchen/release_scope/`, KNOWLEDGE).

## CONSUMER-SIDE NOTE (AUDAPACK, informational)

`_AUDAPACK/audapack/saipen_evidence.py` is contract-driven and behaves
correctly: it collects exactly what the manifest declares. It needs NO change
once the contract stops declaring whole live trees as evidence.

One related, separate AUDAPACK-side drift was observed and is NOT this defect:
`_AUDAPACK/tests/test_saipen_manifest_gate.py:369` asserts
`snapshot["non_exportable"] == ["locks/", "recovery/", "LOCAL_STATE.json"]`
while the live snapshot emits `.saipen/locks`, `.saipen/recovery`,
`.saipen/LOCAL_STATE.json` (prefixed, no trailing slash). Reproduce:
`python -m pytest tests/test_saipen_manifest_gate.py -q` -> 3 failed
(1 assertion mismatch above; 2 are a local `git` not on the subprocess PATH).

## ORIGINATING MISSION

`_SAIPENVIEW` T-850 / SRC-007, "P1 audit-artifact authority defect". The
originating handoff asserted the classification repair "lives in the external
SAIPEN manifest owner"; measurement shows no such repair exists in any shipped
source, and the only green artifact was produced from a hand-authored manifest.
The repair belongs to the SAIPEN protocol tree, which is a different repository
than the bound project, so this record is the established cross-project handoff
rather than an edit of unrelated protocol code. The operator explicitly directed
that the protocol repository not be modified from T-850.
