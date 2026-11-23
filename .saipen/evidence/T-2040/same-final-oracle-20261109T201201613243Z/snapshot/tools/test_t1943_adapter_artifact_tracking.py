"""T-1943/SRC-342 R007: a registered adapter artifact must be in the repository.

MEASURED defect, 2026-10-27. `extensions/adapters/registry.json` declares the
ZAICODE adapter:

    "id": "zaicode",
    "hook_artifact": "extensions/adapters/zaicode/saipen-guard.py",
    "hook_install_surface": "~/.zcode/hooks/saipen-guard.py"

and the file exists on this disk, but `git ls-files extensions/adapters/zaicode/`
was EMPTY -- every sibling adapter (claude/, codex/, opencode/) is tracked, and
this one directory is not. So the registry's own promise
(`hook_artifact` is the shipped source) was false in every clone, while the
canonical validator printed:

    PASS: runtime manifest complete (…, all tracked)   # ignored, see below
    FAIL: runtime manifest names a file git does not track:
          extensions/adapters/zaicode/saipen-guard.py

The FAIL was reachable only because `extensions/adapters` is a manifest copy
tree. It was indistinguishable from unrelated untracked work, so nothing named
the specific defect: an adapter can be REGISTERED, SHIPPED and UNTRACKED at the
same time, and `admission.py` reads the artifact from DISK (`artifact.read_bytes()`),
so it reports the hook `current` on the one machine that has the file and
`UNKNOWN`/absent in every clone.

WHY THIS TEST AND NOT A VALIDATOR RULE. The validator already fails the path as
`runtime manifest names a file git does not track` (T-1592 message). What was
missing is the REGISTRY-level statement -- "every `hook_artifact` a host
declares must be a repository file" -- because that is the invariant a clone
depends on, and it is independent of whether the copy tree ever expands. The
check lives here so a green run means the registry and git agree, not that one
particular FAIL line was read.

WHY NOT ASSERT `git ls-files` FOR EVERY ADAPTER. A contribution checkout may be
a shallow export or a tarball with no `.git`; that is legal and must not fail.
The tracked set is therefore only consulted when this tree IS a repository, and
the assertion is about the declaration being satisfiable, not about the current
index having been committed by anyone in particular.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

REGISTRY_PATH = REPO / "extensions" / "adapters" / "registry.json"


def registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))


def adapters() -> list[dict]:
    return [entry for entry in registry().get("adapters", []) if isinstance(entry, dict)]


def git(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, (result.stdout + result.stderr)


def is_a_repository() -> bool:
    return git("rev-parse", "--git-dir")[0] == 0


class EveryDeclaredArtifactIsARepositoryFile(unittest.TestCase):
    """The registry promises a shipped source; git must carry the same file."""

    def test_every_hook_artifact_exists_on_disk(self) -> None:
        missing = []
        for entry in adapters():
            rel = entry.get("hook_artifact")
            if not rel:
                continue
            if not (REPO / rel).is_file():
                missing.append(f"{entry.get('id')}: {rel}")
        self.assertEqual(missing, [], f"declared hook artifacts absent: {missing}")

    def test_every_hook_artifact_is_tracked_when_this_is_a_repository(self) -> None:
        """SRC-342 R007. The defect: zaicode/ declared, present, untracked."""
        if not is_a_repository():
            self.skipTest("no .git here: an export or tarball is a legal checkout")
        rc, tracked_out = git("ls-files", "-z", "--", "extensions/adapters")
        self.assertEqual(rc, 0, tracked_out)
        tracked = {path for path in tracked_out.split("\x00") if path}
        untracked = []
        for entry in adapters():
            rel = entry.get("hook_artifact")
            if not rel or not rel.startswith("extensions/adapters/"):
                continue
            if (REPO / rel).is_file() and rel not in tracked:
                untracked.append(f"{entry.get('id')}: {rel}")
        self.assertEqual(
            untracked,
            [],
            "these registered adapter artifacts exist here and in no clone -- "
            "stage their content, then commit: " + "; ".join(untracked),
        )

    def test_the_zaicode_artifact_is_the_one_the_registry_names(self) -> None:
        """The specific declaration this ticket measured, pinned by name."""
        zaicode = {entry.get("id"): entry for entry in adapters()}.get("zaicode")
        self.assertIsNotNone(zaicode, "the zaicode adapter disappeared from the registry")
        self.assertEqual(
            zaicode["hook_artifact"], "extensions/adapters/zaicode/saipen-guard.py"
        )
        self.assertEqual(zaicode["hook_install_surface"], "~/.zcode/hooks/saipen-guard.py")
        self.assertTrue((REPO / zaicode["hook_artifact"]).is_file())


class NoSiblingIsRegisteredButUntracked(unittest.TestCase):
    """A general statement, so the next adapter cannot repeat this quietly."""

    def test_every_adapter_artifact_shares_one_tracking_state(self) -> None:
        if not is_a_repository():
            self.skipTest("no .git here")
        rc, tracked_out = git("ls-files", "-z")
        self.assertEqual(rc, 0, tracked_out)
        tracked = {path for path in tracked_out.split("\x00") if path}
        # `gemini` and `kiro` deliberately share `tools/host_guard.py`, so the
        # artifact set is deduplicated by path, not by adapter id.
        present = {
            entry["hook_artifact"]
            for entry in adapters()
            if entry.get("hook_artifact") and (REPO / entry["hook_artifact"]).is_file()
        }
        self.assertEqual(
            present - tracked,
            set(),
            "an adapter artifact exists on disk and in no index; every clone "
            "registers a host whose shipped source is missing",
        )

    def test_every_declared_artifact_is_a_path_git_can_track(self) -> None:
        """A `hook_artifact` outside the repository root could not be shipped."""
        undeclarable = []
        for entry in adapters():
            rel = entry.get("hook_artifact")
            if not rel:
                continue
            path = Path(str(rel))
            if path.is_absolute() or ".." in path.parts:
                undeclarable.append(f"{entry.get('id')}: {rel}")
        self.assertEqual(
            undeclarable,
            [],
            "a hook artifact must be a repository-relative path: " + "; ".join(undeclarable),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
