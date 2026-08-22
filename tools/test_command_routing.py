"""Regression tests: deterministic shortcut + compound-command routing.

Closes the defect class where protocol commands/shortcuts reach free-form
natural-language reasoning before deterministic SAIPEN resolution:

- "sc" answered as a style-mode greeting instead of `saipen crew`;
- "saipen push + build ccc" executing only one segment while the other was
  narrated away as unnecessary.

Run standalone:
    python tools/test_command_routing.py

Exit code 0 when every test passes; 1 on the first failure batch.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import commands as CM  # noqa: E402

PROTOCOL_DIR = TOOLS.parent / "saipen"


def table():
    return CM.load_shortcut_table(PROTOCOL_DIR)


class CommandRoutingTests(unittest.TestCase):
    # ── 1. Bare shortcut ────────────────────────────────────────────────
    def test_bare_sc_shortcut_resolves(self):
        resolved = CM.resolve_compound_command("sc", table=table())
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["kind"], "shortcut")
        self.assertEqual(resolved[0]["command"], "saipen crew")

    def test_bare_shortcuts_from_live_table(self):
        t = table()
        self.assertIn("cc", t)
        self.assertIn("ccc", t)
        self.assertIn("ee", t)
        self.assertIn("qq", t)
        self.assertIn("gg", t)
        self.assertIn("hh", t)
        self.assertIn("ss", t)
        self.assertIn("sss", t)
        self.assertIn("dd", t)
        self.assertIn("aa", t)
        self.assertIn("qqq", t)
        self.assertIn("eee", t)
        self.assertIn("pp", t)
        self.assertIn("tt", t)
        self.assertIn("sc", t)
        # Every declared shortcut resolves to a canonical command row.
        for key, target in t.items():
            self.assertTrue(target.startswith("saipen "), f"{key} -> {target}")

    def test_cyrillic_twin_shortcut(self):
        # сс (Cyrillic) folds through the confusable set c->c to `cc`  # noqa: RUF003
        # (CORE.md: a shortcut typed in Cyrillic is the same shortcut).
        resolved = CM.resolve_compound_command("сс", table=table())  # noqa: RUF001
        self.assertEqual(resolved[0]["kind"], "shortcut")
        self.assertEqual(resolved[0]["command"], "saipen continue")

    # ── 2. Compound command ─────────────────────────────────────────────
    def test_compound_two_segments(self):
        resolved = CM.resolve_compound_command("saipen push + build ccc", table=table())
        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0]["segment"], "saipen push")
        self.assertEqual(resolved[0]["kind"], "command")
        self.assertEqual(resolved[1]["segment"], "build ccc")
        self.assertEqual(resolved[1]["kind"], "shortcut")
        self.assertEqual(resolved[1]["command"], "saipen continue")

    def test_compound_newline_separated(self):
        resolved = CM.resolve_compound_command("saipen status\nsaipen next", table=table())
        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0]["command"], "saipen status")
        self.assertEqual(resolved[1]["command"], "saipen next")

    def test_compound_shortcut_inside(self):
        resolved = CM.resolve_compound_command("cc + qq", table=table())
        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0]["command"], "saipen continue")
        self.assertEqual(resolved[1]["command"], "saipen prepare saiwiki")

    # ── 3. First segment refusal -> chain policy ────────────────────────
    def test_chain_stop_on_failure_default(self):
        out = CM.chain_disposition(["EXECUTED", "REFUSED", "EXECUTED"])
        self.assertEqual(out, ["EXECUTED", "REFUSED", "NOT_RUN"])

    def test_chain_continue_when_independent(self):
        out = CM.chain_disposition(
            ["EXECUTED", "REFUSED", "EXECUTED"],
            policy=CM.CHAIN_CONTINUE_WHEN_INDEPENDENT,
            independent=[False, False, True],
        )
        self.assertEqual(out, ["EXECUTED", "REFUSED", "EXECUTED"])

    def test_chain_not_run_after_blocked(self):
        out = CM.chain_disposition(["EXECUTED", "BLOCKED", "EXECUTED"])
        self.assertEqual(out, ["EXECUTED", "BLOCKED", "NOT_RUN"])

    # ── 4. Already-satisfied state ──────────────────────────────────────
    def test_already_satisfied_terminology(self):
        # The disposition vocabulary is explicit; ALREADY_SATISFIED is a
        # canonical status a command may return, never a model's intuition.
        self.assertEqual(
            CM.DISPOSITION_ALREADY_SATISFIED, "ALREADY_SATISFIED"
        )
        self.assertIn(CM.DISPOSITION_ALREADY_SATISFIED, {
            CM.DISPOSITION_EXECUTED,
            CM.DISPOSITION_REFUSED,
            CM.DISPOSITION_BLOCKED,
            CM.DISPOSITION_SKIPPED_BY_PROTOCOL,
            CM.DISPOSITION_ALREADY_SATISFIED,
            CM.DISPOSITION_NOT_RUN,
            CM.DISPOSITION_FAILED,
        })

    # ── 5. Unknown short token ──────────────────────────────────────────
    def test_unknown_token_not_shortcut(self):
        for token in ("xy", "zz", "qb", "wt"):
            resolved = CM.resolve_compound_command(token, table=table())
            self.assertEqual(len(resolved), 1)
            self.assertEqual(resolved[0]["kind"], "unknown", token)
            self.assertEqual(resolved[0]["command"], "", token)

    def test_unknown_token_in_compound(self):
        resolved = CM.resolve_compound_command("saipen status + xy", table=table())
        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[1]["kind"], "unknown")

    # ── 6. Style-control separation ─────────────────────────────────────
    def test_sc_not_stop_caveman(self):
        sc = CM.resolve_compound_command("sc", table=table())
        style = CM.resolve_compound_command("stop caveman", table=table())
        self.assertEqual(sc[0]["command"], "saipen crew")
        self.assertEqual(style[0]["kind"], "unknown")
        self.assertEqual(style[0]["command"], "")

    def test_normal_mode_not_shortcut(self):
        resolved = CM.resolve_compound_command("normal mode", table=table())
        self.assertEqual(resolved[0]["kind"], "unknown")

    # ── 7. Multiple shortcuts from live table ───────────────────────────
    def test_multiple_shortcuts(self):
        for token, expected in (
            ("sc", "saipen crew"),
            ("cc", "saipen continue"),
            ("eee", "saipen collect saitranslate"),
            ("qqq", "saipen collect saiwiki"),
            ("tt", "saipen test"),
        ):
            resolved = CM.resolve_compound_command(token, table=table())
            self.assertEqual(resolved[0]["command"], expected, token)

    def test_shortcut_nested_in_compound(self):
        resolved = CM.resolve_compound_command("saipen push + qq", table=table())
        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[1]["command"], "saipen prepare saiwiki")

    # ── 8. Provenance (protocol contract surface) ───────────────────────
    def test_protocol_declares_compound_and_truthfulness(self):
        core = (PROTOCOL_DIR / "CORE.md").read_text(encoding="utf-8-sig")
        self.assertIn("Compound commands", core)
        self.assertIn("STOP_ON_FAILURE", core)
        self.assertIn("ALREADY_SATISFIED", core)
        self.assertIn("RESULT: REFUSED", core)
        self.assertIn("Bare shortcut activation", core)
        # The shortcut table is derived from CORE.md, never a second copy.
        self.assertIn("sc", table())

    def test_injectors_declare_shortcut_gate(self):
        ps = (TOOLS.parent / "bootstrap" / "inject.ps1").read_text(encoding="utf-8")
        sh = (TOOLS.parent / "bootstrap" / "inject.sh").read_text(encoding="utf-8")
        for text in (ps, sh):
            self.assertIn("SHORTCUT ACTIVATION GATE", text)
            self.assertIn("sc", text)
            self.assertIn("never \"stop caveman\"", text)
            self.assertIn("a full-token shortcut match ALWAYS wins", text)

    def test_boot_declares_compound_first(self):
        boot = (PROTOCOL_DIR / "BOOT.md").read_text(encoding="utf-8")
        self.assertIn("Compound input first", boot)
        self.assertIn("STOP_ON_FAILURE", boot)


if __name__ == "__main__":
    unittest.main(verbosity=2)