"""T-1555: editing STYLE.md must not red the fixture world.

`style_contract` was a global chokepoint: 13 scenario STATE fixtures, an
evidence script and the project STATE each hardcoded the live marker, so any
STYLE.md edit -- a legitimate document change -- instantly reded the whole
validation surface. The fix is ownership, not tolerance: fixture bytes carry
the `ded-0facade0` placeholder and every materialization site resolves the
LIVE marker of the installation it runs against. This oracle holds both
halves: a static scan that no real marker is hardcoded where a placeholder
belongs, and a behavioral proof that a STYLE.md edit in a sandboxed install
leaves the fixture suite green -- plus the control that removing the
restamp makes that edit red again, so the oracle can actually fail.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_fixture_support import LIVE_PLACEHOLDER  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

MARKER_RE = re.compile(r"ded-[0-9a-f]{8}")
#: The only hex markers a scenario fixture may carry: the live-resolving
#: placeholder, and the deliberately-wrong hostile fixture's deadbeef.
ALLOWED_IN_SCENARIOS = {LIVE_PLACEHOLDER, "ded-deadbeef"}
#: A deliberately-wrong marker assertion must stay pinned to its reason.
HOSTILE_STYLE_FIXTURES = {"hr-wrong-style_contract", "hr-missing-style_contract"}
#: Infixes a before/after evidence capture inserts into its subject's file
#: name: `audit_checks.py` is captured as `audit_checks.before.py`.
CAPTURE_INFIXES = (".before", ".after", ".orig")


def _subject_file_name(script_name: str) -> str:
    """The shipped file an evidence script is a capture of, or itself."""
    if not script_name.endswith(".py"):
        return script_name
    stem = script_name[: -len(".py")]
    for infix in CAPTURE_INFIXES:
        if stem.endswith(infix):
            return stem[: -len(infix)] + ".py"
    return script_name


def _shipped_subject_markers(script_name: str) -> set[str] | None:
    """Markers the shipped subject of an evidence script already carries.

    An evidence script is not always hand-authored: a seat captures the bytes
    of a production file as `audit_checks.before.py` / `run_scenarios.py` to
    prove a before/after pair, and those bytes carry the subject's own marker.
    Such a copy is a record of the subject, not a second place that has to be
    edited when STYLE.md moves, so it inherits the subject's markers instead of
    counting as a hardcoded one. A marker the subject does NOT have stays a
    hardcoded marker and still fails -- the boundary is inheritance, not a
    blanket exemption for anything parked under a candidate directory (T-1589).
    """
    subject = TOOLS / _subject_file_name(script_name)
    if not subject.is_file():
        return None
    return set(MARKER_RE.findall(subject.read_text(encoding="utf-8-sig")))


def _novel_markers(script_name: str, markers: set[str]) -> set[str]:
    """Markers an evidence script hardcodes rather than inherits."""
    inherited = _shipped_subject_markers(script_name)
    if inherited is None:
        return markers
    return markers - inherited


def setUpModule() -> None:
    isolate_host_session()


def _sandbox_install(case: unittest.TestCase) -> Path:
    """A disposable install whose STYLE.md claims a DIFFERENT live marker.

    Copies exactly what `tools/validate.py` needs (the engine, the protocol
    documents) and edits the sandbox STYLE.md's boot marker, which is the
    chokepoint scenario in miniature: the install moved on, and the fixture
    world must not fall over.
    """
    home = Path(tempfile.mkdtemp(prefix="saipen-t1555-home-"))
    case.addCleanup(shutil.rmtree, home, True)
    # The validator's sibling tools modules (freshness, improve, autoinject,
    # userperson, ...) resolve next to validate.py, so the sandbox carries
    # every non-test tool script plus the engine and the protocol documents.
    (home / "tools").mkdir()
    for script in (ROOT / "tools").glob("*.py"):
        if not script.name.startswith("test_"):
            shutil.copy2(script, home / "tools" / script.name)
    shutil.copytree(ROOT / "tools" / "saipen_engine", home / "tools" / "saipen_engine")
    shutil.copytree(ROOT / "saipen", home / "saipen")
    shutil.copytree(ROOT / "extensions", home / "extensions")
    # A REAL STYLE.md edit: the marker is the hash of the file's own text
    # minus its declaration line, so the sandbox changes the body and then
    # redeclares the honestly-derived marker -- exactly what a legitimate
    # STYLE.md edit does to every hardcoded token downstream.
    from saipen_engine.state import style_contract_token

    style = home / "saipen" / "STYLE.md"
    text = style.read_text(encoding="utf-8-sig")
    original = style_contract_token(text)
    edited = text.rstrip("\n") + "\n\n<!-- T-1555 sandbox voice edit -->\n"
    derived = style_contract_token(edited)
    assert derived != original, "the sandbox edit changed no bytes the hash sees"
    style.write_text(MARKER_RE.sub(derived, edited), encoding="utf-8", newline="")
    return home


class StaticChokepointTests(unittest.TestCase):
    def test_scenario_fixtures_carry_no_install_specific_marker(self):
        offenders = []
        for state in (ROOT / "tests" / "scenarios").rglob("STATE.md"):
            for marker in MARKER_RE.findall(state.read_text(encoding="utf-8-sig")):
                if marker not in ALLOWED_IN_SCENARIOS:
                    offenders.append(f"{state.relative_to(ROOT)}: {marker}")
        self.assertEqual(offenders, [], "hardcoded live/retired markers: " + "; ".join(offenders))

    def test_the_placeholder_is_actually_used_and_the_hostile_pair_stays_wrong(self):
        placeholders = sum(
            1
            for state in (ROOT / "tests" / "scenarios").rglob("STATE.md")
            if LIVE_PLACEHOLDER in state.read_text(encoding="utf-8-sig")
        )
        self.assertGreaterEqual(
            placeholders, 13, "fixtures regressed to raw copytree materialization"
        )
        for name in HOSTILE_STYLE_FIXTURES:
            readme = (ROOT / "tests" / "scenarios" / name / "README.md").read_text(
                encoding="utf-8-sig"
            )
            self.assertIn("expect_fail_contains: style_contract", readme, name)

    def test_evidence_scripts_hardcode_no_marker(self):
        offenders = []
        evidence = ROOT / ".saipen" / "evidence"
        for script in evidence.rglob("*.py") if evidence.is_dir() else []:
            markers = set(MARKER_RE.findall(script.read_text(encoding="utf-8-sig")))
            for marker in sorted(_novel_markers(script.name, markers)):
                offenders.append(f"{script.relative_to(ROOT)}: {marker}")
        self.assertEqual(
            offenders, [], "hardcoded markers in evidence scripts: " + "; ".join(offenders)
        )

    def test_a_captured_copy_inherits_its_subject_markers_only(self):
        # The boundary is inheritance, so both directions are pinned: a
        # capture of a shipped subject carries no novel marker, and the same
        # capture carrying anything else -- or any script with no shipped
        # subject at all -- is still a hardcoded marker.
        self.assertEqual(
            _novel_markers("audit_checks.before.py", {"ded-deadbeef"}), set()
        )
        self.assertEqual(
            _novel_markers("audit_checks.py", {"ded-deadbeef"}), set()
        )
        self.assertEqual(
            _novel_markers("run_scenarios.py", {"ded-00000000", "ded-deadbeef"}), set()
        )
        self.assertEqual(
            _novel_markers("audit_checks.before.py", {"ded-00000000"}),
            {"ded-00000000"},
            "a marker the subject does not carry is still hardcoded",
        )
        self.assertEqual(
            _novel_markers("hand_written_probe.py", {"ded-deadbeef"}),
            {"ded-deadbeef"},
            "a script with no shipped subject inherits nothing",
        )

    def test_a_hand_written_evidence_probe_still_fails(self):
        # The red control for the exemption above: an evidence script that
        # hardcodes a marker with no shipped subject behind it must still be
        # reported, so the boundary cannot become a blanket candidate-dir skip.
        with tempfile.TemporaryDirectory(prefix="saipen-evidence-probe-") as td:
            probe = Path(td) / "evidence_probe.py"
            probe.write_text("STYLE = 'ded-deadbeef'\n", encoding="utf-8")
            markers = set(MARKER_RE.findall(probe.read_text(encoding="utf-8")))
            self.assertEqual(_novel_markers(probe.name, markers), {"ded-deadbeef"})


class BehavioralChokepointTests(unittest.TestCase):
    def _run_fixture_loop(self, home: Path, scenarios: Path) -> tuple[list[str], int, int]:
        import run_scenarios

        with mock.patch.object(run_scenarios, "HOME", home), mock.patch.object(
            run_scenarios, "VALIDATOR", home / "tools" / "validate.py"
        ), mock.patch.object(run_scenarios, "SCENARIOS", scenarios):
            return run_scenarios.run_scenario_fixture_probes(enabled=True)

    def _sandbox_scenarios(self, home: Path) -> Path:
        """One expect:pass fixture (bytes carry the placeholder) + the two
        deliberately-wrong style fixtures, under a scenario root of their own."""
        scenarios = home / "tests" / "scenarios"
        source = ROOT / "tests" / "scenarios" / "userperson-valid"
        shutil.copytree(source, scenarios / "userperson-valid")
        for name in HOSTILE_STYLE_FIXTURES:
            shutil.copytree(ROOT / "tests" / "scenarios" / name, scenarios / name)
        return scenarios

    def test_a_style_edit_leaves_the_fixture_suite_green(self):
        home = _sandbox_install(self)
        scenarios = self._sandbox_scenarios(home)
        failures, checked, _skipped = self._run_fixture_loop(home, scenarios)
        self.assertEqual(failures, [], "; ".join(failures))
        self.assertGreaterEqual(checked, 3, "the loop checked nothing")

    def test_control_without_the_restamp_the_same_edit_reds(self):
        # The pre-fix subject: materialize the fixture bytes verbatim. The
        # placeholder then meets the sandbox's edited marker and the fixture
        # fails exactly the way the 13 reds did -- proving the oracle sees
        # the chokepoint it exists to guard. run_scenarios imports the helper
        # inside the loop, so the patch must land on its SOURCE module.
        import test_fixture_support

        home = _sandbox_install(self)
        scenarios = self._sandbox_scenarios(home)
        with mock.patch.object(test_fixture_support, "restamp_live_style", lambda root, *a, **k: 0):
            failures, checked, _skipped = self._run_fixture_loop(home, scenarios)
        self.assertGreaterEqual(checked, 1)
        self.assertTrue(
            any("userperson-valid" in line for line in failures),
            failures,
        )


if __name__ == "__main__":
    unittest.main()
