"""T-1568: the OpenCode hook measures ORDINARY_CHAT, not only operational turns.

`experimental.text.complete` returned before the canonical checker whenever the
turn never consumed a canonical `saipen` command, so on this host the entire
ordinary half of STYLE.md -- the chat line budget, the banned openers, the
pinned `reply_language` -- had no mechanical check at all, while the registry
called the same hook's response gate MECHANICAL. The defect STYLE.md exists to
remove (an essay where a compressed answer belongs, a polite register, the
wrong language) passed unmeasured on exactly one supported host.

These cases drive the REAL node module through the shared driver, against the
real classifier, in a real admitted project. They are behavioural: the hook
must REFUSE an over-budget ordinary reply and ACCEPT a compact one in the
pinned language, on the same binding and the same session shape. Operational
gates are untouched and stay covered by test_opencode_adapter.

The plugin path is overridable so the regression pair runs the SAME oracle and
the SAME command against the preserved pre-fix artifact (red) and the live one
(green).
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_opencode_adapter import run_cases  # noqa: E402

NODE = shutil.which("node")
PYTHON = shutil.which("python") or shutil.which("python3")

#: The live hook unless the regression pair points the oracle at a preserved
#: pre-fix artifact. No default to the repository copy is right: the copy is
#: what the pair is judging.
PLUGIN = Path(os.environ.get("SAIPEN_OPENCODE_PLUGIN") or (
    REPO / "extensions" / "adapters" / "opencode" / "saipen-guard.js"
))


def setUpModule() -> None:
    isolate_host_session()


#: A compact reply in the pinned reply language. Measured against the compiled
#: contract in _assert_compact_passes, so the fixture cannot rot into a
#: language the project no longer pins.
COMPACT = "Parandatud. Põhjus oli sabakna; vaata tools/saipen.py:11346."

#: Ordinary conversation that is exactly what STYLE.md exists to refuse: a
#: banned preamble opener, far over the chat line budget, and no marker of the
#: pinned language.
OVER_BUDGET = (
    "Here is a detailed and lengthy explanation of everything you asked about. "
    "It covers the background, the options, the trade-offs and the next steps. "
) * 6


@unittest.skipUnless(NODE, "node runtime unavailable")
@unittest.skipUnless(PYTHON, "no python runtime for the guard round trip")
class OpenCodeOrdinaryChatIsMeasured(unittest.TestCase):
    """The ORDINARY_CHAT half of the contract, enforced on this host."""

    @classmethod
    def setUpClass(cls):
        # A project with NO active canonical work, because the canonical
        # classifier -- not this adapter -- decides which half of the contract
        # governs a reply. With an active Work the turn is operational by
        # definition and ORDINARY_CHAT is unreachable here.
        cls.project = fresh_project()
        cls.tmp = Path(tempfile.mkdtemp(prefix="saipen-t1568-"))
        cls.results = run_cases(
            PLUGIN, cls._cases(), cls.tmp, extra_env={"SAIPEN_PYTHON": PYTHON}
        )
        cls.by_id = {item["id"]: item for item in cls.results}

    @staticmethod
    def _env(**overrides):
        env = {
            "SAIPEN_SKILL_ROOT": str(REPO),
            "SAIPEN_PYTHON": PYTHON,
            "SAIPEN_GUARD_STARTUP_PROBE": None,
            "SAIPEN_AGENT": "test-agent",
        }
        env.update(overrides)
        return env

    @classmethod
    def _cases(cls) -> list[dict]:
        return [
            {
                "id": "ordinary_over_budget",
                "project": str(cls.project),
                "env": cls._env(),
                "session_id": "ses_t1568_drift",
                "text_complete": OVER_BUDGET,
            },
            {
                "id": "ordinary_compact",
                "project": str(cls.project),
                "env": cls._env(),
                "session_id": "ses_t1568_ok",
                "text_complete": COMPACT,
            },
        ]

    def test_an_over_budget_ordinary_reply_is_refused(self):
        record = self.by_id["ordinary_over_budget"]
        self.assertEqual(record["outcome"], "blocked", record)
        self.assertIn("CHAT_STYLE_DRIFT", record["message"], record)

    def test_a_compact_ordinary_reply_in_the_pinned_language_is_accepted(self):
        record = self.by_id["ordinary_compact"]
        self.assertEqual(record["outcome"], "allowed", record)

    def test_the_fixtures_measure_what_they_claim(self):
        """The pair is only evidence if the two texts really differ in verdict.

        Checked against the canonical classifier directly, so a fixture that
        stopped being over budget (a STYLE.md edit, a language restamp) fails
        loudly instead of quietly making the gate look green.
        """
        from saipen_engine.chat_style import chat_style_errors, compile_style_contract
        from saipen_engine.state import running_style_text

        contract = compile_style_contract(running_style_text())
        self.assertTrue(chat_style_errors(OVER_BUDGET, contract=contract), OVER_BUDGET)
        self.assertEqual(chat_style_errors(COMPACT, contract=contract), [], COMPACT)

    def test_the_registry_claim_matches_the_measured_hook(self):
        """MECHANICAL style may not be a claim the artifact does not carry."""
        registry = json.loads(
            (REPO / "extensions" / "adapters" / "registry.json").read_text(
                encoding="utf-8-sig"
            )
        )
        opencode = {a["id"]: a for a in registry["adapters"]}["opencode"]
        self.assertEqual(opencode["style_enforcement"], "MECHANICAL", opencode)
        # Without hard admission: the plugin still writes no admission evidence.
        self.assertNotEqual(opencode["admission_enforcement"], "MECHANICAL", opencode)
        token = opencode.get("style_hook")
        self.assertTrue(token, opencode)
        self.assertIn(token, PLUGIN.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()