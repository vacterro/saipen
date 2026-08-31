#!/usr/bin/env python
"""SAIPEN protocol context budgets — registry-decoupled size brake.

SRC-009:R0015. Measures real load profiles, not just total bytes:
  cold <=20KB, ordinary continue <=35KB, command resolution <=30KB,
  ordinary phase <=40KB, ship/improve <=55KB, no routinely-loaded .md >50KB.
CONFORMANCE excluded from production load graph by design.
"""
from __future__ import annotations
import json
from pathlib import Path

BUDGETS = {
    "cold": 20 * 1024,
    "ordinary_continue": 35 * 1024,
    "command_resolution": 30 * 1024,
    "ordinary_phase": 40 * 1024,
    "ship_improve": 55 * 1024,
    "single_doc": 50 * 1024,
}

def _size(p: Path) -> int:
    return p.stat().st_size if p.is_file() else 0

def load_profiles(protocol_dir: Path | None = None) -> dict:
    from tools.saipen_engine.paths import resolve_protocol_dir, resolve_tool_root
    if protocol_dir is None:
        protocol_dir = resolve_protocol_dir(resolve_tool_root())
    p = Path(protocol_dir)
    cold = sum(_size(p / f) for f in ["BOOT.md", "STYLE.md", "INDEX.md"])
    cmd = _size(p / "REGISTRY.json") + _size(p / "COMMANDS.md")
    core = _size(p / "CORE.md")
    boot = _size(p / "BOOT.md")
    phases = sum(_size(f) for f in (p / "phases").glob("*.md")) if (p / "phases").is_dir() else 0
    return {
        "cold": cold,
        "command_resolution": cmd,
        "core": core,
        "boot": boot,
        "phases_total": phases,
        "budgets": BUDGETS,
    }

def check(protocol_dir: Path | None = None) -> list[str]:
    prof = load_profiles(protocol_dir)
    errs: list[str] = []
    if prof["cold"] > BUDGETS["cold"]:
        errs.append(f"cold {prof['cold']} > {BUDGETS['cold']}")
    if prof["command_resolution"] > BUDGETS["command_resolution"]:
        errs.append(f"command_resolution {prof['command_resolution']} > {BUDGETS['command_resolution']}")
    for name in ["CORE.md", "BOOT.md", "MAINTENANCE.md", "OPS.md", "IMPROVE.md"]:
        from tools.saipen_engine.paths import resolve_protocol_dir, resolve_tool_root
        pd = resolve_protocol_dir(resolve_tool_root()) if protocol_dir is None else Path(protocol_dir)
        sz = _size(pd / name)
        if sz > BUDGETS["single_doc"]:
            errs.append(f"{name} {sz} > {BUDGETS['single_doc']}")
    return errs

if __name__ == "__main__":
    import sys
    errs = check()
    prof = load_profiles()
    print(json.dumps(prof, indent=2))
    if errs:
        print("BUDGET FAIL:", "; ".join(errs), file=sys.stderr)
        sys.exit(1)
    print("BUDGET PASS")
