# Changelog

## 6.1.0 -- 2026-07-17
- doc: Reframed ASP completely around the **"Continuation Test"**. Memory is a means to an end; instant action is the goal. Tagline changed to "One command. Zero amnesia."
- feat: Added `TEST-001: The Continuation Test` to the Conformance section as the gold standard for release validation.
- feat: `next_action` in `STATE.md` MUST now be an explicitly executable command (e.g. `pytest tests/`), not a vague intent, to ensure zero-context resumption.

## 6.0.0 -- 2026-07-17
- BREAKING / REBRAND: Renamed "Cross-Agent Project Memory Protocol" to **Agent Session Protocol (ASP)**.
- BREAKING: `LOG.md` events are no longer linear lists. They are now graph nodes identified by `[E-XXX]` and `[parent: E-XXX]`, enabling safe multi-agent branching and merges.
- feat: Implemented Two-Way Capability Negotiation. The protocol now dictates `requires:` in `STATE.md`, and the agent locks its `mode:` based on local capabilities.
- feat: Formalized Architecture Decision Records (ADR). Long-term truths live in `KNOWLEDGE/ADR-XXX.md` to prevent log bloat.
- feat: Expanded `extensions/` architecture with `security/` and `performance/` hook documentation.
- doc: Radically split documentation. `README.md` is now just a 5-minute pitch. `SPEC.md` is the human-readable RFC. `PROTOCOL.md` is strictly machine instructions. `GUIDE.md` is the human tutorial.

## 5.3.0 -- 2026-07-17
- feat: Added dedicated `validate` phase and `vacskill validate` command.
- feat: Added `tests/validate.ps1` and `tests/validate.sh` conformance checker scripts.
- test: Added `tests/scenarios/` with 7 mock `.vacskill` states for protocol compliance testing (crash-recovery, staleness, claim conflicts).
- struct: Explicitly separated Core (`vacskill/`) from Adaptive Extensions (`extensions/` schemas, adapters, templates) to prevent protocol pollution.

## 5.2.0 -- 2026-07-17
- BREAKING / REWRITE: Converted the core `PROTOCOL.md` from a conversational guide into a strict, RFC-style normative specification.
- feat: Formalized the State Machine (`INIT → PLAN → SCOUT → BUILD → VERIFY → REVIEW → SHIP → DONE | BLOCKED`).
- feat: Formalized Claim/Ownership logic (`owner` and `claim_time` added to `board.schema.json`) to prevent multi-agent race conditions.
- feat: Added Capability Negotiation handshake (agents MUST check capabilities like git/shell before engaging).
- feat: Added formal Recovery doctrine.
- doc: Stripped all "marketing copy" and persona out of `PROTOCOL.md` into non-normative abstracts, reinforcing that voice (`STYLE.md`) never overrides logic.

## 5.1.0 -- 2026-07-17
- feat: unified "дед с района" persona. Removed haiku requirement completely. The direct, witty, tough-love "grandpa" style is now the default for both chat responses and LOG entries (while maintaining strict caveman token compression and preserving facts verbatim).

## 5.0.1 -- 2026-07-17
- fix: extract missing `verify.md`, `review.md`, `done.md`, and `blocked.md` phases that were unintentionally merged or omitted in 5.0.0, which broke lazy loading when STATE entered these phases

## 5.0.0 -- 2026-07-17
- BREAKING: 2-tier protocol architecture. PROTOCOL.md is now a dense boot loader (~110 lines, ~1,200 tokens cold start). Phase-specific rules moved to lazy-loaded vacskill/phases/ modules (init, plan, scout, build, ship, hunt). Agent loads only the phase it needs -- 60% fewer tokens per session vs monolithic v4. All rules preserved, zero lost. README rewritten for ASP (Agent Session Protocol) positioning
## 4.1.0 -- 2026-07-17
- Public launch edition: fix encoding corruption throughout (control chars -> clean ASCII, no BOM anywhere); README rewritten for public consumption with clean ASCII art; PROTOCOL.md audited and rebuilt clean

## 4.0.0 -- 2026-07-17
- BREAKING: skill -> protocol. vacskill/PROTOCOL.md is the single vendor-neutral canon (240 lines, capability degradation table included); SKILL.md shrunk to a thin skill-reader adapter. New: adapters/ (9 platforms), templates/ (init boilerplate), style/ (opt-in voices), schemas/ frozen for a future orchestrator. Injectors point everything at PROTOCOL.md, upgrade stale 3.x blocks, and write UTF-8 without BOM. Positioning: vendor-neutral project execution protocol for LLM agents

## 3.1.2 -- 2026-07-16
- hotfix: ensure FreeBuff and Antigravity plugins receive copy, not junction, as their scanners ignore symlinks

## 3.1.1 -- 2026-07-15
- core reliability audit: HUNT skip was a phantom rule since 2.0.0 (no clean-line format, no anchor) -- now `hunt -> clean @<hash>` vs HEAD; legacy rename no longer assumes git; STYLE.md-missing fallback; REVIEW pass counter lives in LOG not memory; graph-mode claim race resolved by re-read; history prune made explicit. Net zero lines -- fixes paid for by compression

## 3.1.0a -- 2026-07-15
- drop _archive_versions/ -- identical twins of v1.2.2, already served by tags (`git show v1.2.2:VAC/SKILL.md`)

## 3.1.0 -- 2026-07-15
- anti-drift: STYLE.md Persistence section (voice holds every response, no revert after many turns) + protocol loads it upfront; git tags as release archive (all 17 past versions tagged retroactively); memory backup rule for non-git projects; self-imposed ~250-line cap -- SKILL.md compressed 281 -> 249 with zero rules lost

## 3.0.0 -- 2026-07-15
- BREAKING: renamed VAC -> vacskill everywhere -- skill name, folder, memory dir (.vac/ -> .vacskill/), pointer blocks (VACSKILL:BEGIN), repo (github.com/vacterro/vacskill). Short alias `vac` still works for every command. Injector migrates pre-3.0 installs automatically; in projects run `git mv .vac .vacskill`

## 2.1.0a -- 2026-07-15
- README rewritten for v2.x: angrier grandpa, phases/confidence/graph/KNOWLEDGE covered

## 2.1.0 -- 2026-07-15
- verify confidence (high/med/low) on DONE tickets; graph mode: parallel agents claim [P] tickets over needs: DAG; KNOWLEDGE index.md rule; vac status quick metrics

## 2.0.0 -- 2026-07-15
- protocol/personality split: SKILL.md cold protocol + new STYLE.md (voices); SCOUT and REVIEW promoted to phases (PLAN->SCOUT->BUILD->VERIFY->REVIEW->SHIP); KNOWLEDGE/ base (architecture/conventions/decisions/traps) -- LOG is journal only; BOARD needs: dependencies + no-free-will pick rule; minimal STATE

## 1.2.2 -- 2026-07-15
- injectors detect generic ~/.agents/skills (FreeBuff etc.); fixed broken-encoding stale copy there

## 1.2.1 -- 2026-07-15
- README rewritten: caveman English voice, ELI5 usage guide, half the size, twice the punch

## 1.2.0 -- 2026-07-15
- one-shot injectors inject.ps1 + inject.sh: auto-detect and wire all agentic systems (Claude Code, OpenCode, Codex, Gemini, Antigravity plugins, Aider), idempotent re-runs

## 1.1.5 -- 2026-07-15
- chat voice: compressed, direct, no filler; LOG persona unchanged

## 1.1.4a -- 2026-07-15
- voice boundaries hardened: LOG voice confined to .vac/ files only; chat strictly direct

## 1.1.4 -- 2026-07-15
- human dates DD.MM.YY HH:mm in LOG, wise-angry-grandpa commentary voice (facts stay exact), closing haiku on stop/ship; chat voice unchanged

## 1.1.3 -- 2026-07-15
- self-cleaning: scratch confined to .vac/tmp/ (deleted at stop/ship), orphan-file hunting with proven-unreferenced guard, no-litter iron rule

## 1.1.2 -- 2026-07-15
- publish target now user-agnostic: repo's own origin / logged-in gh account -- no hardcoded owner

## 1.1.1 -- 2026-07-15
- concurrent-agent takeover guard; new-machine bootstrap fallback in pointer block; .gitignore/.env guard before publish commits

## 1.1.0a -- 2026-07-15
- add "vac set" as official resume alias

## 1.1.0 -- 2026-07-15
- loop caps (3 hypotheses / 2 fix cycles -> BLOCKED, never spin); PUBLISH opt-in only (no auto-push of user projects); HUNT skips unchanged-clean repos; runtime token discipline section; unified checkpoint doctrine

## 1.0.1 -- 2026-07-15
- portable install: clone-anywhere paths, macOS/Linux symlinks; MIT LICENSE; SKILL.md init block uses <VAC_HOME> instead of hardcoded path

## 1.0.0 -- 2026-07-15
- first release: single VAC skill (PLAN/BUILD/CHECK/SHIP/HUNT loop), .vac/ cross-agent memory, ship-to-GitHub flow