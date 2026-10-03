"""T-147: the T-1352 generation exit must survive a stale style_contract.

RED CONTROL. `migrate_saipen_generation` reads the checkpoint with
`_read(root, allow_dead_home=True)`: it tolerates a dead `saipen_home`, because
proving the home is that operation's whole job. It does NOT tolerate a stale
`style_contract`, so the strict verdict from `parse_state_or_error` raises
StateMalformedError before the version comparison is ever reached. A project
that drifted on BOTH axes therefore cannot reach GENERATION_RECORDED -- and the
only remaining exit is hand-editing a protected canonical file, which the guard
correctly forbids. A guard whose refusal has no exit is a dead end, and this one
had two doors, both shut.

Reading tolerantly is not enough on its own: the WRITE must also land a state
that passes strict validation, so the fix has to record the whole generation
identity -- the version AND the style contract of the proven home -- not half of
it. These tests pin both halves.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = str(Path(__file__).resolve().parent)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import saipen_engine.operations as operations  # noqa: E402
from saipen_engine.codec import read_doc  # noqa: E402
from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402
from saipen_engine.state import (  # noqa: E402
    parse_state,
    running_home,
    parse_state_or_error,
    running_style_token,
)
from test_hermetic_env import isolate_host_session  # noqa: E402

STALE_STYLE = "ded-0000stale0000"

STATE_TEMPLATE = (
    "---\n"
    "phase: DONE\n"
    "task: none\n"
    'next_action: "saipen continue"\n'
    'blocker: ""\n'
    "transition_from: SHIP\n"
    "saipen_version: {version}\n"
    "schema_version: 3\n"
    "last_event: 100\n"
    "style_contract: {style}\n"
    'saipen_home: "{home}"\n'
    "mode: full\n"
    "updated: 2026-09-12T00:00:00Z\n"
    "agent: test-agent\n"
    "---\n"
)

BOARD = "## DOING\n## TODO\n## DONE\n## BLOCKED\n"
LOG = "- 12.09.26 00:00 [E-100] [agent: test-agent] RUN: generation fixture\n"


def _home(base: Path, version: str = "8.0.1") -> Path:
    """The REAL running home.

    `parse_state_or_error` only arms the style_contract check when the STATE's
    `saipen_home` resolves to the RUNNING home -- a foreign home is judged
    against its own generation instead. A fake temp home therefore reproduces
    no defect at all: it exercises a path the defect never touches. Bind the
    real one, and skip when it is not a loadable SAIPEN home.
    """
    root = Path(running_home())
    if not (root / "VERSION").is_file():
        raise unittest.SkipTest(f"running home {root} is not a loadable SAIPEN home")
    return root

def _project(base: Path, home_path: Path, declared: int, style: str) -> Path:
    root = base / "project"
    saipen = root / ".saipen"
    saipen.mkdir(parents=True)
    saipen.joinpath("STATE.md").write_text(
        STATE_TEMPLATE.format(version=declared, home=home_path, style=style),
        encoding="utf-8",
    )
    saipen.joinpath("BOARD.md").write_text(BOARD, encoding="utf-8")
    saipen.joinpath("LOG.md").write_text(LOG, encoding="utf-8")
    saipen.joinpath("IDENTITY.md").write_text(
        identity_file_content(new_project_lineage()), encoding="utf-8"
    )
    return root


def setUpModule() -> None:
    isolate_host_session()


class GenerationExitBehindStyleDrift(unittest.TestCase):
    """A drifted style_contract must not hide the generation exit."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="t147-")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.home = _home(self.base)

    def _migrate(self, declared: int, style: str):
        root = _project(self.base, self.home, declared, style)
        return root, operations.migrate_saipen_generation(root, "test-agent")

    def test_version_only_drift_still_reaches_generation_recorded(self) -> None:
        """The T-1352 baseline: this path already worked and must keep working."""
        current = running_style_token()
        _, result = self._migrate(7, current)
        self.assertEqual(result.code, "GENERATION_RECORDED", result.message)

    def test_style_drift_no_longer_hides_the_generation_exit(self) -> None:
        """The defect: both axes drifted, so the exit was unreachable."""
        _, result = self._migrate(7, STALE_STYLE)
        self.assertEqual(result.code, "GENERATION_RECORDED", result.message)

    def test_the_recorded_state_passes_strict_validation(self) -> None:
        """Reading tolerantly is not enough -- the WRITE must land clean too."""
        root, result = self._migrate(7, STALE_STYLE)
        self.assertEqual(result.code, "GENERATION_RECORDED", result.message)
        text = read_doc(root / ".saipen" / "STATE.md")
        error = parse_state_or_error(text)[1]
        self.assertIsNone(error, f"the migrated STATE is still malformed: {error}")
        self.assertEqual(parse_state(text).get("saipen_version"), 8)
        self.assertEqual(
            parse_state(text).get("style_contract"),
            running_style_token(),
            "recording the generation must carry the whole generation identity",
        )

    def test_style_drift_alone_is_not_a_generation_change(self) -> None:
        """Reaching the exit must not invent work: an equal major still refuses."""
        # The running home is the fixture's home, so "equal" is derived from
        # it rather than hardcoded -- a hardcoded major silently turns this
        # into a second copy of the drift test the day the version moves.
        equal = int(Path(self.home / "VERSION").read_text(encoding="utf-8").split(".")[0])
        _, result = self._migrate(equal, STALE_STYLE)
        self.assertNotEqual(result.code, "GENERATION_RECORDED")
        self.assertEqual(result.code, "VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
