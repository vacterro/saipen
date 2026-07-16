# Decisions

- Protocol/personality split (v2.0.0): SKILL.md = cold workflow, STYLE.md =
  voices, UI.md = theme. Reason: long mixed prompts drift — every extra
  personality rule lowers compliance with workflow rules. Load STYLE with
  SKILL; UI only for UI work.
- Phases PLAN→SCOUT→BUILD→VERIFY→REVIEW→SHIP (v2.0.0): SCOUT mandatory
  before BUILD (most agent errors = invented architecture instead of read);
  VERIFY (works?) split from REVIEW (well made?).
- KNOWLEDGE/ over fat LOG (v2.0.0): LOG = time-ordered journal only;
  durable truth lives in architecture/conventions/decisions/traps files.
- FreeBuff-class readers (~/.agents/skills): need lowercase dir + real copy,
  skip junctions and uppercase names. Injector copies, never links there.
- v2.1.0 accepted from review: confidence on verified tickets, graph mode
  over needs: DAG, KNOWLEDGE index rule, status metrics. REJECTED for now:
  agents/ manifest files and .vac/metrics.md file (both belong to a future
  external Python orchestrator, not to the skill — LLM-maintained metrics
  files drift into fiction). Next evolution direction: small orchestrator
  reading BOARD needs: DAG and dispatching agents; SKILL.md then becomes
  the worker contract, not the top document.

- 2-tier protocol (v5.0.0): PROTOCOL.md = dense boot loader (~110 lines,
  ~1,200 tokens). Phase rules live in vacskill/phases/*.md, loaded on
  demand per STATE.phase. Reason: monolithic v4 loaded 240 lines (~3k
  tokens) every cold start even when 80% was irrelevant. Now BUILD session
  never parses SHIP rules. Inspired by caveman skill's single-sentence
  calibration: lead with state machine, not positioning text.
