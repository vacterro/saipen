# T-2061 — ZAICODE continuation-authority deadlock: measured investigation

Status: investigation complete; the ticket stays `BLOCKED` because its hold is
`WAIT_USER_DECISION` and only operator authority may lift it. No canonical
STATE/BOARD/LOG write was attempted for T-2061 or for the `_ZAICODE` project.
T-540 ownership is untouched.

- measured: 2026-11-17, SAIPEN repo HEAD `dc39709c`, installed home 8.1.0
- engine that produced every status projection below: the installed engine
  `C:/Users/vac34/AppData/Local/saipen/scheduled-source` (the canonical one)

## 1. The live ZAICODE project state (read-only projection)

`saipen status --project-root V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_ZAICODE`

```
phase: DONE                      task: none
next_action: saipen continue     computed_next_action: saipen audit status
computed_reason: audit-inbox-unworkable
execution_intent: goal           continuation_authority: operator_required
authority_source: E-8390         authority_until: budget
safety_valve_mode: hard_wait     top_workable_ticket: null
```

`saipen audit --project-root …/_ZAICODE`: pending 2, no workable ACTIVE/NEW
layer, `NO_ADMISSIBLE_WORK`, route `saipen audit status`. So the audit inbox is
not the way out either.

## 2. Why a fresh `cc` cannot renew it (root cause: the fix is not installed)

`goal_authority.py` (`bounded_resume_requirement`, `reset_authority`) is
deterministic: a budget-exhausted goal needs either persistent proof (fails),
`protocol_home` (false: `_ZAICODE` is a managed project, not the protocol
home), or a witnessed `operator_carrier` via `fresh_cc_provenance`. An agent
CLI replay cannot supply that witness.

The witness path itself is broken in the installed generation. The T-2066
repair (five host-ingress defects, DONE with an engine-measured FAIL→PASS pair
`.saipen/evidence/regression/regression-execution-5a4171eb…json`) is present in
this repo and green:

- `python -m pytest tools/test_t2066_zaicode_host_policy.py -q` → **15 passed** (3.10 s)
- repo policy: `{"host_images": ["zaicode.exe","ZCode.exe"], "host_signers": [],
  "bridge_images": [], "max_shells": 0, "max_bridges": 0}`

It is absent from the installed generation:

| subject | repo sha256:16 | installed sha256:16 |
| --- | --- | --- |
| `saipen/REGISTRY.json` | `0bb482ca54f6ef93` | `afb5e63b9659f742` |
| `tools/saipen_engine/host_authority_broker.py` | `8e7dff652e47d5ef` | `9049c4b81585e57b` |
| `tools/saipen_engine/host_authority_client.py` | `98d9da9d4080d657` | `8a883702a6083fcd` |
| `tools/saipen_engine/operator_origin.py` | `9e803ef6580c9368` | `687b4f54afb2a7a0` |
| `tools/test_t2066_zaicode_host_policy.py` | `7d93882c2e9fd3b6` | ABSENT |

Installed policy is the older partial one:
`{"host_images": ["zaicode.exe"], "host_signers": []}` — no `ZCode.exe`, no
rendered zero bounds. `int_setting` (the explicit-zero repair) is absent from
the installed broker.

The live hook surface confirms the same gap, read-only:

`python tools/install_host_guard.py zaicode --check`

```
installed: true   current: false   configured: false
problems: ["config-entry-differs", "delegated-root-stale"]
effective: ENFORCEMENT_GAP
saipen_root: C:\Users\vac34\AppData\Local\saipen\scheduled-source   root_current: false
artifact: C:\Users\vac34\.zcode\hooks\saipen-guard.py
config:   C:\Users\vac34\.zcode\cli\config.json
```

T-2066's own report records the observable incident this produces: a genuine
operator `cc` under the real ZAICODE host is refused at the prompt boundary,
the origin never seals, and the valve stays `hard_wait`
(`.saipen/evidence/T-2066/REPORT.md`).

## 3. Why the agent cannot lift the hold by decision

`operations.py:6753` (`ticket_move`, unblock branch) arms the operator gate
when `unblock_requires_operator(current_blocker)` is true; the head token here
is `WAIT_USER_DECISION` (`operations.py:18228`). Without a verified
`operator_carrier` witness the only other admission is a prose token
(`"authorized by operator"`, `"operator_approved"`, `"live_receipt"`,
`"vendor_session_probe"`). Writing one of those tokens into an agent-composed
decision would fabricate operator authority, which the standing handoff
forbids; it was not done.

Every canonical route to the ticket was then measured (all `--dry-run`, no
writes):

| command | verdict |
| --- | --- |
| `saipen ticket unblock T-2061 "<investigation decision>" --dry-run` | `WAIT_USER_DECISION` — "unblocking requires verified operator authority or authentic proof" |
| `saipen claim T-2061 --dry-run` | `TICKET_NOT_WORKABLE` — "carries a blocker; explicit priority override does not override authorization" |
| `saipen checkpoint DEC T-2061 "…" --dry-run` | `STALE_WORK_CONTEXT` — "STATE.task is 'none' … use `saipen claim` to adopt the ticket first" |

The three refusals close the loop: the ticket cannot be claimed, unblocked or
annotated by an agent while its hold is `WAIT_USER_DECISION`.

Consequence: the deadlock is real and its resolution is an operator action,
not a ticket decision.

## 4. T-540 is not displaced (measured)

`_ZAICODE/.saipen/BOARD.md:230` — T-540 is under `## BLOCKED`, blocker
`EXTERNAL_RESOURCE_UNAVAILABLE`: the shipped artifact has no arbitrary V4
frame publisher or runtime restart control, so the packaged RED/GREEN receipt
cannot execute without a separately scoped E2E producer seam
(`.saipen/evidence/T-540/packaged-receipt.md`). It is not `DOING/BUILD`; this
investigation made no change to it or to the `_ZAICODE` project.

## 5. Exact remedy, in order

1. Publish/install the 8.1.1 generation into `scheduled-source` — the T-2058
   gate A operator decision (`.saipen/evidence/T-2058-release-index/BLOCKED.md`).
   Without it the repo fix cannot reach the live witness path.
2. Refresh the live hook from the now-current root
   (`install_host_guard.py zaicode`), which clears `ENFORCEMENT_GAP`,
   `config-entry-differs` and `delegated-root-stale`.
3. Send one genuine `cc` through ZAICODE native ingress. `fresh_cc_provenance`
   then yields `operator_carrier`, `reset_authority` returns
   `{"mode": "reauthorize", "source": "operator_carrier"}`, and the ZAICODE
   budget resumes.
4. Only then can T-2061 be unblocked and closed, and T-540 worked under its own
   blocker.
