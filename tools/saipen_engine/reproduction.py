"""Audit reproduction truth: the defect predicate, never the exit code, decides."""

from collections.abc import Callable


def run_reproduction(probe: Callable[[], tuple[bool | None, str]]) -> dict:
    """Run a probe that measures the original unsafe behavior explicitly.

    The probe may return False after an expected protective rejection only
    after checking that the unsafe effect did not occur. An unhandled error,
    missing evidence or an unknown predicate cannot establish either outcome.
    """
    try:
        observed, evidence = probe()
    except Exception as exc:
        return {"status": "INVALID", "defect_observed": None,
                "evidence": f"{type(exc).__name__}: {exc}", "reason": "probe failed"}
    if type(observed) is not bool or not isinstance(evidence, str) or not evidence.strip():
        return {"status": "INVALID", "defect_observed": None,
                "evidence": str(evidence), "reason": "defect predicate or evidence unavailable"}
    return {"status": "REPRODUCED" if observed else "NOT_REPRODUCED",
            "defect_observed": observed, "evidence": evidence,
            "reason": ("original defect predicate observed" if observed
                       else "unsafe effect prevented/absent")}
