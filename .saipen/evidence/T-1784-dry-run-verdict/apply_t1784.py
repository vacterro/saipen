"""Apply the T-1784 change under a given root.

    python -B apply_t1784.py <root> [--check]

1. tools/improve.py: the seven Improve mutators take `dry_run` and return
   their plan exactly where they would write, after every gate has run.
2. tools/saipen.py: the improve branches carry `dry_run` into those mutators,
   and the static planner `_improve_dry_run_plan` (grammar only, a fixed
   plan) is removed with its short-circuit.

Every anchor must match exactly once. Keeps line endings.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
IMPROVE = ROOT / "tools/improve.py"
CLI = ROOT / "tools/saipen.py"

HELPER = '''def _dry_run_plan(action: str, target: Path, detail: str, **identity) -> dict:
    """T-1784: a mutator's dry run is its own verdict with the write withheld.

    Every gate of the mutator has run when this is returned, so a plan can
    never promise a transition the real call would refuse.
    """
    return {
        "ok": True,
        "code": "DRY_RUN_PLAN",
        "action": action,
        **identity,
        "targets": [str(target)],
        "detail": f"{detail}; no writes",
    }


'''


def guard(text: str, detail: str) -> str:
    return "    if dry_run:\n        return _dry_run_plan(\n" + detail + "        )\n" + text


IMPROVE_EDITS = [
    (
        "def resolve_stale_complete_seat(cycle_dir: Path, seat_id: str, replacement_seat: str) -> dict:\n",
        HELPER
        + "def resolve_stale_complete_seat(\n"
        "    cycle_dir: Path, seat_id: str, replacement_seat: str, *, dry_run: bool = False\n"
        ") -> dict:\n",
    ),
    (
        '    result = _journaled_write(manifest, proposed, "seat", base_hash=_base_hash(manifest))\n'
        '    if not result.get("ok"):\n'
        "        raise ImproveError(\n"
        '            f"seat {seat} not superseded:',
        guard(
            '    result = _journaled_write(manifest, proposed, "seat", base_hash=_base_hash(manifest))\n'
            '    if not result.get("ok"):\n'
            "        raise ImproveError(\n"
            '            f"seat {seat} not superseded:',
            '            "retire",\n            manifest,\n'
            '            "planned stale COMPLETE -> superseded binding",\n'
            "            cycle_id=cycle_dir.name,\n            seat_id=seat,\n"
            "            replacement_seat=replacement,\n",
        ),
    ),
    ("def abort_cycle(cycle_dir: Path) -> dict:\n", "def abort_cycle(cycle_dir: Path, *, dry_run: bool = False) -> dict:\n"),
    (
        '    result = _journaled_write(manifest, new_text, "cycle", base_hash=_base_hash(manifest))\n'
        '    if not result.get("ok"):\n'
        "        raise ImproveError(\n"
        '            f"cycle {cycle_dir.name} not aborted:',
        guard(
            '    result = _journaled_write(manifest, new_text, "cycle", base_hash=_base_hash(manifest))\n'
            '    if not result.get("ok"):\n'
            "        raise ImproveError(\n"
            '            f"cycle {cycle_dir.name} not aborted:',
            '            "abort",\n            manifest,\n'
            '            "planned cycle ACTIVE -> archived (cycle_aborted: draft-preserved)",\n'
            "            cycle_id=cycle_dir.name,\n",
        ),
    ),
    (
        "def retire_seat(cycle_dir: Path, seat_id: str, reason: str) -> dict:\n",
        "def retire_seat(cycle_dir: Path, seat_id: str, reason: str, *, dry_run: bool = False) -> dict:\n",
    ),
    (
        '    result = _journaled_write(manifest, new_text, "seat", base_hash=_base_hash(manifest))\n'
        '    if not result.get("ok"):\n'
        "        raise ImproveError(\n"
        '            f"seat {seat} not retired:',
        guard(
            '    result = _journaled_write(manifest, new_text, "seat", base_hash=_base_hash(manifest))\n'
            '    if not result.get("ok"):\n'
            "        raise ImproveError(\n"
            '            f"seat {seat} not retired:',
            '            "retire",\n            manifest,\n'
            '            "planned seat availability -> unavailable",\n'
            "            cycle_id=cycle_dir.name,\n            seat_id=seat,\n"
            "            reason=reason,\n",
        ),
    ),
    ("def complete_cycle(cycle_dir: Path) -> dict:\n", "def complete_cycle(cycle_dir: Path, *, dry_run: bool = False) -> dict:\n"),
    (
        '    result = _journaled_write(manifest, new_text, "cycle", base_hash=_base_hash(manifest))\n'
        '    if not result.get("ok"):\n'
        "        raise ImproveError(\n"
        '            f"cycle {cycle_dir.name} not completed:',
        guard(
            '    result = _journaled_write(manifest, new_text, "cycle", base_hash=_base_hash(manifest))\n'
            '    if not result.get("ok"):\n'
            "        raise ImproveError(\n"
            '            f"cycle {cycle_dir.name} not completed:',
            '            "cycle-complete",\n            manifest,\n'
            '            "planned cycle ACTIVE -> COMPLETE",\n'
            "            cycle_id=cycle_dir.name,\n",
        ),
    ),
    ("def complete_report(report_path: Path) -> dict:\n", "def complete_report(report_path: Path, *, dry_run: bool = False) -> dict:\n"),
    (
        '    result = _journaled_write(report_path, new_text, "report", base_hash=_base_hash(report_path))\n'
        '    if not result.get("ok"):\n'
        "        raise ImproveError(\n"
        '            f"report not completed:',
        guard(
            '    result = _journaled_write(report_path, new_text, "report", base_hash=_base_hash(report_path))\n'
            '    if not result.get("ok"):\n'
            "        raise ImproveError(\n"
            '            f"report not completed:',
            '            "complete",\n            report_path,\n'
            '            "planned report draft -> complete",\n'
            "            report=str(report_path),\n",
        ),
    ),
    (
        "def rebind_report_protocol(report_path: Path) -> dict:\n",
        "def rebind_report_protocol(report_path: Path, *, dry_run: bool = False) -> dict:\n",
    ),
    (
        '    committed = _journaled_write(report_path, proposed, "report", base_hash=_base_hash(report_path))\n',
        guard(
            '    committed = _journaled_write(report_path, proposed, "report", base_hash=_base_hash(report_path))\n',
            '            "rebind",\n            report_path,\n'
            '            "planned draft identity re-stamp to the installed protocol; RUN content untouched",\n'
            "            report=str(report_path),\n",
        ),
    ),
    (
        "def append_run(report_path: Path, run_text: str) -> dict:\n",
        "def append_run(report_path: Path, run_text: str, *, dry_run: bool = False) -> dict:\n",
    ),
    (
        '    result = _journaled_write(report_path, proposed, "run", base_hash=_base_hash(report_path))\n',
        guard(
            '    result = _journaled_write(report_path, proposed, "run", base_hash=_base_hash(report_path))\n',
            '            "submit",\n            report_path,\n'
            '            "planned RUN append",\n'
            "            report=str(report_path),\n",
        ),
    ),
]

SHORT_CIRCUIT = (
    "    # CORE-002 (audit fdc73e06): the improve MUTATORS (submit/complete/\n"
    "    # cycle-complete/abort) now run their semantic PLAN under --dry-run and\n"
    "    # return the planned targets with zero writes. Refusal classes are the\n"
    "    # same as non-dry; valid requests report concrete plan targets. The\n"
    "    # previous `DRY_RUN_UNSUPPORTED` short-circuit hid the plan and made\n"
    "    # dry-run observationally different from a real submission.\n"
    '    if dry_run and action in ("submit", "complete", "rebind", "cycle-complete", "abort", "retire"):\n'
    "        return _improve_dry_run_plan(project_root, action, args[1:] if action else [], as_json)\n"
)
SHORT_CIRCUIT_NEW = (
    "    # CORE-002 / T-1784: under --dry-run the improve MUTATORS (submit,\n"
    "    # complete, rebind, cycle-complete, abort, retire) take their real branch\n"
    "    # and the mutator returns its plan where it would write, after every\n"
    "    # gate has run: one implementation, so a plan can never promise what the\n"
    "    # real call refuses (a separate grammar-only planner did, T-1784).\n"
)

CLI_CALLS = [
    ("            result = _append_run(report, run_text)\n", "            result = _append_run(report, run_text, dry_run=dry_run)\n"),
    ("            result = _complete_report(report)\n", "            result = _complete_report(report, dry_run=dry_run)\n"),
    ("            result = _rebind_report_protocol(report)\n", "            result = _rebind_report_protocol(report, dry_run=dry_run)\n"),
    ("            result = complete_cycle(cycle)\n", "            result = complete_cycle(cycle, dry_run=dry_run)\n"),
    ("            result = _abort_cycle(cycle)\n", "            result = _abort_cycle(cycle, dry_run=dry_run)\n"),
    (
        "                result = _resolve_stale_complete_seat(cycle, args[2], replacement)\n",
        "                result = _resolve_stale_complete_seat(\n"
        "                    cycle, args[2], replacement, dry_run=dry_run\n"
        "                )\n",
    ),
    (
        "                result = _retire_seat(cycle, args[2], reason)\n",
        "                result = _retire_seat(cycle, args[2], reason, dry_run=dry_run)\n",
    ),
]

PLANNER_START = "def _improve_dry_run_plan(project_root: Path, action: str, rest: list[str], as_json: bool) -> int:\n"
PLANNER_END = "def _improve(project_root: Path, args: list[str], as_json: bool, dry_run: bool) -> int:\n"


def read(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes()
    return raw.decode("utf-8").replace("\r\n", "\n"), b"\r\n" in raw


def write(path: Path, text: str, crlf: bool) -> None:
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def apply_pairs(text: str, pairs, name: str) -> str:
    for old, new in pairs:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"ABORT: {name}: anchor found {count} times: {old.strip()[:70]!r}")
        text = text.replace(old, new)
    return text


def main() -> int:
    check = "--check" in sys.argv
    improve_text, improve_crlf = read(IMPROVE)
    cli_text, cli_crlf = read(CLI)
    if "def _dry_run_plan(" in improve_text:
        print("ALREADY_APPLIED")
        return 0
    improve_text = apply_pairs(improve_text, IMPROVE_EDITS, "improve.py")
    cli_text = apply_pairs(cli_text, [(SHORT_CIRCUIT, SHORT_CIRCUIT_NEW), *CLI_CALLS], "saipen.py")
    if cli_text.count(PLANNER_START) != 1 or cli_text.count(PLANNER_END) != 1:
        raise SystemExit("ABORT: saipen.py: planner span not unique")
    start = cli_text.index(PLANNER_START)
    end = cli_text.index(PLANNER_END)
    if end < start:
        raise SystemExit("ABORT: saipen.py: planner span out of order")
    cli_text = cli_text[:start] + cli_text[end:]
    if "_improve_dry_run_plan" in cli_text:
        raise SystemExit("ABORT: saipen.py: a reference to the removed planner remains")
    if check:
        print("CHECK OK: every anchor matches once; nothing written")
        return 0
    write(IMPROVE, improve_text, improve_crlf)
    write(CLI, cli_text, cli_crlf)
    print(f"patched {IMPROVE}\npatched {CLI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
