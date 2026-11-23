<!-- SAIPEN FUTURE GATE v1 -->
id: FG-0046
title: Unified provider- and account-aware saipen launch (SRC-184)
state: DEFERRED
priority: P2
basis: measured
estimate: 1
slice: read-only account discovery -- `saipen launch --list` names provider, alias, profile directory, installed, authenticated and managed/direct for every Claude, Codex and Antigravity account on the machine, reading no secret
needs: T-1635
evidence: .saipen/intake/active/SRC-184.md

# Unified provider- and account-aware saipen launch (SRC-184)

Operator request SRC-184 (2026-10-06), recorded as a deferred target and not as Work: a unified provider- and account-aware `saipen launch`. Standing in any project directory, `saipen launch cl1` (or `claude --account 2`, `cx3`, `ag1`) starts that provider account with the caller's working directory, a process-scoped environment and no manual preparation. Required by the source: one provider adapter contract (discovery, version/auth/account/plan probes, environment builder, native and managed launch, doctor, repair) with the T-1623/T-1624 Claude integration as its first implementation, not a parallel stack; aliases that are never canonical identity; a shared account registry contract with SAITULS / SAI Accounts instead of two truths; best-effort plan and limits (UNKNOWN is a launchable state); the fail-open order MANAGED_AVAILABLE -> MANAGED_UNAVAILABLE_BUT_DIRECT_SAFE -> DIRECT_UNSAFE; mandatory multi-account isolation; no secret in logs, arguments, STATE or BOARD; discovery read-only unless import is asked for. Non-goals: billing, dashboard scraping, bypassing provider authentication or limits, destructive account switching, plaintext credentials. Bounded first slice already measured and ticketed: T-1635 -- host integration knows one Claude profile (~/.claude) and one Codex home (~/.codex), while this machine runs claude-2 (~/.claude-account2) and codex-2/codex-3-free (~/.codex-account2, ~/.codex-account3free) through the SAITULS consoles with CLAUDE_CONFIG_DIR / CODEX_HOME; those accounts get no SAIPEN hook and the doctor does not list them. Existing launch surface to generalize: tools/saipen_engine/host_launch.py (registry-derived, `saipen launch <host>`). Test matrix: the 20 cases of SRC-184, with real-process smoke where safe.

Deferred authority candidate. Not Work, not a rule source, not
implementation authority until `saipen future promote`.
