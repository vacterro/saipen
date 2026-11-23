"""T-1685: a fixture never inherits the operator's Claude configuration profile.

Measured 2026-10-08: launched from a Claude Code session whose profile sets
CLAUDE_CONFIG_DIR, the declared family went 57 red and its installer fixtures
wrote into that live profile (settings.json hooks, CLAUDE.md, skills/saipen).
`claude_profiles.directory()` rightly lets the carrier outrank HOME in
production -- a hook running under a second profile must serve that profile --
so the harness owns the repair: neither `isolate_host_session` nor the family
runner removed the carrier, and three host modules called no isolation at all.

Every check here names a disposable stand-in profile, never a real one, and
proves the stand-in is left byte-for-byte empty.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.claude_profiles import ENVIRONMENT  # noqa: E402
from saipen_engine.test_runner import TestFamily, _run_family  # noqa: E402
from test_hermetic_env import HOST_SESSION_VARIABLES, isolate_host_session  # noqa: E402

#: One red test per carrier path measured on 2026-10-08: an isolated installer
#: module, the stop-hook installer, and the three modules that isolated nothing.
LEAKED = (
    "test_adapter_parity.OneTemplateTests.test_both_injectors_install_identical_normalized_blocks",
    "test_claude_stop_hook.ClaudeInstallerTests.test_the_original_settings_are_backed_up_once",
    "test_t1649_refusal_step.HealthRecordTests.test_no_step_is_no_field",
    "test_t1635_claude_profiles.SharedAuthority."
    "test_real_hooks_in_two_profiles_share_one_service_without_profile_confusion",
    "test_host_authority_broker.ClaudeHostPathTests."
    "test_the_normal_host_path_is_admitted_without_a_magic_phrase",
)


def setUpModule() -> None:
    isolate_host_session()


def _contents(directory: Path) -> list[str]:
    return sorted(str(path.relative_to(directory)) for path in directory.rglob("*"))


class ProfileCarrierTests(unittest.TestCase):
    def test_the_harness_strips_the_profile_carrier(self):
        self.assertIn(ENVIRONMENT, HOST_SESSION_VARIABLES)

    def test_a_family_child_inherits_no_profile_carrier(self):
        probe = f"import os; print(repr(os.environ.get({ENVIRONMENT!r})))"
        with tempfile.TemporaryDirectory(prefix="saipen-t1685-family-") as tmp:
            root = Path(tmp)
            spool = root / "spool"
            spool.mkdir()
            operator = root / "operator-profile"
            operator.mkdir()
            with mock.patch.dict(os.environ, {ENVIRONMENT: str(operator)}):
                report = _run_family(
                    root, TestFamily("probe", (sys.executable, "-c", probe), 60), spool=spool
                )
            self.assertEqual(report["status"], "PASS", report)
            self.assertEqual((spool / "stdout").read_text(encoding="utf-8").strip(), "None")

    def test_host_fixtures_never_reach_the_operators_profile(self):
        with tempfile.TemporaryDirectory(prefix="saipen-t1685-operator-") as tmp:
            operator = Path(tmp) / ".claude-operator"
            operator.mkdir()
            env = dict(os.environ, **{ENVIRONMENT: str(operator)})
            proc = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", *LEAKED],
                cwd=TOOLS, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=900,
            )
            self.assertEqual(_contents(operator), [])
        self.assertEqual(proc.returncode, 0, proc.stderr[-4000:])


if __name__ == "__main__":
    unittest.main()
