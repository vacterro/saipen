"""T-1354: a blocked project must not mean a blocked agent.

Live report, reproduced: an OpenCode session entered AUDAPACK, was admitted at
the bootstrap binding, and from then on could read, glob and grep while EVERY
consequential tool was refused -- including a write to an unrelated
`V:\\_TEMP_` directory. The agent completed static analysis and returned
UPSTREAM_BLOCKED. It became an analyst because the infrastructure removed its
execution path, which is the failure mode SAIPEN exists to prevent.

The deciding measurement is that the two layers disagree. Asked about the same
blocked project through the same installed runtime, `evaluate_admission`
answers ADMITTED "protocol state sound" for an ordinary source edit, a new
file and a shell command, and refuses only the protected canonical path -- it
already refuses the minimum unsafe operation. The project-wide gate in
`saipen-guard.js` then overrides that with a total ban, because it admits only
`BOUND_VALID` and `NON_SAIPEN`.

Two distinct ways that becomes permanent:

  * an OPERATOR-ONLY condition (AUDAPACK's `RECONCILE_REAUTH_REQUIRED`, one
    2026-09-02 widget ticket) can never clear itself, so the ban is forever
    while a human is not looking;
  * an AUTOMATABLE condition whose repair cannot succeed keeps the ban too:
    `fleet prepare` answers `RECOVERY_FAILED` with `requires_reissue: true`
    after a repair that refused and moved nothing, so the model is told to
    reissue against "current bytes" that are the same bytes. Measured on three
    separate projects at once.

None of this is a stale verdict. `_RESOLVE_CACHE` memoises root resolution
only, `fleet.py` and `reconcile.py` cache nothing, and a blocked fixture goes
BLOCKED -> repaired -> BOUND_VALID inside one process. The refusal is honestly
recomputed every time; its SCOPE is the defect.

The invariant: REFUSE THE MINIMUM UNSAFE OPERATION. A condition blocks the work
that depends on it, and nothing else.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.admission import evaluate_admission  # noqa: E402
from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402
from test_opencode_adapter import PLUGIN, run_cases  # noqa: E402

NODE = shutil.which("node")


def setUpModule() -> None:
    isolate_host_session()


STATE = """---
phase: BUILD
task: T-1
next_action: "PHASE BUILD T-1"
blocker: ""
transition_from: SCOUT
saipen_version: 8
schema_version: 3
last_event: 100
style_contract: ded-4ae736e4
mode: full
updated: 2026-09-12T00:00:00Z
agent: test-agent
---
"""

# The DOING ticket is properly ALLOCATED; the legacy records below are not.
# That is the field shape -- a history where the allocation contract is in
# force and older records that predate it. With no allocation event at all the
# checker never engages and the fixture stops reproducing anything.
LOG = (
    "- 12.09.26 00:00 [E-99] [T-1] [agent: test-agent] [op: ticket-fixture] "
    "DEC: ticket added via SAIOPS\n"
    "- 12.09.26 00:00 [E-100] [agent: test-agent] RUN: reachability fixture\n"
)


def _board(extra: str = "") -> str:
    return (
        "## DOING\n"
        "- [/] T-1 [P1] reachability fixture work | verify: the matrix runs "
        "| owner: test-agent | claim_time: 2026-09-12T00:00:00Z\n"
        "## TODO\n" + extra + "## DONE\n## BLOCKED\n"
    )


def project(base: Path, name: str, *, board_extra: str = "") -> Path:
    root = base / name
    saipen = root / ".saipen"
    saipen.mkdir(parents=True)
    (saipen / "STATE.md").write_text(STATE, encoding="utf-8")
    (saipen / "BOARD.md").write_text(_board(board_extra), encoding="utf-8")
    (saipen / "LOG.md").write_text(LOG, encoding="utf-8")
    (saipen / "IDENTITY.md").write_text(
        identity_file_content(new_project_lineage()), encoding="utf-8"
    )
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    return root


def legacy_board_project(base: Path, name: str) -> Path:
    """Legacy records plus ONE modern recoverable defect (the field shape).

    Measured on three separate user projects: a BOARD record is oversized, the
    canonical repair is `saipen ticket compact T-###`, and the whole-board
    validation refused it because OTHER records predate the allocation
    contract. The named route could not run from the state that asked for it,
    so Fleet reported a failed repair forever and every consequential tool in
    those sessions was refused.
    """
    oversize = "x" * 4000
    extra = (
        f"- [ ] T-2 [P1] legacy oversized record {oversize} | verify: {oversize}\n"
        "- [ ] T-3 [P1] a legacy record with no allocation event | verify: legacy\n"
    )
    return project(base, name, board_extra=extra)


def fleet_prepare(root: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, str(TOOLS / "saipen.py"), "fleet", "prepare",
         "--cwd", str(root), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=hermetic_env(),
        timeout=600,
    )
    try:
        return json.loads(completed.stdout)
    except ValueError:
        raise AssertionError(
            f"fleet prepare produced no record (rc={completed.returncode})\n"
            f"{completed.stdout[-800:]}\n{completed.stderr[-800:]}"
        ) from None


class RecoveryLivenessTests(unittest.TestCase):
    """A named repair must be executable from the state that names it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1354-")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def test_the_named_repair_runs_on_a_legacy_board(self) -> None:
        """Point 1: unrelated legacy records are not this repair's veto."""
        root = legacy_board_project(self.base, "legacy")
        # preflight, not prepare: prepare would DISPATCH the repair, and this
        # case is about whether the named route can run at all.
        from saipen_engine.fleet import preflight

        first = preflight(str(root))
        self.assertEqual(
            first.get("reason_code"),
            "BOARD_RECORD_OVERSIZE",
            f"fixture no longer reproduces the field shape: {first.get('reason_code')}",
        )
        completed = subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "--project-root", str(root),
             "ticket", "compact", first["canonical_next_command"].split()[-1],
             "--dry-run", "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=hermetic_env(), timeout=600,
        )
        record = json.loads(completed.stdout)
        self.assertTrue(
            record.get("ok"),
            "the canonical repair the protocol itself names cannot run from the "
            f"state that names it: {record.get('detail')}",
        )
        self.assertGreater(
            record.get("carried_finding_count", 0),
            0,
            "the legacy records were silently legitimized rather than carried",
        )

    def test_convergence_is_bounded(self) -> None:
        """Points 3 and 7: N sanctioned steps, then VALID or one terminal state.

        Never `prepare -> SAFE repair -> refusal -> prepare -> same repair`.
        """
        root = legacy_board_project(self.base, "converge")
        seen = []
        for _ in range(8):
            record = fleet_prepare(root)
            seen.append((record.get("classification"), record.get("code")))
            if record.get("classification") in ("BOUND_VALID", "NON_SAIPEN"):
                break
            if record.get("operator_decision_available"):
                # A named terminal state IS a legal end: the automatic route
                # handed over to a human instead of spinning.
                self.assertTrue(record.get("canonical_next_command"), record)
                break
            self.assertFalse(
                record.get("requires_reissue")
                and record.get("code", "").startswith("RECOVERY_FAILED"),
                f"a failed repair asked for a reissue against unchanged bytes: {record}",
            )
        else:
            terminal = seen[-1]
            self.assertIn(
                terminal[1],
                ("RECOVERY_EXHAUSTED", "RECOVERY_NOT_AUTOMATABLE",
                 "BOUND_RECOVERY_REQUIRED_BLOCKED"),
                f"eight sanctioned steps neither converged nor reached a named "
                f"terminal state: {seen}",
            )
        self.assertLessEqual(len(seen), 8, seen)

    def test_the_reissue_demand_stops(self) -> None:
        """`requires_reissue` promises MOVED bytes, so it cannot be forever.

        A repair that actually changed the generation may legitimately ask the
        caller to reread once -- that is the protocol working. What must not
        survive is the demand repeating against bytes that stopped moving,
        which is how a real session refused every consequential tool forever.
        """
        root = legacy_board_project(self.base, "stuck")
        demands = []
        for _ in range(5):
            record = fleet_prepare(root)
            demands.append(bool(record.get("requires_reissue")))
            if not record.get("requires_reissue"):
                break
        self.assertFalse(
            demands[-1],
            f"five sanctioned calls and the reissue demand never stopped: {demands}",
        )


class OrdinaryWorkOutsideTheBlockedSurfaceTests(unittest.TestCase):
    """The per-operation layer already answers correctly; prove it stays."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1354-")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def test_admission_admits_ordinary_work_in_a_blocked_project(self) -> None:
        root = legacy_board_project(self.base, "stuck")
        for action, target in (("edit", "src/app.py"), ("write", "src/new.py")):
            with self.subTest(action=action):
                result = evaluate_admission(root, target_path=target, action=action)
                self.assertTrue(result["admitted"], result)

    def test_admission_still_refuses_the_canonical_surface(self) -> None:
        root = legacy_board_project(self.base, "stuck")
        result = evaluate_admission(root, target_path=".saipen/STATE.md", action="write")
        self.assertFalse(result["admitted"], result)
        self.assertEqual(result["code"], "PROTECTED_CANONICAL_NAMESPACE")

    def test_an_ordinary_file_outside_the_root_is_not_foreign_project_mutation(
        self,
    ) -> None:
        """T-1354: the `V:\\_TEMP_` refusal in the live report.

        A bound identity may not authorize mutation of ANOTHER SAIPEN
        PROJECT's canonical state -- T-1351 refuses that on every surface. An
        ordinary file in a directory that is no project at all is not that,
        and a shell command already writes it freely, so refusing the file
        tool is friction rather than protection.
        """
        root = project(self.base, "bound")
        scratch = self.base / "scratch-not-a-project"
        scratch.mkdir()
        target = scratch / "notes.txt"
        target.write_text("x\n", encoding="utf-8")
        result = evaluate_admission(
            root, target_path=str(target), action="write", explicit_root=root
        )
        self.assertTrue(
            result["admitted"],
            "a bound session was refused an unrelated file that belongs to no "
            f"project: {result}",
        )


@unittest.skipUnless(NODE, "node runtime unavailable")
class PluginGateScopeTests(unittest.TestCase):
    """The gate as the host loads it, driving the real plugin through node."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t1354-plugin-")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def _cases(self, root: Path) -> list[dict]:
        env = hermetic_env(SAIPEN_AGENT="test-agent")
        env = {k: v for k, v in env.items() if k.startswith("SAIPEN_")}
        # Exercise the engine UNDER TEST. Without this the plugin resolves the
        # INSTALLED skill root and the case silently measures whatever runtime
        # happens to be deployed on this machine instead of this working tree.
        env["SAIPEN_SKILL_ROOT"] = str(REPO)
        base = {"project": str(root), "env": env}
        return [
            # Issued TWICE on purpose. A first refusal can be honest: if the
            # canonical generation actually moved, the payload in hand is stale
            # and one reroute is the protocol working. What must not happen is
            # the SECOND action hitting the same wall -- that is a session that
            # can only read.
            {
                **base,
                "id": "ordinary-edit-first",
                "input": {"tool": "edit", "sessionID": "ses_reach_edit"},
                "output": {"args": {"filePath": str(root / "src" / "app.py"),
                                    "oldString": "x = 1"}},
            },
            {
                **base,
                "id": "ordinary-edit",
                "input": {"tool": "edit", "sessionID": "ses_reach_edit"},
                "output": {"args": {"filePath": str(root / "src" / "app.py"),
                                    "oldString": "x = 1"}},
            },
            {
                **base,
                "id": "protected-edit",
                "input": {"tool": "edit", "sessionID": "ses_reach_protected"},
                "output": {"args": {"filePath": str(root / ".saipen" / "STATE.md"),
                                    "oldString": "phase"}},
            },
        ]

    def test_ordinary_work_survives_an_legacy_board_project(self) -> None:
        root = legacy_board_project(self.base, "stuck")
        records = run_cases(PLUGIN, self._cases(root), self.base / "gate")
        by_id = {r["id"]: r for r in records}
        self.assertEqual(
            by_id["ordinary-edit"]["outcome"],
            "allowed",
            "a legacy board made an ordinary source edit impossible, so the "
            "agent can only read: "
            f"{by_id['ordinary-edit']['message']}",
        )
        self.assertEqual(
            by_id["protected-edit"]["outcome"],
            "blocked",
            "the canonical surface must stay refused whatever else is relaxed",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
