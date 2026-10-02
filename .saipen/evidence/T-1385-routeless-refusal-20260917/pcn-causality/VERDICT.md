# T-1385 -- were the repeated PROTECTED_CANONICAL_NAMESPACE refusals a carousel?

Source: OpenCode's session store (`~/.local/share/opencode/opencode.db`), opened
read-only by `pcn_causality.py`. Raw per-refusal records are in
`pcn-causality.json`. Scope: every session whose polygon record carried
`PROTECTED_CANONICAL_NAMESPACE` in `repeated_refusal` -- the evidence T-1385 was
opened on and the smoke that showed it partial (SRC-057 section 2).

## Per-pair shape

| session | generation | condition | PCN | pairs | shape of each pair |
|---|---|---|---|---|---|
| ses_f5016f4c6ffe1NOZyPZ7KhoW6l | 420e04e7 | long_file_task | 4 | 3 | DISTINCT x3 (shell reads of `.saipen` files: git/Get-Content/Get-ChildItem) |
| ses_f5076c641ffeLV1NnwFbGjrI7b | b374ef1f | captured_unprojected | 2 | 1 | DISTINCT (`Get-Content .saipen/STATE.md` then a `Test-Path .saipen\kitchen` probe) |
| ses_f50740ca9ffeJuU5anJUITaotw | b374ef1f | windows_path_task | 3 | 2 | REWORDED_RETRY x2 (`saipen checkpoint RUN T-1 '...'`, text mentions `.saipen memory`) |
| ses_f500173eaffe77ECIDxoJjYWhL | a8290234 | long_file_task | 2 | 1 | DISTINCT (run `.saipen\kitchen\review_check.py`, then delete it) |

Totals: 11 refusals, 7 consecutive pairs.

- PARALLEL_DUPLICATE: **0**. No pair shared an assistant step; every second call
  started after the first refusal completed (smallest gap 2 613 ms).
- SEQUENTIAL_EQUIVALENT_RETRY (identical effect): **0**.
- SEQUENTIAL_REWORDED_RETRY (same canonical operation, free text changed): **2**.
- SEQUENTIAL_DISTINCT_EFFECT: **5**.
- Route delivered to the model: **0 of 11**. Every host error text was exactly
  `SAIPEN_GUARD_REFUSAL: PROTECTED_CANONICAL_NAMESPACE: the host tool did not execute`.

## The pair SRC-057 asked about (T-1385 smoke, long_file_task)

| field | call A | call B |
|---|---|---|
| message_id | msg_0affff483001BaSWG7V3J61K5T | msg_0b00012d4001LBQ9vALmNltfrr |
| call id | call_00_ET_MXRVw5yBfdWiIzZlzPQW1971 | call_00_M0J85lW8hPxpqyWfwKGI5745 |
| tool | bash | bash |
| attempted | `python "<fixture>\.saipen\kitchen\review_check.py"` | `Remove-Item -LiteralPath "<fixture>\.saipen\kitchen\review_check.py" ...; Test-Path ...` |
| effect fingerprint | 605243dd7e72b048 | d9e9691236d53dd1 |
| call start / refusal end (ms) | 1789659183918 / 1789659184076 | 1789659192725 / 1789659192880 |
| assistant step created / completed | 1789659182211 / 1789659184254 | 1789659189972 / 1789659193069 |
| parent message | msg_0affe8c50001lt4L3spW9q2dOq | msg_0affe8c50001lt4L3spW9q2dOq |
| canonical position | 10 canonical successes before (LOG E-11, phase REVIEW, T-1) | 10 (unchanged) |
| canonical_next_command reaching the model | none | none |

Between them the session ran two steps: it wrote the same script to
`V:\_TEMP_\opencode\saipen_review_check.py` and ran it successfully. Call B was
issued 8 649 ms after refusal A was observable and attempted a different
effect. It is neither CASE A (parallel) nor CASE B (an equivalent retry).

## What this proves

1. The polygon scored distinct effects as one refusal repeating because the
   OpenCode adapter's terminal-code branch threw a constant sentence with no
   `attempted:` identity -- the defect T-1380 fixed only for the other branch.
2. T-1385's first-slice route could not have influenced any session: the same
   branch dropped `next:`. The smoke's improvement in `captured_unprojected` and
   `windows_path_task` was not caused by the route.
3. One real sequential carousel exists in this evidence (b374ef1f
   windows_path_task): a canonical checkpoint whose prose mentions `.saipen` is
   judged as an ordinary shell line and refused. It reproduces on current bytes
   (`neighbor-probe.txt`) and is not the routeless-refusal class.
4. The T-1385 smoke pair comes from a surface asymmetry: the write tool may
   create `.saipen/kitchen/<file>` and the shell may then neither run nor delete
   it. Also reproduced on current bytes (`neighbor-probe.txt`).
