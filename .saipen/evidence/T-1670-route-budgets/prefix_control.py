"""SRC-191 PRE-FIX CONTROL: a tiny valid clause is refused by the repository total alone.

usage: python prefix_control.py <repo-root> <fresh-copy-dir>

Copies the protocol, the tools and the tests of the repository as they stand
into a disposable tree (no VCS, no project memory), and in that copy:

  1. runs the registry suite and the budget tool untouched       -> baseline
  2. appends one sentence to a document no budgeted route loads  -> subject
  3. runs both again

The claim under test (SRC-191 R015): step 3 is red on exactly one assertion,
`human_markdown_total <= cap`, while every route budget the tool measures is
still within its limit. Nothing in the repository is written.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

CLAUSE = (
    "\nA candidate that names no receipt stays a candidate: promotion never "
    "invents the authority it lacks.\n"
)
TARGET = "saipen/FUTURE.md"
SUITE = "test_protocol_registry"
SKIP = {
    ".git", ".saipen", "__pycache__", ".pytest_cache", ".ruff_cache",
    ".workbuddy-ai", ".codenomad", ".freebuff", ".claude",
}


def run_suite(copy: Path) -> tuple[int, str]:
    done = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", SUITE],
        cwd=copy / "tools",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return done.returncode, done.stdout + done.stderr


def measure(copy: Path) -> dict:
    done = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import json, protocol_budget as b; m = b.load_profiles(); "
            "print(json.dumps({'over': b.check(), 'total': m['human_markdown_total'], "
            "'budgets': m['budgets'], 'measured': {k: m[k] for k in m['budgets']}}))",
        ],
        cwd=copy / "tools",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return json.loads(done.stdout)


def report(label: str, copy: Path) -> tuple[int, list[str], dict]:
    code, out = run_suite(copy)
    ran = re.search(r"^Ran (\d+) tests? in", out, re.MULTILINE)
    red = re.findall(r"^(?:FAIL|ERROR): (\S+) \((\S+)\)", out, re.MULTILINE)
    asserted = re.findall(r"^AssertionError: .*$", out, re.MULTILINE)
    facts = measure(copy)
    print(f"== {label}")
    print(f"   suite {SUITE}: exit {code}, ran {ran.group(1) if ran else '?'}, red {len(red)}")
    for name, test_id in red:
        print(f"     red: {test_id}")
    for line in asserted:
        print(f"     {line}")
    print(f"   human_markdown_total: {facts['total']} (cap {327 * 1024})")
    for name, limit in facts["budgets"].items():
        print(f"   route budget {name}: {facts['measured'][name]} / {limit}")
    print(f"   route budgets over their limit: {facts['over']}")
    return code, [test_id for _name, test_id in red], facts


def main() -> int:
    repo = Path(sys.argv[1]).resolve()
    copy = Path(sys.argv[2]).resolve()
    assert repo != copy and repo not in copy.parents and not copy.exists(), copy
    shutil.copytree(
        repo, copy, ignore=lambda _d, names: [n for n in names if n in SKIP or n.endswith(".pyc")]
    )
    base_code, base_red, base = report("baseline: the copy as the repository stands", copy)

    target = copy / TARGET
    raw = target.read_bytes()
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    target.write_bytes(raw + CLAUSE.encode("utf-8").replace(b"\n", newline))
    added = len(CLAUSE.encode("utf-8"))
    print(f"== subject: {added} bytes of one sentence appended to {TARGET}")
    code, red, after = report("after the clause", copy)

    only_total = (
        base_code == 0
        and not base["over"]
        and code != 0
        and len(red) == 1
        and red[0].endswith("test_every_declared_load_budget_is_measured_from_registry")
        and not after["over"]
        and after["measured"] == base["measured"]
        and after["total"] == base["total"] + added
        and after["total"] > 327 * 1024
    )
    print(
        "== verdict: "
        + (
            "RED BY THE REPOSITORY TOTAL ALONE -- every route budget is unchanged and "
            "within its limit; the one red assertion is the total against its cap"
            if only_total
            else "NOT THE CLAIMED SHAPE -- read the facts above"
        )
    )
    return 0 if only_total else 1


if __name__ == "__main__":
    raise SystemExit(main())
