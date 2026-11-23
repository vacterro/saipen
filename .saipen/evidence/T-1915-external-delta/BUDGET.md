# Budget re-derivation — ship_improve (T-1915 / SRC-325 §10)

## What changed and why

`saipen source delta <SRC-###>` is a new READ-ONLY verb: the classifier that
describes implementation performed OUTSIDE the canonical lifecycle. Its row in
`COMMANDS_REFERENCE.md` is the only place an agent can discover the verb — an
undocumented read-only diagnostic is a verb nobody runs.

The row measures **313 bytes**. `ship_improve` sat at its ceiling
(56320) with 4 bytes of headroom:

```
before: 56316 / 56320   headroom 4
after:  56629 / 56320   over by 309    <- measured, refused
```

## Re-derivation

`ship_improve` is re-derived to the next whole KiB above the measured surface:
**56320 → 57344** (`56629` measured, 715 bytes headroom).

No rule, no document and no table row was dropped to pay for the addition; the
budget moved because the surface genuinely grew. This follows the same
re-derivation precedent as T-1596, T-1614, T-1619, T-1623, T-1624 and T-1845.

## Measurement

```
$ python -B -c "import sys; sys.path.insert(0,'tools'); import protocol_budget;
  from pathlib import Path; print(protocol_budget.load_profiles(Path('saipen')))"
ship_improve 56629   (limit 57344 after re-derivation)

$ python -B -m pytest test_protocol_registry.py -q
20 passed
```

`cold` stays at 27648: the cold route never loads `COMMANDS_REFERENCE.md`.
