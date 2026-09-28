"""T-1282: the `[op: ...]` provenance tag must resolve to a real operation.

The presence check (T-584) proves only that a bracket is present, so an op id
hand-typed outside a SAIOPS run passes it. These tests run the REAL canonical
validator against a fixture whose recovery ledger holds specific operations,
then prove:

  AC-01  a tagged ACTIVE-log event whose id names no operation record FAILs,
         and the message is distinct from the plain missing-tag [saio] FAIL;
  AC-02  a genuinely mechanized event (its id is in the ledger) validates with
         no new finding;
  AC-04  sealed-segment history is exempt (its ops were legitimately compacted
         before the durable index existed) rather than reported;
  AC-05  the check goes red on a hand-typed id and green once the same id names
         a real settled operation -- one red control, one variable.

The check is UNAVAILABLE (not red) when no ledger exists on the checkout, so a
fixture with no recovery tree exits 0: there is nothing to resolve against.
The forgery vector is the ACTIVE log, because a new (forged) event only ever
lands there; sealed segments are immutable append-only history.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.journal import resolvable_op_ids  # noqa: E402
from test_hermetic_env import hermetic_env, isolate_host_session  # noqa: E402

SCENARIO = ROOT / "tests" / "scenarios" / "userperson-valid" / ".saipen"

REAL_OP = "checkpoint-0123456789abcdef0123456789abcdef"
FORGED_OP = "checkpoint-deadbeefdeadbeefdeadbeefdeadbeef"


def setUpModule() -> None:
    isolate_host_session()


class OpIdResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t1282-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir()
        shutil.copytree(SCENARIO, self.root / ".saipen")
        state_path = self.root / ".saipen" / "STATE.md"
        state = state_path.read_text(encoding="utf-8")
        state = state.replace("last_event: 1", "last_event: 2")
        state_path.write_text(state, encoding="utf-8")

    def seed_active_log(self, tail_op: str) -> None:
        # E-001 provenanced boundary (resolvable), E-002 the tail event under
        # test -- both in the ACTIVE log, which is where any forgery lands.
        self.log_path().write_text(
            f"- 08.08.26 00:00 [E-001] [agent: probe] [op: {REAL_OP}] "
            "DEC: claimed via SAIOPS -- owner probe\n"
            f"- 08.08.26 00:01 [E-002] [agent: probe] [op: {tail_op}] "
            "RUN: transition to BUILD -- tail event under test\n",
            encoding="utf-8",
        )

    def log_path(self) -> Path:
        return self.root / ".saipen" / "LOG.md"

    def settle_op(self, op_id: str) -> None:
        op_dir = self.root / ".saipen" / "recovery" / "settled" / op_id
        op_dir.mkdir(parents=True, exist_ok=True)
        (op_dir / "operation.json").write_text(
            json.dumps({"op_id": op_id, "status": "COMMITTED"}), encoding="utf-8"
        )

    def run_validator(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(TOOLS / "validate.py"), "--project-root",
             str(self.root), "--gate", "core"],
            capture_output=True, text=True, encoding="utf-8",
            env=hermetic_env(), timeout=300,
        )

    def test_ac05_red_on_forged_id_green_when_the_same_id_is_real(self) -> None:
        # RED: the boundary op is real, the tail op is hand-typed. The tail
        # event resolves to nothing, so the ledger-backed check FAILs.
        self.seed_active_log(FORGED_OP)
        self.settle_op(REAL_OP)
        red = self.run_validator()
        self.assertNotEqual(red.returncode, 0, red.stdout + red.stderr)
        self.assertIn("resolves to NO", red.stdout)
        self.assertIn("(T-1282)", red.stdout)
        self.assertIn(FORGED_OP, red.stdout)

        # GREEN: the ONLY change is that the same tail id now names a real
        # settled operation. Nothing about the LOG or the check moved.
        self.settle_op(FORGED_OP)
        green = self.run_validator()
        self.assertNotIn("resolves to NO", green.stdout)

    def test_ac02_mechanized_event_validates_with_no_new_finding(self) -> None:
        tail = "transition-fedcba9876543210fedcba9876543210"
        self.seed_active_log(tail)
        self.settle_op(REAL_OP)
        self.settle_op(tail)
        done = self.run_validator()
        self.assertNotIn("resolves to NO", done.stdout)

    def test_ac01_forged_id_is_reported_distinctly_from_a_missing_tag(self) -> None:
        self.seed_active_log(FORGED_OP)
        self.settle_op(REAL_OP)
        out = self.run_validator().stdout
        # The forged-id finding names resolution, not mere absence of a bracket.
        forged_line = next(
            line for line in out.splitlines()
            if "T-1282" in line and "resolves to NO" in line
        )
        self.assertIn(FORGED_OP, forged_line)
        self.assertNotIn("lack `[op: ...]`", forged_line)

    def test_ac04_sealed_segment_history_is_exempt(self) -> None:
        # A sealed segment carries a tagged event whose op was compacted away
        # (no live record). The active log is clean. Sealed history is
        # append-only and its ops were legitimately settled, so it must NOT be
        # reported -- only the active log is the forgery surface.
        logs_dir = self.root / ".saipen" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "LOG-001.md").write_text(
            "- 08.08.26 00:00 [E-001] [agent: probe] "
            "[op: checkpoint-compactedawaycompactedawaycompacted] "
            "DEC: claimed via SAIOPS -- sealed history, op since compacted\n",
            encoding="utf-8",
        )
        self.log_path().write_text(
            f"- 08.08.26 00:01 [E-002] [agent: probe] [op: {REAL_OP}] "
            "RUN: transition to BUILD -- resolvable active event\n",
            encoding="utf-8",
        )
        self.settle_op(REAL_OP)
        out = self.run_validator().stdout
        self.assertNotIn("resolves to NO", out)

    def test_no_ledger_makes_the_check_unavailable_not_red(self) -> None:
        # A checkout with no recovery ledger (fresh clone / consumer) must not
        # red every logged op id -- there is nothing on disk to resolve against.
        shutil.rmtree(self.root / ".saipen" / "recovery", ignore_errors=True)
        self.seed_active_log(FORGED_OP)
        self.assertEqual(resolvable_op_ids(self.root), set())
        out = self.run_validator().stdout
        self.assertNotIn("resolves to NO", out)

    def test_resolver_reads_settled(self) -> None:
        self.settle_op(REAL_OP)
        resolved = resolvable_op_ids(self.root)
        self.assertIn(REAL_OP, resolved)
        self.assertNotIn(FORGED_OP, resolved)


if __name__ == "__main__":
    unittest.main()
