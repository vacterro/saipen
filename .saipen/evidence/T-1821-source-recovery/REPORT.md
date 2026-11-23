# T-1821 / SRC-279: report readability

Historical implementation report. Current acceptance and the retained
unconditional external clause are recorded in `CURRENT-VERIFICATION.md`.
The older test totals below are not evidence for the current generation.

## What the operator actually asked for

The intake receipt `SRC-279` holds one line:

    SAIHANDOFF T-301 live input acceptance and readable reporting

That is a title a previous session supplied, not the operator's message. The
real handoff was still in the host's `session_input` store, promoted into this
session, and is preserved at `operator-message.txt` (8 539 bytes) beside this
file, with the recovery method in `RECOVERY.md`.

The recovered body addresses `EXECUTOR: SAITULS agent` and has two halves:

* **Sections 1-4** (interactive-desktop root cause, real Windows input
  acceptance, staged vs installed binary): SAITULS T-301 work. The same body
  says `Do not patch foreign repositories from SAITULS`. Out of scope here, and
  explicitly recorded as non-goals `SRC-279:R008`.
* **Sections 5-6 and regressions A-C, L**: the SAIPEN-owned corrective this
  repository can implement.

## The measured diagnosis (what section 5 asked for)

Section 5 asks for the actual text boundary, comparing raw agent response,
canonical SAIPEN rendering, stored host payload and displayed text. Measured
here, not assumed:

| Stage | Finding |
| --- | --- |
| Raw agent reply | 9 810 chars, 422 newlines (stored `part` row) |
| Canonical renderer | `render_boundary` joined fields with `"\n"` |
| Stored host payload | 19 newlines kept; the store never flattened anything |
| Displayed text | GFM soft break: a single newline inside a paragraph run joins with a space |

The decisive measurement is the host's own parser. With the same
`remark-gfm` pipeline the ZAICODE UI uses (Streamdown defaults: `gfm`, no
`remark-breaks`):

    "STATUS: BLOCKED\nRESULT: x\nVALIDATION: y"
      -> ONE text node  (one paragraph)

    "STATUS: BLOCKED  \nRESULT: x  \nVALIDATION: y"
      -> text / break / text / break / text  (real line breaks)

So the six fields were never concatenated by SAIPEN's code and the payload was
never damaged in transit. The canonical wire format did not survive CommonMark.
That is why the operator saw "STATUS: BLOCKED RESULT: ... BLOCKER: ... NEXT
EXACT ACTION: ..." as one enormous paragraph.

## The fix

`tools/saipen_engine/response_surface.py`

* `FIELD_SEPARATOR` is `"  \n"` (two spaces, newline): a CommonMark hard break.
* `_field_text()` normalizes every line *inside* a field value to the same
  break. A multi-line `DETAILS` value was the second half of the same defect:
  a report the operator explicitly authorized still arrived as one paragraph.
* The gate is unchanged. `response_errors` and `overflow_diagnostic` still
  count every `splitlines()` line against `REASON_BUDGETS`, so EXECUTION.md's
  "labels, blanks, fences included" stays true. A five-field boundary is five
  visible lines against a six-line ceiling.

**Why not a blank line between fields.** That was the first attempt and it was
rejected on evidence: blank separators consume the visible-line budget, so six
fields plus five separators exceeded the six-line ceiling and the renderer's own
readable output was refused. Making blanks free would have required weakening
`REASON_BUDGETS`, which is exactly the gate this ticket must not trade away. The
hard break buys the same visible result for zero budget change. The reviewer
should read that as the reason the separation mechanism looks unusual.

The separator contract is documented in the module itself, directly above
`FIELD_SEPARATOR`, because that comment sits beside the code a future editor
will change. `saipen/EXECUTION.md` is deliberately left untouched: its budget
rule ("labels, blanks, fences included") is still literally true and is the
reason the blank-line variant lost, so there is nothing there to amend.

## Tests

`tools/test_t1821_markdown_surface.py`, 7 tests, covering exactly the
regressions the handoff names for this repository:

* **A** every field line is a Markdown hard break (zero soft breaks)
* **B** each canonical field keeps its own line and its own label
* **C** canonical checker still accepts the render, still inside its budget
* **L** technical detail stays in evidence, not in the surface
* plus a multi-line `DETAILS` case and a guard pinning the separator constant

Red control (`red-control.txt`): restoring the bare-newline separator and the
unnormalized value in a disposable copy gives `FAILED (failures=3)`, exit 1.
The three reds are the hard-break assertion, the multi-line DETAILS assertion
and the separator guard.

## Verification

* `tools.test_t1821_markdown_surface` 7/7 PASS
* response family (`test_response_surface_contract`, `test_response_digest`,
  `test_response_delivery`, `test_response_fact_binding`, `test_chat_style`,
  `test_hush_runtime`): 158 tests PASS
* declared core-unit family: record cited in the VERIFY checkpoint
* `python tools/validate.py --gate core`: see the SHIP checkpoint

## What is explicitly not done here

Sections 1-4 of the recovered handoff (interactive desktop probe, real input
delivery, staged vs installed binary, deployment authority) and regressions
D-K belong to `__SAITULS` T-301, which is already `BLOCKED` there on
`VENDOR_ACCEPTANCE_BLOCKED`. This ticket did not simulate them, did not claim
their results, and did not patch that repository.
