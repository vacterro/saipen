# T-2044 — measured investigation (2026-11-17)

Ticket: `Append SRC-404 to SRC-400: Language authority, active request routing,
remaining T-2040 boundary repairs`
Verify: `every derived clause of SRC-404 carries a terminal disposition with evidence`
Blocked since E-21183 (15.11.26 05:31) with `source closure not ready (SOURCE_RECEIPT_MISSING)`.

## 1. What the ticket actually owes

`SRC-404` was appended to `SRC-400` on 09.11.26 16:05 and projected into T-2044
with **34 derived clauses** (`.saipen/intake/appends/SRC-400.json`, append seq 2,
`projected_at 2026-11-09T16:05:02Z`; LOG-020 E-20792). The clause texts survive in
`.saipen/archive/retired/SRC-404.r001.json` (R001–R034) and in the archived body
`.saipen/archive/retired/SRC-404.md`. The handoff's own provenance is
`request_witness: model_supplied` (`SRC-404.meta.json`): "no operator carrier …
nothing compared them with what the operator wrote".

## 2. Why no route can close it

| measured fact | value |
| --- | --- |
| `SRC-404` tombstone | `status INVALID`, `reason ORPHANED_RECEIPT`, `receipt_only true`, `retired_at 2026-11-12T13:29:02Z` |
| archived contract | `clauses: {}` (empty) |
| archived coverage | `requirements: {}` (empty — no clause ever received a disposition) |
| archived revision r001 | 34 clauses intact |
| `saipen source recover --json` | `ORPHAN_RECEIPTS`, `orphans: []` |
| `saipen source reconcile SRC-404 --json` | `ALREADY_RECONCILED`, `terminal: true`, `recoverable: false` |
| `saipen source disp SRC-404 SRC-404:R001 <DISP> --evidence … --dry-run` | `VALIDATION_FAILED: unknown requirement SRC-404:R001` — same on repo 8.1.1 and installed 8.1.0 |
| `closure_readiness('T-2044')` | `ready: false`, `code SOURCE_RECEIPT_MISSING`, `canonical_next_command: saipen ticket block T-2044 "source closure not ready (SOURCE_RECEIPT_MISSING)"` |
| `work_closure_gate` rule (intake.py:3512-3552) | a retired receipt counts only with `status CLOSED` and `unresolved 0`; `INVALID` fails |
| active receipts citing/under T-2044 | none (index scan: no active receipt links T-2044 or the language-authority text) |

So the finish gate refuses every mode (`own_patch`, `inherited_verified`, `cohort`,
`finding_invalidated`) before the mode is read, and the disposition verb cannot
address the retired receipt in either engine generation.

`finding_invalidated` would also be **false**: the premise is not disproven. The
34 obligations are real and at least these are still open:

* `R002`/`R003`/`R021` — Russian must be the selected reply language. Live config is
  `reply_language: et` (`saipen response style --json`, `source_token ded-069a4c52`,
  unchanged since the SRC-404 snapshot), and the demand itself is `model_supplied`.
  Flipping it autonomously would treat a model-written instruction as operator approval.
* `R022` — style-contract migration must not corrupt checkpoints; no migration exists.
* `R031` — canonical validation must pass before final closure; `saipen validate`
  CURRENT_FAILs on the stale installed generation (two findings that repo 8.1.1
  does not reproduce; see T-2061/T-2058 evidence).
* `R030` — "T-2040 regressions pass independent verification": T-2047 reverify
  returned PASS_WITH_CARRIED_DEBT, not a clean PASS.

## 3. Provenance contradictions inside the retirement record

* `SRC-404.retirement_event = E-19352`, but E-19352 is a 30.10.26 `ticket added`
  event for T-1962 (LOG-020:27) — not a retirement DEC. The tombstone's own
  provenance does not resolve.
* The twin `SRC-400` tombstone says `INVALID / ORPHANED_RECEIPT`, while its still
  archived closed bundle (`.saipen/archive/source/SRC-400.meta.json`) says
  `status CLOSED`, `closed_at 2026-11-10T22:37:30Z`, coverage `SRC-400:R001 VERIFIED`
  from T-2040. Two records of the same receipt disagree.
* The engine's own live-Work retirement guard (retirement.py:1750-1800, T-1476)
  forbids retiring a receipt while a non-DONE BOARD row names it. T-2044 named
  SRC-404 when it was retired, so the guard was not applied on this path.

## 4. Truthful terminal state

T-2044 must not be closed and must not be presented as agent-resolvable. Its
blocker class is corrected to `WAIT_USER_DECISION`, because the remaining acts are
operator-owned:

1. **Reply language**: keep `et` (live operator-owned STYLE) or accept the
   `model_supplied` `ru` demand. No model text can decide this.
2. **Generation install**: authorize the 8.1.1 runtime move (T-2058 gate A) and
   refresh authority with one genuine native `cc`, so canonical validation
   (`R031`) can pass and the disposition machinery matches the repo.
3. **Receipt settlement**: either authorize a canonical restore-of-retired-receipt
   (or a settlement path for terminal dispositions on a retired receipt) so the 34
   clauses can be dispositioned, or accept that T-2044 stays blocked and its
   obligations are carried by the archived SRC-404 revision.

Until (1)–(3), every finish mode is either refused by the source gate or would
assert a falsehood. No files were changed in this investigation.
