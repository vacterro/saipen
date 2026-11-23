"""T-149: `sub dispose` must be able to reach the package it retires.

The selection in `sub_disposition` used to require a READY package whose
`source_head` and `source_tree_fingerprint` still equalled the CURRENT ones.
`sub_collect` writes its receipt into the very tree the package recorded, so
every collected package was stale by construction and every dispose stopped at
`PACKAGE_INCOMPLETE` with "no current READY package to dispose" -- naming a
corrupt package when the package was in fact the only one that could be
retired.

The test asserts where dispose STOPS, not that it succeeds: reaching the
receipt check is the observable difference, and a full collect-to-dispose round
trip needs a real Core review ticket, which is integration territory.
"""

from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(TOOLS))

from saipen_engine import state as S  # noqa: E402
from saipen_engine import subs  # noqa: E402

SCENARIO = TOOLS.parent / "tests/scenarios/saiui-adoption/.saipen"
ROLE = "saiui"
#: The role revision the packaged fixture's UI-001 records.
FIXTURE_ROLE_REVISION = "sha256:f2e3685b908a3b9837917f12c5414628d847c35fb72567f0306e2c8b19a8dab8"
#: A recorded head that is well-formed but no longer the current one.
AGED_HEAD = "b" * 40
#: Its paired tree fingerprint, likewise well-formed and no longer current.
AGED_FINGERPRINT = "git-delta-v1:" + "c" * 64


class DisposeReachesCollectedPackageTests(unittest.TestCase):
    def _project(self) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        shutil.copytree(SCENARIO, root / ".saipen", dirs_exist_ok=True)
        # The shipped scenario predates the voice-contract marker, and STATE
        # validation refuses a checkpoint written against a STYLE.md the agent
        # never read -- so bind the scratch project to the installed one.
        installed = (
            TOOLS.parent / "saipen/STYLE.md"
        ).read_text(encoding="utf-8").split("style_contract: ", 1)[1].split()[0].strip("`")
        state_path = root / ".saipen/STATE.md"
        state_path.write_text(
            S.patch_state(
                state_path.read_text(encoding="utf-8"),
                {"saipen_home": str(TOOLS.parent.resolve()), "style_contract": installed},
            ),
            encoding="utf-8",
            newline="\n",
        )
        return root

    @staticmethod
    def _age_the_source_head(root: Path) -> None:
        """Reproduce what collect does to the tree the package recorded.

        The shipped fixture says `no-git`, which a non-git scratch root also
        computes -- so it would be current, and the selection defect would be
        invisible. Aging the recorded head to what a collect leaves behind is
        the state dispose is actually invoked in.

        The same pass repairs two fields the shipped scenario predates: the
        recorded head has to be a real 40-hex id to parse, and `verified` is
        now a closed verdict grammar rather than free prose.
        """
        outbox = root / subs.SUBS_REL / ROLE / "kitchen" / "OUTBOX.md"
        text = outbox.read_text(encoding="utf-8")
        text = text.replace("- **source_head:** no-git", f"- **source_head:** {AGED_HEAD}")
        text = re.sub(
            r"- \*\*source_tree_fingerprint:\*\* .*",
            f"- **source_tree_fingerprint:** {AGED_FINGERPRINT}",
            text,
        )
        text = re.sub(
            r"- \*\*verified:\*\* .*",
            "- **verified:** PASS -- pytest (12 passed); ruff clean",
            text,
        )
        outbox.write_text(text, encoding="utf-8", newline="\n")

    def test_dispose_reaches_the_collected_package(self):
        root = self._project()
        self._age_the_source_head(root)
        with mock.patch.object(
            subs, "current_local_role_revision", return_value=FIXTURE_ROLE_REVISION
        ):
            result = subs.sub_disposition(root, ROLE)

        self.assertNotEqual(
            result.code,
            "PACKAGE_INCOMPLETE",
            f"dispose stopped at package selection instead of reaching the receipt "
            f"check: {result.code}: {result.message}",
        )
        # Where it must stop: the collect receipt, not the package filter.
        self.assertIn("no durable collect receipt", str(result.message))


if __name__ == "__main__":
    unittest.main()
