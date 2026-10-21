"""T-1821 / SRC-279: the operator surface must survive a Markdown host.

SRC-279's receipt on disk is one title line, but the operator's actual handoff
was recovered from the host's session_input store (evidence:
.saipen/evidence/T-1821-source-recovery/). Section 5 of it says the report the
operator sees concatenates STATUS, AUTHORITY, TICKET, INPUT ABI, DESKTOP PROBE,
WINDOW OWNERSHIP and the rest "into one enormous paragraph", and asks for the
actual text boundary to be diagnosed rather than assumed.

The measured boundary is this: `render_boundary` separated canonical fields with
a SINGLE newline, and the operator's Markdown host (Streamdown: remark-gfm with
no remark-breaks) treats a newline inside a paragraph run as a soft break.
Measured on the host's own parser, `"a\nb"` parses to ONE text node, while
`"a  \nb"` parses to text / break / text. The renderer was emitting six correct
fields as one run of prose -- the fields were never concatenated by SAIPEN's
code, and the stored payload kept its newlines; the collision was between the
canonical wire format and CommonMark.

Section 7 names the regression set. The tests here cover the ones SAIPEN owns:
A (raw multiline stays multiline), B (structured fields are not concatenated),
C (canonical response checks still pass) and L (details stay in evidence without
flooding the surface). D-J and K belong to SAITULS T-301's input harness and are
deliberately not simulated here -- this repository does not own that binary.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import response_surface as RS  # noqa: E402


def soft_breaks(rendered: str) -> int:
    """Count newlines that a Markdown host would render as a SPACE.

    This is the defect's own measure, independent of the fix: in CommonMark a
    line ending is a hard break only when it is preceded by two spaces (or a
    backslash). Any other newline inside a paragraph joins the lines with a
    space, which is exactly the "one enormous paragraph" report.
    """
    lines = rendered.split("\n")
    return sum(
        1
        for index, line in enumerate(lines[:-1])
        if line.strip() and not line.endswith("  ") and not line.endswith("\\")
    )


class FieldsSurviveAMarkdownHost(unittest.TestCase):
    def boundary(self, **kwargs):
        base = dict(
            status="BLOCKED",
            result="T-301 retained; no fabricated PASS",
            blocker="ENV_UNAVAILABLE -- no interactive desktop for the test worker",
            operator_action="NONE",
            next_exact_action="NONE",
            validation="CURRENT_PASS | full core 6958 | red 0 | new_red 0",
        )
        base.update(kwargs)
        return RS.OperationalBoundary(**base)

    def test_regression_a_every_field_line_is_a_markdown_hard_break(self):
        """A: raw multiline response remains multiline once Markdown renders it."""
        rendered = RS.render_boundary(self.boundary())
        self.assertEqual(
            soft_breaks(rendered),
            0,
            "a Markdown host would collapse these lines into one paragraph:\n" + rendered,
        )

    def test_regression_b_fields_are_not_concatenated(self):
        """B: each canonical field keeps its own line and its own label."""
        rendered = RS.render_boundary(self.boundary())
        lines = [line for line in rendered.splitlines() if line.strip()]
        self.assertEqual(len(lines), 5, rendered)
        for line in lines:
            self.assertRegex(line, r"^(STATUS|RESULT|BLOCKER|NEXT EXACT ACTION|VALIDATION): ")

    def test_regression_c_canonical_check_still_accepts_the_render(self):
        """C: the readable form is the form the canonical checker accepts."""
        rendered = RS.render_boundary(self.boundary())
        self.assertEqual(RS.response_errors(rendered), [])

    def test_regression_c_the_render_stays_inside_its_line_budget(self):
        """C: readability may not be bought by relaxing the visible budget."""
        rendered = RS.render_boundary(self.boundary())
        self.assertLessEqual(len(rendered.splitlines()), 6)
        self.assertLessEqual(len(rendered), RS.ORDINARY_RESPONSE_CHAR_BUDGET)

    def test_regression_l_detail_stays_out_of_the_surface(self):
        """L: the technical detail is referenced, never dumped into the reply."""
        rendered = RS.render_boundary(
            self.boundary(
                validation="CURRENT_PASS",
                details=".saipen/evidence/T-1821-source-recovery/RECOVERY.md",
            ),
            detail_mode=RS.DETAIL_MODE_NONE,
        )
        self.assertNotIn("\n" * 2, rendered)
        self.assertNotRegex(rendered, r"(?i)(?:[0-9a-f]{40,64}[ ,|;]*){2,}")
        self.assertEqual(RS.response_errors(rendered), [])

    def test_a_field_value_never_introduces_an_unhard_broken_line(self):
        # A DETAILS block is the one authorized multiline field. Its own lines
        # must also be hard-broken, or an authorized report reintroduces the
        # exact collapse this ticket removed.
        rendered = RS.render_boundary(
            self.boundary(
                validation="CURRENT_PASS",
                details=".saipen/evidence/a.md\n.saipen/evidence/b.md",
            ),
            detail_mode=RS.DETAIL_MODE_REPORT,
        )
        self.assertEqual(soft_breaks(rendered), 0, rendered)

    def test_the_separator_is_the_measured_fix_not_a_relabelled_newline(self):
        # Guard against a future edit that reverts to "\n" while the tests above
        # keep passing because they only check labels.
        self.assertEqual(RS.FIELD_SEPARATOR, "  \n")
        rendered = RS.render_boundary(self.boundary())
        self.assertTrue(
            rendered.splitlines()[0].endswith("  "),
            "the first field must carry the hard break, not a bare newline",
        )


if __name__ == "__main__":
    unittest.main()
