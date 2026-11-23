"""T-1487: an operator-ordered agent switch has a command, and nothing else does.

Field incident SAI-DEFECT-20260922-silent-actor-inheritance-misattribution
(SAIMAIL T-108): a host with SAIPEN_AGENT unset inherited STATE.agent `astra`
silently, and when the operator ordered "работай как opus" the only honest move
-- `operations.handover_agent(explicit=True)` -- had no command, so the session
called the Python API. These controls hold both halves:

* `saipen handoff T-### --to AGENT` moves a LIVE claim when the current owner
  runs it, or when an ACTIVE operator receipt grants exactly that pair; a new
  session that merely appeared is refused, and a plain `claim` still cannot
  take a live foreign claim;
* START's human answer says when the acting agent was inherited.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import json  # noqa: E402
import hashlib  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402

from saipen_engine import codec, handoff  # noqa: E402
from saipen_engine.board import parse_board  # noqa: E402
from saipen_engine.state import parse_state  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1363_zero_manual_entry import (  # noqa: E402
    CLI,
    PYTHON,
    _allocation_log,
    _doing,
    project,
)

CAPSULE = f"{handoff.GRANT_HEADER}\nT-108 -> opus\n{handoff.GRANT_TERMINATOR}\n"
WORK = "T-9100"


def setUpModule() -> None:
    isolate_host_session()


def run(
    root: Path, *args: str, agent: str | None = None,
    task_carrier: str | None = None,
) -> tuple[int, dict | None, str]:
    """One real CLI call; `agent=None` means NO declared identity at all."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
    if task_carrier is not None:
        env["SAIPEN_TASK_SHA256"] = hashlib.sha256(
            task_carrier.replace("\r\n", "\n").strip().encode("utf-8")
        ).hexdigest()
    argv = [PYTHON, str(CLI), *args, "--project-root", str(root)]
    if agent is not None:
        argv += ["--agent", agent]
    proc = subprocess.run(
        argv, capture_output=True, text=True, env=env, timeout=300,
        encoding="utf-8", errors="replace",
    )
    payload = None
    if "--json" in args:
        try:
            payload = json.loads(proc.stdout)
        except ValueError:
            payload = None
    return proc.returncode, payload, proc.stdout + proc.stderr


def live_work(case: unittest.TestCase, owner: str = "test-agent") -> Path:
    """BUILD on T-9100 under a LIVE claim of `owner`, which is also STATE.agent."""
    return project(
        case,
        phase="BUILD",
        task=WORK,
        next_action=f"PHASE BUILD {WORK}",
        transition_from="SCOUT",
        agent=owner,
        board=_doing(WORK, "wire the importer", owner, 0),
        log=_allocation_log(WORK),
    )


def seat(root: Path) -> tuple[str, str, str]:
    state = parse_state(codec.read_doc(root / ".saipen" / "STATE.md"))
    board = parse_board(codec.read_doc(root / ".saipen" / "BOARD.md"))
    return state.get("agent"), state.get("phase"), board["tickets"][WORK]["fields"]["owner"]


def log_of(root: Path) -> str:
    return (root / ".saipen" / "LOG.md").read_text(encoding="utf-8")


class GrantGrammarTests(unittest.TestCase):
    def test_a_closed_capsule_grants_its_exact_pair(self):
        parsed = handoff.handoff_grants("please switch\n" + CAPSULE)
        self.assertEqual(parsed.grants, {"T-108": "opus"})
        self.assertEqual(parsed.problems, ())

    def test_prose_grants_nothing(self):
        for text in (
            "handoff T-108 to opus please",
            "T-108 -> opus",
            f"```\n{CAPSULE}```\n",
            f"{handoff.GRANT_HEADER}\nT-108 -> opus\n",
            f"{handoff.GRANT_HEADER}\nT-108 to opus\nonly.\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(handoff.handoff_grants(text).grants, {})

    def test_conflicting_grants_grant_nothing(self):
        text = CAPSULE + f"{handoff.GRANT_HEADER}\nT-108 -> codex\nonly.\n"
        parsed = handoff.handoff_grants(text)
        self.assertEqual(parsed.grants, {})
        self.assertTrue(parsed.problems)


class HandoffCommandTests(unittest.TestCase):
    def test_the_owner_hands_its_own_work_on_at_the_same_phase(self):
        root = live_work(self)
        code, payload, text = run(root, "handoff", WORK, "--to", "opus", "--json",
                                  agent="test-agent")
        self.assertEqual(code, 0, text)
        self.assertEqual(payload["code"], "HANDOVERED", text)
        self.assertEqual(seat(root), ("opus", "BUILD", "opus"))
        self.assertIn(f"handoff of {WORK}, voluntary, by its owner test-agent", log_of(root))

    def test_an_inherited_identity_is_not_the_owner_speaking(self):
        root = live_work(self)
        before = seat(root)
        code, payload, text = run(root, "handoff", WORK, "--to", "opus", "--json")
        self.assertNotEqual(code, 0, text)
        self.assertEqual(payload["code"], "HANDOFF_AUTHORITY_REQUIRED", text)
        self.assertIn("inherited from STATE.agent", payload["detail"])
        self.assertEqual(seat(root), before)

    def test_a_new_session_cannot_hand_itself_a_live_claim(self):
        root = live_work(self)
        before = seat(root)
        code, payload, text = run(root, "handoff", WORK, "--to", "intruder", "--json",
                                  agent="intruder")
        self.assertNotEqual(code, 0, text)
        self.assertEqual(payload["code"], "HANDOFF_AUTHORITY_REQUIRED", text)
        self.assertEqual(
            payload["canonical_next_command"],
            f"saipen handoff {WORK} --to intruder --authority <SRC-###>",
        )
        self.assertEqual(seat(root), before)

    def test_an_operator_capsule_grants_exactly_its_pair(self):
        root = live_work(self)
        capsule = root / "handoff.md"
        capsule.write_text(
            f"switch agents\n{handoff.GRANT_HEADER}\n{WORK} -> opus\n"
            f"{handoff.GRANT_TERMINATOR}\n",
            encoding="utf-8",
        )
        code, captured, text = run(
            root, "authority", "capture", "--file", str(capsule), "--json",
            agent="opus", task_carrier=capsule.read_text(encoding="utf-8"),
        )
        self.assertEqual(code, 0, text)
        receipt = captured["receipt"]
        # The grant is for opus, not for anyone who holds the receipt id.
        code, payload, text = run(root, "handoff", WORK, "--to", "intruder", "--authority",
                                  receipt, "--json", agent="intruder")
        self.assertNotEqual(code, 0, text)
        self.assertEqual(payload["code"], "HANDOFF_AUTHORITY_REQUIRED", text)
        code, payload, text = run(root, "handoff", WORK, "--to", "opus", "--authority",
                                  receipt, "--json", agent="opus")
        self.assertEqual(code, 0, text)
        self.assertEqual(seat(root), ("opus", "BUILD", "opus"))
        self.assertIn(f"handoff of {WORK}, operator authority {receipt}", log_of(root))

    def test_model_supplied_capsule_cannot_grant_a_foreign_claim(self):
        root = live_work(self)
        capsule = root / "handoff.md"
        capsule.write_text(f"{handoff.GRANT_HEADER}\n{WORK} -> intruder\nonly.\n",
                           encoding="utf-8")
        code, captured, text = run(root, "authority", "capture", "--file", str(capsule),
                                   "--json", agent="intruder")
        self.assertEqual(code, 0, text)
        code, payload, text = run(root, "handoff", WORK, "--to", "intruder",
                                  "--authority", captured["receipt"], "--json", agent="intruder")
        self.assertNotEqual(code, 0, text)
        self.assertEqual(payload["code"], "HANDOFF_AUTHORITY_REQUIRED")
        self.assertIn("the owner runs the handoff", payload["detail"])
        self.assertEqual(seat(root), ("test-agent", "BUILD", "test-agent"))

    def test_claim_still_refuses_a_live_claim_and_names_the_handoff(self):
        root = live_work(self)
        code, payload, text = run(root, "claim", WORK, "--json", agent="opus")
        self.assertNotEqual(code, 0, text)
        self.assertEqual(payload["code"], "TICKET_NOT_WORKABLE", text)
        self.assertEqual(
            payload["canonical_next_command"],
            f"saipen handoff {WORK} --to opus --authority <SRC-###>",
        )


class InheritedActorIsSaidTests(unittest.TestCase):
    def test_runtime_reports_inherited_and_explicit_actor_source(self):
        root = project(self, agent="astra")
        code, payload, text = run(root, "runtime", "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(payload["actor_source"], "inherited")
        code, payload, text = run(root, "runtime", "--json", agent="opus")
        self.assertEqual(code, 0, text)
        self.assertEqual(payload["actor_source"], "explicit")
        code, _payload, text = run(root, "runtime")
        self.assertEqual(code, 0, text)
        self.assertIn("inherited from STATE.agent", text)

    def test_start_says_when_the_actor_was_inherited(self):
        root = project(self, agent="astra")
        code, _payload, text = run(root, "start", "add a docstring to src/app.py")
        self.assertEqual(code, 0, text)
        self.assertIn("actor: astra (inherited from STATE.agent", text)

    def test_start_json_names_actor_source(self):
        root = project(self, agent="astra")
        code, payload, text = run(root, "start", "add a docstring to src/app.py", "--json")
        self.assertEqual(code, 0, text)
        self.assertEqual(payload["actor_source"], "inherited")

    def test_a_declared_actor_is_not_called_inherited(self):
        root = project(self, agent="astra")
        code, _payload, text = run(root, "start", "add a docstring to src/app.py",
                                   agent="opus")
        self.assertEqual(code, 0, text)
        self.assertNotIn("inherited from STATE.agent", text)


class LogTimeZoneTests(unittest.TestCase):
    """SAIMAIL T-108 read a UTC LOG stamp as a wrong local time."""

    def test_core_log_skeleton_names_utc(self):
        core = (TOOLS.parent / "saipen" / "CORE.md").read_text(encoding="utf-8")
        start = core.index("#### LOG.md")
        section = core[start:core.index("\n####", start + 1)]
        self.assertIn("UTC", section)

    def test_the_engine_stamps_log_lines_in_utc(self):
        import datetime

        from saipen_engine import operations

        before = datetime.datetime.now(datetime.timezone.utc).replace(second=0, microsecond=0)
        stamp = datetime.datetime.strptime(operations._now(), "%d.%m.%y %H:%M").replace(
            tzinfo=datetime.timezone.utc
        )
        after = datetime.datetime.now(datetime.timezone.utc)
        self.assertLessEqual(before, stamp)
        self.assertLessEqual(stamp, after)


if __name__ == "__main__":
    unittest.main()
