# T-1899 — external revalidation asked one question 22 times

## The defect

`continue` runs `_auto_external_revalidate` at the start of every agent turn. On
this project that pass spent **4.0 s** answering a question whose answer never
changed.

`revalidate_external_dependencies` walked every receipt FILE:

```python
for rpath in existing_receipts(root):
    record = load_receipt(root, rpath.stem)
    work = record.get("work")
    ...
    problems = resolution_problems(root, work, ticket)
```

But `resolution_problems` does not answer about the file it was reached from. It
reads the work's BOARD-cited receipt — `external_evidence` — and resolves THAT:

```python
receipt_id = _evidence(ticket)
record = load_receipt(root, receipt_id)
```

Its verdict is therefore a function of the WORK alone. Looping over files asked
the identical question once per append-only resolution that Work had ever
written. Measured on the live tree: **22 receipt files, one Work, ONE distinct
answer, 3.95 s.**

The same loop carried a second, latent defect. `record` was whichever file the
iteration reached, and `record` supplies the authority, implementation and
`verification` entries used when a re-resolution is built. This project's
history holds two implementations for that one Work (`T-289@5f0dc0c` for
EX-000001..10, `T-289@041f00ed` for EX-000011..22). A Work whose only problem is
a moved engine would have counted and re-resolved once per file, potentially
writing a receipt for an identity the BOARD no longer names.

## The change

One loop over DONE Work that cites a receipt, in `sorted()` order for
determinism; the record comes from the cited receipt:

```python
cited_work: dict[str, str] = {}
for tid, ticket in tickets.items():
    if ticket.get("section") != "## DONE":
        continue
    evidence = _evidence(ticket)
    if evidence:
        cited_work[tid] = evidence
for work, receipt_id in sorted(cited_work.items()):
    if target_ticket and work != target_ticket:
        continue
    try:
        record = load_receipt(root, receipt_id)
    except ExternalRefusal:
        continue
    problems = resolution_problems(root, work, tickets[work])
```

No gate is weakened. A receipt that fails to load is still skipped
(`ExternalRefusal`), a Work with no cited receipt is still not a candidate, and
`resolution_problems` is still the ONE predicate that decides.

## Evidence

Red/green on two trees with **identical test bytes** (`prefix` = working tree with
only this hunk reverted):

| tree | result |
|---|---|
| prefix | 2 failed, 34 deselected |
| postfix | 2 passed, 34 deselected |

The two red failures name the defect directly: `resolved 12 times for one Work`,
and `asked about ['EX-000001', 'EX-000002']`.

Measured on the identical live workload (22 receipt files, 1 cited):

| | prefix | postfix |
|---|---|---|
| revalidation, median of 3 | 4.1313 s | **0.2051 s** |
| revalidation, min of 3 | 3.9901 s | **0.1986 s** |
| outcome | inspected 0, all lists empty | identical |

End to end, `saipen continue --json` median of 3: **6.92 s → 2.868 s** (−59%).
`status` does not call this path, so its run-to-run spread is machine noise and
is not claimed as either a gain or a regression.

Family: `tools/test_external_revalidation.py` **36 passed**;
`tools/test_external_authentication_contract.py` **11 passed**.

## What this does NOT claim

- It does not change how often a re-resolution is *warranted*; it changes how
  often the same warrant is *asked about*. On a machine where no engine has
  moved, both versions inspect zero.
- It does not bound `semantic_receipt_snapshot`, which is a separate 3.59 s of
  `status` and cannot be narrowed without weakening convergence's corruption
  gate (INV-13). That was investigated and left alone.
- It does not make `status` faster. `status` was 11.5 s before and 12.4 s after,
  within this machine's noise band for that command.

## Note on repository state

`revalidate_external_dependencies` does not exist in `HEAD` — the revalidator is
in-flight uncommitted work in this checkout. The control therefore rebuilds the
pre-fix tree by reverting this one hunk, not from `git archive HEAD`, which would
have removed the entire function and made the comparison meaningless.
