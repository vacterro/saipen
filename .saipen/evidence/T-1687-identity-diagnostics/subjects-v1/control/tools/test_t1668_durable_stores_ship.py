"""T-1668: a clone keeps every durable store a tracked file cites.

Found in T-1640 REVIEW: a BOARD row over the live cap keeps a compact
projection and cites its full record by `detail_ref` under
`.saipen/recovery/board-compaction/`. This repository's `.gitignore` excluded
`.saipen/recovery/*` and excepted only `log-detail`, so none of the 308 detail
files was tracked while 101 live rows cited one; on a copy with the store moved
aside, as a clone has it, 56 of 56 cited references did not resolve and
`validate --gate core` printed the same findings as before.

* SHIP     -- git itself answers, for every root `runtime_namespace` calls
              durable under `.saipen/recovery/`, whether this repository's
              `.gitignore` ships it; one that is ignored needs a recorded
              `# unshipped-durable:` reason there, and a reason for a shipped
              root is stale.
* REPORT   -- the validator names a BOARD `detail_ref` that does not resolve,
              and the full record its metadata names.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import runtime_namespace  # noqa: E402
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

GIT = shutil.which("git")
VALIDATE_PY = TOOLS / "validate.py"
RECOVERY = ".saipen/recovery/"
_REASON = re.compile(r"^# unshipped-durable: (\S+) -- (.+\S)\s*$", re.MULTILINE)


def setUpModule() -> None:
    isolate_host_session()


def recorded_reasons(gitignore: str) -> dict[str, str]:
    return dict(_REASON.findall(gitignore))


def ignored(gitignore: str, paths: list[str]) -> set[str]:
    """The paths git ignores under `gitignore`, asked of git in a scratch repo."""
    with tempfile.TemporaryDirectory(prefix="saipen-t1668-git-") as raw:
        repo = Path(raw)
        subprocess.run([GIT, "init", "-q", str(repo)], check=True, capture_output=True)
        (repo / ".gitignore").write_text(gitignore, encoding="utf-8")
        # NUL-separated bytes: a text-mode pipe on Windows would hand git
        # every path with a trailing CR, and git ignores none of those.
        proc = subprocess.run(
            [GIT, "-C", str(repo), "check-ignore", "--no-index", "--stdin", "-z"],
            input=b"".join(path.encode("utf-8") + b"\0" for path in paths),
            capture_output=True,
            check=False,
        )
        return {item for item in proc.stdout.decode("utf-8").split("\0") if item}


def problems(gitignore: str, roots: tuple[str, ...]) -> list[str]:
    """Every durable recovery root this `.gitignore` drops without a reason,
    and every recorded reason that no longer describes an ignored store."""
    durable = [root for root in roots if root.startswith(RECOVERY)]
    probes = {root: root + "probe/record.json" for root in durable}
    dropped = {
        root for root, probe in probes.items() if probe in ignored(gitignore, list(probes.values()))
    }
    reasons = recorded_reasons(gitignore)
    found = [
        f"{root} is ignored with no recorded reason" for root in sorted(dropped - set(reasons))
    ]
    found += [f"{root} has a reason but ships" for root in sorted(set(reasons) - dropped)]
    found += [
        f"{root} has a reason but is not a durable store"
        for root in sorted(set(reasons) - set(durable))
    ]
    return found


@unittest.skipUnless(GIT, "git unavailable")
class ShipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    def test_every_durable_recovery_store_ships_or_names_its_reason(self):
        self.assertEqual(problems(self.gitignore, runtime_namespace.DURABLE_PROTECTED), [])
        for root in ("board-compaction", "board-compaction-lineage", "log-detail", "board-scrub"):
            with self.subTest(root=root):
                probe = f"{RECOVERY}{root}/T-1/T-1-x.json"
                self.assertNotIn(probe, ignored(self.gitignore, [probe]))
        for reason in recorded_reasons(self.gitignore).values():
            self.assertGreater(len(reason), 20, reason)

    def test_a_new_durable_store_cannot_be_dropped_silently(self):
        roots = (*runtime_namespace.DURABLE_PROTECTED, RECOVERY + "new-store/")
        self.assertEqual(
            problems(self.gitignore, roots),
            [f"{RECOVERY}new-store/ is ignored with no recorded reason"],
        )

    def test_a_reason_for_a_store_that_ships_is_stale(self):
        text = (
            self.gitignore + "# unshipped-durable: .saipen/recovery/log-detail/ -- old note here\n"
        )
        self.assertIn(
            ".saipen/recovery/log-detail/ has a reason but ships",
            problems(text, runtime_namespace.DURABLE_PROTECTED),
        )

    def test_the_release_receipts_a_clone_resolves_closures_against_ship(self):
        # closure._published_releases: the receipts a fresh clone must see.
        probes = [
            ".saipen/kitchen/release_receipt.json",
            ".saipen/kitchen/release_receipts/T-1-v1.json",
        ]
        self.assertEqual(ignored(self.gitignore, probes), set())
        self.assertIn(
            ".saipen/kitchen/scratch.log", ignored(self.gitignore, [".saipen/kitchen/scratch.log"])
        )

    def test_the_compaction_lineage_root_is_durable(self):
        from saipen_engine.board_compaction import LINEAGE_CHECKPOINT_ROOT

        self.assertIn(LINEAGE_CHECKPOINT_ROOT + "/", runtime_namespace.DURABLE_PROTECTED)


def _core_fails(root: Path) -> list[str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(VALIDATE_PY), "--gate", "core"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        env=env,
        cwd=str(root),
        timeout=600,
        check=False,
    )
    text = proc.stdout.decode("utf-8", errors="replace")
    return [line for line in text.splitlines() if line.startswith("FAIL")]


class ReportTests(unittest.TestCase):
    DETAIL = ".saipen/recovery/board-compaction/T-0007/T-0007-abc.json"
    ORIGINAL = ".saipen/recovery/board-compaction/T-0007/T-0007-abc.BOARD.md"

    def project(self) -> Path:
        root = fresh_project(phase="DONE", task="none", next_action="saipen continue")
        board = root / ".saipen" / "BOARD.md"
        board.write_text(
            "# Board\n## DOING\n## TODO\n"
            f"- [ ] T-0007 [P2] compact projection... | verify: proof | detail_ref: {self.DETAIL}\n"
            "## DONE\n## BLOCKED\n",
            encoding="utf-8",
        )
        return root

    def dangling(self, root: Path) -> list[str]:
        return [line for line in _core_fails(root) if "detail_ref does not resolve" in line]

    def test_a_missing_record_is_reported_and_a_present_one_is_not(self):
        root = self.project()
        found = self.dangling(root)
        self.assertEqual(len(found), 1, found)
        self.assertIn("T-0007", found[0])
        self.assertIn(self.DETAIL, found[0])
        meta = root / self.DETAIL
        meta.parent.mkdir(parents=True)
        meta.write_text(json.dumps({"original_record_path": self.ORIGINAL}), encoding="utf-8")
        (root / self.ORIGINAL).write_text("- [ ] T-0007 full text | verify: proof\n", "utf-8")
        self.assertEqual(self.dangling(root), [])

    def test_metadata_whose_full_record_is_gone_is_reported(self):
        root = self.project()
        meta = root / self.DETAIL
        meta.parent.mkdir(parents=True)
        meta.write_text(json.dumps({"original_record_path": self.ORIGINAL}), encoding="utf-8")
        found = self.dangling(root)
        self.assertEqual(len(found), 1, found)
        self.assertIn(self.ORIGINAL, found[0])


if __name__ == "__main__":
    unittest.main()
