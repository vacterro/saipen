"""T-1659 regression pair, measured in two disposable copies of the tree.

RED   = the working tree with every subject file put back to its pre-fix bytes
        (the snapshot taken before the first edit) and the new module absent.
GREEN = the working tree as it is.

The verifier (command + the bytes that define success) is identical in both;
only the subject differs. Nothing in the live tree is written.

usage: regression_pair.py <repo> <prefix-snapshot> <work-dir> <out-dir>
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

COMMAND = "python -B -m unittest test_t1659_run_window   (cwd tools/)"
ORACLE = [
    "tools/test_t1659_run_window.py",
    "tools/test_t1614_future_gate.py",
    "tools/test_hermetic_env.py",
    "tools/test_fixture_support.py",
]
SUBJECT = [
    "tools/saipen_engine/response_surface.py",
]
NEW: list[str] = []


def tracked(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z", "--cached", "--", ".", ":!:.saipen"],
        capture_output=True,
        check=True,
    ).stdout
    return [name for name in out.decode("utf-8").split("\0") if name]


def copy_tree(repo: Path, target: Path) -> int:
    if target.exists():
        shutil.rmtree(target)
    count = 0
    for name in tracked(repo):
        source = repo / name
        if not source.is_file():
            continue
        landed = target / name
        landed.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, landed)
        count += 1
    return count


def run(root: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", "-B", "-m", "unittest", "test_t1659_run_window"],
        cwd=str(root / "tools"),
        capture_output=True,
        timeout=900,
        check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", "replace")


def identities(repo: Path, root: Path) -> tuple[str, str]:
    sys.path.insert(0, str(repo / "tools"))
    from saipen_engine import oracle

    verifier = oracle.verifier_identity(COMMAND, ORACLE, root)[:16]
    subject = oracle.oracle_digest(root, SUBJECT)[:16]
    return verifier, subject


def main() -> int:
    repo, prefix, work, out = (Path(arg) for arg in sys.argv[1:5])
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"command": COMMAND, "oracle": ORACLE, "subject": SUBJECT}

    red = work / "red"
    report["red_files"] = copy_tree(repo, red)
    restored = []
    for name in SUBJECT:
        if name in NEW:
            (red / name).unlink(missing_ok=True)
            continue
        shutil.copyfile(prefix / name, red / name)
        restored.append(name)
    report["red_restored"] = restored
    report["red_absent"] = NEW
    verifier_red, subject_red = identities(repo, red)
    rc_red, text_red = run(red)
    (out / "red_half_tests.txt").write_text(text_red, encoding="utf-8")

    green = work / "green"
    report["green_files"] = copy_tree(repo, green)
    verifier_green, subject_green = identities(repo, green)
    rc_green, text_green = run(green)
    (out / "green_half_tests.txt").write_text(text_green, encoding="utf-8")

    def tail(text: str) -> list[str]:
        lines = [line for line in text.splitlines() if line.strip()]
        return lines[-3:]

    report.update(
        red={"rc": rc_red, "verifier": verifier_red, "subject": subject_red, "tail": tail(text_red)},
        green={
            "rc": rc_green,
            "verifier": verifier_green,
            "subject": subject_green,
            "tail": tail(text_green),
        },
    )
    (out / "regression_pair.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
