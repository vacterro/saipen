"""T-1332: the validator must resolve protocol docs in BOTH install layouts.

A SAIPEN home is legitimately installed two ways: the source tree keeps the
normative documents under `saipen/`, and `bootstrap/inject.*` flattens that
folder into the skill root. A validator that derives a protocol path as
`_tools_parent / "saipen" / name` therefore crashes with FileNotFoundError in
every flattened install, and the failure surfaces upstream as
`FINDINGS_CAPTURE_FAILED` during a lifecycle transition (the exact defect this
ticket names).

WHAT THIS ORACLE PROVES, and why it is built the way it is.

The first version of this regression ran the SOURCE-layout capture from the
live checkout (`HOME`) and the flattened capture from a temp copy. That is not
hermetic, and an independent archive-context run found it: executed from an
AUDAPACK-produced source snapshot the suite went 1 PASS / 1 FAIL, with equal
ruleset fingerprints and exactly one source-only finding --

    cross-doc drift [root-file-set] -- _AUDAPACK_MANIFEST.json

The packager writes that file at the archive root. `validate.py`'s closed-set
check inspects the VALIDATOR HOME's own root and is gated on
`<home>/saipen/RFC.md`, so the source-layout home judged the packaging metadata
while the flattened home (no `saipen/`, therefore not a repo clone) skipped the
check entirely. The layout was no longer the only variable between the two
runs: the packaging context was too.

The cure is COMPLETE VALIDATOR PARITY over declared inputs (option B). BOTH
homes are now materialized by this test from the runtime manifest surface --
the exact set the injectors ship -- so neither home's root can carry a file the
manifest never declared. `_AUDAPACK_MANIFEST.json` is not a manifest entry, so
it is never copied into either home, and the check stays ARMED on the
source-layout home rather than silenced: a genuine stray in the shipped surface
would still be caught. The archive metadata and the source repository keep
their different semantics, and the oracle reads neither.

The project under validation is then varied deliberately: a NEUTRAL fixture
project the test constructs (nothing at its root but `.saipen/`), and the live
repository. The full finding set must agree across layouts for both.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
TOOLS = HOME / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402

from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    # An outer host session (SAIPEN_PROJECT_ROOT/LINEAGE, SAIPEN_AGENT, ...)
    # must never bind this module's disposable fixtures (test_hermetic_env).
    isolate_host_session()


_VALIDATOR = "tools/validate.py"
_CAPTURE_TIMEOUT = 1800

NEUTRAL_STATE = (
    '---\n'
    'phase: SCOUT\n'
    'task: none\n'
    'next_action: "PHASE SCOUT"\n'
    'blocker: ""\n'
    'transition_from: DONE\n'
    'saipen_version: 7\n'
    'schema_version: 3\n'
    'last_event: 1\n'
    'style_contract: '
    + CURRENT_STYLE_CONTRACT +
    '\nmode: full\n'
    'updated: 2026-09-15T00:00:00Z\n'
    'agent: test-agent\n'
    '---\n'
)

NEUTRAL_BOARD = """## DOING
## TODO
## DONE
## BLOCKED
"""

NEUTRAL_LOG = (
    "- 15.09.26 00:00 [E-001] [agent: test-agent] "
    "[op: transition-00000000000000000000000000000000] RUN: transition to SCOUT\n"
)


def _manifest_members() -> list[tuple[Path, str]]:
    """Every shipped file as (absolute source, repository-relative path).

    Derived from `saipen/MANIFEST.json`, so it is the DECLARED surface rather
    than whatever happens to be lying in the checkout. Anything a packager adds
    on top -- an archive manifest, a build receipt, an operator's scratch file
    -- is outside this set by construction and cannot reach the oracle.
    """
    from saipen_engine.runtime_surface import runtime_surface_items

    # T-1342: the one runtime-surface owner, the same inventory the generation
    # identity hashes. In the source layout a declared name IS the
    # repository-relative path.
    return [(member, declared) for declared, member in runtime_surface_items(HOME)]


def _build_home(destination: Path, *, flatten: bool) -> None:
    """Materialize one install layout from the declared manifest surface.

    `flatten=False` is the source layout (`saipen/` preserved); `flatten=True`
    is what `bootstrap/inject.*` produces. Both come from the SAME declared
    member list, so the layout is the only variable between them.
    """
    from autoinject import installed_relpath

    for member, relative in _manifest_members():
        target = destination / (installed_relpath(relative) if flatten else relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(member, target)


def _neutral_project(destination: Path) -> Path:
    """A minimal valid project whose root carries nothing but `.saipen/`."""
    memory = destination / ".saipen"
    memory.mkdir(parents=True)
    (memory / "IDENTITY.md").write_text(
        identity_file_content(new_project_lineage()), encoding="utf-8"
    )
    (memory / "STATE.md").write_text(NEUTRAL_STATE, encoding="utf-8")
    (memory / "BOARD.md").write_text(NEUTRAL_BOARD, encoding="utf-8")
    (memory / "LOG.md").write_text(NEUTRAL_LOG, encoding="utf-8")
    return destination


def _capture_findings(validator_root: Path, project_root: Path, out_path: Path):
    completed = subprocess.run(
        [
            sys.executable,
            str(validator_root / _VALIDATOR),
            "--gate",
            "core",
            "--project-root",
            str(project_root),
            "--findings-json",
            str(out_path),
            "--no-receipt",
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=_CAPTURE_TIMEOUT,
    )
    return completed


def _problem_keys(doc: dict) -> set[tuple[str, str]]:
    return {
        (p.get("severity", ""), p.get("detail_hash", "")) for p in doc.get("problems", [])
    }


def _problem_details(doc: dict) -> list[str]:
    return [str(p.get("detail", ""))[:200] for p in doc.get("problems", [])]


@unittest.skipUnless(
    (HOME / "saipen" / "MANIFEST.json").is_file(),
    "source home manifest is required to build the layout fixtures",
)
class InstalledValidatorLayoutParityTests(unittest.TestCase):
    def _homes(self, tmp: Path) -> tuple[Path, Path]:
        source = tmp / "source-home"
        flat = tmp / "flat-home"
        source.mkdir()
        flat.mkdir()
        _build_home(source, flatten=False)
        _build_home(flat, flatten=True)
        return source, flat

    def test_flattened_home_resolves_protocol_docs(self):
        """No protocol read may assume the source tree's `saipen/` prefix."""
        with tempfile.TemporaryDirectory(prefix="saipen-flat-home-") as raw:
            tmp = Path(raw)
            _source, flat = self._homes(tmp)
            self.assertTrue((flat / "CORE.md").is_file())
            self.assertFalse((flat / "saipen").exists())

            project = _neutral_project(tmp / "project")
            flat_out = tmp / "flat.json"
            flat_run = _capture_findings(flat, project, flat_out)
            self.assertTrue(
                flat_out.is_file(),
                "flattened validator produced no findings artifact "
                f"(exit={flat_run.returncode}); stderr tail:\n{flat_run.stderr[-2000:]}",
            )
            # The flattened runtime resolves every protocol document: no
            # FileNotFoundError, no FINDINGS_CAPTURE_FAILED.
            self.assertNotIn("FileNotFoundError", flat_run.stderr)
            self.assertNotIn("FINDINGS_CAPTURE_FAILED", flat_run.stderr)

    def _assert_parity(self, tmp: Path, project: Path, label: str) -> None:
        source, flat = self._homes(tmp)
        source_out = tmp / f"{label}-source.json"
        flat_out = tmp / f"{label}-flat.json"
        source_run = _capture_findings(source, project, source_out)
        flat_run = _capture_findings(flat, project, flat_out)

        self.assertTrue(
            source_out.is_file(),
            f"{label}: source-layout capture produced no artifact "
            f"(exit={source_run.returncode}); stderr tail:\n{source_run.stderr[-2000:]}",
        )
        self.assertTrue(
            flat_out.is_file(),
            f"{label}: flattened capture produced no artifact "
            f"(exit={flat_run.returncode}); stderr tail:\n{flat_run.stderr[-2000:]}",
        )

        source_doc = json.loads(source_out.read_text(encoding="utf-8"))
        flat_doc = json.loads(flat_out.read_text(encoding="utf-8"))

        self.assertEqual(
            source_doc.get("ruleset_fingerprint"),
            flat_doc.get("ruleset_fingerprint"),
            f"{label}: the two layouts disagreed on the ruleset fingerprint",
        )
        source_keys = _problem_keys(source_doc)
        flat_keys = _problem_keys(flat_doc)
        self.assertEqual(
            source_keys,
            flat_keys,
            f"{label}: the two layouts classified the project's problems "
            f"differently.\nsource-only: {_problem_details(source_doc)}\n"
            f"flat-only: {_problem_details(flat_doc)}",
        )

    def test_layouts_agree_on_a_neutral_project(self):
        """Complete validator parity with no packaging-only file anywhere."""
        with tempfile.TemporaryDirectory(prefix="saipen-layout-neutral-") as raw:
            tmp = Path(raw)
            self._assert_parity(tmp, _neutral_project(tmp / "project"), "neutral")

    def test_layouts_agree_on_the_live_repository(self):
        """The same parity against a real, fully populated project.

        The project under test is a FROZEN copy of the live home. Running the
        two layouts against the live tree itself raced its own source
        freshness: the validator fingerprints the project while sibling
        activity (a family run's own checkpoint writes, a co-seat's edits)
        touches the same tree, and the git-delta listing legitimately refused
        a tree that changed mid-read -- red under load, green standalone,
        proving nothing about layout parity. A frozen copy is the only input
        whose immutability the comparison can rely on.
        """
        with tempfile.TemporaryDirectory(prefix="saipen-layout-live-") as raw:
            tmp = Path(raw)
            frozen = tmp / "live-project"
            shutil.copytree(
                HOME,
                frozen,
                ignore=shutil.ignore_patterns(
                    ".git", "__pycache__", "*.pyc", "node_modules",
                    ".saipen/cache", ".saipen/locks", ".saipen/kitchen",
                ),
            )
            self._assert_parity(tmp, frozen, "live")

    def test_packaging_metadata_at_the_home_root_cannot_reach_the_oracle(self):
        """The hermetic seal, proven rather than assumed.

        This is the exact archive-context reproduction: a packager writes
        `_AUDAPACK_MANIFEST.json` beside the checkout. The homes this oracle
        builds come from the declared manifest surface, so the file is not a
        member and neither layout ever sees it. The closed-set check stays
        ARMED on the source-layout home -- it is not silenced, it simply has
        nothing undeclared to judge.
        """
        members = {relative for _source, relative in _manifest_members()}
        self.assertNotIn("_AUDAPACK_MANIFEST.json", members)
        with tempfile.TemporaryDirectory(prefix="saipen-layout-seal-") as raw:
            tmp = Path(raw)
            source, flat = self._homes(tmp)
            self.assertFalse((source / "_AUDAPACK_MANIFEST.json").exists())
            self.assertFalse((flat / "_AUDAPACK_MANIFEST.json").exists())
            # ARMED, not silenced: the source layout still presents itself as a
            # repository clone, which is what gates the closed-set check.
            self.assertTrue((source / "saipen" / "RFC.md").is_file())
            self.assertFalse((flat / "saipen").exists())


#: A root-file name in NO ANSI code page (box-drawing glyphs). A host hook that
#: runs its payload as commands writes exactly this kind of stray when the text
#: it read was Cyrillic and the console decoded it as cp866 (T-1475): four
#: letters become eight glyphs that cp1251, cp1252 and ASCII all refuse.
NON_LOCALE_STRAY = "╨╛╨┤╨╕╨╜"


@unittest.skipUnless(
    (HOME / "saipen" / "MANIFEST.json").is_file(),
    "source home manifest is required to build the layout fixtures",
)
class RootStrayLocaleTests(unittest.TestCase):
    """T-1558: a stray root file must FAIL the validator, never crash it.

    `[root-file-set]` pipes the root names into `git check-ignore --stdin`. Text
    mode encodes that pipe with the LOCALE (cp1251 on the operator's Windows
    host), so a stray outside the locale raised UnicodeEncodeError out of the
    validator: no findings artifact, `FINDINGS_CAPTURE_FAILED` on every
    pre-BUILD baseline, and the FAIL that names the writing hook (T-1475) was
    unreachable. Every other test here passes `PYTHONUTF8=1`, which is the
    local environment answering a global question.
    """

    @staticmethod
    def _narrow_locale_env() -> dict:
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONUTF8", "PYTHONIOENCODING", "LC_ALL", "LANG"}
        }
        # Windows: the ANSI code page decides. POSIX: the C locale is ASCII.
        env.update(
            {"PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0", "LC_ALL": "C"}
        )
        return env

    def test_non_locale_root_stray_is_reported_not_a_crash(self):
        with tempfile.TemporaryDirectory(prefix="saipen-stray-home-") as raw:
            tmp = Path(raw)
            home = tmp / "home"
            home.mkdir()
            _build_home(home, flatten=False)
            stray = home / NON_LOCALE_STRAY
            try:
                stray.write_text("", encoding="utf-8")
            except OSError as exc:  # a filesystem that cannot hold the name
                self.skipTest(f"filesystem refuses the stray name: {exc}")
            project = _neutral_project(tmp / "project")
            out_path = tmp / "findings.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(home / _VALIDATOR),
                    "--gate",
                    "core",
                    "--project-root",
                    str(project),
                    "--findings-json",
                    str(out_path),
                    "--no-receipt",
                ],
                cwd=str(project),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env=self._narrow_locale_env(),
                timeout=_CAPTURE_TIMEOUT,
            )
            self.assertNotIn(
                "UnicodeEncodeError",
                completed.stderr,
                "the validator crashed on a root name outside the locale:\n"
                + completed.stderr[-1500:],
            )
            self.assertTrue(
                out_path.is_file(),
                "no findings artifact: a stray root file must be a finding, "
                f"not a crash (exit={completed.returncode})",
            )
            self.assertIn("[root-file-set]", completed.stdout)
            self.assertIn(NON_LOCALE_STRAY, completed.stdout)


if __name__ == "__main__":
    unittest.main()
