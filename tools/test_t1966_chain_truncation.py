"""T-1966: an unobservable ancestor must not void the whole origin chain.

MEASURED defect (2026-10-30). `operator_origin.OperatorOrigins._chain` walked
the ancestry and returned `[]` if ANY fact lacked a readable creation time.
On an interactive Windows desktop every ancestry terminates at a protected
system process (`winlogon.exe`) that an ordinary token cannot describe, so the
rule discarded the entire chain and `issue-origin` answered
`HOST_PROVENANCE_UNAVAILABLE -- native host process birth could not be
observed` for every genuine operator event. Measured on this machine: the real
ancestry of the running host is ten facts and its last is `winlogon.exe` with
image None, name None and created None.

The distinction the fix draws, and the one these tests pin:

* an UNREADABLE ancestor is not evidence of tampering -- the chain keeps every
  fact it could verify and stops at the top it could not;
* a CONTRADICTION still is -- a parent born after its child, or a parent whose
  recorded ppid does not name that child, still voids the chain.

The second control matters because the tempting fix ("stop validating past the
first gap") would admit a forged chain above an unreadable boundary.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import operator_origin as O  # noqa: E402
from saipen_engine.host_authority_process import ProcessFact  # noqa: E402


class _Ledger:
    def verify(self, proof):  # pragma: no cover - never reached by _chain
        return True, ""


def fact(pid: int, ppid: int, created, name: str | None = None) -> ProcessFact:
    return ProcessFact(
        pid=pid,
        ppid=ppid,
        image=None,
        name=name,
        argv=None,
        created=created,
    )


def origins(facts):
    """An OperatorOrigins whose ancestry is the supplied list, in order."""
    return O.OperatorOrigins(
        _Ledger(), clock=lambda: 0.0, ancestry=lambda pid, limit=32: list(facts), ttl=60
    )


class AnUnreadableAncestorTruncatesInsteadOfVoiding(unittest.TestCase):
    def test_the_verified_prefix_survives_an_unobservable_top(self):
        """The measured shape: a readable chain ending in winlogon.exe."""
        facts = [
            fact(10, 9, 100.0, "python.exe"),
            fact(9, 8, 90.0, "zaicode.exe"),
            fact(8, 7, 80.0, "explorer.exe"),
            fact(7, 6, None, None),  # winlogon.exe: unreadable to this account
        ]
        chain = origins(facts)._chain(10)
        self.assertEqual([item.pid for item in chain], [10, 9, 8])

    def test_a_fully_readable_chain_is_returned_whole(self):
        facts = [
            fact(10, 9, 100.0, "python.exe"),
            fact(9, 8, 90.0, "zaicode.exe"),
        ]
        self.assertEqual([item.pid for item in origins(facts)._chain(10)], [10, 9])

    def test_the_star_being_unreadable_is_still_no_chain(self):
        """The peer is the fact being proven; without it there is nothing."""
        self.assertEqual(origins([fact(10, 9, None, None)])._chain(10), [])

    def test_red_control_the_all_or_nothing_rule_refuses_the_same_chain(self):
        """The shipped rule, restored verbatim, fails the first case.

        Without this, the test above would pass on a module that had never
        been broken, and the measured defect would not be pinned at all.
        """
        import importlib
        import types

        source = (TOOLS / "saipen_engine" / "operator_origin.py").read_text(encoding="utf-8")
        marker = "        for i, fact in enumerate(facts):\n"
        self.assertIn(marker, source, "the walk moved; update this control")
        red_source = source.replace(
            marker,
            marker + "            if _birth(fact) is None:\n                return []\n",
            1,
        )
        self.assertNotEqual(red_source, source)
        # Execute it AS the package submodule it is, so its relative imports
        # resolve; a standalone `exec` cannot import `.codec` and dies at line 19.
        module = types.ModuleType("saipen_engine._operator_origin_pre_fix")
        module.__package__ = "saipen_engine"
        module.__file__ = str(TOOLS / "saipen_engine" / "operator_origin.py")
        exec(compile(red_source, module.__file__, "exec"), module.__dict__)  # noqa: S102
        red = module.OperatorOrigins
        chain = red(
            _Ledger(),
            clock=lambda: 0.0,
            ancestry=lambda pid, limit=32: [
                fact(10, 9, 100.0, "python.exe"),
                fact(9, 8, 90.0, "zaicode.exe"),
                fact(8, 7, 80.0, "explorer.exe"),
                fact(7, 6, None, None),
            ],
            ttl=60,
        )._chain(10)
        self.assertEqual(chain, [], "the pre-fix rule must void the whole chain")


class AContradictionStillVoidsTheChain(unittest.TestCase):
    def test_a_parent_born_after_its_child_voids_the_chain(self):
        facts = [
            fact(10, 9, 100.0, "python.exe"),
            fact(9, 8, 200.0, "zaicode.exe"),  # born after its own child
            fact(8, 7, 80.0, None),
        ]
        self.assertEqual(origins(facts)._chain(10), [])

    def test_a_broken_parent_link_voids_the_chain(self):
        facts = [
            fact(10, 9, 100.0, "python.exe"),
            fact(9, 999, 90.0, "zaicode.exe"),  # claims a different parent
            fact(8, 7, 80.0, None),
        ]
        self.assertEqual(origins(facts)._chain(10), [])

    def test_a_contradiction_above_an_unreadable_gap_is_never_reached(self):
        """Truncation happens first, so nothing above the gap is admitted.

        This is the reason truncation is safe: the walk does not resume past an
        unobservable fact, so no contradictory ancestor can hide above one.
        """
        facts = [
            fact(10, 9, 100.0, "python.exe"),
            fact(9, 8, 90.0, "zaicode.exe"),
            fact(8, 7, None, None),
            fact(7, 6, 500.0, "forged.exe"),  # would contradict if it were read
        ]
        chain = origins(facts)._chain(10)
        self.assertEqual([item.pid for item in chain], [10, 9])


if __name__ == "__main__":
    unittest.main()
