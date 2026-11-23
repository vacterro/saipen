"""Refused local releases settle only untouched plans; runtime owns validation."""

import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from saipen_engine import release
from saipen_engine.journal import Journal, scan_pending
from test_t1746_crew_terminal_outcome import _DownstreamShape


class RefusedLocalReleaseTests(_DownstreamShape):
    def _record(self, plan):
        return Journal(self.root, plan.op_id).read()

    def test_failed_gate_aborts_and_two_retries_need_no_recovery(self):
        self._shape()
        canonical = self._canonical()
        for _ in range(2):
            plan = self._plan()
            ready, _gate, parity = self._patches()
            with ready, parity, patch.object(
                release, "_run_gate", return_value={"ok": False, "detail": "FAIL: fixture"}
            ):
                refused = release.execute_release(self.root, plan)
            self.assertFalse(refused["ok"], refused)
            self.assertEqual(refused["stage"], "NO_PUBLISH", refused)
            self.assertEqual(self._record(plan)["status"], "ABORTED")
            self.assertEqual(scan_pending(self.root), ([], []))
            self.assertEqual(self._canonical(), canonical)
            self.assertNotEqual(self._verdict()["status"], "ok")
        closed, _result = self._close()
        self.assertEqual(self._verdict()["evidence"]["op_id"], closed.op_id)

    def test_closure_planning_refusal_aborts_without_changing_canonical_bytes(self):
        self._shape()
        plan = self._plan()
        canonical = self._canonical()
        with patch.object(
            release, "_finish_targets",
            side_effect=release.ReleaseRefusal("RELEASE_FAILED", "fixture"),
        ):
            refused = self._apply(plan)
        self.assertFalse(refused["ok"], refused)
        self.assertEqual(self._record(plan)["status"], "ABORTED")
        self.assertEqual(self._canonical(), canonical)
        self.assertEqual(scan_pending(self.root), ([], []))

    def test_registered_but_untouched_targets_abort(self):
        self._shape()
        plan = self._plan()
        canonical = self._canonical()

        def refuse(root, journal, targets):
            journal.append_targets(targets)
            raise release.ReleaseRefusal("RELEASE_FAILED", "before the first target")

        with patch.object(release, "_apply_closure_targets", side_effect=refuse):
            refused = self._apply(plan)
        self.assertFalse(refused["ok"], refused)
        self.assertTrue(self._record(plan)["targets"])
        self.assertEqual(self._record(plan)["status"], "ABORTED")
        self.assertEqual(self._canonical(), canonical)
        self.assertEqual(scan_pending(self.root), ([], []))

    def test_refusal_after_a_marked_target_keeps_recovery_and_replays(self):
        self._shape()
        plan = self._plan()
        original = release._mark_target

        def refuse(journal, index):
            original(journal, index)
            raise release.ReleaseRefusal("RELEASE_FAILED", "after a target")

        with patch.object(release, "_mark_target", side_effect=refuse):
            refused = self._apply(plan)
        self.assertFalse(refused["ok"], refused)
        self.assertNotEqual(self._record(plan)["status"], "ABORTED")
        self.assertEqual(self._refusal().code, "RECOVERY_REQUIRED")
        recovered = release.recover_release_op(self.root, plan.op_id)
        self.assertEqual((recovered["ok"], recovered["code"]), (True, "COMMITTED"), recovered)
        self.assertEqual(self._verdict()["status"], "ok")

    def test_landed_bytes_without_a_progress_marker_keep_recovery(self):
        self._shape()
        plan = self._plan()
        with patch.object(
            release, "_mark_target",
            side_effect=release.ReleaseRefusal("RELEASE_FAILED", "marker failed"),
        ):
            refused = self._apply(plan)
        self.assertFalse(refused["ok"], refused)
        record = self._record(plan)
        self.assertFalse(any(target["applied"] for target in record["targets"]))
        self.assertNotEqual(record["status"], "ABORTED")
        self.assertEqual(self._refusal().code, "RECOVERY_REQUIRED")
        recovered = release.recover_release_op(self.root, plan.op_id)
        self.assertEqual((recovered["ok"], recovered["code"]), (True, "COMMITTED"), recovered)
        self.assertEqual(self._verdict()["status"], "ok")

    def test_foreign_bytes_preserve_the_operation_and_refuse_recovery(self):
        self._shape()
        plan = self._plan()
        changed = []

        def refuse(root, journal, targets):
            journal.append_targets(targets)
            path = root / targets[0]["path"]
            foreign = path.read_bytes() + b"\nforeign writer\n"
            path.write_bytes(foreign)
            changed.append((path, foreign))
            raise release.ReleaseRefusal("RELEASE_FAILED", "third-state target")

        with patch.object(release, "_apply_closure_targets", side_effect=refuse):
            refused = self._apply(plan)
        self.assertFalse(refused["ok"], refused)
        self.assertNotEqual(self._record(plan)["status"], "ABORTED")
        recovered = release.recover_release_op(self.root, plan.op_id)
        self.assertEqual((recovered["ok"], recovered["code"]), (False, "CONFLICT"), recovered)
        self.assertEqual(changed[0][0].read_bytes(), changed[0][1])

    def test_a_marked_noop_does_not_turn_an_untouched_refusal_into_recovery(self):
        self._shape()
        plan = self._plan()
        canonical = self._canonical()

        def refuse(root, journal, targets):
            path = root / ".saipen/STATE.md"
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()[:16]
            journal.append_targets([{
                "path": ".saipen/STATE.md", "role": "state", "content": content,
                "before_hash": digest, "after_hash": digest,
            }])
            release._mark_target(journal, 0)
            raise release.ReleaseRefusal("RELEASE_FAILED", "only a no-op was reached")

        with patch.object(release, "_apply_closure_targets", side_effect=refuse):
            refused = self._apply(plan)
        self.assertFalse(refused["ok"], refused)
        self.assertEqual(self._record(plan)["status"], "ABORTED")
        self.assertEqual(self._canonical(), canonical)
        self.assertEqual(scan_pending(self.root), ([], []))

    def test_process_death_before_body_still_requires_canonical_recovery(self):
        self._shape()
        plan = self._plan()
        canonical = self._canonical()
        death = patch.object(release, "_no_publish_body", side_effect=SystemExit(86))
        with death, self.assertRaises(SystemExit):
            self._apply(plan)
        self.assertEqual(self._record(plan)["status"], "PREPARED")
        self.assertEqual(self._refusal().code, "RECOVERY_REQUIRED")
        recovered = release.recover_release_op(self.root, plan.op_id)
        self.assertEqual((recovered["ok"], recovered["code"]), (True, "ABORTED"), recovered)
        self.assertEqual(self._canonical(), canonical)


class RuntimeValidatorTests(_DownstreamShape):
    def _home(self):
        home = self.root / "runtime-home"
        engine = home / "tools/saipen_engine/release.py"
        engine.parent.mkdir(parents=True)
        engine.write_text("# running engine location\n", encoding="utf-8")
        return home, engine

    def test_downstream_validator_cannot_replace_the_runtime_gate(self):
        home, engine = self._home()
        project = self.root / "managed"
        (project / "tools").mkdir(parents=True)
        local_marker = project / "local-ran.txt"
        runtime_marker = home / "runtime-ran.txt"
        (project / "tools/validate.py").write_text(
            "from pathlib import Path\n"
            f"Path({str(local_marker)!r}).write_text('local', encoding='utf-8')\n"
            "raise SystemExit(0)\n", encoding="utf-8",
        )
        canonical = home / "tools/validate.py"
        canonical.write_text(
            "from pathlib import Path\n"
            f"Path({str(runtime_marker)!r}).write_text('runtime', encoding='utf-8')\n"
            "print('FAIL: canonical fixture')\nraise SystemExit(1)\n", encoding="utf-8",
        )
        with patch.object(release, "__file__", str(engine)):
            command = release._gate_command(project, "core")
            verdict = release._run_gate(project, "core")
        self.assertEqual(command[1:], [
            str(canonical), "--project-root", str(project), "--gate", "core",
        ])
        self.assertFalse(verdict["ok"], verdict)
        self.assertIn("canonical fixture", verdict["detail"])
        self.assertTrue(runtime_marker.is_file())
        self.assertFalse(local_marker.exists())

    def test_running_home_keeps_self_validation(self):
        home, engine = self._home()
        canonical = home / "tools/validate.py"
        canonical.write_text("raise SystemExit(0)\n", encoding="utf-8")
        with patch.object(release, "__file__", str(engine)):
            self.assertEqual(release._gate_command(home, "ship")[1:], [
                str(canonical), "--gate", "ship",
            ])
            self.assertEqual(release._run_gate(home, "ship"), {"ok": True})

    def test_missing_runtime_validator_cannot_fall_back_to_downstream_code(self):
        home, engine = self._home()
        project = self.root / "managed"
        (project / "tools").mkdir(parents=True)
        (project / "tools/validate.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
        with patch.object(release, "__file__", str(engine)):
            command = release._gate_command(project, "core")
            verdict = release._run_gate(project, "core")
        self.assertEqual(Path(command[1]), home / "tools/validate.py")
        self.assertFalse(verdict["ok"], verdict)


if __name__ == "__main__":
    unittest.main()
