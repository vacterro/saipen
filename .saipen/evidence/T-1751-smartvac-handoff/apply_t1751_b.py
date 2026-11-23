"""T-1751 second edit: the reconcile gate asks with the acting agent.

A dry run under a placeholder actor proposes STATE.agent = <placeholder>, which
reconcile itself refuses as an owner split (VALIDATION_FAILED), so the gate must
ask exactly as `continue` does: with the acting actor, else STATE.agent.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path.cwd()
EDITS: list[tuple[str, str, str]] = []


def edit(path: str, old: str, new: str) -> None:
    EDITS.append((path, old, new))


edit(
    "tools/saipen_engine/router.py",
    "def gate_route(project_root, routed: dict, *, reconciled: dict | None = None) -> dict | None:\n",
    "def gate_route(\n"
    "    project_root, routed: dict, *, reconciled: dict | None = None, agent: str | None = None\n"
    ") -> dict | None:\n",
)
edit(
    "tools/saipen_engine/router.py",
    "    `reconciled` is the reconciliation the caller already ran: the CLI\n"
    "    continuation reconciles before it routes, so it hands its verdict over\n"
    "    instead of paying for a second one.\n"
    '    """\n'
    "    rewritten = reconcile_gate(project_root, routed, reconciled=reconciled)\n",
    "    `reconciled` is the reconciliation the caller already ran: the CLI\n"
    "    continuation reconciles before it routes, so it hands its verdict over\n"
    "    instead of paying for a second one. `agent` is the acting actor the\n"
    "    continuation would reconcile as.\n"
    '    """\n'
    "    rewritten = reconcile_gate(project_root, routed, reconciled=reconciled, agent=agent)\n",
)
edit(
    "tools/saipen_engine/router.py",
    "def reconcile_gate(project_root, routed: dict, *, reconciled: dict | None = None) -> dict | None:\n",
    "def reconcile_gate(\n"
    "    project_root, routed: dict, *, reconciled: dict | None = None, agent: str | None = None\n"
    ") -> dict | None:\n",
)
edit(
    "tools/saipen_engine/router.py",
    "    command is an operator decision; one that names none is a stop.\n"
    '    """\n'
    "    if project_root is None or not routed.get(\"ok\"):\n"
    "        return None\n"
    "    if reconciled is None:\n"
    "        try:\n"
    "            from .reconcile import reconcile_protocol_state\n"
    "\n"
    '            reconciled = reconcile_protocol_state(project_root, "diagnostic", dry_run=True)\n',
    "    command is an operator decision; one that names none is a stop.\n"
    "\n"
    "    The dry run asks as the acting actor, else STATE.agent, as `continue`\n"
    "    does: under a placeholder actor reconcile proposes that actor as\n"
    "    STATE.agent and refuses its own plan as an owner split.\n"
    '    """\n'
    "    if project_root is None or not routed.get(\"ok\"):\n"
    "        return None\n"
    "    if reconciled is None:\n"
    "        try:\n"
    "            from . import codec\n"
    "            from .reconcile import reconcile_protocol_state\n"
    "            from .state import parse_state\n"
    "\n"
    "            actor = agent or parse_state(\n"
    '                codec.read_doc(Path(project_root) / ".saipen/STATE.md")\n'
    '            ).get("agent")\n'
    "            reconciled = reconcile_protocol_state(\n"
    '                project_root, str(actor or "diagnostic"), dry_run=True\n'
    "            )\n",
)
edit(
    "tools/saipen.py",
    "    _status_gated = gate_route(project_root, routed)\n",
    "    _status_gated = gate_route(project_root, routed, agent=resolved_agent)\n",
)
edit(
    "tools/saipen.py",
    "    _gated = gate_route(project_root, routed, reconciled=reconciled)\n",
    "    _gated = gate_route(project_root, routed, reconciled=reconciled, agent=resolved_agent)\n",
)
edit(
    "tools/saipen.py",
    "    gated = gate_route(project_root, routed)\n"
    "    if gated is not None:\n"
    "        routed = gated\n",
    "    gated = gate_route(project_root, routed, agent=resolved_agent)\n"
    "    if gated is not None:\n"
    "        routed = gated\n",
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
