# T-1858 — AC-01..AC-04 closure with measured AC-03

Measured 2026-10-30 by saipen-cli. No engine source was modified for this ticket;
the title operation was already complete and the remaining clause was an
observation, not an implementation. This report records what was executed.

## The title operation is already complete

`saipen status --json` reports `SRC-289 -> SRC-290 APPEND active: 1`.
`saipen source status SRC-290` reports `status: ACTIVE`, `amends: SRC-289`,
`linked_work: T-1858`. The journal carries both halves:

- `E-17340` — append SRC-290 to SRC-289 received (seq 1, APPEND/implementation)
- `E-17342` — append SRC-290 to SRC-289 projected into T-1858: 1 clause(s),
  created T-1858, no rewind

Nothing further is needed for the title operation.

## AC-01 [INTEGRATION]

`cc`, `saipen continue`, `continue` and `cc all` preserve the existing goal and
the same bounded authorization semantics.

Covered by `tools/test_t1858_valve_guidance.py`
(`test_native_resume_spellings_are_equivalent_without_weakening_hard_wait`,
`test_all_modifier_resumes_the_existing_goal_with_real_origin`,
`test_all_modifier_cannot_supply_operator_authority`). The tests assert
`goal_tickets == 0`, `execution_intent == "goal"`, `safety_valve_mode == "hard_wait"`
for each spelling, and that `cc all` alone is refused `RECONCILE_REAUTH_REQUIRED`
with STATE/BOARD/LOG byte-identical afterwards.

## AC-02 [UNIT]

Model-issued or forged input never resets `hard_wait`.

Covered by `test_automation_keeps_hard_wait_and_exposes_the_missing_input`,
`test_bounded_reset_refusal_names_missing_native_ingress` and the forged-carrier
cases in `tools/test_operator_ingress_matrix.py`. Measured live in this session:
the agent's own turn leaves `safety_valve_mode: hard_wait` and
`continuation_authority: operator_required` unchanged.

One correction, because the first draft of this report overstated it: calling
`goal_authority.reset_authority(root, state)` in *this* project returns
`{"mode": "reauthorize", "source": "protocol_home"}`, not the `"wait"` answer,
because this repository *is* the protocol home and that branch is checked first
(`goal_authority.py:508`). The `{"mode": "wait", "required_ingress":
"operator_carrier"}` answer is what a NON-protocol-home project receives, which
is exactly why `test_bounded_reset_refusal_names_missing_native_ingress` patches
`protocol_home` to `False` before asserting it. AC-02 is about forged input never
clearing `hard_wait`, and that is what the unit tests measure; the protocol-home
short circuit is a separate, intended route and is not forged input.

## AC-03 [LIVE] — measured satisfied

The clause names *the reported FastPrompter and ZAICODE native UI*. That root is
`V:/___VAC/__K/__CODE/_PY/_FastPrompter`, and the evidence is durable there, not
in this project's ingress store. The earlier block called AC-03 unobservable
because it inspected only `.saipen/cache/ingress` of this repository.

Four conjuncts, each measured:

1. **Genuine operator ingress through the native UI.** 9 `operator_carrier`
   records, every one `declared_by: host_ingress`, `host: zaicode`,
   project-bound to `_fastprompter`, MAC-bearing across three broker
   generations. Newest `2026-10-29T22:23:57Z` sealed by the current generation
   `cf193f57`. See `fastprompter-ingress.json`.

2. **Bound to the actual event/session/worker.** `saipen-guard.py` writes
   `envelope["operator_origin"]` only when `issue_operator_origin` **and**
   `register_operator_worker` both answer `ok`, and `register_operator_worker`
   takes `os.getpid()` — the hook process itself, which the broker accepts only
   as an observed child of the proven native host. The presence of
   `operator_origin` therefore proves the whole seal, including the worker
   binding. All 9 records carry `session_id: sess_389151f2-976c-46f2-…`.

3. **Bound to the budget, and canonically renewed.** The carriers at
   `17:43:37`, `17:44:07` and `17:44:10` carry `budget: E-4436`, and journal
   `E-4436` (28.10 17:44, op `valve-400ece91`) records:
   `DEC: goal reauthorized -- goal_waves 0->0, goal_tickets 20->0; authority_source operator_carrier`.
   The string `operator_carrier` in that position has exactly one writer,
   `goal_authority.py:513`, reachable only through `fresh_cc_provenance()` →
   `authority_for_provenance(...)["reset_bounded_authority"]`, which requires the
   broker to verify the origin. Its single caller,
   `operations.py:23290`, renders that exact DEC text. `protocol_home()` is
   `False` for that root, so the protocol-home short circuit is excluded and the
   renewal could not have come from that route.

4. **Canonical eligible Work resumed.** `E-4437`/`E-4439`/`E-4441`/`E-4447` and
   later `E-4620`/`E-4626` show tickets advancing and closing in the same
   project, most recently at 07:14 today. See `fastprompter-journal.json`.

A disposable broker double cannot produce `E-4436`: that line is written by the
engine's own valve path from a `reset_authority` verdict that only a
broker-verified carrier yields, and the carrier files are HMAC-sealed by the
live broker's keys.

## AC-04 [INTEGRATION]

An absent trusted ingress is named as the real infrastructure boundary, with no
false promise that only a bare `cc` spelling will fix it.

Covered by `test_bounded_reset_refusal_names_missing_native_ingress`, which
asserts `required_ingress == "operator_carrier"`, `canonical_next_command is None`
and an `operator_action` naming authenticated native ingress. This is also what
the plugin double in that test says, matching `SRC-293`'s own analysis: the
carrier is a property of the host adapter, not of the command's spelling.

## Test runs

`python -B -m unittest tools.test_t1858_valve_guidance -v` → 9 tests OK in 5.062s.
`tools/test_operator_ingress_matrix.py` clause M pins the
carrier→`reset_authority`→`operator_carrier` step this report relies on.

## Files

| file | content |
|---|---|
| `fastprompter-ingress.json` | all 9 operator_carrier records with origin, budget, kid, mac presence and per-file sha256 |
| `fastprompter-journal.json` | E-4436 renewal line, six resumption lines, and the LOG sha256 they came from |
| `REPORT.md` | this document |
