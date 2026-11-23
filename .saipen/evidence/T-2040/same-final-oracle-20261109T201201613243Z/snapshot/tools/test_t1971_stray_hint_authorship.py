"""T-1971: the stray hint must not claim authorship it never observed.

`host_hooks.stray_hint` parses host settings files and reports hooks whose
command form would run their own payload. It never watches a write. Until
T-1971 it printed "Likely writer (HOST_HOOK_RUNS_PAYLOAD)", and that sentence
was read as authorship evidence for a 21,470-byte roadmap that appeared at the
repository root.

The contamination is real and belongs to the same detector: the hook shape it
names produces an EMPTY file whose name is a shell fragment (`BLOCKED`, `` M` ``)
because the payload is executed as command lines. It cannot produce 633 lines of
coherent roadmap prose. The hint therefore has two honest jobs -- name the
configured hazard, and not present configuration as a conclusion about who
wrote a specific file. These tests hold both:

* the positive control: a configured hazard is still named, with its settings
  file, event and matcher, so the detector is not weakened by this change;
* the regression: the sentence must not assert authorship. A reader who sees
  `stray_hint` output must be able to tell it is configuration evidence.

The pre-fix bytes are preserved at
`.saipen/evidence/T-1971-adjudication/prefix-host-hooks.py` so the red half is
reproducible: this same file, run against those bytes, fails on the regression
cases and passes the positive control.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import host_hooks  # noqa: E402

FIELD_COMMAND = (
    "cmd.exe /d /v:off /s /c "
    "'\"\"%USERPROFILE%\\.claude\\hooks\\cbm-code-discovery-gate.cmd\"\"'"
)


def settings(*commands: str, event: str = "PostToolUse", matcher: str = "Read") -> str:
    return json.dumps(
        {
            "hooks": {
                event: [
                    {
                        "matcher": matcher,
                        "hooks": [{"type": "command", "command": c} for c in commands],
                    }
                ]
            }
        }
    )


class StrayHintDoesNotClaimAuthorship(unittest.TestCase):
    """The regression: configuration evidence is never presented as a writer."""

    def hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir()
            (home / ".claude" / "settings.json").write_text(
                settings(FIELD_COMMAND), encoding="utf-8"
            )
            return host_hooks.stray_hint(home / "p", home, "win32")

    def test_the_hint_does_not_say_likely_writer(self):
        """The exact overclaim that produced the T-1971 misattribution."""
        self.assertNotIn(
            "Likely writer",
            self.hint(),
            "the hint must not present a configured hazard as the writer of a "
            "specific stray: it parses settings and observes no write",
        )

    def test_the_hint_says_it_is_configuration_evidence(self):
        hint = self.hint()
        self.assertIn("not observed", hint)
        self.assertIn("CONFIGURED", hint)

    def test_the_hint_names_the_shape_it_predicts(self):
        """A reader must be able to rule the hook OUT for a prose stray."""
        hint = self.hint()
        self.assertIn("shell-fragment", hint)
        self.assertIn("not prose", hint)


class TheDetectorItselfIsUnchanged(unittest.TestCase):
    """Positive controls: naming the hazard still works after the rewording."""

    def test_the_hint_still_names_file_event_and_matcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir()
            path = home / ".claude" / "settings.json"
            path.write_text(settings(FIELD_COMMAND), encoding="utf-8")
            hint = host_hooks.stray_hint(home / "p", home, "win32")
            self.assertIn(str(path), hint)
            self.assertIn("PostToolUse/Read", hint)
            self.assertIn(host_hooks.CODE, hint)

    def test_no_hazard_says_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.assertEqual(host_hooks.stray_hint(home / "p", home, "win32"), "")

    def test_other_platforms_say_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir()
            (home / ".claude" / "settings.json").write_text(
                settings(FIELD_COMMAND), encoding="utf-8"
            )
            self.assertEqual(host_hooks.stray_hint(home / "p", home, "linux"), "")


if __name__ == "__main__":
    unittest.main()
