"""Red-before-green control for the layout-parity copytree ignore hook.

VERIFY-ORACLE-01 asks for a control that goes RED on the pre-fix code and
GREEN on the post-fix code. The defect was semantic, not a timing race:

    shutil.ignore_patterns(".saipen/locks", ...) compares each candidate
    NAME against each pattern, so no candidate is ever named
    ".saipen/locks" -- the parent candidate is ".saipen" and the child is
    "locks". The exclusion silently matched nothing.

This script materializes that exact shape and counts what each hook copies.
OLD  = the pre-fix expression, preserved verbatim from the test.
NEW  = the path-relative factory now in the test.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

HOME = Path(r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN")
sys.path.insert(0, str(HOME / "tools"))

from test_validator_layout_parity import _ignore_runtime_state  # noqa: E402

# The exact pre-fix expression, preserved verbatim as the control.
OLD_IGNORE = shutil.ignore_patterns(
    ".git", "__pycache__", "*.pyc", "node_modules",
    ".saipen/cache", ".saipen/locks", ".saipen/kitchen",
)

RUNTIME_PATHS = (
    ".saipen/locks/verification-executor.lock",
    ".saipen/cache/verification-flights/x.json",
    ".saipen/kitchen/scratch.tmp",
)
KEPT_PATHS = ("tools/keeper.py", ".saipen/STATE.md")
TRANSIENT_PATHS = (".git/HEAD", "tools/__pycache__/m.cpython-311.pyc")


def build(root: Path) -> None:
    for rel in RUNTIME_PATHS + KEPT_PATHS + TRANSIENT_PATHS:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", encoding="utf-8")


def copied_files(destination: Path) -> set[str]:
    return {
        p.relative_to(destination).as_posix()
        for p in destination.rglob("*")
        if p.is_file()
    }


def judge(label: str, source: Path, frozen: Path, ignore) -> int:
    shutil.copytree(source, frozen, ignore=ignore)
    copied = copied_files(frozen)

    leaked = sorted(p for p in RUNTIME_PATHS if p in copied)
    kept_ok = all(p in copied for p in KEPT_PATHS)
    transient_ok = not any(p in copied for p in TRANSIENT_PATHS)

    print(f"{label}:")
    print(f"  runtime files copied : {len(leaked)}/{len(RUNTIME_PATHS)} {leaked}")
    print(f"  live state preserved : {kept_ok}")
    print(f"  transient excluded   : {transient_ok}")
    # RED when runtime state leaks, or when the filter over-reaches and
    # drops something that must survive.
    red = bool(leaked) or not kept_ok or not transient_ok
    print(f"  verdict              : {'RED' if red else 'GREEN'}")
    return 1 if red else 0


def run_old() -> int:
    with tempfile.TemporaryDirectory(prefix="control-old-") as raw:
        tmp = Path(raw)
        source = tmp / "source"
        build(source)
        return judge(
            "OLD hook (shutil.ignore_patterns -- pre-fix)",
            source,
            tmp / "frozen",
            OLD_IGNORE,
        )


def run_new() -> int:
    with tempfile.TemporaryDirectory(prefix="control-new-") as raw:
        tmp = Path(raw)
        source = tmp / "source"
        build(source)
        # The factory binds to the tree being copied, exactly as the test
        # binds it to HOME.
        return judge(
            "NEW hook (_ignore_runtime_state -- post-fix)",
            source,
            tmp / "frozen",
            _ignore_runtime_state(source),
        )


if __name__ == "__main__":
    old = run_old()
    new = run_new()
    print()
    if old == 1 and new == 0:
        print("CONTROL HOLDS: old code RED, new code GREEN")
        sys.exit(0)
    print(f"CONTROL FAILED: old_exit={old} new_exit={new} (need old=1 new=0)")
    sys.exit(2)
