SAIPEN

# FUTURE GATE — OPER-SHARE AUTHOR IDEAS

STATUS: PROPOSAL / DEFERRED UNTIL THE ELIGIBILITY GATE BELOW HOLDS
PRIORITY: P3 PROTOCOL QUALITY
OWNER: SAIPEN protocol
SOURCE: SRC-109 (operator request, 2026-09-23): take inspiration from this
author's system and fold it into SAIPEN as a future gate, once SAIPEN itself
is whole enough. Ticket T-1477, slice of T-1471.
STUDIED: `v:/___VAC/__K/__CODE/___GIT_HUB/oper-share` on 2026-09-24 —
README.md, AGENTS.md, BIRTH.md, BOOT.md, MANIFEST.md, SKILLS.md, all of
`docs/` (Principles, Governance, Code, Data-Safety, Version-Control,
Working-Base, Autonomy-Charter, Skills, KB-RAG and Infrastructure by section),
`knowledge/INDEX.md` with selected findings and wiki lessons, `_memory/INDEX.md`,
and the skills most related to protocol work (relevance-scan, autorun,
loops/autonomous-work, tool-claims-verification, fable-judge, discipline
parts). The 97-skill catalog was read at index level only.

## Provenance and licence

oper-share ("Oper") is a CC BY 4.0 package: a coding-agent constitution
(`AGENTS.md` plus normative `docs/`) and a skill library. Not every file in it
is the Oper author's own work: `fable-judge`, `fable-method` and several
`discipline` parts carry a third-party source credit (a Telegram channel).
Ideas taken from those files are attributed to that source below, not to the
Oper author. This document quotes only short phrases; nothing is copied.

## Why this is a future gate and not Work

SAIPEN is mid-hardening: the T-1446 24-hour field gate is running, five
isolated candidates wait for integration behind it, and protocol markdown
sits at 306917 of its 307200-byte cap (T-1503 is recovering about 5 KB). Adopting new rules now would compete
with correctness Work for the same seat and the same bytes. The operator's own
condition — "when SAIPEN itself is whole enough" — is made mechanical in the
next section.

## Eligibility gate (all must hold before any idea below becomes a ticket)

1. **Field gate met.** T-1446 is DONE: its `report.json` shows 86400 s of
   wall time and every SRC-100 / SRC-105 / SRC-106 quality counter at zero.
2. **Core-unit proof is cheap.** T-1344 / T-1472 hold: the declared family
   runs in materially less than the 2254 s measured at af93fd56, and its red
   set is no larger than `tools/core_unit_baseline.json`. (The 2026-09-24
   worktree run took 1818 s.)
3. **No open P1.** BOARD carries no P1 in DOING or TODO, blocked ones
   included. Today this fails on T-1375 (WAIT_USER_DECISION) and T-1431,
   among others.
4. **Budget headroom exists.** Each adopted idea names its protocol-markdown
   byte cost and where the bytes come from. The cap is not raised to admit it.
5. **It beats doing nothing.** Each idea is adopted only with a measured
   incident it would have prevented (CORE §1.1: prose that names no defect
   class is not written). "Doing nothing" is always a valid outcome.

When the gate holds, each **Candidate** below becomes one ticket through
`saipen ticket add`, never a batch umbrella.

## Ideas

Verdicts: **Candidate** (adopt when eligible), **Measure first** (adopt only
if a measurement shows the defect exists here), **Already owned** (SAIPEN has
it; recorded so nobody re-imports it), **Rejected**.

### 1. Premise check before execution — Candidate

- **Source:** `AGENTS.md`, "Saniti-Check"; skill `relevance-scan`.
- **Idea:** before executing any plan, ask the outside-view question — would
  someone new to this workspace grab an existing tool, or skip the work? The
  check targets the premise, not plan quality: "the more polished the plan,
  the more important the check."
- **SAIPEN today:** SCOUT reads KNOWLEDGE and one neighbour; BUILD has a reuse
  ladder (project, stdlib, dependency, new). Neither asks whether the Work
  should exist at all, or whether an existing SAIPEN owner already covers it.
- **New:** one mandatory clause in the SCOUT LOG line — `premise: <existing
  owner or tool that covers this | none found>`. No new phase.
- **Defect class killed:** a well-formed ticket executed on a rotten premise
  (a parallel owner reinvented; T-1348 was superseded after measurement showed
  its own verify clause asked for the wrong trade).
- **Cost:** about 150 bytes in `phases/scout.md`.

### 2. Weakened-check detection in VERIFY — Candidate

- **Source:** skill `fable-judge` (third-party credit), "Hunt the classic
  frauds": loosened or deleted assertions, skipped tests, real calls replaced
  by mocks — "a changed test is guilty until its justification traces to a
  spec."
- **SAIPEN today:** VERIFY re-runs gates; core-unit evidence binds a tree
  fingerprint and refuses red outside the baseline. Nothing inspects whether
  the tests themselves were made weaker in the same Work.
- **New:** a mechanical VERIFY check over the ticket's diff of `tools/test_*`
  and `tests/`: removed `assert*` calls, added `skip`/`expectedFailure`,
  widened tolerances. Any hit requires a DEC naming the spec that justifies it.
- **Defect class killed:** green-by-weakening — a gate that passes because
  the check was loosened, not because the code was fixed.
- **Cost:** engine code and a validator control; small protocol text.

### 3. Owned processes and worktrees are cleaned up — Candidate

- **Source:** `docs/Code.md`, "Processes & Cleanup": anything launched is
  owned "until cleanup is verified"; know how to stop before starting.
- **SAIPEN today:** the supervisor owns worker leases, and a blocker names a
  live driver PID. Isolated git worktrees created for Work have no owner
  record and no cleanup step.
- **Measured 2026-09-24:** `git worktree list` showed eight scratch worktrees
  left by ended sessions (wt1383, wt1460, wt1472, wt1478, wt1487, wt1489,
  wt1490, wt1504; wt1460 already `prunable`), besides five live
  `_SAIPEN_WORK_` ones.
- **New:** a worktree created for a ticket is recorded against it; DONE or
  CLEAN removes worktrees whose ticket is terminal, after checking they carry
  no unintegrated diff.
- **Defect class killed:** resource leaks that also make "which candidate is
  current" ambiguous (two T-1487 worktrees existed today, at different bases).
- **Cost:** engine code in the checkpoint/CLEAN path; a short CLEAN step.

### 4. Operator decisions carry self-contained options — Candidate

- **Source:** `AGENTS.md`, Task Cycle step 6, "Self-contained options": each
  option says what the thing is, why it exists, and the concrete cost of the
  drastic choice; the owner "must never have to answer 'what is this even?'
  before voting."
- **SAIPEN today:** EXEC-RESPONSE-01 requires an OPERATOR ACTION field, and a
  WAIT without one is invalid. The stored and projected WAIT text is not
  required to carry the options.
- **Measured 2026-09-24:** T-1375's blocker as projected by BOARD and
  `saipen continue` ends in "...", and the options A/B/C live only in LOG
  detail E-8913. The operator sees a decision request without the choices.
- **New:** a WAIT_USER_DECISION blocker must carry each option in one line
  (label, effect, cost) within the projection bound, or the block is refused.
- **Defect class killed:** unanswerable operator decisions — the human has to
  investigate LOG detail files to learn what they are being asked.
- **Cost:** a validator rule plus about 200 bytes in EXECUTION.md.

### 5. Long gates are estimated and handed over — Candidate

- **Source:** `docs/Code.md`, "Heavy Commands": estimate before running; over
  five minutes, hand over with exact command, cwd, expected duration, stop
  command and what to paste back.
- **SAIPEN today:** bounded timeouts exist; T-1449 blocked because the family
  "exceeded bounded 600-second window without verdict". SRC-108 (T-1471) asks
  for execution-time telemetry.
- **New:** before a declared gate runs, the agent states its expected
  duration from the last recorded run; a run that cannot fit its window is
  started in the background with a completion watch instead of a blocking
  call that times out.
- **Defect class killed:** gates that consume their window and return no
  verdict, which is paid for and proves nothing.
- **Cost:** folds into the SRC-108 telemetry Work; no separate owner.

### 6. Dated claims about live state decay — Candidate

- **Source:** `docs/Infrastructure.md`, "Freshness of Claims" and
  "Verification Labels" (VERIFIED-LIVE, TOOL-SURFACE, CONFIGURED,
  FAILED-LIVE): "a configuration entry never proves live health"; a label
  older than a month means one cheap probe before relying on it.
- **SAIPEN today:** BOOT treats a stale KNOWLEDGE INDEX as non-authority, and
  runtime capabilities are probed. Individual KNOWLEDGE cards that describe
  external or host state carry no verification date.
- **New:** cards that assert live external state carry `verified_at` and a
  label; retrieval marks cards past a decay horizon as needing a probe.
- **Defect class killed:** a months-old card about a host, tool or model
  endpoint read as current truth.
- **Cost:** belongs inside `FUTURE GATE — VERIFIED SHARED KNOWLEDGE
  LAYER_20260910_0607.md`; adopt there, not as a second owner.

### 7. Destructive refusals name a reversible route — Candidate

- **Source:** `docs/Data-Safety.md` and `AGENTS.md`, "Never Destroy —
  Trash-Only": deletion is a move to a recycle location.
- **SAIPEN today:** CORE requires authority for destructive effects, and the
  guard resolves the effects of shell commands and refuses. The refusal does
  not name a reversible alternative.
- **New:** a destructive-effect refusal names the reversible route (move to a
  project-local trash under `.saipen/`, or `git checkout` for tracked files).
  SAIPEN's authority model stays; the absolute "never delete" does not come in.
- **Defect class killed:** after a refusal, an agent hunting for a spelling
  the guard does not recognise, instead of taking the safe route.
- **Cost:** guard message text and one control.

### 8. Decisions record the rejected alternative — Candidate

- **Source:** `docs/Code.md` ("Decision Matrix … at least three viable
  alternatives"); `AGENTS.md` Task Cycle step 10; discipline part
  `changelog-discipline` (third-party credit): "A rejected alternative is
  gold."
- **SAIPEN today:** DEC lines record decisions; ADRs in KNOWLEDGE record some
  alternatives. A DEC need not name what was rejected.
- **New:** a DEC for a design choice ends with `rejected: <alternative> —
  <reason>`, the way T-1375 recorded A/B/C. Convention first; a check only if
  re-litigation is measured.
- **Defect class killed:** a later session "improving" back to a path that
  was already tried and rejected.
- **Cost:** about 120 bytes in CORE's LOG taxonomy text.

### 9. Onboarding probes first and closes on an explicit word — Candidate

- **Source:** `BIRTH.md`: probe the machine yourself, then confirm ("I see
  Windows + git + python 3.12, no node — correct?"); the interview closes only
  on an explicit "enough", never when the agent's question list runs out; the
  file deletes itself in the first personalised commit.
- **SAIPEN today:** INIT phase, USERPERSON, and `FUTURE GATE — GREENFIELD
  BIRTH HAS NO MECHANICAL OPERATION_20260917.md`.
- **New:** probe-then-confirm environment facts into RUNTIME/USERPERSON, and
  an explicit operator close for the preference interview.
- **Defect class killed:** questions the agent could have answered by probing;
  USERPERSON left empty or guessed.
- **Cost:** adopt inside the GREENFIELD BIRTH gate, not as a new owner.

### 10. Two field traps for KNOWLEDGE — Candidate

- **Source:** `docs/Code.md`, "Field Traps": each trap recurred in practice
  before it was promoted.
- **SAIPEN today:** `.saipen/KNOWLEDGE/traps.md` owns project traps. BOOT
  already owns "search tool error is not zero matches"; the heredoc backslash
  trap is known.
- **New:** two traps not yet recorded — a pipeline's exit status is the last
  command's (`grep x | head; echo $?` reports `head`), and an `&&` chain in a
  verification script stops silently at the first non-zero, so later checks
  never ran while the run "looks green".
- **Defect class killed:** verification evidence that reports checks which
  did not execute.
- **Cost:** KNOWLEDGE only, no protocol bytes.

### 11. Evidence level on every claim — Measure first

- **Source:** `docs/Principles.md`, "Evidence levels": Verified, Observed,
  Derived, Assumed; "'Works' only means Verified."
- **SAIPEN today:** SAICRITIC and IMPROVE use proof levels for findings;
  closure evidence is mechanical. Checkpoint prose is free text.
- **Measure:** sample LOG RUN lines for PASS claims with no cited command or
  evidence path. Adopt a validator rule only if such lines exist after the
  current evidence rules.

### 12. Stop transparency — Measure first

- **Source:** `AGENTS.md`, "Stop transparency": name the file, quote the exact
  line, separate the file's demand from the agent's interpretation.
- **SAIPEN today:** mechanical refusals carry a code and a canonical next
  command. Agent-authored stops in prose are not required to cite a rule ID.
- **Measure:** count stops that cite no rule ID. Adopt only on evidence.

### 13. Dead pointers die with their target — Measure first

- **Source:** `docs/Governance.md`, "Pointers die with their target", checked
  by a docs-route validator.
- **SAIPEN today:** `tools/validate.py` checks cross-document drift, registry
  owners and the manifest. Whether every path named in protocol prose,
  KNOWLEDGE and `future_gate/` resolves is not known to be checked.
- **Measure:** one scan for dead repository paths in those trees.

### Already owned — recorded so they are not re-imported

- **One priority ladder, one absolute** (`AGENTS.md`, `docs/Governance.md`):
  EXECUTION's `user/safety/CORE > execution policy > STYLE` and INDEX's
  one-owner rule.
- **Source-of-truth graph** (`docs/Infrastructure.md`): BOOT "files outrank
  model memory", SOURCE-AUTHORITY-01, REGISTRY.json.
- **Parity board for parallel agents** (`docs/Autonomy-Charter.md` §1):
  BOARD claims with owner, claim_time and lease; FOREIGN_STALE matches "stale
  entries do not block". SAIPEN's lease is mechanical and stronger.
- **Run is the default; defer by importance and switch work**
  (Autonomy-Charter §2–§5): GOAL-01, PICK-01, ticket-scoped blocks with
  continued picking (exercised on 2026-09-24).
- **Truthfulness contract / "No Fake Completeness"** (`docs/Principles.md`):
  HABITS, VERIFY, closure provenance.
- **Verify with different eyes** (`docs/Code.md`): SAICRITIC and critic seats.
- **Index freshness in the same change** (`AGENTS.md`): generated KNOWLEDGE
  INDEX with stale-index fallback.
- **Push scope** (`docs/Version-Control.md`): `saipen push` / ship gates and
  first-publish confirmation.
- **Voice bans** (`AGENTS.md`, Language & Voice): STYLE anti-drift sentinels.

### Rejected

- **Full trade-off order** (`docs/Principles.md`: correctness, truthfulness,
  safety, understanding, completeness, simplicity, …): SAIPEN's QUALITY > TIME
  covers every conflict measured so far; a ten-rank list adds bytes without a
  measured defect.
- **§-prefixed append-only memory lines** (skill `autorun`): SAIPEN's LOG and
  KNOWLEDGE are already the canonical memory with a validator.
- **Skill-layer router and parts shape** (`docs/Skills.md`): valuable for a
  97-skill library; SAIPEN's subSaipens and single skill package have no pile
  to prune. Revisit only if extensions pass about five per topic.
- **Absolute trash-only rule** (`docs/Data-Safety.md`): SAIPEN decides
  destructive effects through authority, not a blanket ban; idea 7 keeps the
  useful part.

## Verification of this document

SRC-109:R001 is settled by this file's existence with the per-idea mapping
and the eligibility gate above. No protocol or engine change was made for it.
