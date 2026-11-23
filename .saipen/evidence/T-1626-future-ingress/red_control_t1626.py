"""T-1626 red control for the CHANGED AUTO-14 oracles, run on COPIES.

Two tests own AUTO-14 on the live future_gate corpus and both counted every
live document as historical, so the first gate recorded through
`saipen future add` (FG-0046, machine format) turned them red:

  P1      test_t1618_future_maturation ... test_P1_the_live_corpus_migrates...
  AUTO14  test_t1614_future_gate ... test_AUTO14_the_live_corpus_migrates...

The live tree is never touched: tools/, future_gate/ and saipen/ are copied
into a scratch root per case and the mutant is applied to the copy.

Why the previous session's two mutants stayed green: build_index has a second
net -- `if doc.problems and state == DEFERRED and not reviewed: NEEDS_REVIEW`
-- and every historical document carries a problem, so mutating only
`_initial_state` (or forcing machine=True, which yields header problems) is an
equivalent mutant. The mutants below change observable behaviour:

  A  historical document classified live: both nets removed -> DEFERRED
  B  machine document counted historical: _initial_state always NEEDS_REVIEW
  C  the pre-T-1626 oracle on the current corpus (the original defect)
  D  a historical document is routed: status()["next"] names a NEEDS_REVIEW gate

Usage: python red_control_t1626.py <repo root> <scratch dir>
"""

import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(sys.argv[1]).resolve()
WORK = Path(sys.argv[2]).resolve()
CASES = {
    "P1": "test_t1618_future_maturation.Auto14PerformanceTests."
    "test_P1_the_live_corpus_migrates_within_a_measured_budget",
    "AUTO14": "test_t1614_future_gate.FutureGateAutoDiscoveryTests."
    "test_AUTO14_the_live_corpus_migrates_without_touching_an_original",
}
ENGINE = Path("tools/saipen_engine/future_gate.py")

NET1 = b"    return DEFERRED if doc.machine_readable else NEEDS_REVIEW\n"
NET2 = b"        if doc.problems and state == DEFERRED and not reviewed:\n"
EXPLICIT_REVIEW = b"    if doc.state == NEEDS_REVIEW:\n        return NEEDS_REVIEW\n"
NEXT = b'        "next": chosen.id if chosen else None,\n'
NEXT_LEGACY = (
    b'        "next": next((g.id for g in gates if g.state == NEEDS_REVIEW), None),\n'
)


def fresh_copy(tag: str) -> Path:
    root = WORK / tag
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    shutil.copytree(
        SRC / "tools", root / "tools",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )
    shutil.copytree(SRC / "future_gate", root / "future_gate")
    shutil.copytree(SRC / "saipen", root / "saipen")
    shutil.copytree(SRC / "extensions", root / "extensions",
                    ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
    shutil.copytree(SRC / "bin", root / "bin")
    shutil.copy2(SRC / "VERSION", root / "VERSION")
    return root


def run(root: Path, case: str) -> str:
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", CASES[case]],
        cwd=str(root / "tools"), capture_output=True, stdin=subprocess.DEVNULL, timeout=900,
    )
    tail = proc.stderr.decode("utf-8", errors="replace").strip().splitlines()
    keep = [ln for ln in tail if ln.startswith(("OK", "FAILED", "AssertionError", "AttributeError"))]
    return (f"rc={proc.returncode} " + " | ".join(keep)[:200]).encode("ascii", "replace").decode()


def patch(root: Path, rel: Path, old: bytes, new: bytes) -> None:
    path = root / rel
    data = path.read_bytes().replace(b"\r\n", b"\n")
    assert data.count(old) == 1, f"anchor count {data.count(old)} in {rel}: {old[:60]!r}"
    path.write_bytes(data.replace(old, new))


def pre_t1626_oracles(root: Path) -> None:
    """Restore both tests' committed AUTO-14 oracles (HEAD for t1614; the
    original two lines for t1618, whose file is new in this tree)."""
    head = subprocess.run(
        ["git", "show", "HEAD:tools/test_t1614_future_gate.py"],
        cwd=str(SRC), capture_output=True, check=True,
    ).stdout
    (root / "tools" / "test_t1614_future_gate.py").write_bytes(head)
    path = root / "tools" / "test_t1618_future_maturation.py"
    data = path.read_bytes().replace(b"\r\n", b"\n")
    start = data.index(b"        # AUTO-14 is about the HISTORICAL corpus")
    end = data.index(b"        for relative, blob in originals.items():\n            self.assertEqual((project")
    old = (
        b'        self.assertEqual(indexed["counts"][gates.NEEDS_REVIEW], len(originals))\n'
        b'        self.assertIsNone(gates.status(project, {})["next"])\n'
    )
    path.write_bytes(data[:start] + old + data[end:])


MUTANTS = {
    "control": lambda root: None,
    "A legacy classified DEFERRED": lambda root: (
        patch(root, ENGINE, NET1, b"    return DEFERRED\n"),
        patch(root, ENGINE, NET2, b"        if False:\n"),
    ),
    "B machine gate counted historical": lambda root: patch(
        root, ENGINE, EXPLICIT_REVIEW, b"    if True:\n        return NEEDS_REVIEW\n"
    ),
    "C pre-T-1626 oracle": pre_t1626_oracles,
    "D historical gate routed": lambda root: patch(root, ENGINE, NEXT, NEXT_LEGACY),
}

for index, (name, mutate) in enumerate(MUTANTS.items()):
    root = fresh_copy(f"m{index}")
    mutate(root)
    for case in CASES:
        print(f"{name:34s} {case:7s} {run(root, case)}")
