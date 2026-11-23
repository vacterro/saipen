"""Recheck TEST-13 crew_run replay in the existing disposable fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path.cwd() / "tools"
sys.path.insert(0, str(TOOLS))
from test_hermetic_env import isolate_host_session  # noqa: E402
from test_t1363_zero_manual_entry import cli  # noqa: E402
from test_t1430_crew_run_receipt import CrewRunReceiptTests  # noqa: E402


def main() -> None:
    isolate_host_session()
    case = CrewRunReceiptTests("test_sc2_waits_for_a_receipt_then_the_command_satisfies_it")
    case.setUp()
    try:
        case.write_outbox(case.package("HUNT-900"))
        epoch = case.enter_crew()
        first_code, first_payload, first_text = cli(
            case.root, "crew", "record-run", "saihunt", "--json"
        )
        second_code, second_payload, second_text = cli(
            case.root, "crew", "record-run", "saihunt", "--json"
        )
        log = (case.root / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        records = [line for line in log.splitlines() if "crew run -- epoch" in line]
        print(
            json.dumps(
                {
                    "epoch": epoch,
                    "first": {"exit": first_code, **first_payload},
                    "second": {"exit": second_code, **second_payload},
                    "crew_run_log_records": len(records),
                    "record_events": [
                        line.split("[", 2)[1].split("]", 1)[0]
                        for line in records
                        if "[E-" in line
                    ],
                    "stage_satisfied": case.sc2()["satisfied"],
                    "stderr": [first_text, second_text],
                },
                sort_keys=True,
            )
        )
    finally:
        case.doCleanups()


if __name__ == "__main__":
    main()
