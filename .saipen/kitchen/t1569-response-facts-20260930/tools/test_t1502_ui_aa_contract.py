"""UI.md keeps the antialiasing contract the operator asked for (SRC-115).

T-1502 compacted the operator's strengthening to fit the 300 KiB protocol
markdown budget. A shorter UI.md that quietly turns "always OFF" into a
preference, lets the system smoothing setting decide, or accepts a configured
flag as proof would read fine and fail every real screen, so each of those
meanings is pinned here as a normative phrase.
"""

from __future__ import annotations

import unittest
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "saipen" / "UI.md"


class AntialiasContractTests(unittest.TestCase):
    def setUp(self):
        self.text = " ".join(UI.read_text(encoding="utf-8").split())

    def test_every_meaning_of_the_contract_is_stated(self):
        required = {
            "always off": "AA is always OFF, a hard invariant",
            "no fringe": "no grey or ClearType fringe, no half-pixel edge",
            "system does not decide": (
                "whatever ClearType, font smoothing or driver/browser/toolkit defaults say"
            ),
            "system setting untouched": "never change the system setting",
            "flag is not compliance": "A font name or CSS hint is not compliance",
            "real control": "set the renderer's AA control before any UI, early dialogs included",
            "qt": "`QFont.StyleStrategy.NoAntialias`",
            "gdi": "never `SystemDefault`, ClearType or `AntiAlias`",
            "web limit": "or report the limit",
            "other renderers": "or report there is none",
            "no re-blur": "No re-blur: DPI-aware, no bitmap stretch",
            "pixel proof": "Proof is rendered pixels, not flags",
            "smoothing on": "system smoothing ON",
            "rendering regression": "The regression renders and fails without the AA control",
            "flag secondary": "a flag check is secondary",
            "checklist": "Text passes the *Non-antialiased text* proof.",
        }
        missing = [name for name, phrase in required.items() if phrase not in self.text]
        self.assertEqual(missing, [], "UI.md lost part of the antialiasing contract")

    def test_no_softened_wording(self):
        for weak in ("prefer crisp", "where possible, disable", "if the platform allows"):
            self.assertNotIn(weak, self.text.lower())


if __name__ == "__main__":
    unittest.main()
