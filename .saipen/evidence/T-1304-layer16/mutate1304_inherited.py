"""Red controls for the INHERITED gates T-1304 cites for R007, R008, R010, R012.

Usage: mutate1304_inherited.py <repo> <copy> [--old-r008-test]

The first VERIFY cycle proved these four clauses met by suites that already
existed (test_t1304_r004_transition, test_debt_gate, test_conformance_lineage,
test_t1283_lineage_legacy_ingest, test_producer_gate_policy) and ran them
green, but never gave those gates a known-bad input. VERIFY-ORACLE-01: a gate
that cannot fail is not a gate. Each mutation below removes the property one
clause names; the named suites must go red in every repetition.

The copy is a disposable tree: the repository's own .git and .saipen are left
out (the tests' scenario fixtures under tests/ are not). Each mutation is
applied to the copy only and the file is restored before the next one. Same
discipline as mutate1304.py: the unmutated control and every mutation run three
times, and a test red in some repetitions only is reported.

`--old-r008-test` puts the R008 assertion back the way it stood before the
repair (the mid-work finding read from the create_snapshot result envelope), so
the same mutations can be run against the old and the new verifier. For every
mutation the first test_debt_gate.py line each red test failed at is printed:
that line says WHICH assertion noticed.

The final phase is E-13203's R008 control against the PERSISTED RECORD. Every
mutation above edits production source; this one does not. It installs a small
harness in the copy's tools/ that wraps `debt.create_snapshot`, and when the
fixture persists its mid-work snapshot the harness edits that DEBT-XXXXXX.json
ON DISK -- dropping the source_receipt_unresolved_work/T-001 finding and
recomputing the stored findings digest with the canonical
`findings.findings_digest(problems, warnings)` so `load_snapshot` still accepts
the record. The corrected R008 regression must then go RED at its
persisted-snapshot assertion: the storage truth regressed, the record did not
become structurally corrupt.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
copy = Path(sys.argv[2]).resolve()
old_r008_test = "--old-r008-test" in sys.argv[3:]
assert repo != copy and repo not in copy.parents and not copy.exists(), copy

ROOT_ONLY = {".git", ".saipen", ".workbuddy-ai", ".codenomad", ".freebuff", ".claude"}
ANYWHERE = {"__pycache__", ".pytest_cache", ".ruff_cache"}


def ignore(directory: str, names: list[str]) -> list[str]:
    at_root = Path(directory).resolve() == repo
    return [
        n for n in names
        if n in ANYWHERE or n.endswith(".pyc") or (at_root and n in ROOT_ONLY)
    ]


shutil.copytree(repo, copy, ignore=ignore)

DEBT = "tools/saipen_engine/debt.py"
CONFORMANCE = "tools/saipen_engine/conformance.py"
LINEAGE = "tools/saipen_engine/conformance_lineage.py"
PRODUCER = "tools/saipen_engine/producer_gate.py"
DEBT_TEST = "tools/test_debt_gate.py"
R007 = "test_t1304_r004_transition"
R008 = "test_debt_gate"
R010 = ["test_conformance_lineage", "test_t1283_lineage_legacy_ingest"]
R012 = "test_producer_gate_policy"
ALL = [R007, R008, *R010, R012]

NEW_R008_ASSERTION = (
    "        mid = debt_mod.load_snapshot(self.root, mid_snapshot[\"snapshot_id\"])\n"
    "        assert any(\n"
    "            f[\"rule_id\"] == \"source_receipt_unresolved_work\" and f[\"subject_id\"] == \"T-001\"\n"
    "            for f in mid[\"problems\"]\n"
    "        ), mid[\"problems\"]\n"
    "        self.assertEqual(mid_snapshot[\"problem_count\"], len(mid[\"problems\"]))\n"
)
OLD_R008_ASSERTION = (
    "        assert any(\n"
    "            f[\"rule_id\"] == \"source_receipt_unresolved_work\" and f[\"subject_id\"] == \"T-001\"\n"
    "            for f in mid_snapshot.get(\"problems\", [])\n"
    "        ), mid_snapshot\n"
)


def edit(rel: str, edits: list[tuple[str, str]], label: str) -> bytes:
    """Apply exact single-occurrence edits to the copy; return the copy's prior bytes."""
    target = copy / rel
    original = target.read_bytes()
    newline = "\r\n" if b"\r\n" in original else "\n"
    text = original.decode("utf-8")
    for old, new in edits:
        old, new = old.replace("\n", newline), new.replace("\n", newline)
        assert text.count(old) == 1, (label, text.count(old), old[:70])
        text = text.replace(old, new)
    target.write_bytes(text.encode("utf-8"))
    return original


if old_r008_test:
    edit(DEBT_TEST, [(NEW_R008_ASSERTION, OLD_R008_ASSERTION)], "old R008 test")
    print("verifier: test_debt_gate.py with the R008 assertion as it stood before the repair")
else:
    print("verifier: test_debt_gate.py as it stands in the repository")

KEEP = 'f.get("rule_id") != "source_receipt_unresolved_work"'

MUTATIONS = [
    (
        "M18 R007: baseline reuse ignores the three recorded state fingerprints",
        DEBT,
        [(
            "            if any(record.get(key) != value for key, value in live.items()):\n"
            "                continue\n",
            "            if False:\n"
            "                continue\n",
        )],
        [R007],
    ),
    (
        "M19 R008: the persisted snapshot loses the finding its envelope reports",
        DEBT,
        [(
            "        \"problems\": problems,\n"
            "        \"warnings\": warnings,\n"
            "        \"findings_digest\": digest,\n"
            "        \"reason\": reason,\n",
            f"        \"problems\": [f for f in problems if {KEEP}],\n"
            "        \"warnings\": warnings,\n"
            "        \"findings_digest\": findings_mod.findings_digest(\n"
            f"            [f for f in problems if {KEEP}], warnings\n"
            "        ),\n"
            "        \"reason\": reason,\n",
        )],
        [R008],
    ),
    (
        "M20 R010: production latest_receipt never asks the bounded lineage",
        CONFORMANCE,
        [(
            "        handled, record = latest_receipt_bounded(root, gate)\n",
            "        handled, record = False, None\n",
        )],
        R010,
    ),
    (
        "M21 R010: a canonical append bootstraps the legacy inventory, not advance_append",
        CONFORMANCE,
        [(
            "    if prior_receipt_dir_mtime_ns is not None:\n"
            "        from . import conformance_lineage as _cl\n",
            "    if False:\n"
            "        from . import conformance_lineage as _cl\n",
        )],
        R010,
    ),
    (
        "M22 R010: the explicit deep validation path verifies nothing",
        LINEAGE,
        [(
            "    errors: list[str] = []\n"
            "    head = _read_head(root)\n"
            "    if head is None:\n"
            "        return False, [f\"{HEAD_REL}: absent or untrusted lineage head\"]\n",
            "    return True, []\n",
        )],
        R010,
    ),
    (
        "M23 R012: converge forgets one of its required producers",
        PRODUCER,
        [(
            "        return \"FAIL\" if producer in CONVERGE_REQUIRED_PRODUCERS else \"WARN\"\n",
            "        return \"FAIL\" if producer == \"saitranslate\" else \"WARN\"\n",
        )],
        [R012],
    ),
    (
        "M24 R012: a collect gate hardens every producer",
        PRODUCER,
        [(
            "        return \"FAIL\" if producer == gate.producer else \"WARN\"\n",
            "        return \"FAIL\"\n",
        )],
        [R012],
    ),
]


def run(tests: list[str]) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("SAIPEN")}
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", *tests],
        cwd=str(copy / "tools"), env=env, stdin=subprocess.DEVNULL, capture_output=True,
        timeout=1800, check=False,
    )
    return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", errors="replace")


REPEAT = 3

# ---------------------------------------------------------------------------
# E-13203 R008 control: the persisted record, mutated ON DISK.
# ---------------------------------------------------------------------------
PERSISTED_HARNESS = "_r008_persisted_control.py"
PERSISTED_TARGET = "test_delta_resolves_and_reports_release_blocked"

PERSISTED_HARNESS_SOURCE = '''"""R008 over a PERSISTED snapshot mutated on disk (E-13203).

Installed in a disposable copy's tools/ only. Production source is untouched:
the harness wraps the real `debt.create_snapshot`, and once the R008 fixture
has persisted its mid-work snapshot the harness rewrites that record so the
source_receipt_unresolved_work/T-001 finding is gone and the stored digest is
recomputed with the canonical helper, so `load_snapshot` still accepts it.
"""
import json
import unittest
from pathlib import Path
from unittest import mock

import test_debt_gate
from saipen_engine import debt as debt_mod
from saipen_engine import findings as findings_mod

_REAL_CREATE = debt_mod.create_snapshot
_MUTATED = []


def _create_then_regress_the_stored_record(root, agent, reason, *args, **kwargs):
    result = _REAL_CREATE(root, agent, reason, *args, **kwargs)
    if reason == "mid-work" and result.get("ok"):
        path = Path(root) / debt_mod.DEBT_DIR / (result["snapshot_id"] + ".json")
        record = json.loads(path.read_text(encoding="utf-8"))
        kept = [
            f for f in record["problems"]
            if not (
                f.get("rule_id") == "source_receipt_unresolved_work"
                and f.get("subject_id") == "T-001"
            )
        ]
        assert len(kept) == len(record["problems"]) - 1, record["problems"]
        warnings = record.get("warnings") or []
        record["problems"] = kept
        record["problem_count"] = len(kept)
        record["findings_digest"] = findings_mod.findings_digest(kept, warnings)
        path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        # The record must stay LOADABLE. A DEBT_SNAPSHOT_CORRUPT refusal would
        # make the regression red for the wrong reason.
        debt_mod.load_snapshot(root, result["snapshot_id"])
        _MUTATED.append(result["snapshot_id"])
    return result


class PersistedSnapshotControl(test_debt_gate.DebtGateFixtureTests):
    """The R008 regression run over a persisted snapshot mutated on disk."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(
            debt_mod, "create_snapshot", _create_then_regress_the_stored_record
        )
        patcher.start()
        self.addCleanup(patcher.stop)
'''


def red_names(out: str) -> frozenset[str]:
    return frozenset(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", out, flags=re.M))


def failing_lines(out: str) -> dict[str, str]:
    """For each red test, the test_debt_gate.py lines its traceback passes through."""
    lines: dict[str, str] = {}
    for block in re.split(r"^={20,}$", out, flags=re.M):
        name = re.search(r"^(?:FAIL|ERROR): (test_\w+)", block, flags=re.M)
        if name:
            hits = re.findall(r'test_debt_gate\.py", line (\d+)', block)
            if hits:
                lines[name.group(1)] = ",".join(hits)
    return lines


for attempt in range(REPEAT):
    code, out = run(ALL)
    ran = re.search(r"Ran (\d+) tests", out)
    print(f"CONTROL {attempt + 1}/{REPEAT} unmutated copy: exit {code}, "
          f"{ran.group(0) if ran else out[-300:]}")
    assert code == 0, out[-3000:]

undetected = 0
unstable = 0
for label, rel, edits, tests in MUTATIONS:
    original = edit(rel, edits, label)
    runs = [run(tests) for _ in range(REPEAT)]
    (copy / rel).write_bytes(original)
    reds = [red_names(out) for _code, out in runs]
    always = frozenset.intersection(*reds)
    sometimes = frozenset.union(*reds) - always
    verdict = re.search(r"FAILED \(([^)]*)\)", runs[0][1])
    exits = ",".join(str(code) for code, _out in runs)
    print(f"{label}: exit {exits} {verdict.group(1) if verdict else 'NOT RED'}")
    detected = bool(always) and all(code != 0 for code, _out in runs)
    undetected += 0 if detected else 1
    unstable += 1 if sometimes else 0
    where = failing_lines(runs[0][1])
    for name in sorted(always):
        at = f" (test_debt_gate.py line {where[name]})" if name in where else ""
        print(f"      red: {name}{at}")
    for name in sorted(sometimes):
        print(f"      UNSTABLE (red in some of {REPEAT} runs only): {name}")
(copy / "tools" / PERSISTED_HARNESS).write_text(PERSISTED_HARNESS_SOURCE, encoding="utf-8")
persisted_runs = [
    run([f"{PERSISTED_HARNESS[:-3]}.PersistedSnapshotControl.{PERSISTED_TARGET}"])
    for _ in range(REPEAT)
]
persisted_bad = 0
for attempt, (code, out) in enumerate(persisted_runs, 1):
    reds = red_names(out)
    where = failing_lines(out)
    at = where.get(PERSISTED_TARGET, "")
    assertion = ""
    if at:
        lines = (copy / DEBT_TEST).read_text(encoding="utf-8").splitlines()
        first = int(at.split(",")[0])
        assertion = " ".join(x.strip() for x in lines[first - 1 : first + 4])
    persisted_ok = (
        code != 0
        and reds == {PERSISTED_TARGET}
        and "ERROR:" not in out
        and "DEBT_SNAPSHOT_CORRUPT" not in out
        and 'mid["problems"]' in assertion
    )
    persisted_bad += 0 if persisted_ok else 1
    print(
        f"M25 R008 persisted ON-DISK record: run {attempt}/{REPEAT} exit {code}, "
        f"red {sorted(reds) or 'NOT RED'}"
    )
    print(f"      failed at test_debt_gate.py line {at or '?'}: {assertion[:120]}")

print(f"restored; mutations {len(MUTATIONS)}, undetected {undetected}, "
      f"mutations with an unstable test {unstable}, "
      f"persisted-record control runs failed {persisted_bad}")
raise SystemExit(1 if undetected or unstable or persisted_bad else 0)
