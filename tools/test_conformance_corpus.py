from __future__ import annotations

import unittest
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine.corpus import check_generated, load_cases, validate_cases  # noqa: E402


ROOT = TOOLS.parent


class ConformanceCorpusTests(unittest.TestCase):
    def test_corpus_is_complete_and_generated_view_is_current(self):
        cases = load_cases(ROOT)
        self.assertEqual(validate_cases(cases), [])
        self.assertEqual([case["id"] for case in cases], list(range(1, 257)))
        self.assertEqual(check_generated(ROOT), [])

    def test_rule_ids_and_history_refs_are_separate(self):
        for case in load_cases(ROOT):
            self.assertFalse(any(ref.startswith(("T-", "E-")) for ref in case["rule_ids"]))
            self.assertTrue(all(ref.startswith(("T-", "E-")) for ref in case["history_refs"]))


if __name__ == "__main__":
    unittest.main()
