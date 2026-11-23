# T-1378 -- the runtime's own answer did not agree with its own entry table

## What was measured

2026-09-17, nine-condition matrix. Four of nine sessions opened with a probe
rather than the entry command:

| condition | first `saipen` command |
|---|---|
| `operator_decision` | `saipen status --json` |
| `captured_unprojected` | `saipen continue --json` |
| `already_done` | `saipen continue --json` |
| `windows_path_task` | none at all |

And what those probes answered, reproduced afterwards in a fixture launched
with a declared task:

```
status   -> next_action: "saipen continue"
continue -> IMPROVE_AUDIT_ASSIGNMENT
```

A session that had just been handed a user task was pointed at `continue`, and
`continue` routed it into an improvement audit.

## The finding

BOOT's entry table is right for all nine conditions, `captured_unprojected`
included: `saipen start` de-duplicates onto an existing receipt, so starting the
task it was given is the correct move even when the receipt already exists. The
ticket allowed either fixing the runtime or correcting the table; the table
needed no correction.

What was wrong is that the project could not know a task existed. It can now —
REQUEST-PROVENANCE-01's carrier declares it — so when a carrier names a task and
no receipt here holds those bytes, both diagnostics answer with the entry
command:

```json
"canonical_next_command": "saipen start '<the task you were given, one line>'",
"unstarted_operator_task": {"digest": "…", "declared_by": "SAIPEN_TASK_SHA256"},
"entry_hint": "this session was launched with a task this project has not taken;
               BOOT's entry table routes a new actionable task to `saipen start`"
```

With `SAIPEN_TASK_FILE` the route names that transport instead:
`saipen start --file <path>`.

The hint goes quiet the moment the task becomes a receipt here, is absent for
every session that declares nothing (most of them), never decorates a refusal,
and never overwrites a route a payload already carries. Each of those is a
control, because a hint that never stops is noise and noise is ignored.

## What this ticket deliberately did NOT do

Three sessions never changed the requested target bytes, two of them while
scoring a productive edit — they edited something else. Proving that "the
target" changed requires knowing which file the target is; the harness knows
(it hands out the task) and the protocol does not. The matrix bar measures it
per session and no protocol gate was invented for it.

## Evidence

| file | what it is |
|---|---|
| `green-post-fix.txt` | 9 controls, current bytes |
| `red_subject.py` | copies the tree, reverts ONLY `unstarted()` to answer None |
| `red-final-oracle-vs-pre-fix-subject.txt` | that run: the diagnostics stop naming the entry command |
