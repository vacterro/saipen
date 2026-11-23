# T-1955 SCOUT -- what exactly is being deleted, and what depends on it

Ticket: delete `operations.record_producer_integration` and its
`_plan_producer_integration` helper. T-1954 established *why* (the orphan is
weaker than the live path and adopting it would regress the E-3836 op_id fix).
SCOUT answers the remaining questions a delete has to answer:

1. Where does the region start and end, exactly?
2. Is anything else in the module reachable *only* through it?
3. Is any non-code surface (test, validator, protocol doc, CLI verb) naming it?
4. Does the live `producer_integration` path at `producer.py:2155` keep working
   with the orphan gone?

## 1. Exact region

`tools/saipen_engine/operations.py` is CRLF with a blank line between every
source line (the file's own idiom, not a build artifact). Top-level boundaries
around the orphan:

```
26202  @_state_guard
26204  def record_crew_run(                    <- the live, reachable neighbour
26207  ...
26272  def _plan_producer_integration(         <- region A start
26530  ...    return apply_plan(root, plan)
26536  def _plan_convergence_stage(            <- the next kept symbol
```

The two symbols are **one contiguous block, 1-based lines 26272-26535**
(264 lines). It is one range, not two, because the helper ends immediately
above the writer's decorator:

```
26266  '    return apply_plan(root, plan)\r'     record_crew_run ends (kept)
26267-26271  five blank separator lines          (kept)
26272  'def _plan_producer_integration(\r'        <- delete starts
...    the helper body, ending at 26452 '    )'
26454-26457  its trailing separators
26458  '@_state_guard\r'
26460  'def record_producer_integration(\r'
...
26530  '    return apply_plan(root, plan)\r'        writer ends
26531-26535  five blank separator lines          <- delete ends (26535)
26536  'def _plan_convergence_stage(\r'           next kept symbol
```

Deleting 26272-26535 therefore removes exactly the two definitions and both
trailing separator blocks, and leaves the kept `record_crew_run` followed by
the file's own five-blank-line idiom before `_plan_convergence_stage`. Nothing
between the two symbols is a third, kept function: the only top-level
`def`/`@` markers in 26200-26560 are `:26202`, `:26204`, `:26272`, `:26458`,
`:26460` and `:26536`.

## 2. Dead-after-delete analysis

Deleting a region can orphan *other* symbols. Measured by diffing the identifier
set of the region against the rest of the module:

```
APPLIED INTEGRATION INTEGRATION_RECORDED S0 S1 _plan_producer_integration
core_ticket detects input_source input_source_fingerprint natural
package_identity prepared producer_integration record_producer_integration
resulting_source resulting_source_fingerprint truthfully
```

Every Python name in that list is either a parameter/local of the deleted
functions, a string fragment (`INTEGRATION`, `APPLIED`, `S0`, `S1` come out of
the split identifiers of longer strings), or the two symbols being deleted.
**No helper becomes dead.** All fifteen module-level helpers the region calls
(`_docs_preconditions`, `_event_line`, `_identity`, `_log_targets`, `_now`,
`_read`, `_refuse`, `_render_plan`, `_target`, `_utc_iso`, `apply_plan`,
`build_plan`, `patch_state`, `uuid4_hex`, `validate_texts`) have 36-478
references each elsewhere in the file, so none of them is single-use.

`INTEGRATION_RECORDED` is the orphan's own result code and appears in exactly
one place -- `operations.py:26438`, inside the region. Nothing greps for it.

## 3. Non-code surfaces

| surface | result |
|---|---|
| `git grep record_producer_integration` (whole tree) | `operations.py:26460` only, outside `.saipen/` memory |
| `git grep _plan_producer_integration` (whole tree) | `operations.py:26272`, `:26494` only |
| `tools/audit_checks.py` | no reference |
| `tools/validate.py` / `.github/workflows/` | no reference |
| `saipen/` protocol docs, `COMMANDS.md`, `REGISTRY.json` | no reference -- no CLI verb reaches it (`effects.py`, `saipen.py` were searched in T-1954) |
| `tools/run_scenarios.py` | names the *receipt operation string* `"producer_integration"` (`:4966`, `:4969`), not the function |
| reflective sweeps | the only `vars(operations)` walk is `test_log_tail_quarantine.py:273`, and it filters on `name.endswith("_EVIDENCE_ROOT")`, so it cannot see these symbols |

The remaining references -- `crew.py:1586-2024`, `intent.py:783/1002`,
`release.py:685`, `producer.py` -- all name the **receipt operation string**
`"producer_integration"` or the reader helpers `_producer_integration_receipts`
/ `_producer_integration_edge`. Those read *committed receipts*; they do not
import the writer. Deleting the writer leaves every reader with the same input
it has today, because today the writer is never called to produce one.

## 4. The live path

`producer.py:2155` is a `run_mutation(...)` call whose third positional argument
is the string `"producer_integration"`. It does not import
`operations.record_producer_integration` and shares no code with the orphan
except the receipt key names. Its `op_id` is
`producer-integrate-<identity[:32]>-<base_head[:12]>` and it measures the
resulting source inside the mutation via `_integration_receipt_metadata`. None
of that touches `operations.py`.

Reused neighbours: `record_crew_run` at `:26204` is the same-shape, reachable
writer, and `tools/test_t1430_crew_run_receipt.py` is the test pattern for
"this writer is reachable". The delete must not disturb either.

## Commands used

```
git grep -n "record_producer_integration"
git grep -n "_plan_producer_integration"
git grep -n "producer_integration" -- tools/ saipen/ tests/ README.md CHANGELOG.md VERSION .github/
python - (identifier-set diff of the region vs the rest of operations.py)
python - (boundary map: every top-level def/@/class between 26200 and 26560)
```

## Next

BUILD deletes lines 26272-26530 of `tools/saipen_engine/operations.py` in one
asserted exact-match edit, then proves the file still imports and the symbol
census is zero.
