# TEST-5 -- HUNT-12 independent reproduction

Source: `3a343e8d0e5a04e2cb43b671c9072996e810c65a` / `git-delta-v1:188e314f78fa94f6e953b760887e106af6910f2a2cc35af91b4f97f081e63b47`

## Scenario A -- closure evidence

- Command: `python tools/validate.py`
- Observed: exit 1; T-1100 has no current-cycle VERIFY boundary.
- Verdict: REPRODUCED.

## Scenario B -- admission contract parity

- Command: `python tools/validate.py`
- Observed: exit 1; improve admission mechanical contract tokens are missing after formatting.
- Verdict: REPRODUCED.

## Scenario C -- locale parity

- Command: `python tools/validate.py`
- Observed: exit 1; exactly 32 locale README badges are stale.
- Verdict: REPRODUCED.

## Scenario D -- warning ownership

- Command: `python tools/validate.py`
- Observed: exit 1; `log-soft-cap` has no live BOARD owner after 90 releases.
- Verdict: REPRODUCED.

Control: `python -m ruff check tools` exits 0.
