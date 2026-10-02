"""T-1514: compacted history keeps its verdict at any path.

An oversized LOG event is externalized to `.saipen/recovery/log-detail/`, and
its metadata recorded `project_identity` -- the realpath of the checkout,
which `paths.project_identity` documents as machine-local and never durable
evidence. The reader demanded it match. Measured 2026-09-24: a plain copy of
this repository turned T-1373, T-1400, T-1432 and T-1461 into closure-evidence
FAILs, which made `audit_checks` reject its own unmodified copy and skip the
whole mutation sweep. The lineage is the portable binding; a foreign lineage,
tampered bytes and a lineage-less project at another path still refuse.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.log import (  # noqa: E402
    MAX_NEW_EVENT_BYTES,
    read_history_snapshot,
    verification_evidence,
)
from saipen_engine.operations import apply_claim, checkpoint, transition_phase  # noqa: E402
from saipen_engine.paths import IDENTITY_NAME, SAIPEN_DIR, history_bound_here  # noqa: E402
from saipen_engine.paths import project_identity, project_lineage_identity  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_orchestration_repair import OrchestrationFixture  # noqa: E402

_DETAIL_REF = re.compile(r"detail_ref:\s*(\S+)$")


def setUpModule() -> None:
    isolate_host_session()


class PortableLogDetailTests(OrchestrationFixture):
    def verified_project(self) -> tuple[Path, str]:
        project = self.make_project()
        ticket = self.add(project, "portable evidence fixture")
        for step in (
            apply_claim(project, ticket, "tester"),
            transition_phase(project, "BUILD", "tester", ticket, "build it"),
            transition_phase(project, "VERIFY", "tester", ticket, "verify it"),
        ):
            self.assertTrue(step.ok, step.to_dict())
        verdict = f"verify -> PASS [target: {ticket}] conf: high -- " + "evidence " * (
            MAX_NEW_EVENT_BYTES // 8
        )
        done = checkpoint(project, "tester", "RUN", ticket, verdict)
        self.assertTrue(done.ok, done.to_dict())
        tail = (project / ".saipen" / "LOG.md").read_text(encoding="utf-8").splitlines()[-1]
        self.assertIsNotNone(_DETAIL_REF.search(tail), "the PASS was not externalized")
        return project, ticket

    def copy_of(self, project: Path) -> Path:
        base = Path(tempfile.mkdtemp(prefix="saipen-t1514-copy-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        target = base / "moved" / "project"
        shutil.copytree(project, target)
        return target

    @staticmethod
    def verdict(project: Path, ticket: str) -> bool:
        return verification_evidence(ticket, list(read_history_snapshot(project).events))[0]

    @staticmethod
    def detail_metadata(project: Path) -> Path:
        tail = (project / ".saipen" / "LOG.md").read_text(encoding="utf-8").splitlines()[-1]
        return project / _DETAIL_REF.search(tail).group(1)

    def test_the_compacted_pass_counts_in_place(self):
        project, ticket = self.verified_project()
        self.assertTrue(self.verdict(project, ticket))

    def test_the_compacted_pass_counts_in_a_copy_at_another_path(self):
        project, ticket = self.verified_project()
        moved = self.copy_of(project)
        self.assertNotEqual(project_identity(moved), project_identity(project))
        self.assertTrue(self.verdict(moved, ticket))

    def test_a_foreign_lineage_still_refuses(self):
        project, ticket = self.verified_project()
        moved = self.copy_of(project)
        metadata = self.detail_metadata(moved)
        record = json.loads(metadata.read_text(encoding="utf-8"))
        record["project_lineage"] = "lineage-" + "0" * 32
        metadata.write_text(json.dumps(record, indent=2), encoding="utf-8")
        self.assertFalse(self.verdict(moved, ticket))

    def test_tampered_detail_bytes_still_refuse(self):
        project, ticket = self.verified_project()
        moved = self.copy_of(project)
        record = json.loads(self.detail_metadata(moved).read_text(encoding="utf-8"))
        detail = moved / record["original_event_path"]
        detail.write_bytes(detail.read_bytes().replace(b"evidence", b"evidenc3", 1))
        self.assertFalse(self.verdict(moved, ticket))


class HistoryBindingRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="saipen-t1514-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "project"
        (self.root / SAIPEN_DIR).mkdir(parents=True)

    def test_a_lineage_less_project_stays_bound_to_its_path(self):
        self.assertIsNone(project_lineage_identity(self.root))
        here = project_identity(self.root)
        self.assertTrue(history_bound_here(here, None, self.root))
        self.assertFalse(history_bound_here("some-other-path", None, self.root))

    def test_a_lineage_project_ignores_the_path_and_refuses_another_lineage(self):
        from saipen_engine.paths import identity_file_content, new_project_lineage

        lineage = new_project_lineage()
        (self.root / SAIPEN_DIR / IDENTITY_NAME).write_text(
            identity_file_content(lineage), encoding="utf-8"
        )
        self.assertTrue(history_bound_here("some-other-path", lineage, self.root))
        self.assertFalse(history_bound_here(project_identity(self.root), None, self.root))
        self.assertFalse(
            history_bound_here(project_identity(self.root), new_project_lineage(), self.root)
        )


if __name__ == "__main__":
    unittest.main()
