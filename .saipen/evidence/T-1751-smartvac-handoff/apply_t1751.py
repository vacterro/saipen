"""Apply the T-1751 change set: exact replacements, counts asserted, endings kept.

Run from the repository root:
    python -B .saipen/evidence/T-1751-smartvac-handoff/apply_t1751.py [--check]
Every replacement is checked before any file is written; a mismatch writes nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path.cwd()
EDITS: list[tuple[str, str, str]] = []


def edit(path: str, old: str, new: str) -> None:
    EDITS.append((path, old, new))


# 1. router: the reconcile verdict is the first gate of the one gate chain.
edit(
    "tools/saipen_engine/router.py",
    "def gate_route(project_root, routed: dict) -> dict | None:\n"
    '    """The ONE ordered gate chain every production route surface applies.\n'
    "\n"
    "    Returns the first gate's rewrite, or None when the route stands. Consumers:\n"
    "    `route_next_result` and the CLI continuation, status and explain-next\n"
    "    paths must agree on the executable action.\n"
    '    """\n'
    "    for gate in (goal_checkpoint_gate, conformance_crew_gate,\n"
    "                 closure_finish_gate, conformance_idle_gate):\n"
    "        rewritten = gate(project_root, routed)\n"
    "        if rewritten is not None:\n"
    "            return rewritten\n"
    "    return None\n",
    "def gate_route(project_root, routed: dict, *, reconciled: dict | None = None) -> dict | None:\n"
    '    """The ONE ordered gate chain every production route surface applies.\n'
    "\n"
    "    Returns the first gate's rewrite, or None when the route stands. Consumers:\n"
    "    `route_next_result` and the CLI continuation, status and explain-next\n"
    "    paths must agree on the executable action.\n"
    "\n"
    "    `reconciled` is the reconciliation the caller already ran: the CLI\n"
    "    continuation reconciles before it routes, so it hands its verdict over\n"
    "    instead of paying for a second one.\n"
    '    """\n'
    "    rewritten = reconcile_gate(project_root, routed, reconciled=reconciled)\n"
    "    if rewritten is not None:\n"
    "        return rewritten\n"
    "    for gate in (goal_checkpoint_gate, conformance_crew_gate,\n"
    "                 closure_finish_gate, conformance_idle_gate):\n"
    "        rewritten = gate(project_root, routed)\n"
    "        if rewritten is not None:\n"
    "            return rewritten\n"
    "    return None\n"
    "\n"
    "\n"
    "def reconcile_gate(project_root, routed: dict, *, reconciled: dict | None = None) -> dict | None:\n"
    '    """T-1751: never advertise a route the continuation refuses before routing.\n'
    "\n"
    "    `continue` reconciles first and stops on the refusal. Status, `next`,\n"
    "    explain-next and the automation block routed past it: they advertised\n"
    "    `cc` with no operator action due while `continue` and `recover` answered\n"
    "    RECONCILE_REAUTH_REQUIRED, and the operator-question gate then refused the\n"
    "    handback that very refusal needs (measured: SMART_VAC_CLEANER E-241,\n"
    "    audit/SAIPEN_20261013_1451_SMARTVAC_RECONCILE_HANDOFF.md). The verdict has\n"
    "    one owner, `reconcile_protocol_state`; this gate projects its dry run.\n"
    "\n"
    "    Only an executable route is rewritten -- a route that already refuses\n"
    "    keeps its own refusal -- and a tripped safety valve alone stands, because\n"
    "    `cc` is itself that reauthorization (CORE-001). A refusal that names a\n"
    "    command is an operator decision; one that names none is a stop.\n"
    '    """\n'
    "    if project_root is None or not routed.get(\"ok\"):\n"
    "        return None\n"
    "    if reconciled is None:\n"
    "        try:\n"
    "            from .reconcile import reconcile_protocol_state\n"
    "\n"
    '            reconciled = reconcile_protocol_state(project_root, "diagnostic", dry_run=True)\n'
    "        except Exception:\n"
    "            # The continuation runs the same owner and reports its own fault;\n"
    "            # a projection never invents a refusal it could not read.\n"
    "            return None\n"
    "    if not isinstance(reconciled, dict) or reconciled.get(\"ok\", True):\n"
    "        return None\n"
    "    from .reconcile import SAFETY_VALVE_TRIPPED\n"
    "\n"
    "    if reconciled.get(\"remediation\") == SAFETY_VALVE_TRIPPED:\n"
    "        return None\n"
    '    command = str(reconciled.get("canonical_next_command") or "")\n'
    "    decision = bool(reconciled.get(\"operator_decision_available\")) and bool(command)\n"
    '    code = str(reconciled.get("code") or "RECONCILE_REFUSED")\n'
    "    return {\n"
    '        "ok": False,\n'
    '        "code": code,\n'
    '        "reason": "reconcile-decision" if decision else "reconcile-refused",\n'
    '        "action": command or "saipen recover",\n'
    '        "canonical_next_command": command or "saipen recover",\n'
    '        "detail": " ".join(str(reconciled.get("detail") or code).split())[:600],\n'
    '        "repair_id": reconciled.get("repair_id"),\n'
    '        "operator_action": _reconcile_operator_action(reconciled) if decision else None,\n'
    "    }\n"
    "\n"
    "\n"
    "def _reconcile_operator_action(reconciled: dict) -> str:\n"
    '    """The one human decision a reconcile refusal carries, bounded (T-1751).\n'
    "\n"
    "    Named by its plan id and tickets, never by restating the reasons, which\n"
    "    stay in `saipen recover --json` where the operator reads them whole.\n"
    '    """\n'
    "    decisions = [\n"
    '        item for item in (reconciled.get("operator_decisions") or []) if isinstance(item, dict)\n'
    "    ]\n"
    '    tickets = sorted({str(t) for item in decisions for t in (item.get("tickets") or [])})\n'
    '    named = ", ".join(tickets[:6]) + (f" and {len(tickets) - 6} more" if len(tickets) > 6 else "")\n'
    '    plan = str(reconciled.get("repair_id") or "")[:12]\n'
    "    if plan:\n"
    '        text = f"Approve recovery plan {plan}" + (f" ({named})" if named else "")\n'
    "    else:\n"
    '        text = " ".join(str(reconciled.get("operator_decision") or "").split())\n'
    "        if not text or len(text) > 200:\n"
    '            text = "Decide the recovery refusal"\n'
    '    return text + "; the plan and its reasons: saipen recover --json"\n',
)
edit(
    "tools/saipen_engine/router.py",
    '    "conformance-unknown": "CONFORMANCE_UNKNOWN",\n'
    "}\n",
    '    "conformance-unknown": "CONFORMANCE_UNKNOWN",\n'
    "    # T-1751: the reconcile verdict the continuation enforces before routing.\n"
    "    # Readable state with a named owner, never a malformed-input failure.\n"
    '    "reconcile-decision": "RECONCILE_REAUTH_REQUIRED",\n'
    '    "reconcile-refused": "RECONCILE_REFUSED",\n'
    "}\n",
)

# 2. automation: a reconcile decision is a human boundary, a refusal a stop.
edit(
    "tools/saipen_engine/automation.py",
    '        if reason == "conformance-unknown":\n'
    '            return INVALID, "conformance-unknown"\n',
    '        if reason == "conformance-unknown":\n'
    '            return INVALID, "conformance-unknown"\n'
    "        # T-1751: recovery needs ONE operator decision before the\n"
    "        # continuation routes at all (`router.reconcile_gate`) -- a human\n"
    "        # boundary, never `cc`; a refusal with no command is a stop.\n"
    '        if reason == "reconcile-decision":\n'
    '            return WAIT_USER, "reconcile-decision"\n'
    '        if reason == "reconcile-refused":\n'
    '            return BLOCKED, "reconcile-refused"\n',
)
edit(
    "tools/saipen_engine/automation.py",
    '        if reason_code in ("conformance-remediation", "conformance-unknown"):\n'
    '            block["remediation_command"] = remediation_command\n'
    '            block["diagnostic"] = (routed or {}).get("diagnostic")\n'
    "        return block\n",
    '        if reason_code in ("conformance-remediation", "conformance-unknown"):\n'
    '            block["remediation_command"] = remediation_command\n'
    '            block["diagnostic"] = (routed or {}).get("diagnostic")\n'
    '        if reason_code in ("reconcile-decision", "reconcile-refused"):\n'
    "            # T-1751: the refusal travels with its owner's words: the code, the\n"
    "            # human decision, and the command the agent runs once it is made.\n"
    '            block["reconcile_code"] = (routed or {}).get("code")\n'
    '            block["operator_action"] = (routed or {}).get("operator_action")\n'
    '            block["remediation_command"] = (routed or {}).get("canonical_next_command")\n'
    "        return block\n",
)

# 3. response facts: the digest names the decision instead of the stale route.
edit(
    "tools/saipen_engine/response_surface.py",
    '    if facts["operator_due"]:\n'
    "        # STATE's legal WAIT owns the actual required decision. Do not print\n"
    "        # the router's generic prose or assign its command to the operator.\n"
    '        wait = str(state.get("next_action") or "")\n'
    '        if wait.startswith("WAIT:"):\n'
    '            facts["operator_action"] = wait[5:].strip()\n'
    "    return facts\n",
    '    if facts["operator_due"]:\n'
    "        # STATE's legal WAIT owns the actual required decision. Do not print\n"
    "        # the router's generic prose or assign its command to the operator.\n"
    '        wait = str(state.get("next_action") or "")\n'
    '        if wait.startswith("WAIT:"):\n'
    '            facts["operator_action"] = wait[5:].strip()\n'
    '    if auto.get("reason_code") in ("reconcile-decision", "reconcile-refused"):\n'
    "        # T-1751: no STATE WAIT carries a reconcile refusal; the automation\n"
    "        # block does, from its owner. The persisted next_action is the route\n"
    "        # the continuation refuses, so it is never printed as the next step.\n"
    '        code = str(auto.get("reconcile_code") or "RECONCILE_REFUSED")\n'
    '        facts["blocker"] = f"{code} -- recovery refuses the continuation; saipen recover --json"\n'
    '        if auto.get("operator_action"):\n'
    '            facts["operator_action"] = auto["operator_action"]\n'
    '        facts["next_action"] = "NONE"\n'
    "    return facts\n",
)

# 4. CLI: status says who waits; the continuation hands its own verdict over.
edit(
    "tools/saipen.py",
    "    _status_gated = gate_route(project_root, routed)\n"
    "    if _status_gated is not None:\n"
    "        routed = _status_gated\n",
    "    _status_gated = gate_route(project_root, routed)\n"
    "    if _status_gated is not None:\n"
    "        routed = _status_gated\n"
    "    # T-1751: a reconcile decision the continuation refuses on is the\n"
    "    # operator's, so it is listed where every human wait is listed.\n"
    '    _reconcile_wait = routed.get("operator_action") if routed.get("reason") == (\n'
    '        "reconcile-decision"\n'
    "    ) else None\n",
)
edit(
    "tools/saipen.py",
    "    _operator_gates = operator_gates(board[\"tickets\"])\n"
    "    waiting_on_you: list[str] = []\n"
    "    next_act = state.get(\"next_action\") or \"\"\n"
    "    if next_act.startswith(\"WAIT:\"):\n"
    "        waiting_on_you.append(next_act)\n",
    "    _operator_gates = operator_gates(board[\"tickets\"])\n"
    "    waiting_on_you: list[str] = []\n"
    "    next_act = state.get(\"next_action\") or \"\"\n"
    "    if next_act.startswith(\"WAIT:\"):\n"
    "        waiting_on_you.append(next_act)\n"
    "    if _reconcile_wait:\n"
    "        waiting_on_you.append(f\"{routed.get('code')}: {_reconcile_wait}\")\n",
)
edit(
    "tools/saipen.py",
    "def _route_once(project_root: Path) -> dict:\n",
    "def _route_once(project_root: Path, *, reconciled: dict | None = None) -> dict:\n",
)
edit(
    "tools/saipen.py",
    "    _gated = gate_route(project_root, routed)\n"
    "    if _gated is not None:\n"
    "        routed = _gated\n",
    "    _gated = gate_route(project_root, routed, reconciled=reconciled)\n"
    "    if _gated is not None:\n"
    "        routed = _gated\n",
)
edit(
    "tools/saipen.py",
    "            after_route = _route_once(project_root) if step_ok else None\n",
    "            after_route = (\n"
    "                _route_once(project_root, reconciled=reconciliation) if step_ok else None\n"
    "            )\n",
)
edit(
    "tools/saipen.py",
    "    dry_run: bool = False,\n"
    ") -> int:\n"
    "    route = _route_once(project_root)\n",
    "    dry_run: bool = False,\n"
    ") -> int:\n"
    "    route = _route_once(project_root, reconciled=reconciliation)\n",
)


def main() -> int:
    planned: dict[str, bytes] = {}
    for rel, old, new in EDITS:
        path = ROOT / rel
        data = planned.get(rel) or path.read_bytes()
        crlf = b"\r\n" in data
        old_b = old.encode("utf-8")
        new_b = new.encode("utf-8")
        if crlf:
            old_b = old_b.replace(b"\n", b"\r\n")
            new_b = new_b.replace(b"\n", b"\r\n")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
