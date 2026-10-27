"""T-152 / T-153 / T-154: a red gate must name the repair that resolves it.

Three ways this failed on a live project, all in the path between a blocking
validator finding and the command the operator is handed:

  T-152  the improve-report route set was drawn from EVERY scanned report and
         cut with `[:4]`, so the only FAILING cycle -- the newest one -- was
         named by no route, while four sealed cycles were;
  T-153  the validator emits `... --authority SRC-###` (it cannot know which
         receipt authorises the repair) while the closed remediation table
         required `SRC-\\d+`, so the registered producer-owned route could never
         be extracted from the only message that emits it;
  T-154  the core-sweep repair was embedded INSIDE a `_sweep_errors` element
         and the message then cut the list with `[:6]`, so a repair past the
         sixth error never reached the failure text.

Each test asserts the property, not the patch: it builds the failing message
and asks the machinery that consumes it what it would route.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from saipen_engine import remediation  # noqa: E402
from saipen_engine.conformance import _bounded_remediation_commands  # noqa: E402

VALIDATOR = (TOOLS / "validate.py").read_text(encoding="utf-8-sig")


def _improve_report_failure(scanned: list[str], failing: list[str]) -> str:
    """The message improve-report emits, reconstructed from its own source.

    Both the population and the cap are read out of validate.py rather than
    hardcoded, so a test cannot pass by agreeing with itself: if the source
    reverts, this rebuilds the reverted behaviour.
    """
    failing_only = "_failing_cycles" in VALIDATOR
    errors = [
        f".saipen/improve/{c}/saipen-cli-01/saipen_improve_SAIPEN.md: report error"
        for c in (failing if failing_only else scanned)
    ]
    if not errors:
        return ""  # the block does not fire; nothing is emitted at all
    routes: list[str] = []
    seen: set[str] = set()
    for err in errors:
        cycle = Path(err.split(":", 1)[0]).parent.parent.name
        if cycle and cycle not in seen:
            seen.add(cycle)
            routes.append(f"saipen improve reconcile {cycle}")
    if not failing_only:
        routes = sorted(routes)
        cap = re.search(r"_cycles\[:(\d+)\]", VALIDATOR)
        if cap:
            routes = routes[: int(cap.group(1))]
    return (
        "improve report [improve-report] -- "
        + "; ".join(errors[:6])
        + "; run " + ", ".join(routes)
    )


def _sweep_failure(repairs: list[str], *, generic_before: int = 0) -> str:
    """The message core sweep emits, reconstructed from its own source."""
    errors = [f"SWEEP.md:{i} generic sweep grammar problem" for i in range(generic_before)]
    for ticket in repairs:
        errors.append(
            f"SWEEP.md:{len(errors) + 1} PROTOCOL_VIOLATION RUN-1/IMP-001 produced "
            f"ticket {ticket} without recurrence: and weak_model: (META-IMPROVEMENT "
            f"+ WEAK-MODEL PRECEDENT reasoning gates, red controls 15/16); the "
            f"executable repair is `saipen ticket reasoning {ticket} --recurrence "
            f"<META-IMPROVEMENT reasoning> --weak-model <WEAK-MODEL PRECEDENT "
            f"answer>`, which refuses unless this exact strict-sweep linkage resolves"
        )
    if not errors:
        return "core sweep [sweep-ticket-link] -- "
    cap = re.search(r"; \".join\(_sweep_errors\[:(\d+)\]\)", VALIDATOR)
    prose = errors[: int(cap.group(1))] if cap else errors
    message = "core sweep [sweep-ticket-link] -- " + "; ".join(prose)
    channel = re.search(
        r'executable repairs: " \+ ", "\.join\(_sweep_repairs\[:(\d+)\]\)', VALIDATOR
    )
    if channel:
        # The repair channel is independent of the prose cap: every
        # PROTOCOL_VIOLATION contributes, however deep in the list it sits.
        message += "; executable repairs: " + ", ".join(
            f"saipen ticket reasoning {t}" for t in repairs[: int(channel.group(1))]
        )
    return message


class ProducerLifecycleRouteIsRecoverable(unittest.TestCase):
    """T-153: the validator's own emission must resolve to its table entry."""

    def test_the_emitted_placeholder_form_is_extractable(self) -> None:
        emitted = (
            ".saipen/extensions/subs/saiwiki/STATE.md state/board lifecycle is "
            "incoherent: phase DONE with 2 unresolved BOARD row(s) (SAICREW H); "
            "repair with the producer-owned reconciliation saipen sub reconcile "
            "saiwiki --authority SRC-###"
        )
        self.assertEqual(
            remediation.extract_commands([emitted]),
            ["saipen sub reconcile saiwiki --authority SRC-###"],
            "the registered producer lifecycle route was not recoverable from "
            "the only message that emits it (T-153)",
        )

    def test_the_concrete_form_still_resolves(self) -> None:
        self.assertEqual(
            remediation.resolve_command(
                "saipen sub reconcile saiwiki --authority SRC-123"
            )["rule"],
            "producer lifecycle:terminal",
        )

    def test_the_placeholder_resolves_to_the_same_rule(self) -> None:
        resolved = remediation.resolve_command(
            "saipen sub reconcile saiwiki --authority SRC-###"
        )
        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["rule"], "producer lifecycle:terminal")
        self.assertIn("<SRC-###>", resolved["template"])

    def test_an_unregistered_shape_is_still_refused(self) -> None:
        """The relaxation must not become a hole in the closed table."""
        self.assertFalse(
            remediation.resolve_command(
                "saipen sub reconcile saiwiki --authority lineagenotareceipt"
            ).get("ok")
        )
        self.assertFalse(remediation.resolve_command("saipen sub reconcile ../../etc").get("ok"))


class ImproveReportRouteNamesTheFailingCycle(unittest.TestCase):
    """T-152: the route set is the FAILING population, not the scanned one."""

    CYCLES = [  # noqa: RUF012
        "imp-vacterro-saipal-20260916-1",
        "imp-vacterro-saipal-20260929-1",
        "imp-vacterro-saipal-20260929-2",
        "imp-vacterro-saipal-20260930-1",
        "imp-vacterro-saipal-20261003-1",
    ]

    def test_the_fifth_cycle_is_named_when_it_is_the_failing_one(self) -> None:
        message = _improve_report_failure(self.CYCLES, failing=[self.CYCLES[-1]])
        self.assertIn(
            f"saipen improve reconcile {self.CYCLES[-1]}",
            message,
            "the only failing cycle was named by no route; `saipen continue` "
            "routed the operator at sealed history instead (T-152)",
        )

    def test_no_clean_cycle_is_named(self) -> None:
        message = _improve_report_failure(self.CYCLES, failing=[self.CYCLES[-1]])
        routes = remediation.extract_commands([message])
        self.assertEqual(
            routes,
            [f"saipen improve reconcile {self.CYCLES[-1]}"],
            "the route set named cycles that produced no error (T-152)",
        )

    def test_a_healthy_project_names_no_route_at_all(self) -> None:
        self.assertFalse(
            remediation.extract_commands([_improve_report_failure(self.CYCLES, [])]),
            "four clean cycles were named as the repair for a report that "
            "failed in none of them (T-152)",
        )

    def test_the_route_survives_the_receipts_own_bound(self) -> None:
        message = _improve_report_failure(self.CYCLES, failing=[self.CYCLES[-1]])
        routes = remediation.extract_commands([message])
        self.assertEqual(
            _bounded_remediation_commands(routes),
            routes,
            "the route did not survive the receipt's own bound",
        )


class SweepRepairSurvivesTruncation(unittest.TestCase):
    """T-154: a cap on diagnostic text may never reach the repair."""

    def test_a_repair_past_the_cap_is_still_extracted(self) -> None:
        message = _sweep_failure(["T-042"], generic_before=6)
        self.assertEqual(
            remediation.extract_commands([message]),
            ["saipen ticket reasoning T-042"],
            "the repair was written into the error list and then cut away by "
            "the [:6] join (T-154)",
        )

    def test_a_repair_inside_the_cap_still_survives(self) -> None:
        message = _sweep_failure(["T-007"], generic_before=0)
        self.assertEqual(
            remediation.extract_commands([message]), ["saipen ticket reasoning T-007"]
        )

    def test_several_repairs_all_reach_the_receipt(self) -> None:
        tickets = [f"T-{n:03d}" for n in range(1, 9)]
        message = _sweep_failure(tickets, generic_before=0)
        routes = _bounded_remediation_commands(remediation.extract_commands([message]))
        self.assertEqual(len(routes), len(tickets), routes)
        for ticket in tickets:
            self.assertIn(f"saipen ticket reasoning {ticket}", routes)

    def test_a_clean_sweep_names_no_repair(self) -> None:
        self.assertEqual(remediation.extract_commands([_sweep_failure([])]), [])


class OtherTruncationSitesCarryNoEmbeddedRepair(unittest.TestCase):
    """The sweep T-154 asked for: audit the sibling `[:N]` joins, do not guess.

    The claim under test is that core-sweep is the ONLY site where a machine
    command sits INSIDE a truncated list element. If a future edit embeds one
    elsewhere, this fails and names the site.
    """

    SITES = [1477, 2357, 2382, 2398, 3040, 3620, 4507]  # noqa: RUF012

    def test_no_other_site_embeds_a_command_in_a_truncated_element(self) -> None:
        lines = VALIDATOR.splitlines()
        offenders = []
        for site in self.SITES:
            window = lines[max(0, site - 30) : site]
            join = next(
                (
                    line
                    for line in reversed(window)
                    if re.search(r"join\(_[A-Za-z_]+\[:\d+\]\)", line)
                ),
                None,
            )
            if join is None:
                continue
            # everything between the join's list expression and the join line
            start = window.index(join)
            block = window[start:]
            for offset, line in enumerate(block):
                if re.search(r"join\(_[A-Za-z_]+\[:\d+\]\)", line):
                    break
                if re.search(r"f?\"[^\"]*\bsaipen [a-z]", line):
                    offenders.append(f"line {site - len(block) + offset + 1}")
        self.assertEqual(
            offenders,
            [],
            "a machine command is embedded inside a truncated list element at "
            + ", ".join(offenders)
            + "; lift it out the way core sweep now does",
        )


if __name__ == "__main__":
    unittest.main()
