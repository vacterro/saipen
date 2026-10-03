"""T-175: a seat's report path is whatever the roster recorded.

`resolve_report_path` used to compose `saipen_improve_<project_name>.md` from the
caller's argument and never read MANIFEST.md, while `create_report` compared the
roster's `report_path` against that same composed name. Registration opens a
cycle with the audit scope, and `improve submit <cycle> <seat> <project>` is
handed the project identity, so the two spellings disagree: the mutator resolves
a path the roster does not own and the cycle the engine opened is one it refuses
to finish. Reproduced live in cycle imp-vacterro-zaicode-20261002-1.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(TOOLS))

from improve import ImproveError, resolve_report_path  # noqa: E402

CYCLE = "imp-key-20260101"
SEAT = "seat-1"
#: What `prepare_audit_seat` records when the cycle is opened under the audit scope.
SCOPE_NAME = "saipen_improve_SAIPEN.md"
#: What a caller passes to `improve submit <cycle> <seat> <project>`.
PROJECT_IDENTITY = "vacterro-zaicode"

MANIFEST = f"""# IMPROVE CYCLE ROSTER

manifest_schema: strict
cycle_id: {CYCLE}
created_at: 2026-10-02T10:08:01Z
project_identity: vacterro-zaicode
cycle_status: active
seat_id: {SEAT}
role: core
report_path: {SCOPE_NAME}
availability: expected
"""


class ResolveReportPathTests(unittest.TestCase):
    def _root(self, manifest: str | None) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        if manifest is not None:
            (root / ".saipen/improve" / CYCLE).mkdir(parents=True)
            (root / ".saipen/improve" / CYCLE / "MANIFEST.md").write_text(
                manifest, encoding="utf-8", newline="\n"
            )
        return root

    def test_the_roster_wins_over_the_callers_spelling(self):
        root = self._root(MANIFEST)
        # Both spellings must land on the one path the seat actually owns --
        # a cycle the engine opened must be one the engine can finish.
        for project in ("SAIPEN", PROJECT_IDENTITY, "anything-else"):
            with self.subTest(project=project):
                resolved = resolve_report_path(root, CYCLE, SEAT, project)
                self.assertEqual(resolved.name, SCOPE_NAME)
                self.assertTrue(resolved.is_relative_to(root))

    def test_a_cycle_with_no_roster_still_resolves_the_composed_name(self):
        """An archived or hand-written cycle predating the roster must not break."""
        root = self._root(None)
        self.assertEqual(
            resolve_report_path(root, CYCLE, SEAT, "PROJ").name, "saipen_improve_PROJ.md"
        )

    def test_a_roster_without_this_seat_falls_back_rather_than_refusing(self):
        root = self._root(MANIFEST.replace(f"seat_id: {SEAT}", "seat_id: seat-2"))
        self.assertEqual(
            resolve_report_path(root, CYCLE, SEAT, "PROJ").name, "saipen_improve_PROJ.md"
        )

    def test_a_roster_recording_an_unusable_path_is_refused_not_ignored(self):
        """T-178: absent roster falls back; a roster that cannot be trusted refuses.

        A corrupt roster used to be answered with the caller's composed name, so
        the cycle resolved onto a file the roster never recorded -- the divergence
        T-175 exists to stop, reintroduced by a different route.
        """
        for unusable in ("../../escape.md", "sub/dir.md", "bad name.md", "."):
            with self.subTest(report_path=unusable):
                root = self._root(MANIFEST.replace(SCOPE_NAME, unusable))
                with self.assertRaises(ImproveError):
                    resolve_report_path(root, CYCLE, SEAT, "PROJ")

    def test_a_roster_that_records_no_path_for_this_seat_still_falls_back(self):
        """A seat registered without a report_path is a gap, not a corruption."""
        root = self._root(MANIFEST.replace(f"report_path: {SCOPE_NAME}\n", ""))
        self.assertEqual(
            resolve_report_path(root, CYCLE, SEAT, "PROJ").name, "saipen_improve_PROJ.md"
        )


if __name__ == "__main__":
    unittest.main()