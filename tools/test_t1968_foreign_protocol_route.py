"""T-1968 / EXACT-NAMESPACE-01: an explicit protocol command keeps its owner.

What was measured before this ticket (2026-10-30, _BZ_REA):

* The launcher was healthy. `saipen host entry --json` answered PATH_LAUNCHER
  with a proven home and version 8.1.0 from the affected project, so nothing
  about transport or project binding caused the incident.
* The skill install was healthy. The installed `~/.agents/skills/saipen/
  SKILL.md` was byte-identical to the canonical `saipen/SKILL.md`.
* The collision was real: SAIPEN declares `cc -> saipen continue`, SAIPAL's own
  SKILL.md advertises `continue`, `next` and `status`, and both skills are
  installed side by side.
* The SAIPEN-side gap was that a FOREIGN protocol command was refused exactly
  like a typo: `saipen saipal continue` answered `unknown command: saipal`,
  byte-identical in shape to `saipen bogusxyz`. A refusing foreign protocol
  then looked like a thing to go fix by changing directory into its repo.

The repair does not remove or rename any SAIPEN command, and it does not claim
control over a foreign protocol. It makes the owner of the requested token
explicit, states the standing NO_HOME rule, and leaves a deliberate foreign
request legal.

LIMITS, stated so nobody reads more into these tests than they prove:

* These are UNIT and CONTRACT controls over SAIPEN's own refusal surface. They
  cannot prove what a host's skill picker offers a model, and they do not
  prevent a model from ignoring the refusal. INSTALLED_HOST and LIVE_END_TO_END
  acceptance requires a real FreeBuff run, which is the receiving owner's work.
* Nothing here authorises or forbids SAIPAL's own operations; a genuine SAIPAL
  dispatch is out of scope and must stay working.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
ENGINE = TOOLS / "saipen.py"

sys.path.insert(0, str(TOOLS))

from saipen_engine import commands  # noqa: E402


def run_cli(*argv: str, cwd: Path | None = None) -> tuple[int, str, str]:
    """Run the real CLI. Used so the refusal is measured, never mocked."""
    proc = subprocess.run(
        [sys.executable, "-B", str(ENGINE), *argv],
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def emitted(stdout: str) -> dict:
    """The single JSON document the CLI prints, or {} when it printed none."""
    text = stdout.strip()
    if not text:
        return {}
    start = text.find("{")
    if start < 0:
        return {}
    try:
        return json.loads(text[start:])
    except ValueError:
        return {}


class ForeignOwnerResolutionTests(unittest.TestCase):
    """AC-01: the registry decides ownership, and only declared names count."""

    def test_declared_protocol_name_is_owned(self):
        owner = commands.foreign_protocol_owner("saipal")
        self.assertIsNotNone(owner)
        self.assertEqual(owner["name"], "saipal")

    def test_declared_alias_is_owned(self):
        """`pal` is SAIPAL's own advertised shortcut, so it must resolve too."""
        owner = commands.foreign_protocol_owner("pal")
        self.assertIsNotNone(owner)
        self.assertEqual(owner["name"], "saipal")

    def test_case_and_whitespace_do_not_evade_ownership(self):
        self.assertIsNotNone(commands.foreign_protocol_owner("  SAIPAL "))
        self.assertIsNotNone(commands.foreign_protocol_owner("Pal"))

    def test_a_saipen_verb_is_never_foreign(self):
        for verb in ("continue", "status", "ticket", "ship", "cc", "goal"):
            self.assertIsNone(
                commands.foreign_protocol_owner(verb),
                f"{verb} is a SAIPEN verb and must not be attributed to another protocol",
            )

    def test_an_unknown_token_has_no_owner(self):
        self.assertIsNone(commands.foreign_protocol_owner("bogusxyz"))


class RefusalIsTypedTests(unittest.TestCase):
    """AC-02: the refusal names the owner, the route, and the NO_HOME rule."""

    def test_foreign_command_is_not_a_bare_unknown_command(self):
        code, out, _ = run_cli("saipal", "continue", "--json")
        payload = emitted(out)
        self.assertEqual(code, 2)
        self.assertEqual(
            payload.get("code"),
            "FOREIGN_PROTOCOL_COMMAND",
            "a foreign protocol command must not be refused as an unknown command",
        )
        self.assertNotIn("unknown command", json.dumps(payload))

    def test_the_full_invocation_is_reported_not_just_the_first_token(self):
        _, out, _ = run_cli("saipal", "continue", "--json")
        self.assertEqual(emitted(out).get("requested_command"), "saipal continue")

    def test_the_refusal_carries_the_no_home_rule(self):
        """The exact error that made the agent move repositories."""
        _, out, _ = run_cli("saipal", "continue", "--json")
        rule = str(emitted(out).get("no_home_substitution") or "")
        self.assertIn("NO_HOME", rule)
        self.assertIn("never", rule)
        # It must forbid the concrete act, not merely sound discouraging.
        self.assertRegex(rule, r"changing directory|searching")

    def test_the_refusal_names_the_saipen_route_to_use_instead(self):
        _, out, _ = run_cli("saipal", "continue", "--json")
        self.assertIn("saipen continue", str(emitted(out).get("next_action") or ""))

    def test_human_readable_refusal_is_also_typed(self):
        """A non-JSON caller must not get only `unknown command` either."""
        code, out, _ = run_cli("saipal", "continue")
        self.assertEqual(code, 2)
        self.assertIn("not a saipen command", out)
        self.assertIn("NO_HOME", out)

    def test_every_declared_alias_is_refused_the_same_way(self):
        for token in ("saipal", "pal"):
            code, out, _ = run_cli(token, "--json")
            self.assertEqual(code, 2, token)
            self.assertEqual(emitted(out).get("code"), "FOREIGN_PROTOCOL_COMMAND", token)


class NegativeControlTests(unittest.TestCase):
    """AC-03: the repair did not break anything it did not own."""

    def test_a_real_typo_keeps_the_ordinary_refusal(self):
        code, out, _ = run_cli("bogusxyz", "--json")
        payload = emitted(out)
        self.assertEqual(code, 2)
        self.assertEqual(payload.get("code"), "VALIDATION_FAILED")
        self.assertIn("unknown command: bogusxyz", str(payload.get("detail") or ""))
        self.assertNotEqual(payload.get("code"), "FOREIGN_PROTOCOL_COMMAND")

    def test_declared_saipen_shortcuts_still_resolve(self):
        """`cc` must stay SAIPEN's own; the repair may not shadow a real row."""
        code, out, _ = run_cli("cc", "--json")
        payload = emitted(out)
        self.assertNotEqual(payload.get("code"), "FOREIGN_PROTOCOL_COMMAND")
        self.assertNotIn(
            "FOREIGN_PROTOCOL_COMMAND",
            out,
            "the SAIPEN shortcut cc was claimed by a foreign protocol",
        )

    def test_continue_is_still_a_saipen_command(self):
        code, out, _ = run_cli("continue", "--json")
        self.assertNotIn("FOREIGN_PROTOCOL_COMMAND", out)

    def test_a_damaged_registry_degrades_to_the_old_refusal(self):
        """Fail toward the previous behaviour, never toward a guessed owner."""
        original = commands.load_registry

        def broken(protocol_dir=None):
            return {}

        commands.load_registry = broken
        try:
            self.assertIsNone(commands.foreign_protocol_owner("saipal"))
        finally:
            commands.load_registry = original


if __name__ == "__main__":
    unittest.main()
