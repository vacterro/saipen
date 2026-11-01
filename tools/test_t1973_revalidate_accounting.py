"""T-1973 -- the external recovery surface must never report "nothing to do"
while a DONE closure it owns does not resolve.

`saipen ticket resolve-external --revalidate` is the recovery route a cold agent
is sent to when `validate.py` says a closure's provenance no longer resolves.
On the live tree it answered:

    discovered 0   inspected 0   revalidated 0   resolved []   predicted []

while T-1653 still cited EX-000029, `external.resolution_problems` returned a
non-empty list for it, and `validate.py` printed

    FAIL: closure provenance does not resolve: EX-000029 was verified against
    installed engine generation sha256:06c1149a... but the running engine is
    sha256:6f2cd4c3...; external implementation differs from its carrying
    commit: Scripts/accounts/SaiAccounts.cs; external verifier
    context/runtime/argv changed since the receipt

The cause is one filter. Section 1 of `revalidate_external_dependencies`
iterates DONE Work that cites a receipt and admits a candidate only when

    engine_moved and not other_problems

Every other non-empty `problems` list -- a moved external artifact, a changed
verifier argv, a corrupted predecessor -- is dropped with no counter, no
finding and no mention. The revalidator therefore reports a clean sweep over
work it never looked at. That is the same class of defect the campaign exists
to close: a surface answering a question it did not measure.

The oracle below drives the real function over a fixture project. It does not
assert on prose; it asserts that a non-green DONE closure is accounted for in
the returned report, either as a candidate or as a named blocking finding, and
that a green closure still produces silence.
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

from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from saipen_engine import external as ext_mod  # noqa: E402

EXT_LINEAGE = "lineage-ded945ae8243480ab1bfee73baeb29c6"


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _make_external_repo(tmp: Path) -> tuple[Path, str]:
    """A committed sibling project carrying the implementation commit."""
    ext_root = tmp / "external_repo"
    (ext_root / ".saipen").mkdir(parents=True, exist_ok=True)
    (ext_root / ".saipen" / "IDENTITY.md").write_text(
        f"---\nproject_lineage: {EXT_LINEAGE}\n---\n", encoding="utf-8"
    )
    (ext_root / ".saipen" / "BOARD.md").write_text(
        "# Board\n## DOING\n## TODO\n## DONE\n"
        "- [x] T-289 [P1] readiness separation | evidence: implemented\n"
        "## BLOCKED\n",
        encoding="utf-8",
    )
    (ext_root / "carrier.txt").write_text("implementation\n", encoding="utf-8")
    _git(ext_root, "init", "-q", ".")
    _git(ext_root, "config", "user.email", "fixture@example.invalid")
    _git(ext_root, "config", "user.name", "fixture")
    _git(ext_root, "add", "--", ".saipen/IDENTITY.md", ".saipen/BOARD.md", "carrier.txt")
    _git(ext_root, "-c", "commit.gpgsign=false", "commit", "-qm", "carrier")
    return ext_root, _git(ext_root, "rev-parse", "HEAD")[:8]


def _sealed_contract(loc_repo: Path, work: str) -> str:
    """The only executable authority the revalidator accepts."""
    relative = f".saipen/evidence/ext-contracts/{work}.json"
    path = loc_repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "command": ["{python}", "-c", "import sys; sys.exit(0)"],
                "format": "pytest",
                "context": ["README.md"],
                "oracle_files": ["README.md"],
                "subject_files": [],
                "timeout": 120,
            }
        ),
        encoding="utf-8",
    )
    return relative


def _make_local_repo(tmp: Path, commit: str, *, done_row: bool) -> tuple[Path, str]:
    """A project whose BI-side row is DONE and cites an external receipt.

    The project memory is written here rather than copied from
    `tests/scenarios/`, because the measured pair runs each half inside a
    sandbox that carries only the declared context (`tools`, `saipen`). A
    fixture read from a path outside that context turns both halves into an
    ERROR, which the pair gate correctly refuses as not-FAIL-then-PASS.
    """
    loc_root = tmp / "local_repo"
    (loc_root / ".saipen").mkdir(parents=True, exist_ok=True)
    (loc_root / "README.md").write_text("fixture\n", encoding="utf-8")
    (loc_root / ".saipen" / "IDENTITY.md").write_text(
        f"---\nproject_lineage: {EXT_LINEAGE}\n---\n", encoding="utf-8"
    )
    (loc_root / ".saipen" / "LOG.md").write_text(
        "# Log\n\n- 01.01.26 00:00 [E-1] [agent: tester] DEC: fixture\n", encoding="utf-8"
    )
    (loc_root / ".saipen" / "STATE.md").write_text(
        "---\n"
        "phase: DONE\n"
        "task: none\n"
        'next_action: "PHASE DONE"\n'
        "blocker: none\n"
        "transition_from: DONE\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        "last_event: 1\n"
        f"style_contract: {CURRENT_STYLE_CONTRACT}\n"
        "agent: tester\n"
        "mode: full\n"
        'updated: "2026-09-20T00:00:00Z"\n'
        "---\n",
        encoding="utf-8",
    )
    contract = _sealed_contract(loc_root, "T-100")
    row = (
        "- [x] T-100 [P1] upstream fix | verify: python -B tools/test_ext.py | "
        f"external_authority: {EXT_LINEAGE} | "
        f"external_implementation: T-289@{commit} | "
        f"verification_contract: {contract} | "
        "external_evidence: EX-000001 | closure_mode: external_implementation | "
        "resolution_reason: DEPENDENCY_UPGRADE_VERIFIED\n"
    )
    (loc_root / ".saipen" / "BOARD.md").write_text(
        "# Board\n## DOING\n## TODO\n## DONE\n" + row + "## BLOCKED\n",
        encoding="utf-8",
    )
    return loc_root, contract


class ANonGreenDoneClosureIsNeverSilentlyDropped(unittest.TestCase):
    """Section 1 must account for every DONE closure it does not re-execute."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def _report(self, loc_repo: Path, **kwargs) -> dict:
        return ext_mod.revalidate_external_dependencies(
            loc_repo, "tester", dry_run=True, **kwargs
        )

    def test_a_moved_external_artifact_is_reported_not_dropped(self):
        """Engine still (the unchanged oracle); the EXTERNAL bytes moved.

        This is the live shape: the external product shipped new code, so the
        immutable snapshot no longer matches. Before the fix the revalidator
        counted nothing at all and the operator was told `discovered: 0`.
        """
        ext_repo, commit = _make_external_repo(self.tmp)
        loc_repo, _contract = _make_local_repo(self.tmp, commit, done_row=True)

        receipt = ext_mod.build_receipt(
            root=loc_repo,
            receipt_id="EX-000001",
            work="T-100",
            project_identity="fixture",
            project_lineage=EXT_LINEAGE,
            agent="tester",
            created_at="2026-01-01T00:00:00Z",
            authority=EXT_LINEAGE,
            implementation=f"T-289@{commit}",
            resolution_reason="DEPENDENCY_UPGRADE_VERIFIED",
            defect_contract_digest="sha256:" + "0" * 64,
            defect_contract_text="fixture",
            prior_blocker_sha256="",
            verification=[],
            verification_contract_digest="sha256:" + "0" * 64,
            verdict="PASS",
            op_id="resolve-external-fixture",
            external_snapshot={
                "authority": EXT_LINEAGE,
                "implementation": f"T-289@{commit}",
                "root": str(ext_repo),
                "files": {"carrier.txt": "0" * 64},
                "runtime_inputs": {},
            },
        )
        receipt["installed_identity"] = ext_mod.engine_identity()
        target = loc_repo / ext_mod.EXTERNAL_DIR / "EX-000001.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")

        problems = ext_mod.resolution_problems(loc_repo, "T-100", {"fields": {
            "external_evidence": "EX-000001",
            "external_authority": EXT_LINEAGE,
            "external_implementation": f"T-289@{commit}",
            "resolution_reason": "DEPENDENCY_UPGRADE_VERIFIED",
        }})
        self.assertTrue(problems, "fixture must be non-green for this test to mean anything")

        report = self._report(loc_repo)
        accounted = (
            report.get("inspected", 0)
            + report.get("discovered", 0)
            + len(report.get("still_blocked") or [])
            + len(report.get("inaccessible") or [])
        )
        self.assertGreater(
            accounted,
            0,
            "a DONE closure that does not resolve must appear in the report; "
            "reporting inspected=0/discovered=0/resolved=[] over it is a false "
            "clean sweep",
        )
        named = [
            finding
            for finding in (report.get("still_blocked") or [])
            if finding.get("ticket") == "T-100"
        ]
        self.assertTrue(
            named,
            "the finding must name the Work, not just increment a counter: "
            f"got {json.dumps(report, sort_keys=True)[:600]}",
        )

    def test_a_resolving_closure_stays_silent(self):
        """The control: a green closure must not become noise."""
        _ext_repo, commit = _make_external_repo(self.tmp)
        loc_repo, _contract = _make_local_repo(self.tmp, commit, done_row=True)
        report = self._report(loc_repo)
        named = [
            finding
            for finding in (report.get("still_blocked") or [])
            if finding.get("ticket") == "T-100"
        ]
        self.assertEqual(named, [], "an unblocked Work must not be reported")
        self.assertEqual(report.get("inspected", 0), 0)


if __name__ == "__main__":
    unittest.main()
