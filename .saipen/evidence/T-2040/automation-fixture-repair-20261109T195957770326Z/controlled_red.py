"""Controlled red: unchanged repaired tests against in-memory permissive owners."""
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))
from saipen_engine import automation, work_exhaustion as W

routing = automation._routing_disposition
closure = automation.closure_gate


def permissive_discovery(routed, action, reason, **kwargs):
    if reason == "maintain" and routed.get("work_exhaustion", {}).get("status") == W.INCOMPLETE_DISCOVERY:
        return automation.CONTINUE, "maintain"
    return routing(routed, action, reason, **kwargs)


def permissive_closure(**kwargs):
    result = closure(**kwargs)
    return {**result, "complete": True,
            "conditions": {name: True for name in result["conditions"]}}


cases = (
    ("incomplete-discovery-allowed", "_routing_disposition", permissive_discovery, (
        "test_automation_block.ClosedVocabulary.test_empty_project_without_discovery_cannot_continue",
    )),
    ("closure-vetoes-erased", "closure_gate", permissive_closure, (
        "test_automation_block.ClosureGate.test_audit_quiescence_is_required",
        "test_automation_block.ClosureGate.test_binding_wait_vetoes_closure",
        "test_t1739_wait_boundary.WaitBoundary.test_stale_projection_cannot_certify_current_completion",
    )),
)
summary = []
for name, owner, mutation, tests in cases:
    print(f"\nCONTROLLED RED: {name}", flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromNames(tests)
    with patch.object(automation, owner, side_effect=mutation):
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    summary.append({"mutation": name, "tests": result.testsRun,
                    "failures": len(result.failures), "errors": len(result.errors),
                    "skipped": len(result.skipped)})
    assert result.testsRun == len(tests)
    assert len(result.failures) == len(tests) and not result.errors and not result.skipped
print("\nEXPECTED RED CONFIRMED: " + json.dumps(summary), flush=True)
