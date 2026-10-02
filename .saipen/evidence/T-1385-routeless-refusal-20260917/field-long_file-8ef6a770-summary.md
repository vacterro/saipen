# T-1385 targeted field proof -- long_file_task only, gen-sha256:8ef6a770

Runtime: `injection-6of6.txt` -- `autoinject --check` fresh 6 of 6 at
gen-sha256:8ef6a7700119fadc739784102ab96f5f0a38a0994912d45a0be96f9bd3c59402,
stale 0, every home's runtime generation equal to the source's expected
generation, loaded plugin `~/.config/opencode/plugins/saipen-guard.js` byte-equal
to `extensions/adapters/opencode/saipen-guard.js`. Model `sairoute/SAIFREN`.
Only `long_file_task` was driven; the nine-condition matrix was not run.

Two sessions were driven. Both are reported.

## Run 1 -- `field-long_file-8ef6a770/`

- fixture `V:\_TEMP_\t1363-0qv1tf08`, session `ses_f4fe0700fffegneEjOQ5Wi7yMg`, 41.5 s, 19 tools
- isolation PASS; repository canonical carriers unchanged; nothing minted in the main ledger
- `--file` authority preserved: SRC-001 witness `operator_carrier`, declared by
  `SAIPEN_TASK_FILE`, body carries LONG_TASK byte for byte
- refusals `NO_ACTIVE_WORK`, `INGRESS_TASK_MISMATCH`; `repeated_refusal: []`; zero PCN
- **target NOT changed.** The model read `src/app.py` (6 bytes, `code`) and stopped
  by its own choice: "Docstring would be fabrication." No SAIPEN refusal caused
  the stop. This run proves nothing about PCN and does not meet target mutation.

## Run 2 -- `field-long_file-8ef6a770-run2/`

- fixture `V:\_TEMP_\t1363-u10tl71f`, 178.6 s, 62 tools
- isolation PASS; repository canonical carriers unchanged; nothing minted in the main ledger
- `--file` authority preserved: SRC-001 witness `operator_carrier`, task file equals LONG_TASK
- target changed: `src/app.py` is now `"""Application entry point."""` above the original
  `code`; T-1 reached DONE at fixture E-12 through SCOUT, BUILD, VERIFY, REVIEW, SHIP
- refusals `NO_ACTIVE_WORK`, `INGRESS_TASK_MISMATCH`, `PROTECTED_CANONICAL_NAMESPACE`,
  `INCOMPLETE_TICKET`, `VALIDATION_FAILED`, `VALIDATION_FAILED`; `repeated_refusal: []`

The one PCN refusal, read from the host store (`pcn-causality/rerun-2-long_file-8ef6a770.json`):

| field | value |
|---|---|
| call | `call_00_hUd3rV82vgpkekyjPeSr4978` in `msg_0b022753a001Q47sdRLbtNk9cO` |
| attempted | `git -C <fixture> remote -v; ...; Get-ChildItem ... -notmatch "\.git\\|\.saipen\\"` |
| host error text | `SAIPEN_GUARD_REFUSAL: PROTECTED_CANONICAL_NAMESPACE: the saipen guard refused tool 'bash'; the host tool did not execute attempted: git -C ... next: saipen next --json` |
| route delivered | yes |
| next bash call | `saipen next --json` -- the exact route string (one `read` in between) |
| after that | `git remote -v; git branch -a; git status --porcelain=v1 -uall` -- the same inspection without the `.saipen` segment, admitted |
| PCN again | never |

Against SRC-057 section 7: the original double PCN was sequential (see
`pcn-causality/VERDICT.md`), and the sequential `repeated_refusal` is `[]` in both
runs. Target mutation, `--file` authority and isolation hold in run 2.
