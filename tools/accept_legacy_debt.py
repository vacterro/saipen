#!/usr/bin/env python
"""Register ONE exact sealed historical missing-set as accepted legacy debt.

Canonical registration route for saipen_engine.accepted_debt (Decision B):
validates the exact events against the live canonical history, then writes ONE
journaled AD-NNNNNN record under
`.saipen/recovery/conformance/accepted_debt/`. The canonical validator then
downgrades exactly that finding to a visible warning; everything else stays
blocking. Sealed history is never edited.

    python tools/accept_legacy_debt.py --project-root <path> \
        --events E-964,E-981,E-1007,E-1114,E-1117,E-1124 \
        --authority SRC-047 --reason "operator Decision B ..." [--agent NAME]

Exit 0 only on ACCEPTED_DEBT_REGISTERED. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from saipen_engine.accepted_debt import rebind, register
from saipen_engine.state import parse_state


def _agent(root: Path) -> str:
    try:
        state = parse_state((root / ".saipen" / "STATE.md").read_text(encoding="utf-8"))
        return str(state.get("agent") or "unknown")
    except (OSError, ValueError):
        return "unknown"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".", help="project root (default: cwd)")
    parser.add_argument(
        "--events",
        default=None,
        help="comma-separated exact event ids, e.g. E-964,E-981",
    )
    parser.add_argument(
        "--authority",
        default=None,
        help="canonical authority token: SRC-### | E-### | lineage-<32hex>",
    )
    parser.add_argument("--reason", required=True, help="why this debt is accepted immutable")
    parser.add_argument(
        "--rebind",
        metavar="AD-######",
        default=None,
        help="T-312 rebind mode: re-point this record's evidence at where its events "
        "live NOW (a LOG shard was rotated). The accepted event set is immutable; "
        "combine with --expect-before (the live 16-hex hash being replaced).",
    )
    parser.add_argument(
        "--expect-before",
        default=None,
        help="live hash of the record being repaired; a rebind without it is refused, "
        "because it cannot then prove which bytes it replaces",
    )
    parser.add_argument("--agent", default=None, help="recording agent (default: STATE.agent)")
    args = parser.parse_args(argv)

    if not args.rebind:
        if not args.events:
            parser.error("--events is required unless --rebind is used")
        if not args.authority:
            parser.error("--authority is required unless --rebind is used")
    root = Path(args.project_root).resolve()
    if args.rebind:
        if args.events:
            parser.error("--events and --rebind are mutually exclusive: a rebind never "
                         "changes which events a record accepts")
        if args.authority:
            parser.error("--authority and --rebind are mutually exclusive: the authority "
                         "belongs to the original registration and is immutable")
        if not args.expect_before:
            parser.error("--rebind requires --expect-before")
        result = rebind(
            root,
            args.rebind,
            agent=args.agent or _agent(root),
            reason=args.reason,
            expected_before=args.expect_before,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 1
    events = [part.strip() for part in args.events.split(",") if part.strip()]
    result = register(
        root,
        agent=args.agent or _agent(root),
        events=events,
        reason=args.reason,
        authority=args.authority,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
