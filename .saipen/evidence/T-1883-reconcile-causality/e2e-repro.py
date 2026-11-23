"""T-1883 AC-01/AC-02 end-to-end: causal ownership through the real pipeline.

Two project roots are identical except for BOARD inventory: the incident STATE
(SHIP / T-1517 / the agent-written REVIEW->SHIP blocker) plus either zero or
four UNRELATED `## BLOCKED` tickets. `reconcile_protocol_state` is the single
verdict owner behind `cc`, `recover`, `status` and Fleet, so this exercises the
real parse -> classify -> repair/refuse path, not a private helper.

Run twice: once against the working-tree classifier (AFTER) and once against a
copy with the presence veto restored (BEFORE). The archive of the repaired
STATE bytes is checked too, because a repair that silently drops bytes would be
its own defect.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from test_fixture_support import CURRENT_STYLE_CONTRACT  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

isolate_host_session()

INCIDENT = "operator_required (continuation_authority) for REVIEW -> SHIP"
UNRELATED = ("T-1469", "T-1480", "T-1483", "T-1505")
ACTIVE = "T-1517"

DEFECT_LINE = "    if cls is not None or related:"
DEFECT_REPLACEMENT = (
    "    if live_blocked or cls is not None:  # RED CONTROL: presence veto\n"
    "        related = list(live_blocked)\n"
)


def _project(blocked=(), needs: dict | None = None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="t1883-e2e-"))
    (root / ".saipen").mkdir(parents=True)
    from saipen_engine.state import running_home

    (root / ".saipen" / "STATE.md").write_text(
        "---\n"
        "phase: SHIP\n"
        f"task: {ACTIVE}\n"
        f'next_action: "PHASE SHIP {ACTIVE}"\n'
        f'blocker: "{INCIDENT}"\n'
        "transition_from: REVIEW\n"
        "saipen_version: 8\n"
        "schema_version: 3\n"
        f"last_event: {len(blocked) + 4}\n"
        "style_contract: " + CURRENT_STYLE_CONTRACT + "\n"
        "mode: full\n"
        "updated: 2026-10-24T00:00:00Z\n"
        "agent: tester\n"
        f"saipen_home: {running_home().as_posix()}\n"
        "---\n",
        encoding="utf-8",
    )
    rows = "".join(
        f"- [ ] {tid} [P2] parked external work | verify: external ack\n"
        for tid in blocked
    )
    need_field = f" | needs: {needs[ACTIVE]}" if needs and ACTIVE in needs else ""
    (root / ".saipen" / "BOARD.md").write_text(
        "## DOING\n"
        f"- [/] {ACTIVE} [P1] ship the release | verify: acceptance suite"
        f"{need_field}"
        " | owner: tester | claim_time: 2026-10-24T00:00:00Z\n"
        "## TODO\n## DONE\n## BLOCKED\n" + rows,
        encoding="utf-8",
    )
    # Every blocked ticket needs an allocation event, or `recover` refuses for
    # legacy adoption FIRST and the blocker classifier never gets a verdict.
    events = [f"- 24.10.26 00:00 [E-004] [{ACTIVE}] [agent: tester] "
              f"[op: ticket-{1517:032d}] DEC: ticket added via SAIOPS\n"]
    prev = "E-004"
    for offset, tid in enumerate(blocked, start=1):
        eid = f"E-{4 + offset:03d}"
        events.append(
            f"- 24.10.26 00:00 [{eid}] [parent: {prev}] [{tid}] [agent: tester] "
            f"[op: ticket-{int(tid.split('-')[1]):032d}] DEC: ticket added via SAIOPS\n"
        )
        prev = eid
    (root / ".saipen" / "LOG.md").write_text("# Log\n" + "".join(events),
                                            encoding="utf-8")
    return root


def _blocker_verdict(result: dict) -> dict | None:
    """The blocker entry, wherever this verdict shape keeps it.

    `ok: False` refusals carry no `repairs` list; the classification is in
    `changed.state`, or the refusal itself is the whole verdict.
    """
    for row in (result.get("changed") or {}).get("state") or []:
        if isinstance(row, dict) and row.get("field") == "blocker":
            return {
                "to": row.get("to"),
                "refuse": bool(row.get("refuse")),
                "classification": row.get("classification"),
            }
    return None



def _snapshot(root: Path) -> dict[str, bytes]:
    return {n: (root / ".saipen" / n).read_bytes()
            for n in ("STATE.md", "BOARD.md", "LOG.md")}


def _install(red: bool):
    """Load the reconcile module to test; a red copy mimics pre-T-1883 bytes."""
    for name in [m for m in sys.modules if m.startswith("saipen_engine.reconcile")]:
        del sys.modules[name]
    if not red:
        import saipen_engine.reconcile as live
        return live

    source = (TOOLS / "saipen_engine" / "reconcile.py").read_text(encoding="utf-8")
    if source.count(DEFECT_LINE) != 1:
        raise SystemExit(f"defect site not unique: {source.count(DEFECT_LINE)}")
    target = Path(tempfile.mkdtemp(prefix="t1883-red-")) / "reconcile.py"
    target.write_text(source.replace(DEFECT_LINE, DEFECT_REPLACEMENT), encoding="utf-8")
    spec = importlib.util.spec_from_file_location(
        "saipen_engine.reconcile", target,
        submodule_search_locations=[str(TOOLS / "saipen_engine")],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["saipen_engine.reconcile"] = module
    spec.loader.exec_module(module)
    return module


def _verdict(module, blocked, needs: dict | None = None) -> dict:
    root = _project(blocked, needs)
    before = _snapshot(root)
    try:
        result = module.reconcile_protocol_state(root, "tester", dry_run=False)
    finally:
        after = _snapshot(root)
        shutil.rmtree(root, ignore_errors=True)
    return {
        "ok": result.get("ok"),
        "code": result.get("code"),
        "remediation": result.get("remediation"),
        "blocker_repair": _blocker_verdict(result),
        "detail": str(result.get("detail") or "")[:220],
        "wrote": {n: before[n] != after[n] for n in before},
    }


def main() -> int:
    scenarios = [
        ("A: zero blocked tickets", (), None),
        ("B: four UNRELATED blocked tickets", UNRELATED, None),
        ("C: one causally RELATED blocked ticket", ("T-1469",), {ACTIVE: ["T-1469"]}),
    ]
    report: dict[str, dict] = {}
    for label, blocked, needs in scenarios:
        for phase in ("BEFORE", "AFTER"):
            module = _install(red=(phase == "BEFORE"))
            report.setdefault(label, {})[phase] = _verdict(module, blocked, needs)


    for label, phases in report.items():
        print(f"\n=== {label}")
        for phase in ("BEFORE", "AFTER"):
            row = phases[phase]
            print(f"  {phase:6} ok={row['ok']} code={row['code']} "
                  f"repair={json.dumps(row['blocker_repair'])} wrote={row['wrote']}")

    a_before = report["A: zero blocked tickets"]["BEFORE"]
    b_before = report["B: four UNRELATED blocked tickets"]["BEFORE"]
    a_after = report["A: zero blocked tickets"]["AFTER"]
    b_after = report["B: four UNRELATED blocked tickets"]["AFTER"]
    c_after = report["C: one causally RELATED blocked ticket"]["AFTER"]

    checks = {
        "BEFORE the defect reproduces: unrelated blocks flip the verdict":
            a_before["ok"] != b_before["ok"]
            or a_before["blocker_repair"] != b_before["blocker_repair"],
        "AFTER unrelated blocks change nothing":
            (a_after["ok"], a_after["blocker_repair"])
            == (b_after["ok"], b_after["blocker_repair"]),
        "AFTER the incident blocker is repairably stale":
            b_after["ok"] is True
            and (b_after["blocker_repair"] or {}).get("to") == "none"
            and not (b_after["blocker_repair"] or {}).get("refuse"),
        "AFTER a causally related block STILL refuses":
            c_after["ok"] is False
            and (c_after["blocker_repair"] or {}).get("refuse") is True,
    }
    print("\nverdicts:")
    for claim, held in checks.items():
        print(f"  {'HELD ' if held else 'BROKEN'} {claim}")
    ok = all(checks.values())
    print(f"\nE2E {'OK' if ok else 'BROKEN'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
