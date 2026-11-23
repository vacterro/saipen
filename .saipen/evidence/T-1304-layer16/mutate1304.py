"""Mutation controls for T-1304: remove one property, the named tests must go red.

Usage: mutate1304.py <repo> <copy>

The copy is a disposable tree (no VCS, no project memory). Each mutation is
applied to the copy only, the named tests run from the copy, and the file is
restored from the repository before the next one.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
copy = Path(sys.argv[2]).resolve()
assert repo != copy and repo not in copy.parents and not copy.exists(), copy

skip = {".git", ".saipen", "__pycache__", ".pytest_cache", ".ruff_cache",
        ".workbuddy-ai", ".codenomad", ".freebuff", ".claude"}
shutil.copytree(
    repo, copy, ignore=lambda d, names: [n for n in names if n in skip or n.endswith(".pyc")]
)

JOURNAL = "tools/saipen_engine/journal.py"
PROJECTION = "tools/saipen_engine/settled_projection.py"
FAST = "tools/saipen_engine/fast_check.py"
OPS = "tools/saipen_engine/operations.py"
NAMESPACE = "tools/saipen_engine/runtime_namespace.py"
AUDIT = "tools/audit_checks.py"
R005 = "test_t1304_r005_verifier_boundary"
R006 = "test_t1304_r006_boundary_refusals"
R009 = "test_t1304_r009_settled_wiring"
R011 = "test_t1304_r011_empty_selection"
T1519 = "test_t1519_settled_index"
ALL = [R005, R006, R009, R011, T1519]

HEAD_CALL_ADVANCE = (
    "    head_root = _write_head(\n"
    "        root,\n"
    "        lineage=lineage,\n"
    "        sealed_count=sealed_count,\n"
    "        settled_count=settled_count,\n"
    "        settled_dir_mtime_ns=token,\n"
    "        active_root=tail_root,\n"
    "        latest_sealed_id=latest_sealed_id,\n"
    "        latest_sealed_root=latest_sealed_root,\n"
    "        prev_root=payload.get(\"prev_root\"),\n"
    "    )\n"
)
LOCATOR_LOOP_ADVANCE = (
    "    for name in folded:\n"
    "        operation = folded_operations.get(name)\n"
    "        if isinstance(operation, str) and operation:\n"
    "            _merge_locator_active(root, name, operation)\n"
)
LOCATOR_LOOP_REBUILD = (
    "    for operation, entries in locator_entries.items():\n"
    "        _write_locator(root, operation, entries)\n"
)
HEAD_OPEN_REBUILD = (
    "    head_root = _write_head(\n"
    "        root,\n"
    "        lineage=lineage,\n"
    "        sealed_count=len(sealed),\n"
)

MUTATIONS = [
    (
        "M1 R005: the verifier hands an unreadable history to the ledger contract again",
        FAST,
        [("    if _history is None:\n        errors.append(\n", "    if False:\n        errors.append(\n")],
        [R005],
    ),
    (
        "M2 R006: an unknown source diagnostic is forwarded raw",
        OPS,
        [(
            "    code = diagnostic.get(\"code\")\n"
            "    return code if isinstance(code, str) and code in CODES else default\n",
            "    return diagnostic.get(\"code\", default)\n",
        )],
        [R006],
    ),
    (
        "M3 R009: settlement does not advance the projection",
        JOURNAL,
        [(
            "            settled_projection.advance_after_settlement(\n"
            "                journal.project_root, [settled_dir.name], token\n"
            "            )\n",
            "            pass\n",
        )],
        [R009, T1519],
    ),
    (
        "M4 R009: settlement advances without the pre-move token (rebuilds every time)",
        JOURNAL,
        [(
            "                journal.project_root, [settled_dir.name], token\n",
            "                journal.project_root, [settled_dir.name], None\n",
        )],
        [R009],
    ),
    (
        "M5 R009: an operation query filters the lifetime snapshot",
        JOURNAL,
        [(
            "        if settled_projection.state(root) in honest:\n            break\n",
            "        if True:\n            break\n",
        )],
        [R009],
    ),
    (
        "M6 R009: a stale projection refuses the operation query",
        JOURNAL,
        [(
            "    honest = (settled_projection.STATE_ABSENT, settled_projection.STATE_STALE)\n",
            "    honest = (settled_projection.STATE_ABSENT,)\n",
        )],
        [R009],
    ),
    (
        "M7 R009: projection bytes that fail verification are scanned around",
        JOURNAL,
        [(
            "    honest = (settled_projection.STATE_ABSENT, settled_projection.STATE_STALE)\n",
            "    honest = (settled_projection.STATE_ABSENT, settled_projection.STATE_STALE,\n"
            "              settled_projection.STATE_UNTRUSTED)\n",
        )],
        [R009],
    ),
    (
        "M8 the whole-history snapshot never asks the memo",
        JOURNAL,
        [("        memo=record_memo(root),\n", "        memo=None,\n")],
        [T1519],
    ),
    (
        "M9 a memoized record is used whatever its status",
        JOURNAL,
        [(
            "            if cached is not None and cached.get(\"status\") in SETTLED:\n",
            "            if cached is not None:\n",
        )],
        [R009],
    ),
    (
        "M10 the memo is asked by name, not by the digests of the bytes read",
        JOURNAL,
        [(
            "            cached = memo.get(\n"
            "                (\n"
            "                    entry.name,\n"
            "                    hashlib.sha256(entry.manifest_raw).hexdigest(),\n"
            "                    hashlib.sha256(entry.progress_raw).hexdigest()\n"
            "                    if entry.progress_raw is not None\n"
            "                    else None,\n"
            "                )\n"
            "            )\n",
            "            cached = {key[0]: value for key, value in memo.items()}.get(entry.name)\n",
        )],
        [R009, T1519],
    ),
    (
        "M11 a rebuild leaves the retired index behind",
        PROJECTION,
        [("        _index_path(root, SETTLED_INDEX_REL).unlink()\n", "        pass\n")],
        [R009],
    ),
    (
        "M12 the projection directory is not classed machine-local",
        NAMESPACE,
        [("    (\".saipen/recovery/settled-index/\", \"rebuildable-projection\"),\n", "")],
        [R009],
    ),
    (
        "M13 R011: an empty selection constructs a pool again",
        AUDIT,
        [(
            "    if chunks:\n        with ThreadPoolExecutor(max_workers=worker_count) as executor:\n",
            "    if True:\n"
            "        with ThreadPoolExecutor(max_workers=max(1, worker_count)) as executor:\n",
        )],
        [R011],
    ),
    (
        "M14 a rebuild publishes its head before its locators",
        PROJECTION,
        [
            (LOCATOR_LOOP_REBUILD + HEAD_OPEN_REBUILD, HEAD_OPEN_REBUILD),
            (
                "        prev_root=prev_root,\n    )\n",
                "        prev_root=prev_root,\n    )\n" + LOCATOR_LOOP_REBUILD,
            ),
        ],
        [R009],
    ),
    (
        "M15 an advance publishes its head before the new locator",
        PROJECTION,
        [(LOCATOR_LOOP_ADVANCE + HEAD_CALL_ADVANCE, HEAD_CALL_ADVANCE + LOCATOR_LOOP_ADVANCE)],
        [R009],
    ),
    (
        "M16 a reader believes the first refused read",
        PROJECTION,
        [("_READ_ATTEMPTS = 12\n", "_READ_ATTEMPTS = 1\n")],
        [R009],
    ),
    (
        "M17 an operation query takes one look only",
        JOURNAL,
        [("    for _look in range(2):\n", "    for _look in range(1):\n")],
        [R009],
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


# Every run is repeated: a test whose outcome differs between two runs of the
# same bytes is a coin flip, and a coin flip reads as "detected" under any
# mutation at all. The first edition ran each mutation once and counted three
# such phantom detections (M9, M11, M12) without noticing them.
REPEAT = 3


def red_names(out: str) -> frozenset[str]:
    return frozenset(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", out, flags=re.M))


for attempt in range(REPEAT):
    code, out = run(ALL)
    ran = re.search(r"Ran (\d+) tests", out)
    print(f"CONTROL {attempt + 1}/{REPEAT} unmutated copy: exit {code}, "
          f"{ran.group(0) if ran else out[-300:]}")
    assert code == 0, out[-3000:]

undetected = 0
unstable = 0
for label, rel, edits, tests in MUTATIONS:
    target = copy / rel
    original = (repo / rel).read_bytes()
    newline = "\r\n" if b"\r\n" in original else "\n"
    text = original.decode("utf-8")
    for old, new in edits:
        old, new = old.replace("\n", newline), new.replace("\n", newline)
        assert text.count(old) == 1, (label, text.count(old), old[:70])
        text = text.replace(old, new)
    target.write_bytes(text.encode("utf-8"))
    runs = [run(tests) for _ in range(REPEAT)]
    target.write_bytes(original)
    reds = [red_names(out) for _code, out in runs]
    always = frozenset.intersection(*reds)
    sometimes = frozenset.union(*reds) - always
    verdict = re.search(r"FAILED \(([^)]*)\)", runs[0][1])
    exits = ",".join(str(code) for code, _out in runs)
    print(f"{label}: exit {exits} {verdict.group(1) if verdict else 'NOT RED'}")
    undetected += 0 if always else 1
    unstable += 1 if sometimes else 0
    for name in sorted(always):
        print(f"      red: {name}")
    for name in sorted(sometimes):
        print(f"      UNSTABLE (red in some of {REPEAT} runs only): {name}")
print(f"restored; mutations {len(MUTATIONS)}, undetected {undetected}, "
      f"mutations with an unstable test {unstable}")
raise SystemExit(1 if undetected or unstable else 0)
