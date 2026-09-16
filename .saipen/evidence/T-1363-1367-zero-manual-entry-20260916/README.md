# T-1363 / T-1367 zero-manual entry, 16.09.26

Two commits, one oracle, one field matrix on the installed runtime.

| | |
|---|---|
| pre-slice base | `005a8ac2` |
| T-1363 slice | `8553e721` |
| field findings | `e5a9613b` |
| runtime generation after inject | `gen-sha256:6dc92802b08b2c0c02689cadcbcf1b3113e40f5d75c9c43bbf3e10ebf1965792` |
| installed homes | 6 of 6 CURRENT, stale = 0 |

## The oracle

`tools/test_t1363_zero_manual_entry.py` — 70 controls in 12 classes, all green
on the live tree. `tools/t1363_red_subject.py` builds the same tree with every
file the slice touches reverted to `005a8ac2` and the three it adds removed,
copies the module in VERBATIM, and runs it there: every class goes red.

    BootRouteTests 6            CommandEffectOwnerTests 9
    DiagnosticLivenessTests 14  HumanRefusalTests 5
    IngressGrammarTests 49      LiveTranscriptConvergenceTests 5
    OversizedProjectionTests 3  PluginFleetRoutingTests 9
    ReadOnlyProbeBoundaryTests 4  ReauthProducerMatrixTests 11
    RequestIdentityTests 8      StartEntryTests 7

The base is PINNED, not `HEAD`: once the slice is committed `HEAD` carries the
fix, and an oracle that measures `HEAD` retires itself exactly when it starts
mattering.

## Attribution

Full unit family, same fixtures, same command, only the slice moved:

* live `Ran 2532, FAILED (failures=43, errors=1)`
* baseline (a full copy with the slice reverted) `Ran 2466, FAILED (failures=31, errors=1)`

Live-only reds: 12. Three were controls the slice MOVED (a shell `grep` and
`ls -la` now earn the read class; `saipen/COMMAND_EFFECTS.json` must be
declared in the runtime manifest) and were rewritten against the new owner.
The other nine were the INSTALLED runtime still carrying the pre-slice
generation: `test_opencode_host_smoke` 5, `test_opencode_bound_launch_smoke` 3,
`test_entry_point_parity` 1. All nine are green after the inject.

PATCH_OWNED = 0. UNKNOWN = 0. The remaining 32 reproduce byte-identically on
the baseline and match the recorded T-1354 inherited set.

## Field matrix

`tools/t1363_field_polygon.py`, `sairoute/SAIFREN` through the local 9Router
free pool, eight project conditions, the INSTALLED runtime (no
`SAIPEN_SKILL_ROOT` override).

Seven of eight reached productive work. Six chose `saipen start` as their
FIRST command, ran ONE protocol command, and hit zero refusals.

The eighth is the finding that produced `e5a9613b`: the Windows-path task was
typed in DOUBLE quotes, the guard refused it `INGRESS_TRANSPORT_UNSAFE`, and
the model transcribed the ~700-character hex route TWICE and corrupted it both
times — once by inserting a literal ` app` into the middle of the digits —
before abandoning the route and improvising twelve refusals. A route a weak
model cannot copy is not a route.

## Harness defect found by the same run

The first matrix run minted REAL tickets in this repository (T-1368, T-1369,
receipts SRC-047/SRC-048) and wrote `src/app.py` here.

Two causes, and only the second was decisive. The fixtures were not git
worktrees, so the host did not resolve them as projects; they are worktrees
now. That alone did NOT close it: `subprocess` sets the child's working
directory and leaves `PWD` alone, so the host kept a `PWD` naming the
repository the harness ran from, and the model's shell believed it. Proven by
the probe in between -- the fixture's own canonical files did not change
(`canonical_changed: []`) while the model reported this repository's `T-1368`.

With `PWD` bound to the fixture the sandbox holds: the fixture's BOARD carries
its own `T-1`, its own `src/app.py` was the file edited, its STATE/BOARD/LOG
all moved, and this repository's LOG did not grow by one line.

The two residue rows stay. The ledger is append-only.
