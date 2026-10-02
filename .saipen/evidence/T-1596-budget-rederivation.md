# T-1596 — budget re-derivation for the `cold` load profile

The declared core-unit family run of 02.10.26 (evidence
`.saipen/evidence/core-unit/4644b8dc16e3fd6f-20261002T174000Z.json`, verdict FAIL,
4722 ran, 929 s, `--jobs 6 --timeout 5400`) reported 4 new reds. Three of them are
one defect: the `cold` load profile measures over its cap. This file records the
measurement, the attribution and the branch taken, so the new number is
re-derivable rather than merely larger.

## Measurement

`tools/protocol_budget.py` measures content bytes with LF line ends (`_size`), so
a CRLF checkout and an LF clone measure the same. `cold` routes
`BOOT.md + STYLE.md + EXECUTION.md + INDEX.md`.

| Surface | at `78447758` | measured here | cap before | cap after | slack |
|---|---|---|---|---|---|
| `cold` | 24330 | 26901 | 26880 | 27648 (27 KiB) | 747 |

Per-document contribution (working tree minus `78447758`):

| Document | At `78447758` | Working tree | Delta |
|---|---|---|---|
| `BOOT.md` | 9904 | 9944 | +40 |
| `STYLE.md` | 8465 | 7737 | −728 |
| `EXECUTION.md` | 3611 | 7060 | +3449 |
| `INDEX.md` | 2350 | 2160 | −190 |

## Attribution

`EXECUTION.md` is the whole breach. Its growth is real content whose owners
already exist in code and are named in the document:

- the `COMPACTNESS BUDGET` family (`response_surface.FIELD_*_BUDGETS`),
- `DETAILS AUTHORIZATION` (`response_surface.detail_mode`, closed set),
- `RESPONSE ENFORCEMENT` (`response_enforcement` in `extensions/adapters/registry.json`),
- `PROTOCOL-ADMISSION-01` (`saipen_engine.protocol_admission`),
- `CHAT STYLE GATE` (`saipen_engine.chat_style`),
- `PARALLEL LANE (T-1575)`.

`STYLE.md` and `INDEX.md` gave 918 bytes back. The +40 in `BOOT.md` is T-1515's
transport sentence (the POSIX launcher beside `saipen.cmd`); reverting it to hide
an overage that existed before it would be baselining, so it stays.

The slack that existed before this ticket — 2550 bytes at `78447758` — was not
created by it. It was consumed by the integrated-but-unpublished `EXECUTION.md`
surface; this is the first measurement to cross the line, not the change that
filled the buffer.

## Branch taken

T-1465 closed with two sanctioned options: shrink the routed load without
dropping a rule, or re-derive the budget with evidence. The shrink branch was
rejected on evidence, the same way T-1595 rejected it:

- every byte of the new `EXECUTION.md` text carries an owner that exists in this
  tree; trimming it deletes normative content that real refusals are derived
  from (`response_surface` refuses excess; `protocol_admission` refuses prose).
- `cold` excludes `CONFORMANCE.md`, `CHANGELOG.md` and `phases/*.md` by design,
  so the routed set cannot be narrowed from outside.
- `INDEX.md` and `STYLE.md` were already condensed (−918); the second
  condensation of the same two documents would trade real content for a byte
  count.

So: re-derive, one KiB step, no rule and no document dropped.

## The fourth new red

`test_t1505_core_unit_sandbox_reclaim.HeldSandboxTests.test_a_held_sandbox_is_reported_then_swept_once_its_owner_is_gone`
is not part of this defect. It passes in isolation (4 of 4 consecutive runs,
3.5 s each) and fails only under the parallel family, so it is a timing-sensitive
test in a concurrent run, not a deterministic red. It is recorded as its own
owner ticket rather than absorbed here.

## What would falsify this

If `cold` is later found to be over its cap because a document grew without a
corresponding condensation elsewhere, this re-derivation is not a precedent for
raising the cap again — it is evidence that the cold-start surface is full and
the next rule family needs a real condensation of `EXECUTION.md`, not a larger
number.

`tools/core_unit_baseline.json` was deliberately NOT grown to absorb these reds.
The inherited-red set exists so unrelated Work is not blocked by a red this
project already knows about; these were *new* reds on the tree, and absorbing
them would hide the very measurement this file exists to record.