# T-1595 — budget re-derivation for the `stats` verb

Landing `saipen stats` required a new verb in `saipen/REGISTRY.json` and a new
entry in `saipen/OPS.md`. Both land on byte-budgeted surfaces, and both surfaces
were already within 1% of their caps. This file records the measurement, the
attribution, and the branch of T-1465 that was taken — so the new numbers are
re-derivable rather than merely larger.

## Measurement

`tools/protocol_budget.py` measures the surface with LF-normalised content bytes
(`_size`), so a CRLF checkout and an LF clone measure the same number. Measured
with `protocol_budget.load_profiles(Path("saipen"))` on this tree, at commit
`8f01dbbe` plus the OPS.md trim recorded below.

| Surface | Before T-1595 | Cap before | After T-1595 | New cap | New slack |
|---|---|---|---|---|---|
| `command_resolution` (`REGISTRY.json` + `COMMANDS.md`) | 46074 | 46080 | 46086 | 47104 (46 KiB) | 1018 |
| `human_markdown_total` (every `saipen/**/*.md`) | 306295 | 307200 | 307668 | 308224 (301 KiB) | 556 |

## Attribution

Two contributions, both mine, both real content:

- `saipen/REGISTRY.json`: one line, `   "stats",` — **12 bytes** on
  `command_resolution`. Registration is not optional: 58 of the 59 entries in
  `commands.saipen` also appear in `COMMAND_EFFECTS.verbs`, so the two registries
  are kept in sync by design and a verb in one only is a divergence.
- `saipen/OPS.md`: the telemetry entry, trimmed from 754 to **539 bytes** —
  deliberately cut to roughly the size of the sibling `explain-next` entry
  rather than the 765-byte draft, because the honesty statement is already
  carried verbatim by the `authority` field of every `stats --json` payload and
  by the module docstring. The remaining prose is only what an operator cannot
  read off the payload: which numbers exist, and that gaps are `UNOBSERVED`
  rather than zero.

The slack that existed before this ticket — 6 bytes and 905 bytes — was not
created by it. It was consumed by uncommitted `saipen/COMMANDS.md` edits from a
concurrent session; this ticket is the first change to cross the line, not the
one that filled the buffer.

## Branch taken

T-1465 closed with two sanctioned options: shrink the routine
command-resolution load "without dropping any rule, or re-derive the budget with
evidence". The shrink branch was tried first and rejected on evidence:

- `core` excludes `CORE.md`, `CONFORMANCE.md` and `phases/*.md` from
  `command_resolution` by design, so there is no doc to drop from the router
  surface.
- The `load_profiles.basis` string (192 bytes) explains how each budget is
  measured. Cutting it would drop meaning to win 6 bytes.
- `human_markdown_total` is a blunt sum over 37 real protocol documents. Paying
  for a 539-byte entry by trimming 539 bytes of prose authored elsewhere is a
  net-zero trade that makes the number meaningless; it was not done.

So: re-derive, one KiB step each, no rule and no document dropped.

## What would falsify this

If `command_resolution` is later found to be over its cap because a verb was
added without an OPS.md entry, or a document grew without a corresponding
COMMANDS.md shrink, the re-derivation above is not a precedent for raising the
cap again — it is evidence that the router surface is genuinely full and the
next verb needs a real condensation of `COMMANDS.md`, not a larger number.

`tools/core_unit_baseline.json` was deliberately NOT grown to absorb these two
reds. The inherited-red set exists so unrelated Work is not blocked by a red
this project already knows about; these two were *new* reds caused by this
ticket, and absorbing them would have hidden the very measurement this file
exists to record.