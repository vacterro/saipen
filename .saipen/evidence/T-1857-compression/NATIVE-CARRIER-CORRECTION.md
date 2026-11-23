# Undeployed native candidate: inherited carrier correction

The existing `native-carrier-red.log` proves that the fresh-input test failed: the proposed spawner inherited the old process environment instead of binding the worker to the new request and session. The candidate now removes `SAIPEN_TASK_FILE` and supplies the fresh request digest as `SAIPEN_TASK_SHA256`, plus the accepted native `SAIPEN_HOST_SESSION`, in the child environment. It does not create an origin proof or bypass the separated broker.

Command: `python -B .saipen/evidence/T-1857-compression/test_native_delivery_candidate.py`
Result after this candidate-only change: 8 tests, 0 failures, exit 0 (2026-10-23, Europe/Tallinn). The previous 7-test candidate pass preceded the new carrier control and cannot substitute for it.

Scope: `.saipen/evidence/` scratch candidate only. No product file, installed host callback, broker identity policy, or native LIVE acceptance changed. T-1858/T-1859 and T-1854 remain open.

The disposable OS-process control `test_native_process_candidate.py` then exposed open stdin/stdout/stderr pipes after registration refusal (ResourceWarning on the first run). The candidate now closes all three pipes on both success and failure while `ProcessTree` retains child termination ownership. Its real-child controls pass 2/2, including PID equality, fresh environment, no packet before accepted registration, refusal revocation and reaped child. The existing port controls remain 8/8 green. These are fixture/broker-double results, not deployed native acceptance.
