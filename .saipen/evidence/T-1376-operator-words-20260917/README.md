# T-1376 -- the operator's words reached the protocol only through the model

## What was measured

2026-09-17, nine-condition field matrix, installed generation
`gen-sha256:f3d2104a…`. `long_file_task` was handed this, verbatim:

```
add a docstring to the top of src/app.py.

it should say what the module is for, not repeat the function names, and
it should stay one paragraph. keep the wording plain -- no marketing, no
'this module provides', no bullet list.
… (520 bytes, twelve lines, four constraints)
```

The session ran:

```
saipen start "add a docstring to the top of src/app.py"
```

`T-1` and `SRC-001` minted, `src/app.py` changed, every gate green. T-1372's
obligation never armed: that mechanism records what a transport refusal
REFUSED, and nothing refused anything — the session never attempted the literal
ingress at all.

`source_authority: exact` was true the whole time. It is a statement about
BYTES (the stored body is whole and unredacted), and it was being read as a
statement about WORDS.

## The fix

`REQUEST-PROVENANCE-01`. Every `user_instruction` receipt records its witness:

| witness | who compared what |
|---|---|
| `operator_carrier` | a launcher declared the task's digest and the arriving text matches |
| `transport_obligation` | a transport refusal recorded these bytes and they arrived (T-1372) |
| `model_supplied` | nobody compared anything |

`model_supplied` is honest, not degrading — most sessions have no carrier, and
inventing a witness would be the fabrication this rule exists to stop. What is
refused is a contradiction: `INGRESS_TASK_MISMATCH` when a declared task and the
arriving text disagree (both digests named, `--file` route printed, nothing
captured), and `INGRESS_TASK_CARRIER_INVALID` when a carrier declares a task it
cannot prove.

The carrier is `SAIPEN_TASK_SHA256`, or `SAIPEN_TASK_FILE` when a launcher can
write text but not a digest. Digests normalize line endings and outer whitespace
exactly as INGRESS-AUTHORITY-01 does.

**The polygon now declares each condition's own task digest.** The harness always
knew the request it was about to hand the model — which is exactly what an
operator knows and the protocol never did. So the matrix can measure which of
the two honest outcomes happened: the operator's bytes arrived, or the ingress
was refused.

## A budget moved, deliberately

`load_profiles.budgets.command_resolution` went from 30720 to 32768 bytes.
`REGISTRY.json` is inside that profile, and today it gained four registered
refusal codes and two rules from four measured defects. Refusing to record law
to stay under a byte count is the wrong trade; the budget's purpose — a bounded
routed load — survives at 32 KiB. It is named here because a budget that moves
quietly is not a budget.

## Evidence

| file | what it is |
|---|---|
| `green-post-fix.txt` | 12 controls, current bytes |
| `red_subject.py` | copies the tree, reverts ONLY `witness()` to always answer `model_supplied` |
| `red-final-oracle-vs-pre-fix-subject.txt` | that run: every witness class red |
| `verify-adjacent.txt` | focused + ingress/closure/polygon/registry families |
