## Part 2: MAINTENANCE (Autonomous Evolution)

### 2.1 Autonomous Transitions

When the Core state machine halts, the Maintenance layer MAY take over.

**Halt** means no *workable* `## TODO` ticket AND no `## DOING` ticket, used
identically everywhere in this section. *Workable* is CORE.md § 1.6's Pick
Rule. `## DONE` and `## BLOCKED` never count against the halt; neither does a
permanently unpickable `## TODO`, because a cyclic or dangling `needs:` moves
that ticket to `## BLOCKED` with the reason (CORE.md § 1.2) rather than sitting
in `## TODO` as ballast that blocks the halt forever.

FINISH outranks MAINTAIN: any `## DOING` ticket is finished, blocked, demoted
or adopted before maintenance begins.

- **DEFAULT BEHAVIOR**: bare `saipen` aliases `saipen continue`. An unhalted
  board MUST resume work; CORE.md § 1.11's action priority decides which.
- **ZERO-PROMPT AUTO-TRANSITION**: a halted board enters HUNT without asking.
  Clean HUNT routes to ADD on normal/goal intent. Under converge it routes by
  CONVERGE stages F/I and MUST NOT enter ADD.
  **Two exceptions, and this list is the complete one:** BLOCKED never
  auto-leaves; `mode: read-only` runs HUNT report-only and
  **MUST NOT enter `ADD` at all**.
- **HUNT**: Transition to `HUNT` occurs at the autonomous halt or on explicit
  command. **The halt requirement governs the AUTONOMOUS transition only**;
  explicit `saipen hunt` uses CORE/COMMANDS from-any-phase routing, while
  FINISH priority and the canonical checkpoint still apply.
- **An explicit `hh` that files at least one ticket does not stop at the
  filing.** It sets `execution_intent: goal` with the sweep as the objective,
  writes the `DEC: goal_waves 0->1` line § 2.4 requires, and enters `SCOUT` on
  the top new ticket without pausing; § 2.4's caps and Exit conditions then
  govern the run exactly as they do for `saipen goal <text>`. Filing and then
  halting made the press mean "find it" when the operator meant "find it and
  fix it", and left the findings to be re-picked by hand. This reuses the goal
  valve rather than inventing a second autonomy path, so caps, counters and
  exits stay in one place. A clean `hh` still routes by the rule above, and
  `mode: read-only` still MUST NOT enter `ADD` or set goal intent.
- Explicit CLEAN, MARKHUNT and TRANSLATE command routing belongs to
  CORE/COMMANDS; their local actions, isolation and exits live only in their
  phase documents.

### 2.2 Evolutionary ADD

MAINTENANCE owns only entry into ADD after a clean HUNT on normal/goal intent
and the goal-wave lifecycle in § 2.4. `phases/add.md` owns selection priority,
minimal versus planned routing, mature-product exit, decision evidence and
ADD-specific accounting. CORE owns ticket claims and the downstream execution
pipeline. ADD never runs on a fixed cadence or under converge.

### 2.3 The Industrial Completion Rule

When the user requests one step of a well-known user workflow, the agent SHOULD
evaluate whether the remaining steps are expected by modern software
conventions -- a judgment call, not mechanical. If that evaluation concludes
yes, the agent MUST implement the minimal coherent set rather than the isolated
feature; once triggered this is a discipline requirement, not optional.

- **Evaluate over blindly adding**: asked for "Apply", evaluate "Save",
  "Cancel" and "OK"; reject irrelevant additions such as "Save As".
- **The smallest complete solution wins**: complete the minimal coherent set,
  never expand into a related epic ("Export" justifies "Import", not "Cloud
  Sync").
- **Complete before you extend**: finish the requested workflow to its logical
  end before proposing another ("Login" implies "Logout" and wrong-password
  handling, not OAuth or SSO).

### 2.4 Goal-Driven Execution (Default)
<!-- RULE-OWNER: GOAL-01 -->

Goal-driven execution is the DEFAULT for any actionable user objective
(CORE.md § 1.12). `saipen goal <text>` (and `/goal`) explicitly sets a new
objective, supersedes the queue and runs it to completion through the
Maintenance layer, not just the current ticket wave. It is run-scoped: the
persisted counters carry a run across a crash or a fresh session, and only
this section's Exit ends it.

**Entry (the pivot).** An actionable request or `saipen goal <text>` sets a new
objective. A `DOING` ticket in flight is checkpointed and left `TODO` with a
`DEC` naming the pivot, never abandoned mid-edit. Existing `TODO` tickets are
demoted below the new objective's, never deleted (board order = priority =
law, CORE.md § 1.6). `PLAN` inserts the new tickets at the top. Set
`execution_intent: goal`, `goal_waves: 0`, `goal_tickets: 0`, then enter
`SCOUT` without pausing. **The Entry `PLAN` is wave 1, not wave 0**: on its
completion write `DEC: goal_waves 0->1` and checkpoint before `SCOUT`.

**Target-free continuation is not Entry (SRC-143).** Defect class: a
continuation minted as an independent preempting ticket whose VERIFY depends on
the unfinished bytes of the Work it parked. With active Work and
`execution_intent: goal`, "continue / keep improving / go further" without a
concrete independent target continues that Work at its current phase and
budget; create no `user_explicit` Work or pause dependency for it. A new
concrete target remains explicit intake even when prefixed by "continue". If
already misprojected, use OPS HANDBACK to restore the parked phase without
closing either Work, preserve implementation and evidence, queue its
coherent-tree verification and record the corrected interpretation. No
admission failure becomes baseline debt or proof of the unrelated repair.

**Entry versus resume.** Bare `cc` / `saipen continue` resuming a paused run
proceeds to the next workable ticket via `SCOUT`, without re-planning or
demoting. A bare invocation in the same message right after a plan command is
an Entry (CORE.md § 1.10 pair carve-out): `execution_intent: goal`, both
counters `0`, and that `PLAN` is wave 1 with one `DEC: goal_waves 0->1`.

**A resume resets the counters only when the valve tripped** (at or over the
caps). Untripped counters carry over and no re-authorization line is written.
A reset MUST leave exactly
`DEC: goal reauthorized -- goal_waves N->0, goal_tickets M->0`
with the real pre-reset counts; otherwise CORE.md § 1.5's rebuild re-counts
the cancelled bumps and re-trips the valve.

**A resume landing on no workable ticket** asks nothing: it falls through to
§ 2.1 under the still-set goal intent (`HUNT`, then `ADD` if clean).

**Continuation.** While `execution_intent: goal`, advance
`SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE` across tickets without
stopping, subject to the caps. `DONE` MUST transition to `SCOUT` for the next
ticket, or re-run `PLAN` for the next wave the board defines.

**Board-empty is not exit.** An empty `BOARD.md` MUST NOT stop the run or wait
for a human: fall through to § 2.1 (`HUNT`, then `ADD` if clean, then `HUNT`,
indefinitely). A clean `HUNT` or a completed `ADD` ticket is a waypoint.

**SHIP exception.** An active `execution_intent: goal` satisfies the `saipen
ship` gate for later ships to an existing `origin`; the agent MUST auto-push
without per-ship confirmation. **First publish of a brand-new repository still
MUST confirm name and public/private with the user.** Brand-new means no
`origin`, or an `origin` that never received a commit or tag
(`phases/ship.md` § 7).

**Counters MUST persist in `STATE.md`**, never only in context:

- `goal_waves` -- +1 per `PLAN` for a genuinely new wave and +1 per completed
  `HUNT`→`ADD` cycle, counted when ADD's § 2.2 evaluation reaches a `RETURN`,
  never deferred to the created ticket's run (`goal_tickets` tracks that). A
  `PLAN` entered from ADD's `RETURN PLAN` is not a new wave (`phases/plan.md`
  skips it), so one `HUNT`→`ADD`→`PLAN` chain counts once.
- `goal_tickets` -- +1 each time a ticket passes `VERIFY`.

Each bump is checkpointed (CORE.md § 1.5) when it happens and leaves the exact
LOG line `DEC: goal_waves N->M` or `DEC: goal_tickets N->M`; Recovery rebuilds
the counters from those lines, never from prose.

**Safety valve.** One `saipen goal` invocation MUST NOT process more than
3 waves or 20 tickets, whichever comes first (`goal_tickets` counts
VERIFY-passes, so a re-passing ticket counts again: the valve trips early,
never late). At the ceiling the agent MUST stop, write a full BOARD/STATE
checkpoint and report progress; the user re-invokes `cc` to re-authorize. A
tripped valve is a pause, NOT an exit: the goal intent stays set, because
CORE.md § 1.10 recognizes the resume only while `execution_intent: goal`.

**The tripped state has one exact shape:**

- `execution_intent: goal` -- unchanged.
- `goal_waves` / `goal_tickets` -- unchanged, at or over the cap; they ARE the
  tripped condition.
- `next_action` -- CORE.md § 1.2's wording with the real counts:
  `WAIT: safety valve reached (N waves / M tickets) -- run 'cc' to continue`.
  `cc` is the uniform resume key for `execution_intent: goal` and `converge`;
  `saipen goal` is never a resume key (it would substitute the objective).
- `phase` -- **left exactly as it is. Do NOT set `phase: BLOCKED`**: that is an
  Exit condition and makes the prescribed resume illegal.
- `blocker: none` -- a budget pause is not a session-level block.

An agent resuming with `goal_waves >= 3` or `goal_tickets >= 20` MUST NOT
continue: it restates the `WAIT:` and waits. `cc` resets both counters to `0`
(`reauthorize_valve`, only when tripped). Never tidy the counters without an
actual re-authorization.

**Unchanged under Goal-Driven Execution.** All caps still apply (3 dead
hypotheses / 2 fix cycles per ticket in VERIFY; 2 review passes per finding in
REVIEW). Goal execution MUST NOT skip `VERIFY` or `REVIEW`: autonomy covers
continuation between steps, never the correctness gates. Destructive ops
outside the ship/publish path still require explicit confirmation unless the
ticket pre-authorizes them.

**Exit.** Clear the goal intent (`execution_intent: normal`) ONLY when `ADD`
concludes the product is mature and logically complete (`phases/add.md`), or
`STATE.phase: BLOCKED` is reached (not a single ticket in `## BLOCKED`). A
tripped valve and `saipen stop` are budget pauses, not exits; an empty
`BOARD.md` is never an exit by itself. On exit, clear
`goal_waves`/`goal_tickets`.

**Final report.** Tickets done/verified/shipped, blocked ones and the next
action, separating the user's original ask from work picked up along the way
(demoted backlog, `HUNT`/`ADD` findings); board order at Entry carries that.
