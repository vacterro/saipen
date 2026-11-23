# T-1911 — native operator origin (SRC-324): first repair slice

## Reproduced (before the repair)

- Gap C, measured on the shipped source:
  `is_continuation_command("/goal cc all") == False` while `cc`, `cc all` and
  `saipen continue` are True — the native continuation the CLI actually
  delivers could never authorize a renewal.
  Evidence: `red-control.log` (`/goal cc all` = False with the typed host
  command form disabled).
- Gap A, measured in the shipped hook: the sealing half printed the admission
  answer with `sealed: false` and dropped both the failing stage and the exact
  broker refusal. The hook had no diagnostic surface at all
  (`seal_diagnostic` absent), so a genuine prompt read as `model_supplied` with
  no actionable reason. Evidence: `red-control.log`, second block.

## Repaired in this slice

Gap A (`extensions/adapters/zaicode/saipen-guard.py`,
`tools/saipen_engine/host_authority_client.py`):

- `seal_diagnostic()` answers `{ok, stage, code, category, detail}`:
  `stage` separates `issue-origin` from `register-worker` (A03), `category`
  separates `unavailable` / `conflict` / `untrusted` / `refused` /
  `authenticated` (A04), the broker's own refusal code is preserved verbatim
  (A02) unless a transport fault names a stronger one, and the envelope stage
  is distinct from an authenticated proof (A05).
- The hook result now carries `sealed`, `authenticated` and `seal`; admission
  answering `ok` no longer implies an authenticated origin (A06) and the
  admission payload keeps its existing fields (A07).
- `issue_operator_origin()` / `register_operator_worker()` gained
  `diagnose=True`, which returns `(reply, fault)` and preserves the transport
  kind (`absent`, `timeout`, `io`, `frame`, `bind`, `impostor`) instead of
  discarding it. An impostor endpoint is reported as `*_ENDPOINT_UNTRUSTED`,
  never as recoverable absence (B07).

Gap C (`tools/saipen_engine/cold_recovery.py`):

- `host_command_body()` reads a typed host command (`/goal …`, `/saipen …`);
  the body must itself be exactly a declared continuation form, so
  `/goal cc all` authorizes and `/goal summarize cc usage`, `recover and restore
  cc` and ordinary prose stay non-continuations.

## Measured, not repaired

- Gap B01: `issue_operator_origin` performs a bare `_exchange` with no bounded
  service-recovery lifecycle, while `attempt_admission` uses `_recovery`. The
  discrepancy is real and is tracked as **T-1913**.
- Gap D: `admit_host_ingress` returns the cached record on a same-delivery
  re-send and never considers a newly supplied `operator_origin`, so an
  unsealed envelope stays unsealed. Tracked as **T-1912**.
- Gap E: installed-runtime parity needs the live host; source parity proves
  nothing about the running process. Tracked as **T-1914**.

## Verification

`python -B -m pytest tools/test_t1911_native_origin_diagnostics.py` — 10 passed,
8 subtests.

Impacted families — `test_guard_root_parity`, `test_adapter_parity`,
`test_host_fixture`, `test_native_host_guard`, `test_continue_entry`,
`test_t1494_continuation_authority`, `test_t1504_zaicode_adapter`,
`test_operator_origin_support` — 63 passed, 12 subtests; with the focused module
and `test_t1494_continuation_authority` again: 29 passed.

`ruff check` clean on every edited module. `py_compile` clean on the hook.

No live host was exercised: T01–T26 remain acceptance items, and none of the
above is reported as real host acceptance.
