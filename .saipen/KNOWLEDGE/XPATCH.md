# XPATCH — Cross-Repo Patch Receipt (design, not yet implemented)

Recorded 2026-09-01 from a user design proposal. Proposal mode is
IMPLEMENTED (T-1256, `tools/saipen_engine/xpatch.py`); direct mode stays
DESIGN behind T-1257.

## Defect class this kills

A SAIPEN-controlled project A must change a bounded file set in another
SAIPEN project B. Today B sees only `working tree changed` and has no way to
distinguish a deliberate, attributed foreign mutation from unexplained dirt,
so the honest outcome is a generic stop or a human escalation for something
that is fully explainable. The missing concept is not a lock and not trust:
it is a **provably attributed mutation**.

## The one rule

A foreign change MUST NOT count as an unknown change when a verifiable
receipt states who changed it, from where, why, which exact bytes, and under
which Work.

`ATTRIBUTED_FOREIGN_PATCH` is a new attribution class, not a new verdict.

**Receipt means provenance, never correctness.** B is not obliged to believe
the patch is good. B is obliged to stop treating it as a mystery.

## Namespace boundary

A foreign actor MUST NOT write target `STATE.md`, `BOARD.md`, `LOG.md`,
milestones, release metadata or target ticket lifecycle. The only writable
foreign namespace is:

```
.saipen/exchange/xpatch/XP-000018/
    intent.json        the receipt; the commit pointer, durable before any mutation
    payload.json       base64 after-bytes + the original bytes they displace
    applied.json       observed after-state, written by whoever applied it
    disposition.json   the TARGET's own verdict (target-written only)
```

The payload is EXACT BYTES, not a diff. A fuzzy patch application would
reintroduce the ambiguity the hashes exist to remove; apply writes the
declared bytes and proves the resulting sha256 or refuses.

plus the exact declared target source paths (direct mode only). Target Core
stays the single owner of its canonical state.

The mutation enters target canonical history only when the TARGET records a
verdict: `disposition.json` carries the closed set VERIFIED / REPAIRED /
SUPERSEDED / REVERTED with the live path hashes, and the target's ordinary
checkpoint carries the `DEC:` LOG line beside it. The verdict set is XPATCH's
own; the LOG taxonomy stays CORE.md's closed DEC/RUN/WAIT/REVERT/NOTE/OPS --
a new attribution class does not get to invent a new event kind.

## Receipt shape

```json
{
  "schema": 1,
  "patch_id": "XP-000018",
  "source": {"project_lineage": "...", "work_id": "T-342",
             "attempt_id": "A-4", "agent": "saicont"},
  "target": {"project_lineage": "...", "base_head": "abc123"},
  "reason": "SAICONT requires stable SAITULS session discovery",
  "paths": {"src/session.py": {"before_sha256": "...", "after_sha256": "..."}},
  "verification": [{"command": "python -m unittest ...", "result": "PASS"}]
}
```

No absolute paths. Durable identity comes from `project_lineage_identity`
(`tools/saipen_engine/paths.py:574`), so a moved drive, a re-clone or a
`V:` to `K:` migration does not invalidate a receipt. A verification step
that did not run records `UNKNOWN`, never `PASS`.

## Existing primitives to reuse (no second wheel)

- `project_lineage_identity` — `tools/saipen_engine/paths.py:574`
- `MutationRecord` + path/effect authorization — `tools/saipen_engine/effects.py:232`
- `read_set_from` / `write_set_before` / deterministic package identity /
  `COMPATIBLE_DRIFT` reasoning — `tools/saipen_engine/producer.py:342,352,215`
- atomic writes and OS locks — current engine (`lock.py`, `operations.py`)

## Two modes

**proposal** (implemented) — zero target-source writes. The receipt and patch
package are left in the exchange namespace; the target applies them itself
through `apply_proposal`, which re-proves every before-hash at write time and
returns `TARGET_DRIFT writes=0` on any movement. Touches no concurrency
surface.

**direct** (refused until T-473) — bounded CAS write into the foreign repo.
`apply_direct` returns `DIRECT_MODE_UNAVAILABLE writes=0` and names the gate.
Reading a direct receipt is supported; producing the mutation is not.
Preconditions, all mandatory: target lineage proved, intent well-formed, every declared path
inside the declared scope, every `before_sha256` still current at write time,
no target path already dirty, receipt namespace safe, effect reversible,
receipt written before the mutation. Any failure produces
`TARGET_DRIFT mode=proposal writes=0`.

## Target-side attribution order

1. target's own active Work
2. valid XPATCH receipts (lineage match AND exact path AND `after_sha256` match)
3. known kitchen/generated state
4. unattributed user/foreign data

A receipt is never a blanket amnesty for a path. Current bytes must equal the
recorded hash, or the change is unattributed again.

A PENDING receipt claims only the paths whose live bytes ALREADY equal its
declared after-state. Not circular: the hash it must match was declared in
advance in a lineage-bound receipt. One rule closes both windows -- a crash
after a direct write leaves bytes the intent still explains, and an unapplied
proposal claims nothing, because claiming an after-state nobody wrote would
report every waiting proposal as a stale claim over bytes that never moved.
A pending receipt whose path holds a THIRD state (neither before nor after)
is conflicting: those bytes belong to somebody else and the patch can no
longer be applied over them.

Mode says who was SUPPOSED to write, never who MAY. The target can finish a
PENDING receipt of either mode -- a direct receipt whose source died before
touching a byte must not strand the target with a patch nobody is allowed to
complete. The CAS still guards every path.

## Autonomy rules

- Overlap with the target's active work MUST NOT auto-produce `WAIT_USER`.
  Re-read, classify, reconcile. Escalate only when semantic intent genuinely
  cannot be resolved.
- Failed target verification MUST NOT abandon the receipt. Preserve the
  evidence, then `REPAIR` or `SUPERSEDE` through normal target BUILD/VERIFY.
- Blind reverse-patch is allowed only while current bytes still equal
  `after_sha256`; otherwise repair the current bytes instead of clobbering
  later work.
- Human boundary stays where it already is: destructive/irreversible effect,
  conflicting user intents, undecidable correct behaviour, security breach,
  corrupted provenance. "Another SAIPEN agent changed two files and left a
  valid receipt" is not a human boundary.

## Gate conflict — the part an implementer must not paper over

`direct` mode IS a compare-and-swap on a file another agent may hold. That is
exactly T-473 (concurrent whole-file clobber guard), which is HELD on T-442
(v8 Concurrent Mode gate). Without that guard the target agent can write a
stale in-memory copy over a landed XPATCH milliseconds later and the receipt
becomes a lie.

Therefore: **direct mode is not implementable ahead of T-473.** Either T-473
lands first as the shared stale-write guard, or XPATCH direct is refused.
Proposal mode has no such dependency because it writes no target source.

Do not silently weaken T-442/T-473. XPATCH must stay bounded interoperability,
not distributed Core ownership through the back door.

## Cold-context surface

One line, no dashboard, emitted by `context.py` only when a receipt exists:

```
FOREIGN PATCHES: 1 unreviewed, 2 verified, 0 conflicting
load: .saipen/exchange/xpatch/<XP-ID>/intent.json
```

`unreviewed` = bound, no target disposition yet (a pending proposal counts).
`verified` = the target itself recorded VERIFIED. `conflicting` = a receipt
that does not bind, or whose live bytes match neither the state it claims nor
its declared before-state. REPAIRED/SUPERSEDED/REVERTED are closed target
Work and stop being foreign news.

## Required hostile coverage

simultaneous source drift; wrong project lineage; forged receipt; duplicate
receipt; crash between intent/apply/applied; symlink or path escape;
pre-existing dirty target path; target modified after XPATCH; duplicate
delivery; good patch; bad-but-repairable patch; unrelated foreign dirt.

## Where it lives

- engine: `tools/saipen_engine/xpatch.py`
- attribution: `tools/saipen_engine/convergence.py` `_attribution_snapshot`
  gains the `xpatch_intent` / `xpatch_applied` / `xpatch_disposition` claim
  sources, merged under the SAME chronology every other claim source obeys
- cold surface: `tools/saipen_engine/context.py` `_xpatch_section`
- hostile cases: `tools/test_xpatch.py` (31)
- red controls: `tools/test_xpatch_controls.py` (5 mutations, each proven to
  turn its case red)

## Acceptance

Project A patches an exact clean file set in project B and continues its own
Work immediately. B later discovers the receipt, names who/why/what with
hashes, does NOT stop merely because of those bytes, verifies them
independently, and either keeps or repairs them. Killing either agent at every
transaction boundary must never leave an unexplained target mutation.
