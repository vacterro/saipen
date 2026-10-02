Test: saiwiki (a read-only wiki-drift subSaipen) detects stale version badge
in the GitHub wiki, writes finding to `kitchen/OUTBOX.md`, and the main agent
collects + applies the fix. Demonstrates the full subSaipen lifecycle:
drift detection -> OUTBOX -> collect -> apply.

extensions/subs/PROTOCOL.md § 2 (OUTBOX format), § 4 (collect), § 7 (bare
name adoption). The sub reads the project, never writes to it. Findings leave
through OUTBOX -- the only door out.

**Sequence:**
1. Main ships vX.Y.Z. Wiki still shows vX.Y.Z-1 (inevitable drift).
2. `saiwiki` spawns/adopts via bare name. Reads project STATE/BOARD/LOG,
   compares against wiki (`git clone --depth 1` or manual inventory).
3. Finds drift: Home.md badge stale, _Footer version stale, Scenarios row
   count wrong. Writes WIKI-NNN to OUTBOX as `status: ready` with per-page
   delta in `details:`.
4. Main runs `saipen sub collect` -> sees WIKI-NNN `critical: false`.
   Applies the 3-5 line fixes directly (light refresh, not regeneration).
5. saiwiki STATE updated to DONE + WAIT: user brake. Next drift scan on next
   `saiwiki` adoption.

**Why not automate wiki sync in CI?** The wiki is human-facing prose, not
auto-generated docs. A full regeneration rewrites examples, tone, ded-style
rants, and locale flags by hand -- a CI job cannot judge whether a rephrased
paragraph is clearer. saiwiki is a cheap read-only sensor that flags WHAT is
stale and trusts a human or Core agent to decide HOW to fix it. Concretely,
saiwiki caught Home.md CI-trigger section being stale while the CI badge
itself was already green -- a purely prose gap that no automated check
could have flagged.

**The failure this catches:** a wiki that silently drifts release after
release, accumulating stale version numbers, outdated feature descriptions,
and CI claims that no longer match the workflow. Each release widens the gap;
a full regeneration every time is prohibitive. saiwiki's per-release light
refresh (3-5 pages, ~15 min) keeps the wiki truthful at P3 cost.

Behavioral, README-only: the assertion is that a read-only sub can detect
prose-level drift and surface it without writing to the main tree. The cycle
is demonstrated by this repo's own history: saiwiki W-015 (v7.97.0 full
refresh), W-017 (v7.98.0 light refresh), W-018 (CI trigger prose fix).
Correctly declares no expected outcome, so `tools/run_scenarios.py` skips it.
