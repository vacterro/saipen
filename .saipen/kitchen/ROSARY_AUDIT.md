# Rosary borrow audit -- observe-only, no changes made

Source read: `github.com/agentic-research/rosary` (README/docs, 2026-08-03).
Rosary is an executing orchestrator: SQLite/Dolt-backed beads, a scanning
dispatch loop, isolated agent workspaces, a six-tier verification gate, Linear
sync. SAIPEN is a portable file protocol with no runtime. Everything below is
judged on whether the *invariant* transfers, never the machinery.

Nothing in this document is implemented. No RFC, no ticket, no code.

---

## 1. What SAIPEN already implements fully

**Deterministic action selection (direction 1, partly 2).** § 1.11 fixes the
priority RECOVER > UNBLOCK > FINISH > START > MAINTAIN, first match wins, "no
weighing". § 1.6's Pick Rule then takes the topmost workable `## TODO` line.
Since T-424 `tools/validate.py` re-derives that pick and FAILs a
`next_action` naming anything other than the topmost workable ticket -- so the
pre-computed pick is checked against the board rather than trusted. This is
Rosary's reconcile step expressed as a rule plus a checker, which is exactly
the shape the brief asks for.

**Readiness as a derived predicate (direction 2).** *Workable* = open
checkbox + every `needs:` in `## DONE` + not under another agent's active
claim (§ 1.6). No `ready=true` field exists and none is wanted. NOT_READY
reasons are materialised where they matter: a cyclic or dangling `needs:`
moves the ticket to `## BLOCKED` with `| blocker: dependency cycle: ...` or
`| blocker: needs nonexistent T-###` (§ 1.2). Ordering is total: board order
is priority. Negative tests exist (`dependency-cycle`,
`dangling-needs-reference`, the pick-rule controls in `audit_checks.py`).

**Structured handoff (direction 8).** Already canonical and already richer
than the brief's list: `extensions/subs/PROTOCOL.md` § 2 defines the OUTBOX
record and `phases/prepare.md` step 4 requires `status`, `producer`,
`source_head`, `coverage`, `payload`, `verified`, `instructions` on every
collectable handoff, with `status: ready` legal only when coverage is
complete and the head is current. `saipen collect` refuses anything else with
a fixed no-op reply. `.saipen/kitchen/digest.md` is the compact human
projection. CONFORMANCE 53 validates the shape.

**Evidence and provenance (direction 10).** Stronger here than in the source.
`| verify:` is REQUIRED and non-empty in `## DONE` (CONFORMANCE 44). A
CONFORMANCE row may not cite a ticket the board still leaves open (199) --
which caught a real early claim this session. A LOG line MUST record what
happened, never an intention (§ 1.2, CONFORMANCE 197). MARKHUNT findings need
a real `file:line` or command output, "no cite, no ticket" (52). Since T-438 a
conformance run has a fixed findable form, `RUN: validate.py -> PASS|FAIL`.

**Stopping conditions, most of them (direction 9).** `WAIT:` carries a
category from a closed set of seven, and a vague `WAIT: need more context`
FAILs (CONFORMANCE 57) -- the brief's "'could not' without classification is
not a state" is already enforced mechanically. § 1.11 makes insufficient
information a stop rather than a guess. § 1.4 defines takeover precisely: a
`claim_time` 15+ minutes old is forfeit, and the taker LOGs a `DEC` naming
the old owner and the observed staleness.

---

## 2. What is partial

**Reconciliation when the validator cannot run (direction 1).** The pick
re-derivation lives in `tools/validate.py`. The frozen portable floor catches
11 of 41 defects it catches (CONFORMANCE 78) and the pick check is not among
them -- a `grep` cannot parse a board's dependency graph. So on a host without
Python, `BOOT.md` step 7's "execute `next_action` immediately" executes a
pick nobody re-derived. The rule is right; its witness is host-dependent and
BOOT does not say so.

**Bounded retry (direction 4).** The caps exist and are real:
`phases/verify.md` 3 dead hypotheses or 2 failed fix cycles, `review.md` 2
passes per finding, `ship.md` retry-once, § 2.4's 3-wave/20-ticket valve, and
§ 1.6's "a repeated attempt MUST be able to name what changed" -- which is the
brief's infinite-loop concern stated as a rule. Failure classes are named
where they bite: `ship.md` step 10 splits transient / non-fast-forward /
other, `verify.md` closes with `conf: high|med|low`.
**The gap is countability.** REVIEW's cap became a real field, `review_passes:`
(§ 1.2, CONFORMANCE 132), precisely because "the cap was where the RFC says it
must not be -- in memory". VERIFY's 3/2 cap never got the same treatment: it is
still counted from memory, and `verify.md`'s hysteresis rule (append to
`| blocker:`, never overwrite) preserves the history as prose that nothing can
sum. Same defect, same document, one field over.

**Verification ladder (direction 5).** `verify.md` already orders
`parse -> import -> unit -> repro -> smoke` and calls it "strongest
available", and it carries two rules the brief does not ask for and should:
a gate that cannot fail is not a gate (break it once on purpose), and a gate
stuck red lies as loudly as one stuck green (run a known-good control before
reporting a total failure). What is missing is (a) the explicit
cheapest-first ordering claim, (b) a stated rule that the first mandatory
failure ends the PASS claim, (c) any record of how far the ladder got.

**Discoverable verification contract (direction 6).** `| verify:` pins the
command per ticket at PLAN time, `scout.md` step 3 notes the repo's harness
and build commands, and `verify.md` says "repo's own harness only (never
invent one)". But nothing requires the discovered commands to land in one
canonical place, so each session re-derives them and two agents can pick
different ones. `KNOWLEDGE/` is defined as exactly this ("durable truths") and
is simply not being used for it.

**Generator/evaluator separation (direction 7).** REVIEW is a separate phase
with its own cap and its own verdict vocabulary, and subSaipens are structural
read-only workers whose output reaches Core only through OUTBOX + `collect` +
the normal gates. What is absent is the brief's sharpest clause: *the
evaluator does not trust the generator's claimed results, it repeats the
mandatory checks itself*. `review.md` reviews the diff; nothing tells it to
re-run the ticket's own `verify:`.

---

## 3. Real logical holes that remain

**H1 -- concurrent whole-file clobber (direction 3).** Witnessed twice this
session, not hypothetical. A parallel session overwrote `BOARD.md`, reverting
six `## DONE` moves whose work was already committed and pushed (E-1863); the
board then contradicted shipped history and only CONFORMANCE 199's citation
check caught it. § 1.4 already anticipates this and calls it outside Core's
envelope by design, and § 1.4/§ 1.5 require re-reading after a write -- but a
re-read after *your own* write cannot see a clobber that lands after it. There
is no cheap guard on "the file changed between my read and my write".

**H2 -- VERIFY's cap is uncountable.** See § 2 above. A ticket can spend a
fresh 3/2 budget on every visit and no artifact can show it; the hysteresis
rule that exists to stop exactly that relies on prose in `| blocker:`.

**H3 -- no terminal state distinct from an ordinary block.** § 1.11 and
`blocked.md` cover "stuck, needs a human". Nothing marks "this is finished
being retried, resumption is forbidden without new grounds", which is the
brief's dead-letter. T-427 already owns the adjacent problem (permanent-warning
owner tickets that the Pick Rule can still select and that can never close).

**H4 -- the pick is re-derived only where Python runs.** See § 2.

---

## 4. Rosary ideas that are runtime-only and do not transfer

- The scanning dispatch loop, isolated workspaces, `sprites.dev` containers,
  `--concurrency N`: these presuppose a process that runs agents. SAIPEN is
  read by an agent; it does not run one.
- SQLite `beads.db`, per-repo Dolt servers, Linear sync, MCP dispatch tables
  (`rsry_dispatch_record` and friends): storage and integration, both barred
  by the zero-dependency constraint and by SAIPEN's whole premise that the
  state is plain files a human can read and a stranger's agent can continue.
- `bead` / `thread` / `decade` vocabulary: SAIPEN already has ticket,
  `needs:` chain, and CONFORMANCE row. Renaming buys nothing.
- Numeric backoff timers: SAIPEN never schedules its own re-execution, so a
  `retry_after` would be a field nobody reads. The brief says this itself.
- Plugin-injected `coverage: f64` gates: language-specific, and the protocol
  deliberately hardcodes no toolchain.

---

## 5. Minimal adaptation per useful idea

Each is one invariant, no new component, no new file.

**A1 (H4, direction 1).** `BOOT.md` states that `next_action` is the previous
session's pre-computed pick and is re-derived, not trusted, whenever the
validator cannot run; § 1.11 already owns the rule, BOOT only stops implying
the value is authoritative on its own.
*Files*: `saipen/BOOT.md`. *Check*: marker presence, red control.

**A2 (H2, direction 4).** Give VERIFY's cap the field REVIEW's cap already
has: `verify_attempts: N` on the ticket line, incremented per failed fix
cycle, checked against `verify.md`'s cap by `tools/validate.py`. Precedent,
grammar slot and enforcement pattern all already exist (`review_passes:`,
CONFORMANCE 132), so this is one entry in § 1.2's closed field list plus one
comparison.
*Files*: `saipen/RFC.md` § 1.2 field list, `phases/verify.md`,
`tools/validate.py`, `tools/audit_checks.py`. *Check*: a ticket over the cap
FAILs; a red control raises it past the cap.

**A3 (H1, direction 3).** Not scope locks -- a write-collision guard. § 1.5's
checkpoint already reads each file before writing it; require the writer to
compare the file's content against what it read immediately before the write,
and refuse the write on a difference rather than clobbering. Derived from
existing state, no new field, no daemon, and it is the one mechanism that
would have caught E-1863 at the moment of damage instead of an hour later.
Scope contracts stay where they belong: T-442..T-451 already own the v8 Crew
concurrency design and this must not pre-empt it.
*Files*: `saipen/RFC.md` § 1.5, `tools/validate.py` (advisory only).
*Check*: behavioral; a fixture can construct the read-then-clobber sequence.

**A4 (direction 5).** Two sentences in `phases/verify.md`: the ladder runs
cheapest-first, and the first failed *mandatory* gate ends the PASS claim --
no later green may restore it. Do NOT add per-gate evidence records or a
`highest_passed_gate` field; `| verify:` plus the LOG `RUN:` lines already
carry command and result, and a second ledger is the bureaucracy the brief
warns against.
*Files*: `phases/verify.md`. *Check*: marker presence.

**A5 (direction 6).** `phases/scout.md` already notes the harness; require
that the commands it finds are written once into `KNOWLEDGE/` and cited
thereafter, so executor and reviewer read the same line instead of each
guessing. Unresolvable -> `WAIT: blocked` naming the missing fact, which
§ 1.11 already requires.
*Files*: `phases/scout.md`, `phases/verify.md`. *Check*: marker presence.

**A6 (direction 7).** One clause in `phases/review.md`: REVIEW re-runs the
ticket's own `verify:` rather than reading BUILD's claim of it. No new agent
caste, no risk tiers, no ceremony -- the phase already exists and already has
a cap. This kills a class observed in this very session, where a VERIFY was
reported green and the audit harness was red.
*Files*: `phases/review.md`. *Check*: marker presence, red control.

---

## 6. Files and sections that would change

| Adaptation | Files |
|---|---|
| A1 | `saipen/BOOT.md` |
| A2 | `saipen/RFC.md` § 1.2 (closed field list), `saipen/phases/verify.md`, `tools/validate.py`, `tools/audit_checks.py`, `saipen/CONFORMANCE.md` |
| A3 | `saipen/RFC.md` § 1.5, `tools/validate.py`, `saipen/CONFORMANCE.md`, one `tests/scenarios/` fixture |
| A4 | `saipen/phases/verify.md`, `saipen/CONFORMANCE.md` |
| A5 | `saipen/phases/scout.md`, `saipen/phases/verify.md`, `saipen/CONFORMANCE.md` |
| A6 | `saipen/phases/review.md`, `tools/validate.py`, `tools/audit_checks.py`, `saipen/CONFORMANCE.md` |

No new markdown file is created by any of them. A2 is the only one that adds
a field, and it adds it to an existing closed list with an existing sibling.

---

## 7. Invariants and negative tests needed

- **A2**: `verify_attempts:` is an integer; absent means zero; only VERIFY
  writes it; the validator FAILs a ticket in `## TODO`/`## DOING` whose value
  is at or over `verify.md`'s cap without a `| blocker:`. Negative: raise the
  value past the cap -> FAIL. Negative: a non-integer -> FAIL.
- **A3**: a checkpoint write whose target changed since the read is refused.
  Negative: construct read -> foreign write -> write and assert the refusal.
  Negative: an unchanged file writes normally (the guard must not block the
  ordinary path).
- **A4/A5/A6**: marker presence in the phase doc, each with a red control that
  softens the MUST to a preference -- the pattern used for every rule landed
  this session.
- **A1**: BOOT carries the re-derivation sentence; red control removes it.
- Every one of the above also owes the rule this repository applies to itself:
  name the defect class it kills, or it does not get written (T-420).

---

## 8. Token cost and effect on an ordinary `saipen continue`

- A1, A4, A5, A6 are prose in files already read for their own phase. A1 adds
  ~2 lines to `BOOT.md`, which is the one file every cold start reads -- the
  only non-trivial cost here, and it is small against BOOT's current 130 lines.
- A2 adds one optional field to a ticket line. A board with it is a few bytes
  per affected ticket larger; `BOARD.md` is already the cold-start cost the
  soft cap watches, and this is noise against a 22 KB board.
- A3 changes what a writer does, not what a reader loads: zero added cold-start
  tokens.
- None of them adds a document, a phase, or a mandatory read. A bare
  `saipen continue` still reads STATE -> BOARD -> LOG tail and executes
  `next_action`.

---

## 9. Drift, duplication and bureaucracy risk

- **A2 is the highest-value, lowest-drift item**: it copies a mechanism that
  already exists one document over, so there is no new concept to keep in sync.
- **A3 is the highest-value, highest-care item.** It touches § 1.5, the
  checkpoint order every session runs. Written badly it either blocks ordinary
  writes or becomes advisory prose nobody can check. It also risks pre-empting
  the v8 Crew design (T-442..T-451): the guard must stay a collision *detector*,
  never a scope or locking scheme.
- **A4/A5/A6 risk restating rules that already exist elsewhere.** § 1.1 makes
  RFC normative and phase docs may tighten but never relax; each must cite
  rather than re-enumerate, or they become the fifth copy of a moving rule --
  the exact failure CONFORMANCE 58 exists to catch.
- **Rejected outright**: any per-gate evidence ledger, any `attempt`/
  `retry_after`/`failure_class` field set imported wholesale, any second state
  machine, any handoff record beside OUTBOX. Each duplicates a canonical place.
- The brief's own worst-case -- five chronicles of one expedition -- is the
  real risk here, and the defence is that five of the six adaptations add no
  storage at all.

---

## 10. Decision per direction

| # | Direction | Decision | One-line reason |
|---|---|---|---|
| 1 | Reconciliation over blind continue | **ADAPT (A1)** | Rule and checker exist; BOOT implies the pick is authoritative where the validator cannot run |
| 2 | Computed readiness predicate | **ADOPTED** | § 1.6 Pick Rule is already derived, ordered and negatively tested; no field to add |
| 3 | Scope and parallel conflict | **ADAPT (A3), narrow** | Take the collision *detector* only; scope contracts belong to the v8 Crew tickets, not here |
| 4 | Bounded retry / dead-letter | **ADAPT (A2)** for the countable cap; **DEFER** the terminal state to T-427; **REJECT** backoff timers | SAIPEN never schedules its own retries |
| 5 | Verification ladder | **ADAPT (A4)** ordering + stop rule; **REJECT** per-gate records | The record duplicates `verify:` and the LOG |
| 6 | Discoverable verification contract | **ADAPT (A5)** | `KNOWLEDGE/` is already defined as the place and is not being used for it |
| 7 | Generator/evaluator split | **ADAPT (A6)**, one clause | Phases already separate; only "do not trust the claim" is missing |
| 8 | Structured handoff | **REJECT** | OUTBOX + digest already canonical and richer |
| 9 | Explicit stopping conditions | **ADOPTED**; **DEFER** terminal marker | WAIT categories already make every stop machine-readable |
| 10 | Evidence and provenance | **ADOPTED** | Already ahead of the source on this axis |
| 11 | Bounded post-mortem | **DEFER** | LOG DEC -> `traps.md` -> CONFORMANCE row is the pipeline; T-420 is the gate on new prose |

---

## Recommended order if approved

1. **A2** -- self-contained, has a working precedent, closes a witnessed hole.
2. **A6** -- one clause, kills a class this session demonstrated.
3. **A4**, **A5**, **A1** -- prose plus markers, cheap, low risk.
4. **A3** -- last, deliberately: it touches the checkpoint path every session
   runs, and it should be designed against T-442..T-451 rather than ahead of
   them.

Nothing above is a ticket yet. Awaiting the go/no-go per line.
