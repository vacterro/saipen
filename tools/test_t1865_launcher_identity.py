"""T-1865: verification identity follows the subject, never the launcher.

Measured 2026-10-23 on T-1862. The `saipen` shim on PATH is a `#!/bin/sh`
script that execs `python.EXE`; the same command typed as
`python tools/saipen.py` runs without that shell in between. The two paths
export different `SHELL` values -- one the MSYS stub in `Git/bin`, the other
the real shell in `Git/usr/bin` -- and `verification_cache.capture` hashed the
WHOLE inherited environment.

Consequence: `saipen transition SHIP T-1862` refused the focused evidence its
own engine had just written as "missing or incompatible verification
environment identity", while `python tools/saipen.py transition SHIP T-1862`
accepted the same record on byte-identical tree content. The gate was not
disagreeing about the tree; it was disagreeing about which launcher asked.

T-1834 closed the same class for `CODEX_TOOL_CALL_ID`/`PROMPT`; T-1856 closed
it for the shell's `_`. This ticket closes the two remaining members:
`SHELL` (launcher-only, must not decide identity) and
`ANTIGRAVITY_SOURCE_METADATA` (per-tool-call, must not reach the child at all).

Proven here:
- two environments differing ONLY in `SHELL` capture one identity digest;
- two environments differing ONLY in `ANTIGRAVITY_SOURCE_METADATA` capture one
  identity digest AND a real child never sees the carrier;
- a real environment change still invalidates the identity (the red control
  that keeps this from becoming a no-op rule);
- the declared narrow lists name exactly the offending names;
- end to end: a record written under one launch path is accepted under the
  other, through the real cache module.

Run standalone:
    python tools/test_t1865_launcher_identity.py
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import verification_cache as cache  # noqa: E402
from saipen_engine.test_runner import (  # noqa: E402
    LAUNCHER_ONLY_ENV,
    VERIFIER_DIAGNOSTIC_ENV,
    TestFamily,
    _run_family,
    family_environment,
    identity_environment,
)
from test_hermetic_env import isolate_host_session  # noqa: E402

STUB_SHELL = r"C:\Program Files\Git\bin\bash.exe"
REAL_SHELL = r"C:\Program Files\Git\usr\bin\bash.exe"
CONFIGURATION = {"family": "focused-unit", "patterns": ["test_probe.py"], "timeout": 300}


def setUpModule() -> None:
    isolate_host_session()


class ShellIsLauncherOnlyTests(unittest.TestCase):
    """`SHELL` describes the invocation; a canonical child never uses it."""

    def test_two_shell_values_capture_one_identity(self):
        """The exact T-1862 measurement: one tree, two launch paths, one identity."""
        with mock.patch.dict(os.environ, {"SHELL": STUB_SHELL}):
            through_shim = cache.capture(TOOLS.parent, CONFIGURATION)
        with mock.patch.dict(os.environ, {"SHELL": REAL_SHELL}):
            direct = cache.capture(TOOLS.parent, CONFIGURATION)
        self.assertEqual(
            sorted(
                key
                for key in set(through_shim) | set(direct)
                if through_shim.get(key) != direct.get(key)
            ),
            [],
            "the two launch paths produced different identities for one tree",
        )
        self.assertTrue(
            cache.compatible(TOOLS.parent, through_shim),
            "a record written through the shim was refused on the direct path",
        )

    def test_the_child_still_inherits_shell_because_a_grandchild_may_use_it(self):
        """Narrow by intent: this is dropped from the DIGEST, not from the child."""
        with mock.patch.dict(os.environ, {"SHELL": REAL_SHELL}):
            env = family_environment(TestFamily("identity", (sys.executable,), 10))
        self.assertEqual(env.get("SHELL"), REAL_SHELL)
        self.assertNotIn("SHELL", identity_environment(env))

    def test_a_real_environment_change_still_invalidates_the_identity(self):
        """The red control: dropping launcher names must not erase real drift."""
        with mock.patch.dict(os.environ, {"SHELL": STUB_SHELL}):
            before = cache.capture(TOOLS.parent, CONFIGURATION)
        with mock.patch.dict(os.environ, {"SHELL": REAL_SHELL, "SAIPEN_TEST_MODE": "DIFFERENT"}):
            after = cache.capture(TOOLS.parent, CONFIGURATION)
        self.assertNotEqual(
            before["environment_sha256"],
            after["environment_sha256"],
            "a semantic environment change must still invalidate evidence",
        )
        with mock.patch.dict(os.environ, {"SHELL": REAL_SHELL, "SAIPEN_TEST_MODE": "DIFFERENT"}):
            self.assertFalse(
                cache.compatible(TOOLS.parent, before),
                "a real environment change must still refuse the older identity",
            )


class AntigravityCarrierTests(unittest.TestCase):
    """The per-tool-call step index names the CALL, not the verified tree."""

    def test_the_carrier_never_reaches_the_canonical_child(self):
        for step in ("1", "2", '{"stepIndex":17}'):
            with self.subTest(step=step), mock.patch.dict(
                os.environ, {"ANTIGRAVITY_SOURCE_METADATA": step}
            ):
                env = family_environment(TestFamily("identity", (sys.executable,), 10))
            self.assertNotIn("ANTIGRAVITY_SOURCE_METADATA", env)

    def test_two_step_indices_capture_one_identity(self):
        with mock.patch.dict(
            os.environ, {"ANTIGRAVITY_SOURCE_METADATA": '{"stepIndex":1}'}
        ):
            first = cache.capture(TOOLS.parent, CONFIGURATION)
        with mock.patch.dict(
            os.environ, {"ANTIGRAVITY_SOURCE_METADATA": '{"stepIndex":2}'}
        ):
            second = cache.capture(TOOLS.parent, CONFIGURATION)
        self.assertEqual(first["environment_sha256"], second["environment_sha256"])
        self.assertTrue(cache.compatible(TOOLS.parent, first))

    def test_a_real_child_does_not_see_the_carrier(self):
        """The property through an actual execution, not only the digest."""
        code = (
            "import json,os; print(json.dumps("
            "os.environ.get('ANTIGRAVITY_SOURCE_METADATA')))"
        )
        import shutil
        import tempfile

        from saipen_engine.journal import ensure_project_lineage

        root = Path(tempfile.mkdtemp(prefix="t1865-"))
        self.addCleanup(shutil.rmtree, root, True)
        (root / ".saipen").mkdir(parents=True)
        (root / ".saipen" / "LOG.md").write_text(
            "- 23.10.26 00:00 [E-001] [T-1] [agent: probe] DEC: base\n", encoding="utf-8"
        )
        (root / ".saipen" / "BOARD.md").write_text(
            "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8"
        )
        ensure_project_lineage(root)
        with mock.patch.dict(os.environ, {"ANTIGRAVITY_SOURCE_METADATA": '{"stepIndex":9}'}):
            result = _run_family(
                root, TestFamily("probe", (sys.executable, "-c", code), 60)
            )
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(json.loads(result["stdout"].strip()), None)


class NarrowListTests(unittest.TestCase):
    """A wide list here would hide real drift; assert the exact membership."""

    def test_the_launcher_list_names_exactly_the_launcher_name(self):
        self.assertEqual(LAUNCHER_ONLY_ENV, frozenset({"SHELL"}))

    def test_the_diagnostic_list_names_the_two_per_call_carriers(self):
        self.assertEqual(
            VERIFIER_DIAGNOSTIC_ENV,
            frozenset({"CODEX_TOOL_CALL_ID", "PROMPT", "ANTIGRAVITY_SOURCE_METADATA"}),
        )


class GateMessageTests(unittest.TestCase):
    """Both ship gates name the rule; a reader never gets a bare mystery.

    T-1865's own REVIEW self-audit found the full-family gate in
    `core_unit.py` still emitting the opaque sentence after the focused gate
    was fixed. One owner decides WHAT is incompatible (`incompatibility`);
    each gate decides only how to say it, and both must ask.
    """

    def test_the_full_family_gate_asks_the_rule_owner(self):
        source = (TOOLS / "saipen_engine/core_unit.py").read_text(encoding="utf-8")
        self.assertIn("compatible, incompatibility, replay_supported", source)
        self.assertIn("reason = incompatibility(record.get(\"verification_identity\"))", source)

    def test_the_focused_gate_asks_the_rule_owner(self):
        source = (TOOLS / "saipen_engine/focused_unit.py").read_text(encoding="utf-8")
        self.assertIn("compatible, incompatibility", source)
        self.assertIn("reason = incompatibility(record.get(\"verification_identity\"))", source)

    def test_no_gate_still_returns_the_bare_sentence(self):
        """The opaque form is only allowed as the PREFIX of an explained one."""
        for name in ("core_unit.py", "focused_unit.py"):
            source = (TOOLS / "saipen_engine" / name).read_text(encoding="utf-8")
            for line in source.splitlines():
                if "incompatible verification environment identity" not in line:
                    continue
                if line.lstrip().startswith("#"):
                    continue
                self.assertTrue(
                    line.rstrip().endswith('" + ('),
                    f"{name}: {line.strip()!r} returns the message with no reason attached",
                )


class IdentityRuleTests(unittest.TestCase):
    """A record from an older rule refuses legibly, never as a mystery."""

    def test_a_current_record_names_its_rule_and_is_compatible(self):
        current = cache.capture(TOOLS.parent, CONFIGURATION)
        self.assertEqual(current.get("identity_rule"), cache.IDENTITY_RULE)
        self.assertTrue(cache.compatible(TOOLS.parent, current))
        self.assertIsNone(cache.incompatibility(current))

    def test_a_legacy_record_refusal_names_the_rule_not_the_tree(self):
        """The reader must be able to tell a rule change from a tree change."""
        legacy = cache.capture(TOOLS.parent, CONFIGURATION)
        legacy.pop("identity_rule", None)
        self.assertFalse(cache.compatible(TOOLS.parent, legacy))
        reason = cache.incompatibility(legacy)
        self.assertIsNotNone(reason)
        self.assertIn("identity rule", reason)
        self.assertIn("re-run", reason)
        self.assertIn(cache.IDENTITY_RULE, reason)

    def test_a_semantic_change_still_refuses_without_a_rule_excuse(self):
        """The red control on the message: a real change must not blame the rule."""
        before = cache.capture(TOOLS.parent, CONFIGURATION)
        with mock.patch.dict(os.environ, {"SAIPEN_TEST_MODE": "DIFFERENT"}):
            self.assertFalse(cache.compatible(TOOLS.parent, before))
        self.assertIsNone(
            cache.incompatibility(before),
            "a record captured under the current rule must not be blamed on the rule",
        )


if __name__ == "__main__":
    unittest.main()
