# T-1719 native subscription pilot

Two isolated native provider processes ran concurrently for **4.218 seconds**.
Codex completed the assigned audit. The initial Claude account refused because
its weekly subscription limit was exhausted. A single authorized replacement
Claude account then completed the audit. The replacement began after Codex had
finished, so concurrent successful responses are **not proved** by this pilot.
There were exactly three inference calls, each bounded to 120 seconds.

| Attempt | Existing account/model | Outcome | Duration |
| --- | --- | --- | --- |
| `codex-audit` | `.codex-account2`, `gpt-6.1-sol` | Both arithmetic defects identified | 45.156 s |
| `claude-audit` | `.claude-account2`, `opus` | Weekly subscription limit refused | 4.406 s |
| `claude-replacement` | `.claude`, `opus` | Both arithmetic defects identified | 56.297 s |

Claude's exact refusal was: “You've hit your weekly limit · resets Oct 13, 2pm
(Europe/Tallinn)”. Metadata established that the replacement Claude profile
belongs to a distinct hashed principal. Plan/quotas remain unknown for Codex;
Claude metadata reports Pro without proving remaining quota.

Both successful reports located subtraction in `add` at `arithmetic.py:4` and
the extra denominator increment in `mean` at `arithmetic.py:7`. Saved
counterexamples were independently calculated from the preserved fixture.
Both sealed artifacts have empty changed-path sets. Each worker used its own
initialized project lineage and read-only provider controls.

The replacement's native Stop hook appended an independent-project PLAN
control digest after valid JSON. Strict whole-string JSON parsing missed the
findings. The shared parser now accepts the leading report only when its
remaining suffix passes the canonical response validator; it refuses extra
JSON, duplicate fields, arbitrary instructions, and malformed digests. The
complete original provider response remains unchanged. The weekly-limit
failure classifier now reports `QUOTA_EXHAUSTED` instead of `UNKNOWN`.

Parent source bytes, source modes, index, HEAD, and canonical
`IDENTITY/STATE/BOARD/LOG` remained unchanged during both measured windows.
BOOT, STYLE, EXECUTION, CORE, COMMANDS and REGISTRY also match their initial
hashes. No parent source or profile configuration was edited, and no runtime
or sandbox protection was disabled.

Evidence: `verification.json` contains interpreted findings and original
response hashes; `summary.json` preserves the initial pair; `pilot-summary.json`
adds the replacement and explicit failure reclassification; `final-hashes.json`
binds the final draft provider/worktree modules and tests. Each attempt folder
preserves prompt, native response, redacted provider channels, worker metadata,
and sealed artifact. Scratch projects remain under
`.saipen/cache/parallel-pilot/pilot-20261011T192430/`.

Final provider controls: **48 tests passed, one skipped**, with the parent
`SAIPEN_FORBID_HOST_SPAWN=1` interlock enabled. Worktree controls: **21 passed**.
