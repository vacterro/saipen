# T-1377 -- a refusal that changes nothing about the next attempt

## What was measured

2026-09-17, installed generation `gen-sha256:f3d2104a…`, the nine-condition
field matrix: four of nine sessions repeated an identical refusal with nothing
changed. The payloads, read back from OpenCode's own session store rather than
from the models' prose:

| session | repeated | what the payload said |
|---|---|---|
| `already_done` | `ILLEGAL_TRANSITION` | `SCOUT -> VERIFY is not a legal edge`, then `BUILD -> REVIEW is not a legal edge` |
| `already_done` | `INCOMPLETE_TICKET` | `VERIFY -> REVIEW requires explicit verification evidence for ticket T-8301 (got: unproven/failed)` |
| `already_done`, `safety_valve` | `VALIDATION_FAILED` | `--paths is only valid with closure_mode cohort, not own_patch`; `checkpoint ticket_id 'T-8301 build -> …' is not a valid T-### ref` |
| `operator_decision` | `WAIT_BLOCKED` | `the saipen guard refused tool 'bash'; the host tool did not execute` — no reason, no route |

Every one names the rule. Not one names the move. SRC-051 §11 forbids exactly
this, and this repository's own agent hit the verification-evidence sentence
twice in one session while writing T-1372 — the defect is not a weak-model
problem, it is a payload problem.

## What each refusal carries now

* **ILLEGAL_TRANSITION** — the legal edges out of the phase the project is
  actually in, plus `saipen transition <edge> <T-###> '<why>'`.
* **verification evidence**, at both sites (`VERIFY -> REVIEW` and `ticket
  done`) — the checkpoint SHAPE the gate accepts:
  `saipen checkpoint RUN <T> "verify -> PASS [target: <T>] conf: high -- …"`.
* **checkpoint ticket ref** — the form, and the sentence that explains the
  mistake: the ticket comes BEFORE the text.
* **closure grammar** (`--paths`, `--closure-cohort` with the wrong mode) — the
  corrected `saipen ticket done` line, lifted into the machine field.
* **WAIT_BLOCKED** — the brake's own detail plus the one command that lifts
  that kind of brake: `recover resolve-blocker`, `ticket unblock`, `continue`.

Root cause, not symptom: after T-1379 a finish with no verification evidence
answered `SOURCE_UNRESOLVED`, sending the model to a ledger it cannot edit. When
the only thing awaited is the request's own clause, it answers
`INCOMPLETE_TICKET` with the checkpoint command instead.

## Evidence

| file | what it is |
|---|---|
| `green-post-fix.txt` | the route controls, current bytes; two of them RUN the printed command |
| `red_subject.py` | copies the tree, reverts ONLY the carrying of routes (`_refuse` drops the fields, the brake table empties) |
| `red-final-oracle-vs-pre-fix-subject.txt` | that run: all four route classes red |
| `core-unit-ab-by-identity.txt` | the full family A/B, including the one PATCH_OWNED red this work caused and fixed |
| `verify-adjacent.txt`, `verify-validate.txt` | adjacent families and the validator |

The PATCH_OWNED red is worth keeping in view: the first WAIT route printed
`saipen continue --json   # the persisted WAIT names what it needs`, and
`test_every_printed_command_classifies_as_canonical` refused it — a printed
command has to BE a command. The route is the bare command now.

## The live proof: the repeats are gone

Three live runs of the same four conditions, each on a freshly injected
installed runtime, `repeated_refusal` per condition:

| condition | matrix (f3d2104a) | re-run 1 (c90c61d6) | re-run 2 (caba3969) |
|---|---|---|---|
| `operator_decision` | `['WAIT_BLOCKED']` | `[]` | `[]` |
| `safety_valve` | `['VALIDATION_FAILED']` | `['NO_ACTIVE_WORK','PROTECTED_CANONICAL_NAMESPACE','VALIDATION_FAILED']` | `[]` |
| `already_done` | `['ILLEGAL_TRANSITION','INCOMPLETE_TICKET','VALIDATION_FAILED']` | `['VALIDATION_FAILED']` | `[]` |
| `long_file_task` | `['VALIDATION_FAILED']` | `['VALIDATION_FAILED']` | `[]` |

Re-run 1 is why this ticket has two commits: clearing the first five classes
exposed `saipen ship` in a project with no VERSION (three sessions asked
twice), and the harness itself was scoring three different `VALIDATION_FAILED`
problems as one repeated refusal.

The routes are visible in the live payloads, read back from the host's own
store rather than from the report:

```
WAIT_BLOCKED :: the saipen guard refused tool 'edit'; the host tool did not
                execute next: saipen recover resolve-blocker <decision>
NO_ACTIVE_WORK :: … next: saipen start '<the task, one line>'
VALIDATION_FAILED :: --paths is only valid with closure_mode cohort, not
                own_patch; run: saipen ticket done <T-###> --closure-mode own_patch
VALIDATION_FAILED :: VERSION is missing from the repository root: `saipen ship`
                publishes a versioned release and does not apply to a project …
```

`operator_decision` shows two `WAIT_BLOCKED` refusals in re-run 2 and no repeat:
the payloads differ (`tool 'edit'` and `tool 'bash'`), which is two events, not a
loop. That distinction is the harness half of this ticket.

| file | what it is |
|---|---|
| `field-rerun4-after-routes.json` | re-run 1, the first five classes routed |
| `field-rerun4b-after-second-wave.json` | re-run 2, all four conditions with an empty repeat set |
