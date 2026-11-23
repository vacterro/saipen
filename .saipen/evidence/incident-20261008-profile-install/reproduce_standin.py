"""Reproduce the 2026-10-08 profile write against a STAND-IN profile only.

Run with the three profile carriers already redirected, so nothing on this
machine but the stand-in can be written:

    USERPROFILE=<tmp>/home HOME=<tmp>/home CLAUDE_CONFIG_DIR=<tmp>/standin/.claude \
        python reproduce_standin.py <repo>/tools <tmp>

It refuses to run when CLAUDE_CONFIG_DIR is not under <tmp>.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

tools, sandbox = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
standin = Path(os.environ["CLAUDE_CONFIG_DIR"]).resolve()
if sandbox not in standin.parents or sandbox not in Path(os.environ["USERPROFILE"]).resolve().parents:
    raise SystemExit("refusing: the profile carriers are not redirected under the sandbox")
sys.path.insert(0, str(tools))

import test_hermetic_env as hermetic  # noqa: E402
import test_host_authority_broker as broker_tests  # noqa: E402
from test_protocol_admission import World  # noqa: E402


def listing() -> list[str]:
    return sorted(p.relative_to(standin).as_posix() for p in standin.rglob("*") if p.is_file())


report: dict = {"standin": str(standin), "before": listing()}
hermetic.isolate_host_session()
report["carrier_while_isolated"] = os.environ.get("CLAUDE_CONFIG_DIR")
report["interlock_while_isolated"] = os.environ.get(hermetic.FORBID_HOST_SPAWN)

# The borrowed test, run the way the draft oracle ran it: through a suite.
result = unittest.TestResult()
unittest.TestSuite(
    [broker_tests.IdentityTests("test_the_shipped_policy_names_host_images_and_their_code_signer")]
).run(result)
report["nested_ran"] = result.testsRun
report["nested_problems"] = len(result.failures) + len(result.errors)
report["carrier_after_nested_suite"] = os.environ.get("CLAUDE_CONFIG_DIR")
report["interlock_after_nested_suite"] = os.environ.get(hermetic.FORBID_HOST_SPAWN)
report["after_nested_suite"] = listing()

with tempfile.TemporaryDirectory(dir=sandbox) as tmp:
    world = World(Path(tmp))
    report["fixture_home_has_hook"] = (world.home / ".claude/hooks/saipen-guard.py").is_file()
report["after_world"] = listing()
settings = standin / "settings.json"
if settings.is_file():
    text = settings.read_text(encoding="utf-8")
    report["standin_settings_names_root"] = sorted(
        {part.split()[0] for part in text.split("--saipen-root ")[1:]}
    )
print(json.dumps(report, indent=2))
