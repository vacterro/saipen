# T-1901 — SRC-319 protocol-entry audit: independent verification

SRC-319 (`audit/BZDECOMP-T293-20261025-protocol-entry.md`) is an explanatory
report from another project. It claims nothing about SAIPEN source, so there is
no production delta to make. What it does claim is checkable, and this file
records the check.

## Claim-by-claim verification

Every claim was re-measured from the live state, not read off the report.

### 1. The project is bound to the canonical SAIPEN source checkout

`V:/___VAC/__K/__CODE/_MISC/_BZDECOMP/.saipen/STATE.md` names
`saipen_home: V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN`, `saipen_version: 8`,
`style_contract: ded-069a4c52`. That is this home, this version, and the digest
`saipen response style --json` compiles for this session. **Confirmed.**

### 2. CLI routing, STATE/BOARD/LOG and journaled operations are working

BZDECOMP's `LOG.md` carries 874 events, every one with an `[op: …]` provenance
tag. Current work is T-327, moved BUILD → VERIFY (E-3911) → BUILD (E-3913) after
a `MANUAL-VERIFY RESULT: FAIL` (E-3912). **Confirmed: the lifecycle is live.**

### 3. The first delivered answer preceded canonical T-325 closure

BZDECOMP's T-325 closes canonically: E-3776 transition to SHIP, E-3777 SCOUT
record, E-3778 `finish-…` completion. `SRC-259` is in
`.saipen/intake/tombstones/` with `status: CLOSED`, `unresolved: 0`,
`actionable: 1`. **Confirmed, and the report's own caveat is the honest one:**
the tombstone has `closure_event: null`, so the closure is recorded in the
journal rather than carried on the tombstone. That is a gap in the *report's*
evidence chain, not a contradiction of its claim.

### 4. Host limitations — the load-bearing claim

Re-ran `saipen host doctor --json` in this session. Result, identical to the
report's:

| field | measured now |
| --- | --- |
| `source.kind` | `source-checkout`, `proven: true`, version `8.1.0` |
| `policy.label` | `DEGRADED_ALLOWED`, `source: operator` |
| `authority.running` | `false` |
| `authority.mode_label` | `DEGRADED_ALLOWED` |
| `machine_runtime.code` | `MACHINE_RUNTIME_STALE`, `current: false` |
| `path_launcher.code` | `PATH_LAUNCHER_READY` |
| hosts | 9 × `STALE_RUNTIME`, 1 × `INSTALLED_UNVERIFIED`, rest `UNINSTALLED` |

So the report's central distinction holds: a working canonical source runtime is
NOT a mechanically admitted host session. **Confirmed.**

### 5. No hand-edited canonical files

`STATE`/`BOARD`/`LOG` in BZDECOMP change only through journaled operations; all
875 LOG events carry `op_id`. **Confirmed.**

## Verdict on the defect class

The class under examination — "claiming complete protocol initialization from a
successful skill/style read while canonical lifecycle or host proof is missing" —
is already guarded on the SAIPEN side by two mechanisms this session executed:

- `saipen continue --json` returns an explicit `action` + `load_path` plus
  `continuation_authority`/`safety_valve_mode`; a session cannot close on prose
  it invented.
- `saipen host doctor --json` reports source identity, authority broker state
  and per-host runtime state as separate facts, so "degraded but allowed" is
  visible rather than assumed either way.

No new gate is warranted: the distinction the report asks for is already
machine-visible, and adding a third representation would duplicate it. The audit
requested no SAIPEN source change, and none is made.

## Actionable clauses

| clause | disposition |
| --- | --- |
| answer SRC-259's initialisation question | answered by the report; independently confirmed above |
| audit here if not initialised | not applicable — this home is a proven source checkout |
| continue without repeatedly asking | obeyed; this ticket ran without operator input |
| do not claim a mechanically verified host session | obeyed; the DEGRADED_ALLOWED / stale-runtime state is reported above, not glossed |
| consume the audit layer | performed by the journaled audit-inbox cleanup after this Work reaches DONE |

## What this does not claim

- It does not certify BZDECOMP's gameplay work or T-327.
- It does not repair the host state: the machine runtime remains stale and the
  authority broker remains absent. `saipen host machine install` is the operator's
  action, not this ticket's.
- It makes no claim about any earlier agent turn than the ones journaled above.
