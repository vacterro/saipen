"""Red-before-green measurement for audit/27.md wave 1 (CORE-001..CORE-005).

The audit's CORE_DONE_WHEN demands an ISOLATED red-before-green regression per
finding. The PERF wave already had one (probe_perf.py); wave 1 only had a
probe that printed before/after lines, and one of those lines (CORE-003) was a
TypeError in both directions, so it measured nothing.

For each finding this rebuilds a scratch engine from the current tree, reverts
exactly that one repair to the pre-fix shape the audit describes, and runs the
matching test from tools/test_t1944_core_wave1.py against it. A repair is
proven only when the unchanged test is GREEN on the current tree and RED on the
reverted copy.

CORE-003's repair is REGISTRY.json content, not Python, so its revert
substitutes the pre-fix `goal_authority.until` vocabulary through the same
`load_registry` seam the production code reads -- see control_core003.py for the
standalone version; it is folded in here so all five pairs print as one table.

Read-only against the repository: every mutation happens in a throwaway copy
under V:/_TEMP_/.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRATCH = Path("V:/_TEMP_/t1944-core-revert")
SOURCE_ENGINE = REPO / "tools" / "saipen_engine"


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"anchor not found in {path.name}:\n{old[:300]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _fresh_copy() -> Path:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    (SCRATCH / "tools").mkdir(parents=True)
    shutil.copytree(SOURCE_ENGINE, SCRATCH / "tools" / "saipen_engine")
    shutil.copy(REPO / "tools" / "test_t1944_core_wave1.py", SCRATCH / "tools")
    # CORE-005 drives the real CLI, which reads the whole protocol directory
    # (BOOT.md, REGISTRY.json, COMMAND_EFFECTS.json, ...). Copying only BOOT and
    # REGISTRY made the CLI die on an import-time table load, which looked like
    # a CORE-005 regression in BOTH directions instead of a fixture gap.
    shutil.copytree(REPO / "saipen", SCRATCH / "saipen")
    shutil.copy(REPO / "tools" / "saipen.py", SCRATCH / "tools")
    for cache in SCRATCH.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    return SCRATCH


def _run(expr: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tools/test_t1944_core_wave1.py", "-q", "-k", expr],
        cwd=SCRATCH,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    lines = (proc.stdout or "").strip().splitlines()
    summary = lines[-1] if lines else str((proc.stderr or "").strip().splitlines()[-1:])
    return proc.returncode == 0, summary


def revert_core_001() -> None:
    """Pre-fix: `authenticated is True` plus a string signature was the proof."""
    adapter = SCRATCH / "tools" / "saipen_engine" / "saipal_adapter.py"
    _replace(
        adapter,
        """            verified_by_broker = (
                qual_proof.get("authenticated") is True
                and isinstance(qual_proof.get("signature") or qual_proof.get("provenance"), str)
                and _broker_verified(qual_proof)
            )
            if (
                qual_proof.get("authenticated") is True
                and not verified_by_broker
            ):
                return {
                    "ok": False,
                    "status": "NOT_QUALIFIED",
                    "error": (
                        f"Finding {fid} claims broker authentication that no live "
                        "authority broker can reproduce; a self-declared "
                        "`authenticated`/`signature` pair is not a proof."
                    ),
                    "finding_id": fid,
                }""",
        """            # Pre-fix shape: boolean + string IS the authentication decision.
            verified_by_broker = (
                qual_proof.get("authenticated") is True
                and isinstance(qual_proof.get("signature") or qual_proof.get("provenance"), str)
            )""",
    )


def revert_core_002() -> None:
    """Pre-fix: a state with no `state_digest` was accepted as valid."""
    campaign = SCRATCH / "tools" / "saipen_engine" / "campaign.py"
    text = campaign.read_text(encoding="utf-8")
    start = text.index('        stored_digest = data.get("state_digest")')
    end = text.index("        state_copy = {k: v for k, v in data.items()")
    pre_fix = (
        '        stored_digest = data.get("state_digest")\n'
        "        if not stored_digest:\n"
        "            # Pre-fix shape: an absent digest was simply not checked.\n"
        "            state_copy = {k: v for k, v in data.items() if k not in (\"state_digest\", \"updated_at\")}\n"
        "            data.setdefault(\"state_digest\", \"\")\n"
        "            return _valid_state(data, path)\n"
    )
    campaign.write_text(text[:start] + pre_fix + text[end:], encoding="utf-8")


def revert_core_003() -> None:
    """Pre-fix: the registry's closed `until` vocabulary lacked the scope."""
    registry = SCRATCH / "saipen" / "REGISTRY.json"
    data = json.loads(registry.read_text(encoding="utf-8-sig"))
    data["goal_authority"]["until"] = [
        scope
        for scope in data["goal_authority"]["until"]
        if scope != "continuous_maintenance"
    ]
    registry.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def revert_core_004() -> None:
    """Pre-fix: substring ticket match plus any `.saipen/` path as evidence."""
    adapter = SCRATCH / "tools" / "saipen_engine" / "saipal_adapter.py"
    _replace(
        adapter,
        """            from .board import parse_board

            parsed = parse_board(board_file.read_text(encoding="utf-8"))
            ticket = parsed["tickets"].get(str(task_id).strip())
            if ticket is None:""",
        """            # Pre-fix shape: substring membership, not ticket identity.
            board_text = board_file.read_text(encoding="utf-8")
            if str(task_id).strip() in board_text and "- [x]" in board_text:
                ticket = {"section": "## DONE"}
            else:
                ticket = None
            if ticket is None:""",
    )


def revert_core_005() -> None:
    """Pre-fix: status answered `ok: true, campaign: null` for corruption."""
    saipen = SCRATCH / "tools" / "saipen.py"
    text = saipen.read_text(encoding="utf-8")
    start = text.index("            inspection = campaign_mod.inspect_campaign_state(project_root)")
    end = text.index("        if sub == \"admit\":", start)
    pre_fix = (
        "            # Pre-fix shape: `load_campaign_state` is None for absent AND\n"
        "            # unreadable, and both were reported as success.\n"
        "            state = campaign_mod.load_campaign_state(project_root)\n"
        "            _emit({\"ok\": True, \"campaign\": state, \"route\": command}, as_json)\n"
        "            return 0\n"
    )
    saipen.write_text(text[:start] + pre_fix + text[end:], encoding="utf-8")


CASES = [
    ("CORE-001", "Core001ForgedQualificationProof", revert_core_001),
    ("CORE-002", "Core002CampaignStateDigestIsMandatory", revert_core_002),
    ("CORE-003", "Core003MaintenanceScopeAgreesAcrossWriterAndReader", revert_core_003),
    ("CORE-004", "Core004VerifiedDispositionNeedsExactBinding", revert_core_004),
    ("CORE-005", "Core005CampaignStatusDistinguishesCorruption", revert_core_005),
]


def main() -> int:
    results: list[tuple[str, bool, str, bool, str]] = []
    for name, expr, revert in CASES:
        _fresh_copy()
        green_ok, green_summary = _run(expr)
        revert()
        for cache in SCRATCH.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
        red_ok, red_summary = _run(expr)
        results.append((name, green_ok, green_summary, red_ok, red_summary))
        verdict = "PROVEN" if (green_ok and not red_ok) else "NOT PROVEN"
        print(f"{name} [{expr}]")
        print(f"  current  = {'PASS' if green_ok else 'FAIL'}  ({green_summary})")
        print(f"  reverted = {'PASS' if red_ok else 'FAIL'}  ({red_summary})")
        print(f"  -> {verdict}")
    proven = sum(1 for _n, g, _gs, r, _rs in results if g and not r)
    print()
    print(f"{proven}/{len(results)} red-before-green pairs measured")
    return 0 if proven == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
