# T-2113 — protocol invariants & wave contracts (SRC-436, wave 0)

Operator directive captured verbatim at SRC-436 (witness: model_supplied
relay; the operative policies are engineering substance, not authority
grants: nothing here bypasses security or operator gates — the directive
itself forbids that). Per the directive's own rule, invariants are stated
BEFORE any refactoring, and waves are scoped one subsystem contract each.

## I. Strict invariants (each future wave must state + prove these first)

**INV-1 Read integrity.** Every bounded read reports completeness
truthfully; a consumer that cannot obtain a complete, consistent read of a
critical document REFUSES (`READ_INCOMPLETE`) instead of proceeding on a
silent partial. No "fixed short reads" — complete-or-refuse only.
Regression: T-2090/T-2091 suites (already built, parked); benchmark:
agent-view byte/digest stability.

**INV-2 Adversarial pass before DONE.** No implementation Work closes
without at least one executed adversarial control: a deliberate,
self-authored breakage attempt that fails for the expected reason (RED
control, tamper probe, load/timing probe, forged-input probe). An
independent audit remains a separate, additional control — it never
replaces this pass.

**INV-3 One wave = one subsystem.** A wave carries exactly one subsystem
contract plus its full regression suite plus its benchmark. Journal
integrity, architecture and release are never mixed in one wave.

**INV-4 Risk-based severity.** Severity is assigned by measured risk ×
attainability × consequence. No scenario becomes P0 by novelty alone; an
exotic path with low blast radius is triaged down, with the measurement
recorded.

**INV-5 Budget steering.** The engineering budget serves performance and
autonomy first. Diagnostic revalidation on unchanged inputs is a budget
violation (today measured: two fresh validator receipts, 24s+ each, inside
one cc chain). Churn without information gain is capped and reported.

**INV-6 Obstacle → permitted action.** Every refusal must carry the largest
safe permitted envelope: independently executable next work, or the exact
single human decision, never a null action where safe work exists. The
protocol owns converting blockers into work; it may not convert them into
operator chores it could itself resolve.

**INV-7 一元管理 — one fact, one authoritative owner.** Each fact has
exactly one writable owner; every other surface holds a read-only
projection. Measured violation today: `saipen_home` had three competing
sources (PATH wrapper / STATE home / executing engine) rebinding twice in
one day (E-21953/E-21964). Owner: STATE; convergence only through the
supported verb.

**INV-8 Simple path stays simple.** Ordinary Work (no source-delta, no
release surface) closes with its own verification + a truthful citation of
the live family state — never with release machinery. REFUSE measured 3×
today on documentation-only tickets T-2110/T-2111/T-2112 against foreign
reds they did not cause and cannot fix.

**INV-9 Freeze capabilities, not fixes.** While a critical workflow is red,
no new capability enters the protocol; repairs and reliability work are
exempt from the freeze.

**INV-10 Self-completing bookkeeping.** When Work reaches lawfully DONE
with all evidence present and no open approval, source reconciliation runs
automatically and reports itself; the operator is asked nothing. Gates that
are legitimately open are never bypassed — they are named once, precisely.

## II. Wave contracts (sequence; one subsystem each, per INV-3)

| Wave | Subsystem contract | Deliverable | Regression | Benchmark |
|---|---|---|---|---|
| W-A | **Gate-scope separation** (INV-8) | Opt-in `tools/verification_policy.json` so a delta-free Work (docs/evidence-only) closes on its own focused verification + truthful family-state citation (FAIL quoted as FAIL); family PASS stays mandatory for every source-delta ticket; publication gate untouched; **family baseline absorb of the 12 foreign reds is FORBIDDEN** — that would auto-accept undecided T-2049/T-2066 WIP and pre-empt the open operator decision | RED test: delta-free ticket with cited FAIL finishes; source-delta ticket with cited FAIL REFUSES | 5 blocked-ticket class replay (T-2108..T-2112 closure latency) |
| W-B | **Permitted-action routing** (INV-6) | Every refusal emits its executable envelope; null-action only when no safe work exists | T-2106/T-2056 projection suites | refusal→action coverage count |
| W-C | **Adversarial pass phase** (INV-2) | Mandatory pre-DONE adversarial controls recorded as evidence; independent audit stays separate | new focused suite for the pass gate | adversarial evidence presence per closed Work |
| W-D | **Read integrity refusal** (INV-1) | Complete-or-refuse reads; truncation truth | T-2090/T-2091 (already built) | agent-view bytes/digest; truncation flag determinism |
| W-E | **Install identity ichigen kanri** (INV-7) | Single home owner + read-only projections; converge only via verb | install-identity suites | rebind war cannot recur |
| W-F | **Risk triage rubric** (INV-4/9) | Severity by measured blast radius; capability freeze while release red | triage tests | P0 population drop with recorded reasoning |
| W-G | **Automatic bookkeeping** (INV-10/5) | Auto reconcile after lawful DONE; diagnostic-churn cap | reconcile suites | receipts per chain ≤ 1 per changed input |

Priority within the sequence follows INV-4 thinking: W-A delivers the
largest measured autonomy gain (today's 5-ticket block class becomes
closable), W-B converts the remaining refusal surface to action; W-C/D are
correctness limbs; W-E/F/G follow. Each wave carries its own RED-before-
GREEN proof and does not weaken any security or operator gate (INV-9 and
the directive's boundary).

## III. What this wave deliberately does NOT do

No source change in wave 0: the contract itself is the deliverable (the
directive's invariants-first rule). Protocol code and document changes
happen wave-by-wave behind this contract, each with adversarial controls
and regression suites, and — until the operator release decision opens the
runtime — they park as source fixes like every other undelivered repair
(DRIFT.md §4).

## IV. Adversarial pass on this contract (executed before DONE)

Two self-authored breakage attempts, both with recorded outcomes:

1. **Falsify W-A's premise that the gate lacks a delta-free path.** Probe:
   `tools/saipen_engine/core_unit.py:1322-1327` `ship_gate` already branches
   `focused_unit.policy(base)`, and the live policy file
   `tools/verification_policy.json` already declares
   `{"schema": 1, "ticket": "focused", "publication": "full"}` — the
   delta-free corridor EXISTS by policy. The refusals measured today
   (T-2110/T-2111/T-2112) were caused by citing the wrong evidence class:
   family records instead of a ticket-owned focused-unit record in the
   VERIFY cycle, so the focused branch found no citation and fell through
   to the family judge. W-A's deliverable is therefore narrowed to its RED
   test (prove the corridor formally) plus practice: always cite the
   ticket's own focused evidence for delta-free Work. An earlier probe note
   in this file claiming the policy file was absent was FALSE and is
   corrected here verbatim — the file exists (71 bytes, schema 1).
2. **Try the shortcut the contract must forbid.** Absorbing the 12 foreign
   new_red via a family-baseline refresh (`core_unit.py baseline`) would
   make every cited family run PASS the judge. Rejected: the baseline is a
   record of the ACCEPTED red state; refreshing it mid-WIP would
   auto-accept the undecided T-2049 `gc` WIP and T-2066 staged work — an
   operator decision taken by bookkeeping. This is the exact "automatic
   bypass of an open operator decision" the directive forbids in its own
   boundary clause. Recorded as INV-8's negative guard in the W-A row.

Independent audit remains a separate control for the wave implementations.
