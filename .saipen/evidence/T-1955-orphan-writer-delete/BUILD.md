# T-1955 BUILD -- delete the orphan `producer_integration` writer

## Change

One edit, `tools/saipen_engine/operations.py`, deleting **1-based lines
26272-26535** (264 lines) in a single asserted exact-match slice. Removed:

- `_plan_producer_integration` (definition at 26272, body to 26452)
- `record_producer_integration` with its `@_state_guard` decorator (26458/26460,
  body to 26530)
- both trailing blank-separator blocks (26267-26271 belonged to the helper's
  leading edge and 26531-26535 to the writer's trailing edge, so the range
  starts and ends cleanly)

Kept: `record_crew_run` (the reachable same-shape writer, ending at 26266) and
`_plan_convergence_stage` (the next symbol, now at 26272).

Every one of six boundary assertions was made before the write and would have
raised rather than deleted the wrong thing:

```
lines[26265] == '    return apply_plan(root, plan)'    record_crew_run tail kept
lines[26271] == 'def _plan_producer_integration('
lines[26457] == '@_state_guard'
lines[26459] == 'def record_producer_integration('
lines[26529] == '    return apply_plan(root, plan)'
lines[26535] == 'def _plan_convergence_stage('
region contains exactly 2 lines starting with 'def '
```

The file is CRLF with a blank line between every source line; the edit was done
on the split-on-`\n` representation and rejoined the same way, so no byte of the
surviving 26,687 lines changed except losing the 264 removed ones.

## Why delete rather than wire

T-1954 settled this and BUILD carries the decision out rather than re-arguing it:

| | orphan (`_plan_producer_integration`) | live (`producer.py:2155`) |
|---|---|---|
| `op_id` | `producer-integration-<uuid4_hex()>` -- random per call, cannot ever be idempotent | `producer-integrate-<identity[:32]>-<base_head[:12]>` -- deterministic and input-bound |
| resulting identity | caller-supplied `resulting_source[_fingerprint]` arguments | measured inside the mutation by `_integration_receipt_metadata` |

`producer.py:2133-2145` records that a deterministic-but-identity-only `op_id`
was the E-3836 treadmill root cause. The orphan carries an even weaker form.
Adopting it would regress that fix; the live path already does everything the
orphan was meant to do. Delete.

## Diff shape

```
 tools/saipen_engine/operations.py | 264 --------------------------------------
 1 file changed, 264 deletions(-)
```

Additions: zero. No other file is touched -- the ticket is one dead-code
removal, and the readers of the `"producer_integration"` receipt string
(`crew.py`, `intent.py`, `release.py`, `producer.py`) neither import nor call
the deleted symbols.

## Red control (recorded before the green)

```
$ git show HEAD:tools/saipen_engine/operations.py  (571,073 bytes, kept as prefix-operations.py)
record_producer_integration occurrences: 1
_plan_producer_integration occurrences: 2
def record_producer_integration(: 1
def _plan_producer_integration(: 1

post-delete working tree:
record_producer_integration occurrences: 0
_plan_producer_integration occurrences: 0
```

The red control is the pre-delete HEAD bytes, not a remembered claim: the
symbols demonstrably existed in the same measured form the census reported.
