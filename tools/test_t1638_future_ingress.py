"""T-1638 future-gate ingress: a placeholder never matures, and maturation is
bound to the bytes it was proved on.

Two defects, one class (stored lifecycle state that contradicts the live
verdict):

- `saipen future add` wrote `slice: TODO -- name the ONE bounded unit ...` and
  readiness tested the slice for truthiness only, so a gate added with
  `--evidence` was ELIGIBLE on its first evaluation before its author had
  declared what it may promote.
- monotone maturation kept a stored ELIGIBLE after the document's own bytes
  changed (FG-0046 stored ELIGIBLE while its live reason said the prerequisite
  it had since declared was still TODO).

The BOARD-flip no-oscillation property (T-1618 W2) is the boundary: a gate
whose bytes did not change keeps its maturation when BOARD flips.
"""

from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1614_future_gate as H  # noqa: E402
from saipen_engine import future_gate as gates  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402


def _tickets(project: Path) -> dict:
    text = (project / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
    return parse_board(text)["tickets"]


def _evidence(project: Path) -> str:
    (project / "evidence.md").write_text("measured\n", encoding="utf-8")
    return "evidence.md"


def _set_header(path: Path, field: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").split("\n")
    hits = [i for i, line in enumerate(lines) if line.startswith(f"{field}:")]
    assert len(hits) == 1, (field, hits)
    lines[hits[0]] = f"{field}: {value}"
    path.write_text("\n".join(lines), encoding="utf-8")


class FutureIngressTests(unittest.TestCase):
    def setUp(self):
        self._tmp = []

    def tearDown(self):
        for base in self._tmp:
            shutil.rmtree(base, ignore_errors=True)

    def _proj(self):
        base, project = H._project()
        self._tmp.append(base)
        return project

    def _added(self, project: Path) -> tuple[str, Path]:
        path = gates.add(project, "A deferred idea", "Body.", evidence=(_evidence(project),))
        gates.refresh(project)
        gid = gates.status(project)["gates"][0]["id"]
        return gid, path

    def test_a_gate_fresh_from_add_is_not_eligible_until_it_declares_a_slice(self):
        project = self._proj()
        gid, path = self._added(project)

        gates.evaluate(project, _tickets(project))

        gate = gates.get_gate(project, gid)
        self.assertEqual(gate.state, gates.DEFERRED)
        self.assertIn("no bounded slice declared", gate.reasons)
        self.assertIsNone(gates.status(project, _tickets(project))["next"])

        _set_header(path, "slice", "one bounded unit")
        gates.refresh(project)
        gates.evaluate(project, _tickets(project))
        self.assertEqual(gates.get_gate(project, gid).state, gates.ELIGIBLE)

    def test_a_placeholder_evidence_reference_is_no_evidence(self):
        project = self._proj()
        path = gates.add(project, "No evidence yet", "Body.")
        _set_header(path, "slice", "one bounded unit")
        gates.refresh(project)
        gid = gates.status(project)["gates"][0]["id"]

        gates.evaluate(project, _tickets(project))

        gate = gates.get_gate(project, gid)
        self.assertEqual(gate.state, gates.DEFERRED)
        self.assertIn("no evidence reference", gate.reasons)

    def test_new_bytes_rederive_a_stored_eligible(self):
        project = self._proj()
        gid, path = self._added(project)
        _set_header(path, "slice", "one bounded unit")
        gates.refresh(project)
        gates.evaluate(project, _tickets(project))
        self.assertEqual(gates.get_gate(project, gid).state, gates.ELIGIBLE)

        tid = H._add(project, "prerequisite work")
        _set_header(path, "needs", tid)
        gates.refresh(project)
        gates.evaluate(project, _tickets(project))

        gate = gates.get_gate(project, gid)
        self.assertEqual(gate.state, gates.DEFERRED)
        self.assertIn(f"prerequisite {tid} is ## TODO, not DONE", gate.reasons)
        self.assertIsNone(gates.status(project, _tickets(project))["next"])

    def test_an_eligible_stored_by_an_older_engine_is_reproved(self):
        """An index entry with no maturation binding is re-proved, not trusted."""
        project = self._proj()
        gid, path = self._added(project)
        tid = H._add(project, "prerequisite work")
        _set_header(path, "slice", "one bounded unit")
        _set_header(path, "needs", tid)
        gates.refresh(project)
        index = gates.load_index(project)
        for raw in index["gates"]:
            raw["state"] = gates.ELIGIBLE
            raw.pop("matured_digest", None)
        gates.write_index(project, index)

        gates.evaluate(project, _tickets(project))

        self.assertEqual(gates.get_gate(project, gid).state, gates.DEFERRED)

    def test_a_board_flip_does_not_undo_maturation_of_unchanged_bytes(self):
        project = self._proj()
        tid = H._add(project, "prerequisite work")
        gid, path = self._added(project)
        _set_header(path, "slice", "one bounded unit")
        _set_header(path, "needs", tid)
        gates.refresh(project)
        H._done(project, tid)
        gates.evaluate(project, _tickets(project))
        self.assertEqual(gates.get_gate(project, gid).state, gates.ELIGIBLE)

        board = project / ".saipen" / "BOARD.md"
        board.write_text(
            f"## DOING\n## TODO\n- [ ] {tid} [P1] prerequisite work | verify: verify it\n"
            "## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )
        gates.refresh(project)
        gates.evaluate(project, _tickets(project))

        self.assertEqual(gates.get_gate(project, gid).state, gates.ELIGIBLE)
        self.assertIsNone(gates.status(project, _tickets(project))["next"])


if __name__ == "__main__":
    unittest.main()
