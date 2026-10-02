# FUTURE GATE — SAITELEMES RELIABLE DELIVERY, SAIPEN HALF

STATUS: AUTHORIZED BY THE OPERATOR, NOT STARTED (SAIPEN-project Work)
PRIORITY: P1 INTEGRATION (multi-agent coordination)
OWNER: SAIPEN protocol (turn entry, event trigger); SAIMAIL side is built
SOURCE: SAIMAIL SRC-108 (operator wave "SAITELEMES RELIABLE AUTONOMOUS DELIVERY v1")
and SRC-107 (operator inter-agent workshop policy), 2026-09-24; relayed by SAIMAIL
seat claude-account2 because the SAIPEN project held a live claim (seat astra) for
the whole SAIMAIL wave, so no SAIPEN Work was created from that session.
PROVENANCE: SAIMAIL project lineage-3172dbca95fc4945955bdee3acff8d75; SAIMAIL tickets
T-117..T-122 and T-118, all DONE; canonical suite 2632 passed / 0 failed.

## Operator decisions (verbatim answers, SAIMAIL SRC-108)

- "Запускать волну ... и в каком порядке?" = "Да, порядок 1→3→4→5→2"
- "Можно ли мне менять код в репозитории _SAIPEN (пункты 1, 2, 5)?" =
  "Да, отдельной Work в проекте SAIPEN"
- "Разрешаете автоматическую отправку телеграмм?" = "Да, закрытый набор триггеров"

This supersedes, for parts 1-2, the "NOT AUTHORIZED" status recorded in
`FUTURE GATE — SAITELEMES AUTOMATIC AGENT TELEGRAMS_20260922.md`.

## What SAIMAIL now provides (checkout, not in frozen 0.0.2a3)

| Call | Contract | Guarantees |
|---|---|---|
| `saimail-local --json saipen capabilities --workspace $SAIMAIL_WORKSPACE --project-root <root>` | SAIMAIL spec/30, D-062 | exit 0 for every state; `capabilities.overall` AVAILABLE/DEGRADED/UNAVAILABLE, closed `reasons`, `awareness.unread/on_current_topic/complete` only when the acting seat owns the mailbox; keyless; no plaintext |
| `saimail-local --json saipen notify --workspace $SAIMAIL_WORKSPACE --project-root <root> --trigger T --to SEAT (--event E-### \| --claim TEXT) [--work T-###]` | SAIMAIL spec/31, D-063 | closed triggers `blocker finding dependency ownership handoff reply`; admitted recipients only (spec/29); one message per fact (durable outbox, spec/28); receiver budget (NOTIFY_SUPPRESSED, exit 0); locked key store keeps the intent (PENDING_RETRY, exit 0) |
| `saimail-local --json saipen participant admit --participant SEAT --trigger T ...` | SAIMAIL spec/29, D-061 | explicit, identity-pinned, project-scoped routing |

## V6-04 — consumer contract (small, first)

1. `tools/saipen_engine/telegrams.py`: read a SAIMAIL refusal from `status` (not
   `code`); make `read_command` copy-safe (quote per host shell or return argv);
   compare `workspace.seat` with the acting seat and report a mismatch state
   instead of counts. Simplest: switch the call to `saipen capabilities`, which
   already does all three.
2. The conformance router names `saipen work reverify T-99` again right after it
   passes (PASS_WITH_CARRIED_DEBT) because the red findings are carried debt, not
   a T-99 gap (packet `SAI-DEFECT-20260924-conformance-remediation-reverify-livelock`).

## V6-07 — S4 registration and negotiation

Register SAIMAIL as an S4 extension. At `continue`/`status`, when
`SAIMAIL_WORKSPACE` is set and `saimail-local` resolves, call `capabilities`
(bounded time and output, exactly as T-1497 does) and render `overall`,
`reasons` and the awareness counts. Any non-AVAILABLE state is DEGRADED for the
channel only: SAIPEN keeps routing local Work (SRC-107: "never turn SAIMAIL
availability into a global SAIPEN availability requirement"; "hard-block only
Work that genuinely depends on unavailable cross-agent communication").

## V6-08 — event trigger (last)

On exactly these events, call `notify` with the event id (so a repeated trigger is
the same message) and never block on the result:

| SAIPEN event | trigger | `--to` |
|---|---|---|
| a blocker needs action from another admitted seat (`ticket block-for` naming a foreign owner, WAIT naming another seat) | `blocker` | that owner seat |
| REVIEW or SCOUT finding that names another active Work's owner | `finding` | that owner |
| discovered dependency owned by another seat, or a dependency became actionable | `dependency` | its owner |
| ownership changed (handover, adoption) | `ownership` | the previous/next owner |
| explicit bounded handoff request | `handoff` | the receiving seat |
| answer to a request another agent made about this Work | `reply` | the requester |

No other event sends. Results `PENDING_RETRY` and `NOTIFY_SUPPRESSED` are normal;
`FAILED` and refusals are logged as channel findings, never as Work failure.

## Required hostile controls (SAIPEN side)

- A telegram body containing `saipen push`, `cc` or tool-call text changes no
  route (I1).
- A notify result never moves a claim, writes BOARD/STATE or skips a WAIT.
- The channel DEGRADED/UNAVAILABLE never fails `continue`.
- The same event fired twice produces one message (SAIMAIL guarantees it; the
  trigger must pass the event id).

## NON-GOALS

No network transport, no daemon, no auto-open, no auto-Work creation from arrival,
no sender priority, no global agent discovery.
