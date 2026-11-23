"""T-1508: byte-bound SAIPEN evidence survives Git line-ending conversion.

Measured incident (managed project, 2026-09-24): Git for Windows defaults to
core.autocrlf=true and the project had no `.gitattributes`. Four
`git stash -u` round-trips rewrote seven untracked archived sources with CRLF
while their recorded digests were of the LF bytes, so attribution refused
them with a bare ARCHIVE_BODY_SHA_MISMATCH and status reported
SOURCE_CORRUPTION with no cause.

Covered here:
  * the policy: every byte-bound path is `-text`; a rule the project already
    has (any spelling, a broader pattern Git resolves, `binary`) is honoured,
    a later `text` override is not, and only the missing rules are appended
    without rewriting the existing bytes, BOM or line-ending style;
  * the mechanism itself, red and green: the same stash round-trip converts
    an untracked archived body without the policy and keeps it exact with it;
  * every new capture re-establishes a missing policy, including in a
    project adopted before the policy existed;
  * the diagnosis: drift is named with the path and the proven repair, a
    genuine byte change stays a bare mismatch, a source that really arrived
    with CRLF is not drift, and the named repair restores integrity.

Run standalone:
    python tools/test_t1508_byte_bound_attributes.py
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
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402

from saipen_engine import intake  # noqa: E402
from saipen_engine import runtime_namespace as rn_mod  # noqa: E402
from saipen_engine.paths import unbound_environment  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

SAIPEN_PY = TOOLS / "saipen.py"
SCENARIO = ROOT / "tests" / "scenarios" / "stale-state-reconciliation" / ".saipen"
ALL_PATTERNS = [pattern for pattern, _probe in rn_mod.BYTE_BOUND_PATTERNS]

STATE = f"""---
phase: DONE
task: none
next_action: "PHASE DONE"
blocker: none
transition_from: DONE
saipen_version: 8
schema_version: 3
last_event: 2
style_contract: {CURRENT_STYLE_CONTRACT}
saipen_home: "{ROOT}"
agent: tester
mode: full
updated: "2026-09-24T00:00:00Z"
---
"""
LOG = "- 24.09.26 00:00 [E-001] [T-900] RUN: historical build finished\n"
BOARD = "# Board\n## DOING\n## TODO\n## DONE\n## BLOCKED\n"


def setUpModule() -> None:
    isolate_host_session()


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=tester",
            "-c",
            "user.email=tester@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-C",
            str(root),
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=unbound_environment(),
        timeout=120,
    )


def _rules(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.endswith(" -text")]


class PolicyTests(unittest.TestCase):
    """What counts as protected, and what an application may write."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-t1508-policy-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir(parents=True)
        self.attributes = self.root / ".gitattributes"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_absent_policy_gets_every_rule_once(self):
        self.assertEqual(rn_mod.attributes_policy(self.root)["missing"], ALL_PATTERNS)
        self.assertEqual(rn_mod.attributes_policy_state(self.root), "ABSENT")
        first = rn_mod.ensure_gitattributes_policy(self.root)
        self.assertEqual(first["code"], "ATTRIBUTES_POLICY_ADDED")
        once = self.attributes.read_bytes()
        self.assertEqual(_rules(once.decode("utf-8")), [f"{p} -text" for p in ALL_PATTERNS])
        self.assertEqual(rn_mod.attributes_policy_state(self.root), "CURRENT")
        second = rn_mod.ensure_gitattributes_policy(self.root)
        self.assertEqual(second["code"], "ATTRIBUTES_POLICY_CURRENT")
        self.assertEqual(self.attributes.read_bytes(), once)

    def test_rules_without_the_marker_are_not_duplicated(self):
        # The SAIPEN home's own shape: three rules written by hand, no marker.
        existing = (
            b"* text=auto\n"
            b".saipen/intake/** -text\n"
            b".saipen/archive/source/** -text\n"
            b".saipen/archive/retired/** -text\n"
        )
        self.attributes.write_bytes(existing)
        self.assertEqual(rn_mod.attributes_policy_state(self.root), "PARTIAL")
        result = rn_mod.ensure_gitattributes_policy(self.root)
        self.assertEqual(result["added"], ALL_PATTERNS[3:])
        after = self.attributes.read_bytes()
        self.assertTrue(after.startswith(existing), "existing bytes are never rewritten")
        self.assertEqual(
            sorted(_rules(after.decode("utf-8"))), sorted(f"{p} -text" for p in ALL_PATTERNS)
        )

    def test_crlf_bom_file_keeps_its_bytes_and_style(self):
        existing = b"\xef\xbb\xbf*.png binary\r\n*.sh text eol=lf"
        self.attributes.write_bytes(existing)
        rn_mod.ensure_gitattributes_policy(self.root)
        after = self.attributes.read_bytes()
        self.assertTrue(after.startswith(existing + b"\r\n\r\n"))
        appended = after[len(existing) :]
        self.assertNotIn(b"\n", appended.replace(b"\r\n", b""), "no bare LF in a CRLF file")
        self.assertEqual(rn_mod.attributes_policy_state(self.root), "CURRENT")

    def test_binary_counts_and_a_later_text_override_does_not(self):
        lines = [f"{pattern} binary" for pattern in ALL_PATTERNS]
        lines.append(".saipen/intake/** text")
        self.attributes.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertEqual(rn_mod.attributes_policy(self.root)["missing"], [".saipen/intake/**"])

    def test_a_broader_rule_git_resolves_is_honoured(self):
        self.assertEqual(_git(self.root, "init").returncode, 0)
        self.attributes.write_text(".saipen/** -text\n", encoding="utf-8")
        self.assertEqual(rn_mod.attributes_policy_state(self.root), "CURRENT")
        result = rn_mod.ensure_gitattributes_policy(self.root)
        self.assertEqual(result["code"], "ATTRIBUTES_POLICY_CURRENT")
        self.assertEqual(self.attributes.read_text(encoding="utf-8"), ".saipen/** -text\n")

    def test_evidence_is_not_in_the_policy(self):
        # Tracked test output is ordinary text; marking it -text would show
        # every CRLF working copy as modified.
        self.assertFalse(any(p.startswith(".saipen/evidence") for p in ALL_PATTERNS))


class StashRoundTripTests(unittest.TestCase):
    """The measured mechanism, reproduced: red without the policy, green with it."""

    BODY = b"# audit\nline one\nline two\n"

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-t1508-stash-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir(parents=True)
        for args in (("init",), ("config", "core.autocrlf", "true")):
            self.assertEqual(_git(self.root, *args).returncode, 0)
        (self.root / "README.md").write_bytes(b"project\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _round_trip(self) -> bytes:
        self.assertEqual(_git(self.root, "add", "-A").returncode, 0)
        commit = _git(self.root, "commit", "-m", "base")
        self.assertEqual(commit.returncode, 0, commit.stderr)
        body = self.root / ".saipen" / "archive" / "source" / "SRC-001.md"
        body.parent.mkdir(parents=True)
        body.write_bytes(self.BODY)
        stash = _git(self.root, "stash", "push", "--include-untracked")
        self.assertEqual(stash.returncode, 0, stash.stderr)
        self.assertFalse(body.exists(), "the untracked body went into the stash")
        pop = _git(self.root, "stash", "pop")
        self.assertEqual(pop.returncode, 0, pop.stderr)
        return body.read_bytes()

    def test_without_the_policy_the_round_trip_converts_the_body(self):
        restored = self._round_trip()
        self.assertEqual(restored, self.BODY.replace(b"\n", b"\r\n"))
        digest = intake.hashlib.sha256(self.BODY).hexdigest()
        self.assertTrue(intake.line_ending_drift(restored, digest))

    def test_with_the_policy_the_round_trip_keeps_the_bytes(self):
        self.assertEqual(
            rn_mod.ensure_gitattributes_policy(self.root)["code"], "ATTRIBUTES_POLICY_ADDED"
        )
        self.assertEqual(self._round_trip(), self.BODY)


class CaptureTests(unittest.TestCase):
    """Every new capture re-establishes a missing policy."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-t1508-capture-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir(parents=True)
        shutil.copytree(SCENARIO, self.root / ".saipen")
        (self.root / ".saipen" / "BOARD.md").write_text(BOARD, encoding="utf-8")
        (self.root / ".saipen" / "STATE.md").write_text(STATE, encoding="utf-8")
        (self.root / ".saipen" / "LOG.md").write_text(LOG, encoding="utf-8")
        self.attributes = self.root / ".gitattributes"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_first_capture_establishes_the_policy(self):
        self.assertFalse(self.attributes.exists())
        rc, _payload, out = _run_cli(self.root, "source", "capture", "first request")
        self.assertEqual(rc, 0, out)
        self.assertEqual(rn_mod.attributes_policy_state(self.root), "CURRENT")

    def test_a_project_adopted_before_the_policy_gets_it_at_its_next_capture(self):
        rc, _payload, out = _run_cli(self.root, "source", "capture", "first request")
        self.assertEqual(rc, 0, out)
        self.attributes.unlink()  # the policy did not exist when it was adopted
        rc, _payload, out = _run_cli(self.root, "source", "capture", "second request")
        self.assertEqual(rc, 0, out)
        self.assertEqual(rn_mod.attributes_policy_state(self.root), "CURRENT")
        once = self.attributes.read_bytes()
        rc, _payload, out = _run_cli(self.root, "source", "capture", "third request")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.attributes.read_bytes(), once, "never duplicated")


class DiagnosisTests(unittest.TestCase):
    """Drift is named with its proven repair; nothing else is called drift."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="saipen-t1508-diag-")
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir(parents=True)
        shutil.copytree(SCENARIO, self.root / ".saipen")
        (self.root / ".saipen" / "BOARD.md").write_text(BOARD, encoding="utf-8")
        (self.root / ".saipen" / "STATE.md").write_text(STATE, encoding="utf-8")
        (self.root / ".saipen" / "LOG.md").write_text(LOG, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _capture(self, body: str) -> tuple[str, Path]:
        rc, payload, out = _run_cli(self.root, "source", "capture", body)
        self.assertEqual(rc, 0, out)
        receipt = payload["receipt"]
        return receipt, self.root / ".saipen" / "intake" / "active" / f"{receipt}.md"

    def test_converted_body_is_named_drift_with_the_repair(self):
        receipt, path = self._capture("line one\nline two\n")
        original = path.read_bytes()
        path.write_bytes(original.replace(b"\n", b"\r\n"))
        verdict = intake.verify_integrity(self.root, receipt)
        self.assertEqual(verdict["code"], "SOURCE_CORRUPTION")
        self.assertEqual(verdict["drift"], intake.LINE_ENDING_DRIFT)
        rel = f".saipen/intake/active/{receipt}.md"
        self.assertIn(rel, verdict["detail"])
        self.assertIn("-text", verdict["detail"])
        self.assertIn("CRLF replaced by LF", verdict["detail"])
        # The named repair is exact: the recorded digest proves it.
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(intake.verify_integrity(self.root, receipt)["code"], "SOURCE_INTEGRITY_OK")

    def test_a_genuine_byte_change_stays_a_bare_mismatch(self):
        receipt, path = self._capture("line one\nline two\n")
        path.write_bytes(b"line one\r\nline 2\r\n")
        verdict = intake.verify_integrity(self.root, receipt)
        self.assertEqual(verdict["code"], "SOURCE_CORRUPTION")
        self.assertNotIn("drift", verdict)
        self.assertNotIn("detail", verdict)

    def test_a_source_that_arrived_with_crlf_is_intact_not_drift(self):
        receipt, path = self._capture("line one\r\nline two\r\n")
        self.assertIn(b"\r\n", path.read_bytes())
        self.assertEqual(intake.verify_integrity(self.root, receipt)["code"], "SOURCE_INTEGRITY_OK")

    def test_drift_predicate_needs_a_crlf_and_the_exact_digest(self):
        lf = b"a\nb\n"
        digest = intake.hashlib.sha256(lf).hexdigest()
        self.assertTrue(intake.line_ending_drift(lf.replace(b"\n", b"\r\n"), digest))
        self.assertFalse(intake.line_ending_drift(lf, digest), "no CRLF, no drift")
        self.assertFalse(intake.line_ending_drift(b"a\r\nc\r\n", digest))
        self.assertFalse(intake.line_ending_drift(b"a\r\nb\r\n", None))


def _run_cli(project: Path, *args: str) -> tuple[int, dict, str]:
    proc = subprocess.run(
        [
            sys.executable,
            str(SAIPEN_PY),
            "--project-root",
            str(project),
            "--agent",
            "tester",
            "--json",
            *args,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=unbound_environment(),
        timeout=600,
    )
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except ValueError:
        payload = {"_unparseable_stdout": proc.stdout}
    diagnostic = proc.stdout
    if proc.stderr.strip():
        diagnostic += "\nSTDERR:\n" + proc.stderr
    return proc.returncode, payload, diagnostic


if __name__ == "__main__":
    unittest.main()
