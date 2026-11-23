# T-2090 — SAIPEN Hyperlean Night Shift 5 — final report

Date: 2026-11-18. Agent: GLM 5.3 (ZCode session). Tree: `dc39709c0` (dirty,
publication-debt class, unchanged by this shift's policy). Live checkpoint:
E-21704 (losslessly externalized).

**STATUS: DONE (all five P0s RED→GREEN).**

## Correctness — five independent RED/GREEN proofs

New verifier: `tools/regression_t2089/t2089_p0_night5.py`, run against the
live repo engine (`tools/saipen.py` as module, `saipen_engine.journal` via
package import). RED first — all reproduced on the live tree BEFORE any fix:

- **N5-A global 32 KiB overrun** — 16 saturated blocker groups serialized
  39 916 B, `truncated: true` but past budget (final guard skipped
  `blocker_groups` on purpose). RED 39 916 B > 32 768 B.
- **N5-B1 append truncation lie** — one append, content-cut, `truncated:
  false` (cut derived from row count only). RED.
- **N5-B2 receipt truncation lie** — receipt `other` field dropped by the
  slim filter, `truncated: false`. RED.
- **N5-C UTF-8 tail digest** — `"€"*400` at a 512 B budget: marker hashed
  from raw offset 512 while the true dropped tail began at 510 (straddled
  code-point bytes vanished from both halves). RED: digest mismatch +
  kept_utf8_bytes off by one.
- **N5-D journal short read** — instrumented 7-byte `os.read`: manifest 7 B
  of 84, progress 7 B of 60, `structural_error: None`. RED.
- **N5-E manifest/progress vanish race** — file present at lstat, gone at
  open: `manifest_raw=None, structural_error=None` — masked as plain
  absence. RED, both files.

All 10 checks GREEN after the fixes (one honest SKIP, see below).

### Fixes

`tools/saipen.py` — `_agent_view_payload`:

- **A**: blocker groups charge the shared budget row-serially; a group
  past its byte share still emits an exact-count id-only row (count
  parity pinned by the stress suite); never-emitted groups fold into
  `blocker_group_truncation` with overflow digest + samples. The final
  hard guard can now collapse `blocker_groups` too — counts are hoisted
  and survive, so the guard always converges under 32 KiB.
- **B**: `_emit_appends` sets `cut` on any content-carrying marker, not
  just row overflow; `_emit_conformance` marks dropped receipt fields
  with `receipt_fields_omitted` (count, keys digest, sample) and sets
  `truncated`. Intentional-summary vs lossy-truncation is now explicit:
  slimming 4 named receipt fields with nothing dropped stays clean;
  anything dropped is named.
- **C**: `_bound_string` keeps a valid UTF-8 prefix; a straddled code
  point's bytes move into the tail hash FIRST, so
  `dropped_tail_sha256 = sha256(original[kept_utf8_bytes:])` exactly and
  kept+dropped bytes sum to the original length. New
  `dropped_tail_bytes` count. Verified ASCII / 2-byte / 4-byte / mixed /
  boundary-straddle / empty-tail / determinism cases.

`tools/saipen_engine/journal.py` — `_receipt_namespace_entries`:

- **D**: reads are exact-size single reads with a lawful-short-read
  fallback loop to true EOF (never trusts one `os.read`); mid-read
  OSError is classified (`read failed (…)`) instead of returning partial
  bytes; zero-byte files capture as empty bytes; a 256 MiB hard cap
  classifies anomalous growth instead of feeding unbounded bytes.
- **E**: `_verified_read(path, label)` — identity re-verified through the
  OPEN descriptor (`fstat`), `O_NOFOLLOW` where the platform has it
  (POSIX ELOOP → named error; Windows has no O_NOFOLLOW — file-symlink
  creation there is privilege-gated WinError 1314, and the descriptor
  fstat re-check still refuses non-regular targets). A file that
  vanishes between lstat and open becomes the named structural event
  `"vanished between stat and open"` — a distinct sentinel from the
  never-existed shape, so `_scan_receipt_namespace` surfaces
  `CORRUPT_JOURNAL` and the fail-closed consumers refuse it.

### Honesty notes

- **N5-X3 (symlink substitution TOCTOU) SKIPs loudly on this host**: it
  cannot create symlinks (WinError 1314, no SeCreateSymbolicLink
  privilege). The suite prints `SKIP N5-X3`, never a silent GREEN. The
  engine-side protection (O_NOFOLLOW + descriptor fstat) is still
  exercised on platforms that can create symlinks.
- The handoff's second B-reproduction (`conformance_status.receipt.other`
  dropped) is now BOTH flagged (`truncated: true`) AND named
  (`receipt_fields_omitted`) — a consumer can no longer read the slim
  receipt as complete.

## Verification ledger (this shift, live repo engine)

GREEN: night5 10/10 (1 SKIP); night4 5/5; repro 0 RED/3 GREEN; stress
(120/2000/10 000 groups, 1–20 parity, 40-trial mutation/idempotence,
truncation truth); oracle OK; agent-status-view 4/4; lazy entrypoints 4/4;
finish golden 7/7; t1879 14/14; t1944 22/22; t1734 15/15; continue_chain
6/6; t1304 19/19 (unittest runner); settled_projection 19/19; t1666 OK;
t1903 OK; t1836 rc 0. Live smoke: agent view 28 306 B < 32 KiB on 117
blocker groups, `truncated: true` naming waiting/appends/group overflow,
authority strings plain.

Carried debt (unchanged, NOT this shift's regressions): perf_wave
regressions 37/42 — the 5 failures are the pre-existing
`witnessed_operator(root)` harness drift, identical on stashed baseline;
t2040 import debt (pre-existing).

**Journal semantic digest parity**: `ops-receipt-sha256:b3017614…`,
0 errors, 20 272 records — byte-identical framing pre/post fix. The fix
changes fault handling, not healthy-path semantics.

## Performance — honest interleaved A/B (same corpus, same machine)

- Interim build (looped 1 MiB reads only): agent status p50 **15.87 s**
  vs night-4 single-read **8.95 s** — a REAL +77 % regression, measured
  interleaved 8×2. Removed.
- Final build (exact-size read + short-read fallback): p50 **9.28 s**
  vs single-read 9.17 s (min 8.62 vs 8.67) — **time-neutral** (−1 %,
  within run-to-run spread), while restoring read-to-EOF correctness.
- The handoff's 9.42 s night-4 baseline and today's ~9.2 s are the same
  corridor on this machine/corpus; no performance win is claimed for the
  correctness fix, and none was lost.

## Canonical state (read-only, no operator decisions manufactured)

- T-2090 DOING, phase SCOUT; T-2091 (SRC-425, this night-5 request)
  recorded in queue behind the active seat. Checkpoint E-21704 durable.
- HEAD `dc39709c0`, dirty (4 370+ changed paths; publication-debt class).
  Distribution: 7 installed homes, 7 stale, `fresh: false`, blocker
  `DIRTY_SOURCE` (87 injected-surface paths differ from HEAD — includes
  this shift's 2 new test files), newest_installed_head `7857dbf2`,
  published_head null, pending_consumers [].
- Publication/install/push remain the T-2058 operator cycle; nothing was
  committed, installed, published or pushed; `implementation complete ≠
  publication complete`.

## Files changed (this shift)

- `tools/saipen.py` — P0-A/B/C (bounded group build, honest truncation,
  valid-UTF-8 tail digest).
- `tools/saipen_engine/journal.py` — P0-D/E (`_verified_read`:
  descriptor-identity open, exact-size read + EOF fallback loop, vanish
  classification, O_NOFOLLOW where present, 256 MiB cap).
- NEW `tools/regression_t2089/t2089_p0_night5.py` (verifier, RED-first,
  10 checks + honest SKIP).

## NEXT EXACT ACTION

`saipen continue` — T-2090 phase walk to BUILD/VERIFY with the night-5
regression pair anchored (same-verifier rule), then REVIEW/SHIP closure
within existing authority; publication stays parked on T-2058.
