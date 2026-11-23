# SAIPAL reconciliation request: `NO_DRIFT` receipts and session bundles

Owner: T-1970 / SRC-351, clause `SRC-351:R011`.
Receiving owner: SAIPAL (`.saipal/`) maintainer.
Status: **prepared locally, not sent.** This repository holds no authority over
`.saipal/` and has modified nothing there.

## What is asked, and what is not

The incident witness self-reported that SAIPAL advanced through roughly forty
accepted session bundles, a session index reaching 1019, and five `NO_DRIFT`
candidate receipts; that four of the five candidates were template-generated;
and that some episodes were synthetic smoke fixtures.

**None of this is verifiable from this repository.** It is not promoted to fact
here, and nothing below asks SAIPAL to deny it either. The request is that the
owner reconciles its own records through its own canonical append-only
operations.

## Requested

1. Confirm or refute each of the five receipts against its source episode.
2. Mark any `NO_DRIFT` verdict whose candidate was mechanically derived from a
   template as `disputed` / `unverified` through the supported annotation path.
3. Label any episode originating from a synthetic smoke fixture explicitly, so
   no real-world cleanliness claim rests on it.
4. Preserve the original chronology and provenance. No rewrite. No deletion.

## Explicitly not requested

- No counter edit. No history deletion. No retroactive rewrite of `LOG` or the
  session index.
- No change to SAIPAL's protocol rules in response to this incident. SAIPAL
  answering `NO_HOME` in a `.saipen`-only project was **correct behaviour**; the
  defect was that the calling agent read that refusal as a directory hint.
  SAIPEN's own half of that is repaired under `EXACT-NAMESPACE-01`
  (`FOREIGN_PROTOCOL_COMMAND` plus the registry's `no_home_substitution` rule).
- No disablement of SAIPAL. `saipen/REGISTRY.json` records an independent,
  deliberate SAIPAL request as legitimate use.

## Why this clause stays BLOCKED on the SAIPEN side

`SRC-351:R011` is an unconditional external requirement. Per `saipen/SOURCES.md`
an unconditional external requirement that cannot run is `BLOCKED` in source
coverage and `BLOCKED_EXTERNAL` at Work lifecycle level — it is not eligible for
`UNAVAILABLE_ENVIRONMENT`, which is reserved for a clause normalized in advance
with a structured `when_environment` and a successful absence probe.

Evidence for the classification: `SRC-351` body §9, and
`.saipen/intake/active/SRC-351.meta.json` recording
`request_provenance.witness = model_supplied`.

---

## Addendum: the SRC-037 repair route is now measured (2026-10-31)

Filed with T-1971 rather than T-1972, because a staging decision must not be
used to smuggle a bundle repair.

Three candidate canonical routes were tested against the live receipt. All
three are closed:

- `saipen source reconcile SRC-037` -> `SOURCE_CORRUPTION`,
  `recoverable: false`, one contradiction ("Contract/coverage clause
  identities differ").
- `saipen source reconcile SRC-037 --confirm` is not the mirror image needed
  here. `reconcile_receipt` heals ACTIVE-residue-present / archive-absent
  (`intake.py:6053-6210`: it reads `intake/active/*.meta.json`,
  `intake/active/*.md`, `intake/contracts/*.json`, `intake/coverage/*.json`
  and `intake/tombstones/*.json`, then WRITES the archive bundle). SRC-037 is
  the opposite: the archive bundle is present and all four intake carriers are
  absent, so the survey cannot even reach its strong-proof gates.
- `saipen source retire SRC-037 --reason EMPTY_STALE_SOURCE --dry-run` ->
  `ALREADY_RETIRED`: "SRC-037 already carries a tombstone; retirement never
  rewrites it". The INVALID-tombstone writer is refused because a CLOSED
  tombstone already exists.

So no CLI verb repairs this shape. The measurement that makes the repair
tempting is nonetheless solid, and is recorded here rather than acted on:

| file | archive bytes sha256 | HEAD intake sha256 | identical |
|---|---|---|---|
| SRC-037.contract.json | 1ce989ef… | 1ce989ef… | yes |
| SRC-037.md | b1393000… | b1393000… | yes |
| SRC-037.meta.json | 91210e0f… | 12450157… | no (closure rewrite) |
| SRC-037.coverage.json | 6eacdf24… | b11d8cf9… | **no** |

HEAD's `.saipen/intake/coverage/SRC-037.json` holds 4 requirements whose ids
are `SRC-037:R001..R004`, matching the 4 clause ids in the contract
(`IDENTITY MATCH: True`); the archive copy holds 16 clauses from a JavaScript
project. The truthful ledger therefore still exists in committed bytes.

What T-1971 must decide, and what this note does NOT decide: whether the
sanctioned repair is (a) implement a canonical verb for the
archive-present/intake-absent contradiction, (b) a journalled restore of the
archive coverage from the committed intake bytes, or (c) something else. Until
then the corrupt bytes stay exactly where they are, and T-1972's stage has
pinned them in the index -- which is why no commit may land before T-1971
resolves.
