# T-1259 Hot-Path Ownership Map

Scope: the four hot-path owner documents at their pre-wave sizes --
`CORE.md` 24324, `IMPROVE.md` 23563, `OPS.md` 19872, `MAINTENANCE.md` 16616;
corpus 84375 bytes. T-1229 already compressed the 16 phase deltas
(100304 -> 42078); this wave applies the same classification to the owners the
load profiles actually charge on every run.

Classification reuses T-1229's letters: A own delta, B CORE law,
C OPS/effect law, D MAINTENANCE law, E another owner, F history/rationale,
G repeated checkpoint/log/transition/ticket mechanics.

## Why these four, in this order

`protocol_budget.py` charges them as follows:

- `ordinary_continue` 25471 = CORE 24324 + `phases/done.md` 1147.
- `ordinary_phase` 30574 -- CORE plus the largest phase delta.
- `command_resolution` 24716 = REGISTRY.json 20129 + COMMANDS.md 4587, with
  IMPROVE 23563 conditional.
- `ship_improve` 27238 -- IMPROVE dominates it.
- `single_doc` 24324 = CORE.

So CORE is on every non-cold profile and IMPROVE is the whole weight of two.
MAINTENANCE and OPS are conditional but load on the autonomous and mechanical
paths that run constantly.

## CORE.md -- least compressible

Already normative-dense: T-1229 pushed shared law INTO it, so most of its bytes
are the canonical statements the phase deltas now cite. Compressible surface is
narrow:

- F: the "Protocol-state repair contract (normative)" tail restates §1.5
  recovery, §1.10 continuation and §1.11 determinism in a second voice. Keep
  the repair-order ladder, the CORRUPT/REPAIRED/WARN/BLOCKED classification and
  the carrier-execution rule; drop the sentences that re-explain rules stated
  above it.
- G: §1.10's `cc`/bare-`saipen`/`saipen continue` one-pipeline statement appears
  twice (§1.10 and the repair contract). One owner.
- E: §1.10's USERPERSON precedence paragraph is the longest single block in the
  file and OPS owns its mechanics; keep the precedence chain and the two
  report forms, cite OPS for locations/validation/writes.

Expect a modest reduction. CORE is at or near its semantic floor and forcing it
lower would delete cited law, which is the exact harm the acceptance names.

## MAINTENANCE.md -- largest single win

Written as run-on argumentative prose, not law. Every §2.4 bullet restates its
own rationale, then the counter-argument, then the incident that produced it.

- F remove: "it was until v7.86.0, and that was a deadlock" and the repeated
  re-derivation of why the valve is not an Exit; "Same reasoning that kept the
  valve off the Exit list in v7.86.0"; the double/triple explanation of why
  counters must persist; the narrative about a wave counted twice.
  Retain the exact invariants those stories defend: valve is a pause not an
  exit, `phase` untouched, counters untidied, `blocker: none`, the verbatim
  `WAIT:` form, the exact `DEC:` line texts.
- G cite: checkpoint mechanics, LOG line format, ticket demotion order.
- B cite: Pick Rule, §1.11 action priority, §1.2 WAIT form, §1.5 recovery
  rebuild -- currently quoted at length inside §2.4.
- A retain: halt definition, zero-prompt auto-transition with its two
  exceptions, HUNT entry split, ADD ownership boundary, Industrial Completion,
  goal Entry/Continuation/Board-empty/SHIP-exception/counters/valve/Exit as
  rules rather than as argument.

## IMPROVE.md -- second largest win

Correctly the single owner of the Improve lifecycle, but it explains the same
completion bar four times and repeats each command's validation list in §1 and
again in the section that owns it.

- G remove: the per-command validation prose in §1 where §2/§7/§9/§10 own the
  same rules; §1 keeps the action set, one-line purpose, and the argument shape.
- F remove: the T-552/T-553/T-601/T-632 narrative asides once the invariant
  they justify is stated; keep the ticket refs on the invariants themselves.
- Duplicated completion bar: §2, §9 and the `cycle-complete` bullet each spell
  out "strict manifest, every expected report full-valid, exact composite sweep
  coverage". State it once, cite it three times.
- A retain: meta-control proof, cycle/seat/report identity, composite finding
  identity, closed vocabularies, sweep validation order, chain of custody,
  writer boundary, the two reasoning-gate fields.

## OPS.md -- middle win

Mechanics belong here, but §7's error-code block has grown incident commentary
inline, and §3 restates recovery three times (lifecycle vocabulary, Recovery,
preflight list).

- F remove: the parenthetical ticket stories inside the error-code prose
  (T-1003 carrier-loss wave, NITRO dogfood IV narration) once the code's meaning
  and its executable next action remain.
- G collapse: the recovery preflight rules stated in "Lifecycle vocabulary",
  again under "Recovery", and again as the preflight list. One ordered list.
- B/E cite: CORE §1.5's checkpoint order rather than re-deriving why LOG leads.
- A retain: PLAN/APPLY steps, journal semantics, roll-forward/CONFLICT rules,
  idempotency, provenance markers, locks, dry-run, result shape, the closed
  error-code set, effect vocabulary and coverage verdicts, disposition
  vocabulary, the reconciliation contract's result codes.

## Constraints this wave must not break

- `validate.py` cross-doc-drift checks grep these four files for exact
  phrasings. Baseline is 20 warnings, 0 FAIL; the wave may not add a slug.
- `[improve-state-purity]` and the CORE/IMPROVE/CLI action-set equality check
  read `IMPROVE_ACTIONS` and the routing declaration literally.
- `audit_checks.py` baseline is 227 of 227 red controls.
- Rule-owner comments (`<!-- RULE-OWNER: ... -->`) are machine-read anchors and
  stay exactly where they are.

## Implemented result

Exact before/after bytes:

| Document | before | after | delta | % |
|---|---:|---:|---:|---:|
| `CORE.md` | 24324 | 24146 | -178 | 0.7 |
| `IMPROVE.md` | 23563 | 22245 | -1318 | 5.6 |
| `OPS.md` | 19872 | 19279 | -593 | 3.0 |
| `MAINTENANCE.md` | 16616 | 13886 | -2730 | 16.4 |
| **corpus** | **84375** | **79556** | **-4819** | **5.7** |

`human_markdown_total` 211139 -> 206326. Load-profile deltas
(`tools/protocol_budget.py`):

| Profile | before | after | delta |
|---|---:|---:|---:|
| cold | 15912 | 15912 | 0 |
| ordinary_continue | 25471 | 25293 | -178 |
| command_resolution | 24716 | 24716 | 0 |
| ordinary_phase | 30574 | 30396 | -178 |
| ship_improve | 27238 | 25920 | -1318 |
| single_doc | 24324 | 24146 | -178 |

`cold` and `command_resolution` are unmoved by construction: cold loads
BOOT/STYLE/INDEX and command resolution loads REGISTRY.json + COMMANDS.md, and
this wave touched none of those four files.

## Semantic floor, measured rather than asserted

MAINTENANCE was the only document carrying real narrative weight, and it gave
up 16.5%: the § 2.4 valve rules each argued their own case, re-derived the
v7.86.0 deadlock twice, and restated the counter-persistence argument three
times. The rules survive unchanged -- the exact `DEC:`/`WAIT:` forms, the
untouched-`phase` rule, the untidied counters, the Exit list and its explicit
exclusion of the valve.

The other three were already near their floor, and the reason is T-1229: that
wave pushed shared law INTO these owners so the 16 phase deltas could cite it.
Compressing them further would delete cited law, which is the harm this wave's
acceptance forbids.

That is now measured, not claimed. A 9-gram shingle comparison across the whole
protocol corpus -- all 19 `saipen/*.md` plus all 16 `saipen/phases/*.md` --
finds **zero** shared 9-grams between any of these four documents and any other
protocol document. A 7-gram scan inside each of the four finds **zero**
remaining internal repeats. There is no duplicated text left to remove; what
remains is unique normative statement.

## Ownership defects fixed on the way

- `OPS.md` § 9 and § 10 both cited "CORE § 1.10's host-agent rules". CORE § 1.10
  is the Command Surface and contains no host-agent rules; no document in the
  corpus does. An agent following either citation reads the wrong section, finds
  nothing, and invents. § 9 now cites CORE § 1.1 (`OPS-EFFECT-01`), which
  actually states effect-based authorization; § 10 now cites CORE's
  protocol-state repair contract and names the four rules it carries.
- CORE stated goal-completion authorization twice -- once in § 1.12 and again as
  a repair-contract bullet. § 1.12 keeps it; the bullet is gone.
- `IMPROVE.md` § 1 and § 11 both stated the phase/task/next_action boundary.
  § 11 (the meta-control proof) keeps it; § 1 cites it.
- `IMPROVE.md` stated the cycle-completion bar in three places (§ 2,
  `cycle-complete`, § 9). § 2 now states it once as **the cycle bar**; the other
  two cite it.
- `OPS.md` stated the recovery preflight rules three times (lifecycle
  vocabulary, Recovery, preflight list). One ordered first-match list now owns
  them.
- `IMPROVE.md` § 7 carried two disagreeing descriptions of the sweep record: the
  `SweepRecord` block (`finding_ref, disposition, ticket, report, reproduced,
  fixed_by, verification`) and a prose line naming `seat_id/report_path, run_id,
  IMP-id, ...`. `tools/improve.py:136` has the seven fields of the block and no
  `run_id`; the prose was describing a record that does not exist. Removed.

## Gate evidence (final surface)

- `python tools/validate.py` -- conformant, 0 FAIL, 20 WARN (baseline was the
  same 20; no slug added, none silenced).
- `python tools/protocol_budget.py` -- BUDGET PASS.
- `python -m ruff check tools/ tests/` -- All checks passed.
- `python -m unittest discover -s tools` -- Ran 706 tests, OK.
- `python tools/audit_checks.py` -- 227 of 227 validator checks still go red on
  their own condition.
- `python tools/run_scenarios.py` -- All executable scenarios and injector
  probes passed.

The scenario gate had to be re-run: the first attempt overlapped this ticket's
own edits and reddened `T-1022 nitro probes leave the live HOME tree
byte-identical -- live .saipen tree changed`, which is T-1258's concurrency
defect reproduced rather than a compression regression. The serial re-run over
the final bytes is green.
