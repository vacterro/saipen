# Decisions

- Protocol/personality split (v2.0.0): SKILL.md = cold workflow, STYLE.md =
  voices, UI.md = theme. Reason: long mixed prompts drift - every extra
  personality rule lowers compliance with workflow rules. Load STYLE with
  SKILL; UI only for UI work.
- Phases PLAN->SCOUT->BUILD->VERIFY->REVIEW->SHIP (v2.0.0): SCOUT mandatory
  before BUILD (most agent errors = invented architecture instead of read);
  VERIFY (works?) split from REVIEW (well made?).
- KNOWLEDGE/ over fat LOG (v2.0.0): LOG = time-ordered journal only;
  durable truth lives in architecture/conventions/decisions/traps files.
- FreeBuff-class readers (~/.agents/skills): need lowercase dir + real copy,
  skip junctions and uppercase names. Injector copies, never links there.
- v2.1.0 accepted from review: confidence on verified tickets, graph mode
  over needs: DAG, KNOWLEDGE index rule, status metrics. REJECTED for now:
  agents/ manifest files and .vac/metrics.md file (both belong to a future
  external Python orchestrator, not to the skill - LLM-maintained metrics
  files drift into fiction). Next evolution direction: small orchestrator
  reading BOARD needs: DAG and dispatching agents; SKILL.md then becomes
  the worker contract, not the top document.

- 2-tier protocol (v5.0.0): saipen/RFC.md = dense boot loader (~110 lines,
  ~1,200 tokens). Phase rules live in `phases/*.md`, loaded on demand per STATE.phase. Reason: monolithic v4 loaded 240 lines (~3k
  tokens) every cold start even when 80% was irrelevant. Now BUILD session
  never parses SHIP rules. Inspired by caveman skill's single-sentence
  calibration: lead with state machine, not positioning text.
- `goal_exit: objective | mature` REJECTED, asked three separate times
  (initial decision, re-raised in T-003/v7.13.0, second confirmation in
  v7.13.1): `goal_mode` never exits on a momentarily empty `BOARD.md` --
  that's a waypoint, not a stopping point (RFC § 2.4). Grounded in a real
  stall trace where early-exit-on-empty caused a premature stop. Do not
  re-propose without new evidence (a real trace showing current behavior
  actually causing a problem) -- the bar the original fix cleared. Full
  history: CHANGELOG.md 7.10.0/7.11.2/7.13.0/7.13.1.
- Phase COLLAPSE (16 -> 5/8/4) REJECTED, proposed three ways at once
  (`tofix/saipen_phaseAudit1/2/3`, reviewed at v7.53.0) -- and no two agreed
  on the target count, itself a tell that the "right" factoring is taste,
  not a defect. Grounds: **(1)** the token premise is already solved by the
  2-tier lazy-load above (v5.0.0) -- a phase doc costs nothing until its
  phase is active, so 16 small focused docs beat 8 fat merged ones;
  phaseAudit2 admits this outright (merging hunt+add+markhunt makes every
  `hunt` call also load add+markhunt). Collapsing raises per-call tokens, it
  doesn't lower them. **(2)** The specific merges undo deliberate splits
  recorded above: `scout` is separate from `build` because agents invent
  architecture instead of reading; `VERIFY` ("works?") is separate from
  `REVIEW` ("well made?") on purpose. **(3)** `done`/`blocked` are already
  thin; `markhunt` (dry + uncapped), `add` (§2.2 eval + goal_waves),
  `validate` (runs any time, not just init), `prepare` (handoff freshness),
  `translate` (isolated 32-lang sandbox) each carry a distinct trigger and
  cap that a merge muddies. **(4)** The rewrite surface -- RFC §1.6 enum +
  transition table, CONFORMANCE enum + 33 scenario rows, `tools/validate.py`,
  `state.schema.json`, the subs PROTOCOL that reuses the phase enum, all 33
  guides -- is enormous, and re-opens 100+ versions of phase-specific
  hardening (VERIFY hysteresis, the ADD->HUNT and DONE->ADD phantom removals)
  for an illusory-to-negative token gain. Do not re-propose without a real
  trace showing the current phase count actually costing tokens or causing a
  stall -- the same evidence bar `goal_exit` must clear. (Legit grain taken:
  keep each phase doc individually tight; that is a size discipline, never a
  merge.)
