"""T-1816 R006 bullet 2 -- protected-root hold negative controls (SRC-275).

DRIFT-01 measured a refusal that named ``Bash``/``Edit``/``Write`` as forbidden
probes and was then defeated by an embedded Python write. These controls encode
the four cited message sequences as *effects*, so a future regression that
re-attaches the gate to a verb name fails here.

The tests deliberately never touch the real AUDAPACK root. They build a disposable
hold in ``tmp``, because a control that needs the protected project to exist is
not a control -- and because the audit is forbidden from rehearsing writes there.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from saipen_engine import protected_root as P

READ_ONLY = {
    "schema": 1,
    "root": "V:/___VAC/__K/__CODE/_PY/_AUDAPACK",
    "mode": P.MODE_READ_ONLY,
    "reason": "HISTORY_LEDGER_CORRUPT; absent parents E-3133/E-3136/E-3145",
    "protected_paths": [".saipen/LOG.md", ".saipen/STATE.md", ".saipen/BOARD.md"],
    "lift_command": "saipen recover resolve-blocker SRC-275",
    "declared_by": "operator",
}


class HoldFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".saipen").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_hold(self, data) -> None:
        (self.root / P.HOLD_FILE).write_text(json.dumps(data), encoding="utf-8")

    def verdict(self, targets, **kwargs):
        return P.check(self.root, targets, **kwargs)


class Message402EmbeddedPythonTests(HoldFixture):
    """Message 402: embedded Python wrote LOG.md + STATE.md under an active hold."""

    def test_direct_write_to_log_is_refused(self) -> None:
        self.write_hold(READ_ONLY)
        result = self.verdict([".saipen/LOG.md"])
        self.assertEqual(result["verdict"], P.REFUSE)
        self.assertEqual(result["code"], "PROTECTED_TARGET")
        self.assertEqual(result["held"], [".saipen/LOG.md"])

    def test_the_same_write_refused_through_an_interpreter(self) -> None:
        """The gate must not consult the tool. `python -c` is not a loophole."""
        self.write_hold(READ_ONLY)
        targets = [".saipen/LOG.md", ".saipen/STATE.md"]
        via_shell = self.verdict(
            targets,
            tool="Bash",
            command=(
                "python -c \"from pathlib import Path; "
                "Path('.saipen/LOG.md').write_text('x')\""
            ),
        )
        via_edit = self.verdict(targets, tool="Edit")
        self.assertEqual(via_shell["verdict"], P.REFUSE)
        self.assertEqual(via_edit["verdict"], P.REFUSE)
        # Same targets, same verdict, same held set: the TOOL changed nothing.
        self.assertEqual(via_shell["held"], via_edit["held"])
        self.assertEqual(via_shell["held"], targets)

    def test_a_hold_survives_the_actor_declaring_read_only_intent(self) -> None:
        """Intent is not an effect; a command that claims to be a probe is still
        judged by what it targets."""
        self.write_hold(READ_ONLY)
        result = self.verdict(
            [".saipen/STATE.md"],
            tool="Bash",
            command="echo read-only probe",
        )
        self.assertEqual(result["verdict"], P.REFUSE)
        self.assertIn("declared_intent", result["non_signals"])

    def test_a_transient_refusal_leaves_a_durable_marker_to_read(self) -> None:
        """The defect was that the next process saw no hold. The hold is a FILE."""
        self.write_hold(READ_ONLY)
        self.assertTrue((self.root / P.HOLD_FILE).is_file())
        self.assertEqual(P.load_hold(self.root)["state"], "ACTIVE")


class Message413LogHeadTests(HoldFixture):
    """Message 413: Edit removed an unnumbered line from LOG.md."""

    def test_deleting_the_log_head_is_refused(self) -> None:
        self.write_hold(READ_ONLY)
        result = self.verdict([".saipen/LOG.md"], effect="fs.delete")
        self.assertEqual(result["verdict"], P.REFUSE)

    def test_an_unprotected_artifact_stays_writable(self) -> None:
        """A read-only forensic pass must still be able to record evidence."""
        self.write_hold(READ_ONLY)
        result = self.verdict([".saipen/evidence/T-1816-inventory.md"])
        self.assertEqual(result["verdict"], P.ALLOW)
        self.assertEqual(result["code"], "TARGET_NOT_HELD")


class Message414StateTests(HoldFixture):
    """Message 414: Edit rewrote STATE.md task/next_action/transition_from."""

    def test_state_rewrite_is_refused(self) -> None:
        self.write_hold(READ_ONLY)
        self.assertEqual(self.verdict([".saipen/STATE.md"])["verdict"], P.REFUSE)

    def test_reading_the_held_root_is_allowed(self) -> None:
        self.write_hold(READ_ONLY)
        result = self.verdict([".saipen/STATE.md"], effect="fs.read")
        self.assertEqual(result["verdict"], P.ALLOW)
        self.assertEqual(result["code"], "NON_MUTATING")


class Message431BoardTests(HoldFixture):
    """Message 431: Edit rewrote BOARD.md into malformed ## TODO## DOING."""

    def test_board_rewrite_is_refused(self) -> None:
        self.write_hold(READ_ONLY)
        self.assertEqual(self.verdict([".saipen/BOARD.md"])["verdict"], P.REFUSE)

    def test_a_directory_hold_protects_everything_under_it(self) -> None:
        self.write_hold({**READ_ONLY, "protected_paths": [".saipen/"]})
        self.assertEqual(self.verdict([".saipen/BOARD.md"])["verdict"], P.REFUSE)
        self.assertEqual(self.verdict([".saipen/nested/deep.md"])["verdict"], P.REFUSE)


class FailClosedTests(HoldFixture):
    """Every ambiguous input refuses. Silence is never authorization."""

    def test_no_hold_file_allows(self) -> None:
        result = self.verdict([".saipen/LOG.md"])
        self.assertEqual(result["verdict"], P.ALLOW)
        self.assertEqual(result["code"], "NO_HOLD")

    def test_a_corrupt_hold_refuses_instead_of_vanishing(self) -> None:
        (self.root / P.HOLD_FILE).write_text("{not json", encoding="utf-8")
        result = self.verdict([".saipen/LOG.md"])
        self.assertEqual(result["verdict"], P.REFUSE)
        self.assertEqual(result["code"], "HOLD_UNREADABLE")

    def test_a_non_object_hold_refuses(self) -> None:
        (self.root / P.HOLD_FILE).write_text('["nope"]', encoding="utf-8")
        self.assertEqual(self.verdict([".saipen/LOG.md"])["verdict"], P.REFUSE)

    def test_an_unknown_mode_refuses(self) -> None:
        self.write_hold({**READ_ONLY, "mode": "LIFTED"})
        result = self.verdict([".saipen/LOG.md"])
        self.assertEqual(result["verdict"], P.REFUSE)
        self.assertEqual(result["code"], "HOLD_MODE_UNKNOWN")

    def test_a_sibling_filename_is_not_within_the_protected_path(self) -> None:
        """`.saipen/LOG.md.bak` must not be caught by a hold on `.saipen/LOG.md`."""
        self.write_hold(READ_ONLY)
        result = self.verdict([".saipen/LOG.md.bak"])
        self.assertEqual(result["verdict"], P.ALLOW)

    def test_an_absolute_target_inside_the_root_is_normalized_before_compare(self) -> None:
        self.write_hold(READ_ONLY)
        absolute = str(self.root / ".saipen" / "LOG.md")
        result = self.verdict([absolute])
        self.assertEqual(result["verdict"], P.REFUSE)
        self.assertEqual(result["held"], [".saipen/LOG.md"])

    def test_a_foreign_absolute_path_is_not_silently_protected(self) -> None:
        """A path outside this root belongs to another root's hold, not this one."""
        self.write_hold(READ_ONLY)
        result = self.verdict([r"C:\some\other\root\.saipen\LOG.md"])
        self.assertEqual(result["verdict"], P.ALLOW)

    def test_empty_targets_do_not_manufacture_a_refusal(self) -> None:
        self.write_hold(READ_ONLY)
        self.assertEqual(self.verdict([])["verdict"], P.ALLOW)


if __name__ == "__main__":
    unittest.main()
