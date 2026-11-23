"""Apply the T-1757 change set: exact replacements, counts asserted, endings kept.

Run from the repository root:
    python -B .saipen/evidence/T-1757-claim-route/apply_t1757.py [--check]
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent
EDITS: list[tuple[str, str, str]] = []


def edit(path: str, old: str, new: str) -> None:
    EDITS.append((path, old, new))


OPS = "tools/saipen_engine/operations.py"

edit(
    OPS,
    "def _plan_claim(\n"
    "    root: Path,\n"
    "    ticket_id: str,\n"
    "    agent: str,\n"
    "    now: str,\n"
    "    utc: str,\n"
    "    instant: datetime.datetime | None = None,\n"
    "    explicit: bool = False,\n"
    ") -> OperationPlan | Result:\n",
    "def _audit_route_basis(\n"
    "    root: Path, tickets: dict, agent: str, now: datetime.datetime, ticket_id: str\n"
    ") -> str | None:\n"
    '    """The route that continues with `ticket_id` ahead of the Pick Rule, or None.\n'
    "\n"
    "    T-1757: the router owns continuation, and its audit-inbox route names Work\n"
    "    ahead of the BOARD order (SOURCE-AUDIT-INBOX-01). The claim asked only\n"
    "    `pick_next_work`, so the router's own `PHASE SCOUT <T>` could be followed\n"
    "    only with `--explicit`, which wrote a DEC saying the Pick Rule was stepped\n"
    "    over when nothing was. This asks the router's own seam and decision.\n"
    '    """\n'
    "    try:\n"
    "        from .audit_route import audit_route_owns\n"
    "        from .router import audit_inbox_projection\n"
    "\n"
    "        projection = audit_inbox_projection(root)\n"
    "        owns = audit_route_owns(projection, tickets, agent=agent, now=now)\n"
    "    except Exception:\n"
    "        return None\n"
    "    if owns and isinstance(projection, dict) and projection.get(\"work\") == ticket_id:\n"
    '        return "audit route (SOURCE-AUDIT-INBOX-01)"\n'
    "    return None\n"
    "\n"
    "\n"
    "def _plan_claim(\n"
    "    root: Path,\n"
    "    ticket_id: str,\n"
    "    agent: str,\n"
    "    now: str,\n"
    "    utc: str,\n"
    "    instant: datetime.datetime | None = None,\n"
    "    explicit: bool = False,\n"
    "    basis: str | None = None,\n"
    ") -> OperationPlan | Result:\n",
)
edit(
    OPS,
    "    top_workable, _pick_reason = pick_next_work(tickets, agent=agent, now=instant)\n"
    "    if not explicit:\n"
    "        if top_workable is None or top_workable != ticket_id:\n",
    "    top_workable, _pick_reason = pick_next_work(tickets, agent=agent, now=instant)\n"
    "    # T-1757: a claim of the Work the router or START prescribes is not an\n"
    "    # override: START names the request it was handed (`basis`), the router's\n"
    "    # audit route is asked here.\n"
    "    if basis is None and top_workable != ticket_id:\n"
    "        basis = _audit_route_basis(root, tickets, agent, instant, ticket_id)\n"
    "    if not explicit and basis is None:\n"
    "        if top_workable is None or top_workable != ticket_id:\n",
)
edit(
    OPS,
    "    stepped_over = top_workable if (explicit and top_workable != ticket_id) else None\n"
    '    detail = f"claimed via SAIOPS -- owner {agent}"\n'
    "    if stepped_over is not None:\n"
    '        detail += f" -- EXPLICIT claim over PICK-01: topmost workable was {stepped_over}"\n',
    "    stepped_over = top_workable if ((explicit or basis) and top_workable != ticket_id) else None\n"
    '    detail = f"claimed via SAIOPS -- owner {agent}"\n'
    "    if stepped_over is not None and basis is not None:\n"
    '        detail += f" -- {basis}, ahead of PICK-01 topmost workable {stepped_over}"\n'
    "    elif stepped_over is not None:\n"
    '        detail += f" -- EXPLICIT claim over PICK-01: topmost workable was {stepped_over}"\n',
)
edit(
    OPS,
    "def plan_claim(\n"
    "    project_root: Path | str, ticket_id: str, agent: str, explicit: bool = False\n"
    ") -> Result:\n",
    "def plan_claim(\n"
    "    project_root: Path | str,\n"
    "    ticket_id: str,\n"
    "    agent: str,\n"
    "    explicit: bool = False,\n"
    "    basis: str | None = None,\n"
    ") -> Result:\n",
)
edit(
    OPS,
    "        instant=clock.instant,\n"
    "        explicit=explicit,\n"
    "    )\n"
    "    if isinstance(plan, Result):\n"
    "        return plan\n"
    "    return _render_plan(plan)\n",
    "        instant=clock.instant,\n"
    "        explicit=explicit,\n"
    "        basis=basis,\n"
    "    )\n"
    "    if isinstance(plan, Result):\n"
    "        return plan\n"
    "    return _render_plan(plan)\n",
)
edit(
    OPS,
    "def apply_claim(\n"
    "    project_root: Path | str, ticket_id: str, agent: str, explicit: bool = False\n"
    ") -> Result:\n"
    "    clock = _operation_clock()\n"
    "    plan = _plan_claim(\n"
    "        Path(project_root),\n"
    "        ticket_id,\n"
    "        agent,\n"
    "        clock.now,\n"
    "        clock.utc,\n"
    "        instant=clock.instant,\n"
    "        explicit=explicit,\n"
    "    )\n",
    "def apply_claim(\n"
    "    project_root: Path | str,\n"
    "    ticket_id: str,\n"
    "    agent: str,\n"
    "    explicit: bool = False,\n"
    "    basis: str | None = None,\n"
    ") -> Result:\n"
    "    clock = _operation_clock()\n"
    "    plan = _plan_claim(\n"
    "        Path(project_root),\n"
    "        ticket_id,\n"
    "        agent,\n"
    "        clock.now,\n"
    "        clock.utc,\n"
    "        instant=clock.instant,\n"
    "        explicit=explicit,\n"
    "        basis=basis,\n"
    "    )\n",
)
edit(
    "tools/saipen_engine/entry.py",
    "    # 5. Claim into SCOUT.\n"
    "    claimed = _call(apply_claim, root, ticket, actor, explicit=True)\n",
    "    # 5. Claim into SCOUT. The request is the basis, never a bare override\n"
    "    # (T-1757): OBEY outranks START, and the DEC says so.\n"
    "    claimed = _call(\n"
    "        apply_claim, root, ticket, actor, explicit=True,\n"
    "        basis=f\"user request {captured_receipt}\" if captured_receipt else None,\n"
    "    )\n",
)


def main() -> int:
    planned: dict[str, bytes] = {}
    for rel, old, new in EDITS:
        data = planned.get(rel) or (ROOT / rel).read_bytes()
        crlf = b"\r\n" in data
        old_b, new_b = old.encode("utf-8"), new.encode("utf-8")
        if crlf:
            old_b, new_b = old_b.replace(b"\n", b"\r\n"), new_b.replace(b"\n", b"\r\n")
        count = data.count(old_b)
        if count != 1:
            print(f"ABORT: {rel}: expected exactly one match, found {count}:\n{old[:200]}")
            return 1
        planned[rel] = data.replace(old_b, new_b, 1)
    if "--check" in sys.argv:
        print(f"CHECK OK: {len(EDITS)} edits in {len(planned)} files match exactly once")
        return 0
    for rel, data in planned.items():
        (ROOT / rel).write_bytes(data)
        print(f"patched {rel}")
    target = ROOT / "tools" / "test_t1757_claim_follows_route.py"
    shutil.copyfile(HERE / "draft" / "test_t1757_claim_follows_route.py", target)
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
