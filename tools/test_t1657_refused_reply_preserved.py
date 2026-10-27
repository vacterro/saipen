"""T-1657: an adapter that replaces or corrects a refused reply keeps it first.

SRC-190 R004: brevity of the operator surface never loses machine evidence.
`saipen response preserve` existed (T-1656) and no adapter called it. The
OpenCode plugin REPLACES a completed part with the canonical delivery, so
detail a model wrote only into its reply was gone; the Claude Stop hook asks
for one correction and left the refused reply to a host transcript. Both were
handed the overflow diagnostic by the checker and kept it nowhere.

Now each adapter hands the reply to `saipen response preserve` before it
replaces, corrects or throws, and the engine keeps the overflow account
(field, size, budget, reference) beside the bytes it describes.

The adapter cases run the REAL artifacts: the node module through the shared
driver, the Claude hook through its own stop handler, both against the real
checker in a real project, with the incident reply as the fixture.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_claude_stop_hook as CSH  # noqa: E402
import test_codex_stop_hook as XSH  # noqa: E402
from saipen_engine import response_surface as RS  # noqa: E402
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_operator_origin_support import run_native_cases as run_cases  # noqa: E402
from test_t1568_opencode_chat_style import COMPACT, OVER_BUDGET  # noqa: E402
from test_t1656_operator_readability import wall  # noqa: E402

NODE = shutil.which("node")
PYTHON = shutil.which("python") or shutil.which("python3")
PLUGIN = REPO / "extensions" / "adapters" / "opencode" / "saipen-guard.js"
#: Detail that exists in the incident reply and nowhere in its compact form.
DETAILS = ("MAX_RESAMPLE_PHASES=2048", "478.8 ms", "E-4521")


def setUpModule() -> None:
    isolate_host_session()


def _kept(project: Path, text: str) -> tuple[bytes | None, dict | None]:
    """The preserved bytes and the account beside them, or None for each."""
    reference = RS.rejected_reference(text)
    stored = project / reference
    # Spelled out, not asked of the engine: against an engine that keeps no
    # account these cases must fail on the missing bytes, not on a missing name.
    account = project / (reference[: -len(".txt")] + ".json")
    return (
        stored.read_bytes() if stored.is_file() else None,
        json.loads(account.read_text(encoding="utf-8")) if account.is_file() else None,
    )


def _preserved(project: Path) -> list[str]:
    directory = project / RS.REJECTED_RESPONSE_DIR
    return sorted(p.name for p in directory.glob("rejected-*")) if directory.is_dir() else []


class AccountTests(unittest.TestCase):
    """The engine half: the overflow account travels with the reply."""

    def test_preserve_keeps_the_overflow_account_beside_the_reply(self):
        project = fresh_project()
        kept = RS.preserve_rejected(project, wall())
        self.assertEqual(
            (kept["ok"], kept["code"], kept["written"]), (True, "RESPONSE_PRESERVED", True)
        )
        self.assertEqual(kept["diagnostic_ref"], kept["ref"][:-4] + ".json")
        stored, account = _kept(project, wall())
        self.assertEqual(stored, wall().encode("utf-8"))
        self.assertEqual(
            (account["kind"], account["ref"], account["sha256"], account["bytes"]),
            ("saipen-rejected-response", kept["ref"], kept["sha256"], len(stored)),
        )
        overflow = account["overflow"]
        self.assertEqual(overflow, kept["overflow"])
        self.assertEqual(overflow["detail_ref"], kept["ref"], "the reference")
        self.assertTrue(overflow["fields"], "which field")
        for offender in overflow["fields"]:
            self.assertEqual(
                sorted(offender), ["char_budget", "chars", "field", "line_budget", "lines"]
            )
        self.assertGreater(overflow["total"]["chars"], overflow["total"]["char_budget"])
        self.assertNotIn("compaction", overflow, "what became of the reply is the caller's fact")

    def test_the_same_reply_is_one_record_written_once(self):
        project = fresh_project()
        first = RS.preserve_rejected(project, wall())
        again = RS.preserve_rejected(project, wall().replace("\n", "\r\n"))
        self.assertEqual((again["ref"], again["written"]), (first["ref"], False))
        self.assertEqual(len(_preserved(project)), 2, "one reply, one account")

    def test_a_reply_within_budget_is_kept_with_an_empty_account(self):
        """Refused for another reason than size: the bytes are still kept and
        the account says there was no overflow instead of being absent."""
        project = fresh_project()
        kept = RS.preserve_rejected(project, "Everything is fine.")
        self.assertIsNone(kept["overflow"])
        _stored, account = _kept(project, "Everything is fine.")
        self.assertIsNone(account["overflow"])
        self.assertEqual(account["ref"], kept["ref"])


@unittest.skipUnless(NODE, "node runtime unavailable")
@unittest.skipUnless(PYTHON, "no python runtime for the guard round trip")
class OpenCodeCompletedPartTests(unittest.TestCase):
    """The host that REPLACES: the completed part is kept before it is gone."""

    def run_parts(self, project: Path, cases: list[dict]) -> list[dict]:
        directory = Path(tempfile.mkdtemp(prefix="saipen-t1657-"))
        self.addCleanup(shutil.rmtree, directory, True)
        env = {
            "SAIPEN_SKILL_ROOT": str(REPO),
            "SAIPEN_PYTHON": PYTHON,
            "SAIPEN_AGENT": "test-agent",
        }
        return run_cases(
            PLUGIN,
            [{"project": str(project), "env": env, **case} for case in cases],
            directory,
            extra_env={"SAIPEN_PYTHON": PYTHON},
        )

    def test_the_incident_reply_is_kept_before_it_is_replaced(self):
        project = fresh_project()
        (record,) = self.run_parts(project, [{
            "id": "wall", "session_id": "ses_t1657_wall", "user_request": "saipen status",
            "operational_command": "saipen status", "text_complete": wall(),
        }])
        self.assertEqual(record["outcome"], "allowed", record)
        self.assertNotEqual(record["delivered"], wall(), "the part was replaced")
        self.assertLessEqual(len(record["delivered"]), 900)
        stored, account = _kept(project, wall())
        self.assertEqual(stored, wall().encode("utf-8"), "byte for byte")
        for detail in DETAILS:
            self.assertNotIn(detail, record["delivered"])
            self.assertIn(detail.encode("utf-8"), stored)
        self.assertEqual(account["overflow"]["detail_ref"], RS.rejected_reference(wall()))
        self.assertTrue(account["overflow"]["fields"])

    def test_a_reply_that_is_the_delivery_is_not_a_refused_reply(self):
        project = fresh_project()
        operational = {
            "user_request": "saipen status", "operational_command": "saipen status",
        }
        (first,) = self.run_parts(project, [{
            "id": "first", "session_id": "ses_t1657_a", "text_complete": "Kõik on korras.",
            **operational,
        }])
        delivery = first["delivered"]
        before = _preserved(project)
        self.assertEqual(len(before), 2, "the refused prose and its account")
        (second,) = self.run_parts(project, [{
            "id": "second", "session_id": "ses_t1657_b", "text_complete": delivery, **operational,
        }])
        self.assertEqual((second["outcome"], second["delivered"]), ("allowed", delivery), second)
        self.assertEqual(_preserved(project), before, "an accepted reply is not preserved")

    def test_an_ordinary_reply_refused_for_style_is_kept_before_the_throw(self):
        project = fresh_project()
        refused, accepted = self.run_parts(project, [
            {"id": "drift", "session_id": "ses_t1657_drift", "text_complete": OVER_BUDGET},
            {"id": "compact", "session_id": "ses_t1657_ok", "text_complete": COMPACT},
        ])
        self.assertEqual(refused["outcome"], "blocked", refused)
        self.assertIn("CHAT_STYLE_DRIFT", refused["message"])
        stored, account = _kept(project, OVER_BUDGET)
        self.assertEqual(stored, OVER_BUDGET.replace("\r\n", "\n").encode("utf-8"))
        self.assertIsNotNone(account)
        self.assertEqual(accepted["outcome"], "allowed", accepted)
        self.assertEqual(_kept(project, COMPACT), (None, None))
        self.assertEqual(len(_preserved(project)), 2)


class ClaudeStopHookTests(CSH.AdmittedCase):
    """The host that CORRECTS: the refused reply is kept before the request."""

    def test_the_incident_reply_is_kept_before_the_correction_is_requested(self):
        world = self.make_world(CSH.wait_project())
        rc, out, _ = self.hook(world, text=wall())
        self.assertEqual((rc, out.get("decision")), (0, "block"), out)
        stored, account = _kept(world.project, wall())
        self.assertEqual(stored, wall().encode("utf-8"), "byte for byte")
        for detail in DETAILS:
            self.assertNotIn(detail, out["reason"])
            self.assertIn(detail.encode("utf-8"), stored)
        self.assertEqual(account["overflow"]["detail_ref"], RS.rejected_reference(wall()))
        self.assertTrue(account["overflow"]["fields"])

    def test_a_correction_without_a_delivery_names_where_the_reply_is_kept(self):
        world = self.make_world()
        rc, out, _ = self.hook(world, text=CSH.ESSAY)
        self.assertEqual((rc, out.get("decision")), (0, "block"), out)
        self.assertIn("CHAT_STYLE_DRIFT", out["reason"])
        reference = RS.rejected_reference(CSH.ESSAY)
        self.assertIn(f"The refused reply is kept at {reference}.", out["reason"])
        self.assertEqual(_kept(world.project, CSH.ESSAY)[0], CSH.ESSAY.encode("utf-8"))

    def test_a_reentry_keeps_the_reply_it_records_as_unenforced(self):
        world = self.make_world()
        rc, out, _ = self.hook(world, text=CSH.ESSAY, reentry=True)
        self.assertEqual(rc, 0)
        self.assertNotIn("decision", out, out)
        self.assertIn("CLAUDE_STOP_REENTRY_NO_FAIL_CLOSED", out["systemMessage"])
        self.assertIn(RS.rejected_reference(CSH.ESSAY), out["systemMessage"])
        self.assertIsNotNone(_kept(world.project, CSH.ESSAY)[0])

    def test_an_accepted_reply_is_not_preserved(self):
        world = self.make_world()
        rc, out, _ = self.hook(world, text="An ordinary explanation.")
        self.assertEqual((rc, out), (0, None))
        self.assertEqual(_preserved(world.project), [])

    def test_a_reply_that_cannot_be_kept_is_still_corrected(self):
        """Preserving is evidence, not a gate: when the engine cannot keep the
        reply the stop is handled exactly as before and no reference is claimed."""
        world = self.make_world()
        # The hook reaches the engine in a child process, so the failure is
        # made where that child meets it: a file where the directory belongs.
        blocker = world.project / RS.REJECTED_RESPONSE_DIR
        blocker.parent.mkdir(parents=True, exist_ok=True)
        blocker.write_text("a file where the directory belongs", encoding="utf-8")
        rc, out, _ = self.hook(world, text=CSH.ESSAY)
        self.assertEqual((rc, out.get("decision")), (0, "block"), out)
        self.assertIn("CHAT_STYLE_DRIFT", out["reason"])
        self.assertNotIn("The refused reply is kept at", out["reason"])


class CodexStopHookTests(unittest.TestCase):
    """The third adapter with a mechanical response gate; it corrects like
    Claude does, through the real hook process."""

    def test_the_incident_reply_is_kept_before_the_correction_is_requested(self):
        project = XSH.wait_project()
        rc, out, _ = XSH.stop_event(project, wall())
        self.assertEqual((rc, out.get("decision")), (0, "block"), out)
        stored, account = _kept(project, wall())
        self.assertEqual(stored, wall().encode("utf-8"), "byte for byte")
        for detail in DETAILS:
            self.assertNotIn(detail, out["reason"])
            self.assertIn(detail.encode("utf-8"), stored)
        self.assertEqual(account["overflow"]["detail_ref"], RS.rejected_reference(wall()))
        self.assertTrue(account["overflow"]["fields"])

    def test_a_correction_without_a_delivery_names_where_the_reply_is_kept(self):
        project = fresh_project()
        rc, out, _ = XSH.stop_event(project, CSH.ESSAY)
        self.assertEqual((rc, out.get("decision")), (0, "block"), out)
        self.assertIn("CHAT_STYLE_DRIFT", out["reason"])
        reference = RS.rejected_reference(CSH.ESSAY)
        self.assertIn(f"The refused reply is kept at {reference}.", out["reason"])
        self.assertEqual(_kept(project, CSH.ESSAY)[0], CSH.ESSAY.encode("utf-8"))

    def test_a_reentry_keeps_the_reply_it_records_as_unenforced(self):
        project = fresh_project()
        rc, out, _ = XSH.stop_event(project, CSH.ESSAY, reentry=True)
        self.assertEqual(rc, 0)
        self.assertNotIn("decision", out, out)
        self.assertIn("CODEX_STOP_REENTRY_NO_FAIL_CLOSED", out["systemMessage"])
        self.assertIn(RS.rejected_reference(CSH.ESSAY), out["systemMessage"])
        self.assertIsNotNone(_kept(project, CSH.ESSAY)[0])

    def test_an_accepted_reply_is_not_preserved(self):
        project = fresh_project()
        rc, out, _ = XSH.stop_event(project, "An ordinary explanation.")
        self.assertEqual((rc, out), (0, None))
        self.assertEqual(_preserved(project), [])


class EveryGatedAdapterTests(unittest.TestCase):
    def test_each_adapter_with_a_mechanical_response_gate_hands_the_reply_over(self):
        """The clause is about EVERY adapter that acts on a refused final
        reply. The registry names them; an adapter added to that set without
        the hand-over fails here instead of losing replies in the field."""
        registry = json.loads(
            (REPO / "extensions" / "adapters" / "registry.json").read_text(encoding="utf-8-sig")
        )
        gated = sorted(
            entry["id"]
            for entry in registry["adapters"]
            if entry.get("response_enforcement") == "MECHANICAL"
        )
        self.assertEqual(gated, ["claude", "codex", "opencode"])
        for name in gated:
            with self.subTest(name):
                directory = REPO / "extensions" / "adapters" / name
                source = "".join(
                    path.read_text(encoding="utf-8")
                    for path in sorted(directory.iterdir())
                    if path.suffix in (".py", ".js")
                )
                self.assertRegex(source, r'"response",\s*"preserve",\s*"--stdin"')


if __name__ == "__main__":
    unittest.main()
