"""Red control for real_repository_proof.py (VERIFY-ORACLE-01).

A proof whose every check reads `"ok": true` off disk is not a gate. This
hands the SAME generator a series of known-bad repositories and records that
the matching check goes red each time. Run inside the control fixture.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

CTL = Path(sys.argv[1]).resolve()
GEN = CTL / ".saipen/evidence/T-1370-retirement-20260916/real_repository_proof.py"


def run() -> dict:
    done = subprocess.run(
        [sys.executable, "-B", str(GEN)], cwd=CTL, capture_output=True, text=True
    )
    failed = [
        line.split(":", 1)[0][len("FAIL ") :]
        for line in done.stdout.splitlines()
        if line.startswith("FAIL ")
    ]
    return {"exit": done.returncode, "failed": failed}


def readd_active(_: None) -> None:
    path = CTL / ".saipen/intake/index.json"
    index = json.loads(path.read_text("utf-8-sig"))
    index["active"]["SRC-047"] = {"linked_work": "T-1368"}
    path.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8", newline="\n")


def flip_archived_body(_: None) -> None:
    path = CTL / ".saipen/archive/retired/SRC-047.md"
    path.write_bytes(path.read_bytes().replace(b"one-line", b"ONE-LINE"))


def board_row_back(_: None) -> None:
    path = CTL / ".saipen/BOARD.md"
    text = path.read_text("utf-8-sig")
    row = "- [ ] T-1368 [P1] resurrected row | verify: none\n"
    path.write_text(text.replace("## TODO\n", "## TODO\n" + row, 1), encoding="utf-8", newline="\n")


def fixture_file_back(_: None) -> None:
    target = CTL / "src/app.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('"""back."""\n', encoding="utf-8", newline="\n")


def truncate_residue(_: None) -> None:
    path = CTL / ".saipen/evidence/T-1370-retirement-20260916/src-app.py.residue"
    path.write_bytes(path.read_bytes()[:-5])


def mutate_ticket_record(_: None) -> None:
    path = CTL / ".saipen/archive/retired/T-1368.json"
    record = json.loads(path.read_text("utf-8-sig"))
    record["reason"] = "SOMETHING_ELSE"
    path.write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8", newline="\n")


def fabricate_coverage(_: None) -> None:
    path = CTL / ".saipen/intake/coverage/SRC-047.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"dispositions": [{"clause": "SRC-047:R001", "status": "VERIFIED"}]}, indent=1)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def log_done_claim(_: None) -> None:
    path = CTL / ".saipen/LOG.md"
    text = path.read_text("utf-8-sig")
    path.write_text(
        text + "- 16.09.26 23:59 [E-9999] [T-1368] [agent: x] DEC: ticket finished via SAIOPS\n",
        encoding="utf-8",
        newline="\n",
    )


MUTATIONS = (
    ("SRC-047 back in ACTIVE index", readd_active, "SRC-047 absent from ACTIVE intake index"),
    (
        "archived source body edited",
        flip_archived_body,
        "SRC-047 original request bytes exactly retrievable",
    ),
    ("T-1368 row back on BOARD", board_row_back, "T-1368 absent from schedulable BOARD"),
    ("src/app.py recreated", fixture_file_back, "src/app.py absent"),
    ("residue truncated", truncate_residue, "residue preserves the removed fixture bytes"),
    (
        "ticket record reason mutated",
        mutate_ticket_record,
        "T-1368 forensic record retrievable and valid",
    ),
    ("coverage fabricated", fabricate_coverage, "SRC-047 no fabricated coverage"),
    ("DONE claim appended to LOG", log_done_claim, "T-1368 no DONE claim anywhere in LOG history"),
)


def main() -> int:
    pristine = CTL.parent / (CTL.name + "-pristine")
    if not pristine.exists():
        shutil.copytree(CTL, pristine, symlinks=True)

    green = run()
    results = [
        {
            "mutation": "(none) known-good control",
            "exit": green["exit"],
            "failed": green["failed"],
        }
    ]
    killed = 0
    for label, mutate, expected in MUTATIONS:
        shutil.rmtree(CTL, ignore_errors=True)
        shutil.copytree(pristine, CTL, symlinks=True)
        mutate(None)
        outcome = run()
        hit = expected in outcome["failed"]
        killed += 1 if hit and outcome["exit"] != 0 else 0
        results.append(
            {
                "mutation": label,
                "expected_red_check": expected,
                "exit": outcome["exit"],
                "expected_check_went_red": hit,
                "failed": outcome["failed"],
            }
        )

    shutil.rmtree(CTL, ignore_errors=True)
    shutil.copytree(pristine, CTL, symlinks=True)

    report = {
        "subject": "red control for real_repository_proof.py",
        "known_good_exit": green["exit"],
        "mutations": len(MUTATIONS),
        "killed": killed,
        "results": results,
    }
    print(json.dumps(report, indent=2))
    return 0 if green["exit"] == 0 and killed == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
