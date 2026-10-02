# T-1582 — the sweep must not blame a missing file for a missing privilege

## The defect, in two parts

**Part one (the ticket).** `tools/audit_checks.py` has a `symlink_restore_probe`
whose only failure mode on a host without `SeCreateSymbolicLinkPrivilege` used
to be indistinguishable from the probe's own breakage. It now raises
`ProbeUnproven` — a loud UNPROVEN verdict naming the host capability — and
`_is_symlink_capability_refusal` is the single test that decides "this host may
not make symlinks": WinError 1314, or the POSIX spellings `EPERM`/`EACCES`/
`ENOSYS`. Anything else still fails loudly, because a damaged path or a
read-only temp dir is this probe's breakage, not a host property.

The mutation sweep never got that treatment. Its `SYMLINK_EXTERNAL` case
(`CASES[2]`, "portable project identity becomes an external symlink") reported
one fixed SKIP sentence for every case it could not run:

> the mutation changed nothing: the file is missing, or its anchor text is

On this host that sentence is false. `IDENTITY.md` is present and its anchor
has not moved; the host simply cannot construct the control. The message sent
its own author hunting for a file that was sitting right there.

**Part two (found during this ticket's BUILD, not in its original text).**
`tools/audit_parity.py` consumes the same `apply_case` contract and still tested
**truthiness**. Once `apply_case` began returning a non-empty *reason string* for
a capability refusal, that string is truthy, so `if not ac.apply_case(...)` was
`False` — the case was counted as **applied**. Parity then ran the portable
floor against a tree where the mutation was never planted, and credited the
floor with catching a defect that did not exist. On this host, on every parity
run, for `CASES[2]`. That is a false pass, and it is the same failure the
ticket exists to kill, one function over.

## The repair

In `tools/audit_checks.py`:

- `apply_case` returns `bool | str`. On the symlink path a capability refusal
  returns the reason *"this host cannot create a symlink, so the case was never
  constructed (a host capability, not a missing file): …"*; a genuinely missing
  target still returns a bare `False`. Every other branch keeps its contract.
- `skip_line(label, reason)` prints the reason when there is one and keeps the
  original sentence when `reason is None`. It is deliberately pure, so a test
  can assert both wordings without a 26-minute gate.
- The sweep worker tests `applied is not True` — a reason string must never be
  admitted as successful setup — counts capability skips out of `broken`, and
  raises `ProbeUnproven` rather than ever emitting the full-sweep PASS
  sentence.

In `tools/audit_parity.py`, one line:

```python
if ac.apply_case(root, rel, mutation) is not True:
```

`apply_case` returns exactly `True`, `False`, or a `str` — every branch was
audited, including the `MULTI` branch, which returns a bool — so identity is
the correct predicate and truthiness is provably wrong.

## The controls, and why they are not vacuous

`tools/test_t1582_sweep_skip_reason.py`, 15 tests, all green on this host
(one skips honestly: `test_real_symlink_still_applies` needs the privilege this
host does not have).

The ticket's own red control is
`test_moved_anchor_keeps_the_missing_file_wording`: a case whose anchor really
did move must keep the missing-file sentence, so the fix cannot silence a real
diagnostic. `test_real_missing_anchor_alone_still_uses_generic_skip_and_fail`
covers the same thing end to end through the real sweep and the real
`run_probes`.

The two tests added for part two are:

- `test_a_reason_string_is_truthy_so_truthiness_would_misclassify_it` — pins
  the fact that the defect depended on: the refusal is a truthy non-`True`
  value, so `not result` is `False`.
- `test_parity_call_site_tests_identity_not_truthiness` — pins the call site's
  predicate so the two cannot drift apart again.

`run_chunk` is a closure inside `audit_parity.main`, and reaching it means
spawning the floor for every case, so the predicate is pinned against the real
`apply_case` return values plus a source pin rather than by running parity.

**Non-vacuity of the new control was proven, not assumed.** A script
(`V:/_TEMP_/t1582_redcontrol.py`) reverted the call site to
`if not ac.apply_case(...)`, ran `ParityClassificationTests`, and restored the
file. The control goes red against the old line and green against the new one.

## The gates

| Gate | Result |
|---|---|
| `python -B -m unittest tools.test_t1582_sweep_skip_reason` | 15 tests, OK (1 honest skip) |
| `python -m ruff check` on both changed files | All checks passed |
| `python -B -m unittest tools.test_style_contract_chokepoint` | 7 of 7 OK |
| core-unit family `dbdfad812a781d16-20261002T001042Z` | **PASS — ran 4618, red 0, new_red 0, sandboxes leaked []** |

The family ran **4618** where the previous green run ran 4616: the two new
tests were discovered into the declared family, which is how a control that
nothing executes gets caught.

## The live sweep, unmocked

The control mocks `os.symlink`, so on its own it proves the wording but not
that the real host reaches it. `python tools/audit_checks.py` on this host,
exit code 0, says:

```
UNPROVEN: mutation-sweep -- portable project identity becomes an external
symlink: this host cannot create a symlink, so the case was never constructed
(a host capability, not a missing file): [WinError 1314] A required privilege
is not held by the client: ... -> '...\cases-02\.saipen\IDENTITY.md'
SKIP: portable project identity becomes an external symlink -- this host cannot
create a symlink, so the case was never constructed (a host capability, not a
missing file): [WinError 1314] ...
PROVEN: 246 of 247 mutation controls; host capability unproven: 1; broken: 0
AUDIT: 12 of 14 probes passed; failed: none; skipped: none; unproven (host
capability): mutation-sweep, symlink-restore
```

Three things this proves that the unit control cannot:

1. The pre-existing sentence — *"the mutation changed nothing: the file is
   missing, or its anchor text is"* — **does not appear for this case**. On this
   host, before the fix, that is exactly what it printed.
2. `IDENTITY.md` is present throughout; the run names WinError 1314 as the
   cause instead. The message no longer sends a reader hunting for a file that
   was sitting right there.
3. `broken: 0`. The capability refusal is counted out of the broken tally, so
   it no longer inflates the "no longer prove anything" count the ticket
   complained about, and it never reaches the full-sweep PASS sentence. The
   sweep is `UNPROVEN`, which is the honest verdict on a host that cannot build
   one of its own controls.

`symlink-restore` above reports `UNPROVEN` through the same
`_is_symlink_capability_refusal` test, which is the reuse the verify clause
asks for: one definition, two consumers, one answer on the same host.

## Honest notes

- **The implementation was already in the tree when this ticket was claimed.**
  A prior session under this same ticket (owner `saipen-cli`, claim time
  2026-10-01T12:39Z) had written `tools/audit_checks.py` and staged
  `tools/test_t1582_sweep_skip_reason.py` in git, but the ticket was parked in
  `## TODO` behind a `TIME_GATED_EVIDENCE` blocker (foreign event E-11124,
  stamped 14:54, which self-heals ~14:49Z). That gate has long since expired.
  This pass confirmed the implementation, and found and fixed the part-two hole
  it had missed.
- **The parity change makes a previously-green path loud.** On a host without
  the privilege, parity now reports `FAIL: skipped canonical mutation:
  portable project identity becomes an external symlink` instead of silently
  crediting the floor with a catch. That is the intended trade — parity's own
  skip vocabulary, used honestly, rather than a new verdict invented here — but
  it is a real behaviour change on such hosts and is recorded rather than
  smoothed over.
- **`test_parity_call_site_tests_identity_not_truthiness` is a source pin.**
  It will catch a regression at that exact call site; it does not prove parity's
  end-to-end behaviour, which needs the 155-case floor run.