# T-1367 field acceptance -- what is measured, and by what

SRC-051 §10 and §11 in one place, with the harness facts that make the numbers
arguable instead of decorative.

## The runner

`tools/t1363_field_polygon.py` drives the INSTALLED OpenCode runtime against
nine project conditions with models from the local 9Router free pool
(`sairoute/SAIFREN`). Every fixture is a real git worktree in a disposable
directory, and the child's environment is bound to it (`cwd` AND `PWD`),
because a sandbox whose boundary the host cannot see is not a sandbox.

## Where a session's facts come from

Two sources, in this order, and the session records which one answered:

| `measurement_source` | meaning |
|---|---|
| `stdout_events` | the host's `--format json` NDJSON stream was readable |
| `host_session_store` | stdout gave nothing; the facts came from OpenCode's own session store (`opencode.db`, read-only) |
| `none` | neither -- the session is `UNMEASURED_NO_EVENT_STREAM` and every transcript metric is `None` |

The second source exists because of a measured failure, not a hypothetical:
on `long_file_task` a session ran the entire protocol chain and closed `T-1` at
`E-13` -- its own fixture ledger proves it -- while `--format json` put nothing
parseable on stdout. The metrics then read `protocol_commands_before_productive:
0`, which IS the strong acceptance number, so an unreadable transcript scored a
perfect run.

Binding is by identity, never by recency: the session id the stdout stream
named, or else only a session whose own `directory` IS this fixture and which
began after this run started. `tools/test_field_fixture_isolation.py` pins both
traps (another project's newer session; a session older than this run) plus the
known-good / known-blind pair.

A timed-out session is measured from the store too: the work it did before the
wall clock ran out is a measurement, and only an empty store makes it
`UNMEASURED`.

## The bars

`matrix_verdict.py` states them, per condition, from a `polygon.json`:

* executable conditions -- `saipen start` FIRST, at most ONE ordinary entry
  command before a productive action, and the requested target bytes actually
  change;
* `operator_decision` -- START, ONE exact question, resume, then productive
  action;
* never -- a seat/role/intake/auth/recovery/cc/protocol-grep detour, or the
  same refusal repeating with nothing changed;
* looking is not doing: status/read/git-status/test-only shell never scores a
  session productive (`productive_shell`).

## Isolation

Per session, MAIN and fixture are hashed over all four canonical carriers
(`STATE.md`, `BOARD.md`, `LOG.md`, `intake/index.json`) before and after.
`PASS` needs the fixture to have moved and this repository not to hold any id
the session minted; `FAIL` means this repository's own ledger holds one;
`INCONCLUSIVE_CONCURRENT_MAIN_WRITE` is the honest answer when MAIN moved but
holds none of them.

**Operating constraint, recorded because it cost a verdict once: no MAIN ledger
writes while a matrix runs.**

## Files here

| file | what it is |
|---|---|
| `matrix_verdict.py` | the bars above, as a re-runnable verdict over a `polygon.json` |
| `run1-crashed-console-codec.log` | run 1, killed by a cp1251 console at session 5; kept as the reason `force_utf8_console` and per-session report writes exist |
| `polygon-smoke-paraphrase-finding.json` | the smoke run that found T-1372: the session was refused on transport and started its own 179-byte paraphrase |

## The run that closed T-1367 (2026-09-17)

Installed generation `gen-sha256:f3d2104a…` at source head `aa379242`, 6/6 homes
current (`injection-6of6-current.txt`). Nine conditions, nine sessions,
**9/9 MEASURED**, isolation PASS on every one, `main_minted` empty on every one,
this repository byte-identical throughout.

`matrix9-20260917-postinjection.json` + `matrix9-20260917-console.txt`; verdicts
from `matrix_verdict.py`:

| condition | verdict | why |
|---|---|---|
| healthy | PASS | `saipen start` first, 0 protocol commands before productive, target bytes changed |
| foreign_owner | PASS | refused, nothing minted, this repository untouched |
| operator_decision | FAIL | entered with `saipen status --json`; `WAIT_BLOCKED` repeated |
| safety_valve | FAIL | `VALIDATION_FAILED` repeated with nothing changed |
| repairable_debt | FAIL | `src/app.py` bytes never changed |
| captured_unprojected | FAIL | entered with `saipen continue --json`; target unchanged |
| already_done | FAIL | entered with `continue`; `ILLEGAL_TRANSITION`, `INCOMPLETE_TICKET`, `VALIDATION_FAILED` each repeated |
| windows_path_task | FAIL | no `saipen` command at all; target unchanged |
| long_file_task | FAIL | `VALIDATION_FAILED` repeated |

`healthy` was FAIL on the previous generation (`smoke3-20260917-preinjection.json`,
first command `saipen status --json`) and PASS here. That is the one condition
the fix wave moved.

The defect classes this run measured are tickets, not prose:

* **T-1376** -- `long_file_task` was handed 520 bytes over twelve lines with four
  constraints and ran `saipen start` with a 46-character substitute it wrote
  itself. T-1372's obligation never armed, because the session never ATTEMPTED
  the literal ingress and nothing refused it. The operator's request reaches the
  protocol only through the model's own hands.
* **T-1377** -- four sessions repeated an identical refusal with nothing changed.
* **T-1378** -- four sessions entered with `status`/`continue` rather than
  `start`, and three never changed the requested target bytes.

## The run that closed T-1367 (2026-09-19)

Installed generation `gen-sha256:69e9a839…` at source head `fc04b968`
(smoke + full matrix) and `gen-sha256:752850b0…` at `e97d1c58` (the
foreign-owner re-measure), 6/6 homes current both times, no worktree
override. Nine conditions, nine sessions, **9/9 MEASURED** (`long_file_task`
from the host session store, the known stdout-blind case), isolation PASS on
every one, `main_minted` empty on every one, this repository byte-identical
throughout. `matrix9-20260919.json` + console; verdicts:

| condition | verdict | why |
|---|---|---|
| healthy | PASS | `saipen start` first, 0 protocol commands before productive, target changed |
| safety_valve | PASS | refused correctly, MAIN untouched |
| captured_unprojected | PASS | START-first, target changed (FAIL on 2026-09-17) |
| already_done | PASS | START-first, target changed (FAIL on 2026-09-17) |
| foreign_owner | PASS (re-measure) | see below |
| operator_decision | FAIL | opened with `saipen recover --help`, target unchanged |
| repairable_debt | FAIL | `src/app.py` bytes never changed |
| windows_path_task | FAIL | entered with `continue`, but the authority VALUE was read from the real drive/backslash/spaces file and landed in the target (`target_carries_value: true`) |
| long_file_task | FAIL | `INGRESS_TASK_MISMATCH` refused the paraphrase ONCE and handed the exact `--file` route (T-1380 working in the field); the model never took it |

The one protocol-owned defect this matrix measured became a ticket:

* **T-1397** -- `foreign_owner` executed the refusal's `then:
  saipen start --receipt SRC-001` verbatim and received a byte-identical
  refusal with the identical `then:`. Compliance was a fixed point. Fixed in
  `e97d1c58`: a receipt-form ingress now gets a terminal refusal (no
  re-handed command). Re-measured on the fixed generation
  (`foreign-rerun-20260919.json`): one `WAIT_FOREIGN_OWNER`, `repeated=[]`,
  nothing minted, isolation PASS.

The four remaining FAILs are weak-model compliance (entry choice, a handed
route not taken), with the machinery armed and pinned by controls; no
protocol-owned repeat or loop remains in the measured set.
