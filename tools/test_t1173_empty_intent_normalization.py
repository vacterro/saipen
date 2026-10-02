"""T-1173: an empty optional intent field is unset, not corruption.

Measured 31.08.26 (improve cycle imp-vacterro-fastprompter-20260901-1,
agents-01, IMP-001): a STATE carrying `execution_intent: ""` and
`converge_target: ""` is rejected by the strict reader as out-of-enum. The
repair set owned no rule for it, so `saipen recover` and `saipen continue`
both returned VALIDATION_FAILED proposing ZERO changes -- a STATE no command
could clear, bound with no way forward.

These controls pin the repaired contract:

* `recover --dry-run` PROPOSES removing exactly those two keys;
* `recover --apply` commits the repair through the journal;
* `continue` then routes instead of refusing;
* a NON-empty invalid value is still refused -- that is real corruption and
  normalising it would invent operator intent.

Run standalone:
    python -m unittest tools.test_t1173_empty_intent_normalization
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from test_t1412_conformance_truth import T1412Base, _STATE  # noqa: E402

#: The measured STATE: two optional routing fields written as empty strings.
_EMPTY_INTENT_STATE = _STATE.replace(
    'next_action: "saipen continue"',
    'next_action: "saipen continue"\n'
    "execution_intent: \"\"\n"
    "converge_target: \"\"",
)


class EmptyIntentNormalizationTests(T1412Base):
    def _project(self, name: str, state: str) -> Path:
        return self.make_project(name, state=state)

    def test_dry_run_proposes_removing_exactly_those_keys(self) -> None:
        root = self._project("t1173-dry", _EMPTY_INTENT_STATE)
        _rc, _payload, text = self.run_cli(root, "recover", "--dry-run")
        proposed = json_text(text)
        self.assertIn("execution_intent", proposed)
        self.assertIn("converge_target", proposed)
        state_after = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn('execution_intent: ""', state_after, "dry-run must not write")

    def test_apply_commits_and_continue_routes(self) -> None:
        root = self._project("t1173-apply", _EMPTY_INTENT_STATE)
        # `recover` commits by default; --dry-run is the only preview.
        _rc, _payload, _text = self.run_cli(root, "recover")
        state_after = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertNotIn("execution_intent: \"\"", state_after)
        self.assertNotIn("converge_target: \"\"", state_after)
        _rc2, payload2, text2 = self.run_cli(root, "continue", "--dry-run")
        self.assertNotEqual(
            payload2.get("code"), "VALIDATION_FAILED", text2[:1500]
        )

    def test_a_non_empty_invalid_value_still_refuses(self) -> None:
        """Normalising corruption would invent operator intent."""
        bad = _STATE.replace(
            'next_action: "saipen continue"',
            'next_action: "saipen continue"\nexecution_intent: "bogus"',
        )
        root = self._project("t1173-bogus", bad)
        _rc, _payload, text = self.run_cli(root, "recover", "--dry-run")
        self.assertIn("execution_intent", text)
        state_after = (root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn('execution_intent: "bogus"', state_after)


def json_text(raw: str) -> str:
    """The human/JSON body, minus a possible non-UTF8 tail."""
    return raw


if __name__ == "__main__":
    unittest.main()
