# SRC-126 / audit/18.md per-finding triage (T-1542)

Executed 2026-10-02 against the live tree. The audit ran 2026-09-16 against
source_head `105d3d6`; the tree is now VERSION 8.0.2, so every finding was
re-established against current bytes before any disposition.

| Finding | Verdict | Decisive evidence |
|---|---|---|
| IMP-001 [P1] improve submit refused `NO_ACTIVE_WORK` with an empty DOING board | ALREADY_FIXED | `admission.py:1561` exempts a canonical CLI action (`action_name != "saipen_op"` guard); `improve` is shell-canonical per `command_effects.py:115-117`, so `guard_events.py:1647` sets `action = "saipen_op"`. The CLI improve route itself carries no DOING gate (`saipen.py:8556-8561`). Proven by `tools/test_guard_events.py:704` and `tools/test_src085_improve_run_body.py:102`, and reproduced end to end in a temp fixture: `improve submit` returns `code: COMMITTED` on an idle DONE project while `npm install` still refuses. |
| IMP-002 [P2] improve abort admitted while submit refused — inverse least privilege | ALREADY_FIXED | Same single rule now governs both mutators, so the inversion cannot arise. `saipen/COMMAND_EFFECTS.json` classifies `improve` as EXECUTION with only `status`/`sweep-queue`/`verify` as DIAGNOSTIC. Reproduced: both `submit` and `abort` return `COMMITTED` in the same fixture. |
| IMP-003 [P1] one status payload states two contradictory conformance verdicts | **LIVE — FIXED HERE** | `saipen.py:1790` shipped a LOG-derived `conformance` string (which can read `PASS`) beside the authoritative `conformance_status.status` (which read `STALE_FAIL` in the same fixture). A test at `test_t1412_conformance_truth.py:274` actively PINNED the disagreement, and T-1412/T-1417 had fixed only the human render. The key is renamed `conformance_history`, so no key named `conformance` exists for a consumer to read a verdict from and a reader of the new name knows it is provenance. `tools/saipen.py:1794`, `:7251-7254`; the rewritten assertion is at `test_t1412_conformance_truth.py:284-286` and the new control `test_no_second_route_to_a_conformance_verdict` asserts the payload offers exactly one keyable verdict across every disagreeing fixture. |
| IMP-004 [P1] no canonical verb can write `recurrence:` / `weak_model:` | ALREADY_FIXED | `saipen.py:10828` dispatches `ticket reasoning` to `operations.py:6673 ticket_reasoning`, which validates both texts and writes through `_ticket_fields_in_place` (`:6753`) reaching `board.set_ticket_field` (`operations.py:940`, `board.py:1628`). It refuses `TICKET_REASONING_NOT_LINKED` unless a strict CONFIRMED PROTOCOL_VIOLATION sweep actually names the ticket. Proven by `tools/test_improve_reconcile.py:440`, which drives the validator gate green and back. |
| IMP-005 [P2] no canonical fallback when the host search tool is unavailable | ALREADY_FIXED | `saipen/BOOT.md:57-60` and `SKILL.md:54-58` route to `saipen search --hex`; `search` is DIAGNOSTIC hence shell-canonical, so the guard admits it even on invalid state. `admission.py:1567-1573` names the admitted read-only probe set in the refusal. Proven by `tools/test_search_transport.py:243` and `tools/test_t1402_readonly_reporters.py`. |

## Residual, not dispositioned away

- `NO_ACTIVE_WORK` refusals still carry `canonical_next_command = ENTRY_COMMAND`
  (`admission.py:852`), so the refusal payload itself does not name
  `saipen search --hex`. The route lives in BOOT.md and SKILL.md. This is a
  discoverability gap, not the reported defect, and no ticket names it.
- No single test asserts that `improve submit` and `improve abort` receive the
  SAME guard verdict; they are covered separately (guard level for the
  canonical exemption, CLI level for the commit paths).

## Disposition

Four findings are terminal as already-fixed with the pinning test named:
IMP-001, IMP-002, IMP-004, IMP-005. One was live and is built under T-1542:
IMP-003.
