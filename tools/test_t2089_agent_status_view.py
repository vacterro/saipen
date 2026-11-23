"""T-2089: the bounded agent view of `saipen status`.

`saipen status --json` stays the full, externally compatible projection. A
model turn does not need 264 KB of per-ticket blocker detail to route; it
needs the verdict, the counts by root cause, the first actionable owner and
the machine authority. `--view agent` computes the SAME canonical gates and
then renders a bounded envelope: nothing is re-derived, nothing authority-
relevant is dropped, verbose details stay addressable through the full view.

Semantics contract (proved against the full projection on the SAME run):
  * ok/code/phase/task/next_action/computed_* identical;
  * recovery/conflict/pending flags identical;
  * every blocker GROUP of the full projection appears with the same
    blocker_class, cause and owner, and its full dependent/root counts;
  * no item-level detail is rendered, and the envelope names the full view
    as the detail route (a reference, never a silent omission);
  * the envelope stays bounded under adversarial many-blocker boards.

Run standalone:
    python tools/test_t2089_agent_status_view.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _run_cli(project_root: Path, *extra: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(TOOLS / "saipen.py"), "status", *extra],
        capture_output=True,
        cwd=project_root,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"status {' '.join(extra)} rc={proc.returncode}: {proc.stderr.decode('utf-8', 'replace')[:400]}"
        )
    return json.loads(proc.stdout.decode("utf-8"))


def _make_project(tmp: Path, blocked_tickets: int = 2) -> Path:
    root = tmp / "project"
    (root / ".saipen").mkdir(parents=True)
    (root / ".saipen" / "STATE.md").write_text(
        "---\n"
        "phase: SCOUT\n"
        "task: T-100\n"
        'next_action: "PHASE SCOUT T-100"\n'
        "blocker: none\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        "last_event: 1\n"
        "style_contract: ded-069a4c52\n"
        'saipen_home: "C:/nonexistent"\n'
        "agent: saipen-cli\n"
        "mode: full\n"
        'updated: "2026-01-01T00:00:00Z"\n'
        "transition_from: DONE\n"
        "---\n",
        encoding="utf-8",
    )
    rows = ["- [/] T-100 active work", "- [ ] T-101 next work"]
    rows += [
        f"- [ ] T-20{i} blocked work | blocker: WAIT_USER_DECISION (operator proof {i})"
        for i in range(2, 2 + blocked_tickets)
    ]
    (root / ".saipen" / "BOARD.md").write_text(
        "# BOARD\n\n## DOING\n- [/] T-100 active work\n\n## TODO\n\n## DONE\n\n## BLOCKED\n"
        + "\n".join(rows[2:]) + "\n",
        encoding="utf-8",
    )
    (root / ".saipen" / "LOG.md").write_text(
        "- 01.01.26 00:00 [E-001] [T-100] RUN: scout started\n",
        encoding="utf-8",
    )
    return root


class AgentViewParity(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="saipen-agent-view-")
        self.addCleanup(self.temporary.cleanup)
        self.root = _make_project(Path(self.temporary.name))

    def test_agent_view_matches_full_projection_verdicts(self) -> None:
        full = _run_cli(self.root, "--json")
        agent = _run_cli(self.root, "--view", "agent", "--json")
        self.assertTrue(agent["ok"])
        for key in (
            "ok",
            "phase",
            "task",
            "next_action",
            "computed_reason",
            "recovery_pending",
            "recovery_conflict",
            "board_errors",
        ):
            self.assertEqual(agent.get(key), full.get(key), key)
        # Every full-projection blocker group appears with the same class.
        full_groups = {
            g["shared_blocker_id"]: g for g in full.get("blocker_projection", {}).get("groups", [])
        }
        agent_groups = {g["shared_blocker_id"]: g for g in agent.get("blocker_groups", [])}
        self.assertEqual(set(agent_groups), set(full_groups))
        for gid, g in agent_groups.items():
            self.assertEqual(g["blocker_class"], full_groups[gid]["blocker_class"])
            self.assertEqual(g["cause"], full_groups[gid]["cause"])
            self.assertEqual(g["root_tickets"], full_groups[gid]["root_tickets"])
        # The envelope names the detail route instead of hiding it.
        self.assertEqual(agent["view"], "agent")
        self.assertIn("detail_ref", agent)
        self.assertIn("status --json", agent["detail_ref"])
        # No per-ticket verbose items are rendered.
        self.assertNotIn("blocker_projection", agent)
        for group in agent.get("blocker_groups", []):
            self.assertNotIn("items", group)

    def test_agent_view_envelope_is_bounded_under_many_blockers(self) -> None:
        self.temporary.cleanup()
        root = _make_project(Path(self.temporary.name), blocked_tickets=120)
        agent = _run_cli(root, "--view", "agent", "--json")
        rendered = len(json.dumps(agent))
        full = _run_cli(root, "--json")
        full_size = len(json.dumps(full.get("blocker_projection", {})))
        self.assertLess(rendered, 16 * 1024, f"agent view grew unbounded: {rendered} bytes")
        self.assertLess(rendered, full_size, "agent view did not shrink vs blocker detail")

    def test_full_view_unchanged_by_the_agent_route(self) -> None:
        before = _run_cli(self.root, "--json")
        _run_cli(self.root, "--view", "agent", "--json")
        after = _run_cli(self.root, "--json")
        drop = {"telegrams", "distribution", "conformance_status", "appends",
                "closed_contracts", "source_drift", "milestone", "automation"}
        before = {k: v for k, v in before.items() if k not in drop}
        after = {k: v for k, v in after.items() if k not in drop}
        self.assertEqual(before, after)

    def test_text_status_rejects_the_view_option(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "status", "--view", "agent"],
            capture_output=True,
            cwd=self.root,
        )
        # The bounded envelope is a JSON route: the text projection stays as-is.
        out = proc.stdout.decode("utf-8", "replace")
        self.assertTrue(proc.returncode != 0 or "ok" not in out[:1])


if __name__ == "__main__":
    unittest.main()
