# T-1894 — eighteen more focused modules copy the source tree only

T-1889 built the mechanism: a focused gate copies `1815 MiB / 135450 files` by
default, and `tools/sandbox_scope.json` lets a module declare it reads none of
that history. It shipped six declarations, all of them from the ticket that was
being closed at the time, so the mechanism was proven but almost unused.

This ticket uses it on the modules the focused gate actually runs most.

## Why these modules, measured rather than guessed

Across the 145 focused records on disk, the sandbox copy is **50.8% of the
median run's wall time** (`copy_wall_s` median 38.6 s canonical + 14.5 s subject
against a median `duration_s` of 85.9 s for a full copy). Over the whole record
set that is **2.3 h of 5.06 h** spent copying `.git` and `.saipen` for tests
that never read them.

The 175 pattern occurrences across those records rank the exit criteria: the
module that runs most often is the module whose copy cost is paid most often.
`tools/test_subprocess_utf8.py` appears 15 times, `test_refusal_registry.py` 14,
and so on down the list.

## Selection rule, applied mechanically

A module was a candidate only when its own source contains **no** reference to
`.saipen`, `.git`, `STATE.md`, `BOARD.md`, `LOG.md` or `evidence/` — the trees a
narrowed copy drops. That is a filter for candidates, never the evidence: the
evidence is the narrowed run itself, because the campaign's own rule is that
static inspection does not prove dependency completeness.

## Before and after, per module, same work both sides

Both runs select the same file, on the same tree, with the same execution
command. `ran` is the module's own test count and is identical on both sides —
the narrowed sandbox ran the same tests, not fewer.

| module | FULL wall | narrowed wall | ran | verdict |
|---|---|---|---|---|
| `test_subprocess_utf8.py` | 85.9 s | 24.2 s | 6 | PASS |
| `test_refusal_registry.py` | 66.9 s | 7.9 s | 6 | PASS |
| `test_t1844_operator_origin.py` | 63.5 s | 3.3 s | 8 | PASS |
| `test_t1833_verification_owner.py` | 62.8 s | 3.1 s | 8 | PASS |
| `test_t1850_freebuff_diagnostics.py` | 62.8 s | 2.9 s | 6 | PASS |
| `test_t1834_tool_call_identity.py` | 63.0 s | 3.5 s | 2 | PASS |
| `test_t1670_route_budgets.py` | 64.8 s | 3.4 s | 10 | PASS |
| `test_t1465_budget_line_ends.py` | 65.2 s | 3.1 s | 3 | PASS |
| `test_verify_oracle.py` | 68.9 s | 3.5 s | 28 | PASS |
| `test_verification_grammar.py` | 67.5 s | 3.0 s | 20 | PASS |
| `test_t1472_core_unit_shards.py` | 76.1 s | 4.6 s | 14 | PASS |
| `test_t1857_budget_owner.py` | 67.5 s | 3.3 s | 3 | PASS |
| `test_t1857_shared_blockers.py` | 67.4 s | 3.1 s | 15 | PASS |
| `test_t1867_completion_grammar.py` | 67.1 s | 3.2 s | 5 | PASS |
| `test_t1876_parallel_cleanup.py` | 67.3 s | 3.8 s | 5 | PASS |
| `test_response_digest.py` | 69.6 s | 3.2 s | 10 | PASS |
| `test_t1687_identity_diagnostics.py` | 71.9 s | 6.4 s | 3 | PASS |
| `test_t1676_lifecycle_code.py` | 71.6 s | 8.2 s | 4 | PASS |

Totals: **1229.9 s → 93.6 s**, a 92.4% reduction, with every module reporting
the same `ran` and PASS on both sides.

The four modules whose narrowed run is still 6-8 s (`t1687`, `t1676`, and the
two 24 s/7.9 s heads) are the ones whose own subprocess work dominates once the
copy is gone; the copy is already 0.4 s there, so the residue is the subject,
not the harness.

## One sandbox holds one snapshot

The resolver refuses to narrow when ANY selected pattern is undeclared, so a
mixed run cannot silently drop a tree an undeclared module needed. Verified by
the combined run: five declared patterns (`test_subprocess_utf8`,
`test_refusal_registry`, `test_verify_oracle`, `test_t1876_parallel_cleanup`,
`test_t1472_core_unit_shards`) selected together ran **59 tests, PASS, 36.8 s**
in one narrowed sandbox.

## What is NOT claimed

* No test was changed, removed or skipped; `ran` is identical on every row.
* No `.saipen` or `.git` tree is excluded from any module that reads one — the
  eighteen additions are all `[]`, and every module that references those trees
  is still undeclared and therefore still copies everything.
* The 55-red baseline and the full-suite verdict are untouched by this ticket:
  it changes which bytes a focused sandbox copies, not what any test asserts.
* The remaining ~94 heavy-tree-free modules are NOT declared here. Each needs
  its own narrowed run as evidence; declaring them from the static filter alone
  is exactly what the manifest comment forbids.
