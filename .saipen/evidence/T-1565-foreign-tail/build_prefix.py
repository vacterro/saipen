"""Build a pre-fix copy of the SAIPEN home: current tree minus T-1565's edits."""
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path(r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN")
DEST = Path(sys.argv[1])
if DEST.exists():
    shutil.rmtree(DEST)
IGNORE = shutil.ignore_patterns(".git", ".saipen", "__pycache__", "*.pyc", ".pytest_cache")
DEST.mkdir(parents=True)
for entry in HOME.iterdir():
    if entry.name in (".git", ".saipen"):
        continue
    target = DEST / entry.name
    if entry.is_dir():
        shutil.copytree(entry, target, ignore=IGNORE)
    else:
        shutil.copy2(entry, target)


def head(rel):
    return subprocess.run(
        ["git", "-C", str(HOME), "show", f"HEAD:{rel}"], capture_output=True, check=True
    ).stdout


def text(rel):
    return (DEST / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")


def put(rel, s):
    (DEST / rel).write_bytes(s.encode("utf-8"))


def cut(s, start, end, keep_end=True):
    i = s.index(start)
    j = s.index(end, i)
    return s[:i] + (s[j:] if keep_end else s[j + len(end):])


def swap(s, new, old):
    assert new in s, new[:60]
    return s.replace(new, old, 1)


# Files carrying only T-1565 edits: HEAD is the pre-fix subject.
for rel in ("tools/_log_append.py", "tools/saipen_engine/reconcile.py"):
    (DEST / rel).write_bytes(head(rel))

# log.py: drop the foreign-tail proof.
s = text("tools/saipen_engine/log.py")
s = cut(s, "_ACTIVE_ILLEGAL_RE = ", "def history_hash(")
put("tools/saipen_engine/log.py", s)

# operations.py
s = text("tools/saipen_engine/operations.py")
s = cut(s, "\n#: The one ledger-damage class a reader may look past", 'TAIL_QUARANTINE_OBSERVABLE = ("foreign_tail",)\n', keep_end=False)
s = swap(s, '    allow_foreign_tail = "foreign_tail" in observe\n', "")
s = swap(s, "    foreign_tail = None\n    foreign_tail_refusal = None\n", "")
s = cut(s, "    if allow_foreign_tail:\n        from .log import foreign_tail_cut", "    parked_error = block_parked_evidence_error(state, board, snapshot.events)")
s = cut(s, "                + (\n                    f\" (tail quarantine not provable", "                code=\"HISTORY_LEDGER_CORRUPT\",")
s = swap(s, '"contract -- " + "; ".join(history_problems[:4])\n', '"contract -- " + "; ".join(history_problems[:4]),\n')
s = cut(s, "    if allow_foreign_tail:\n        # The proven cut", "    return docs, state, board, log_tail")
s = cut(s, "#: Where `quarantine_log_tail` preserves the LOG it cut.", "@_state_guard\ndef migrate_saipen_generation(")
put("tools/saipen_engine/operations.py", s)

# saipen.py: drop the recover wiring.
s = text("tools/saipen.py")
s = swap(s, "    quarantine_tail_requested = False\n", "")
s = cut(s, '        if token == "quarantine-log-tail":', '        if token == "--resolve-duplicate-id":')
s = swap(s, '            "[quarantine-log-tail] "\n', "")
s = swap(s, "            or quarantine_tail_requested\n", "")
s = cut(s, "    if quarantine_tail_requested:\n", "    if normalize_log_requested:\n        # T-1356")
put("tools/saipen.py", s)

# runtime_namespace.py: drop the two evidence roots.
s = text("tools/saipen_engine/runtime_namespace.py")
s = swap(s, '    ".saipen/recovery/log-normalize/",\n    ".saipen/recovery/log-foreign-tail/",\n', "")
s = cut(s, "    # A ledger REWRITE keeps the LOG it replaced here;", ")\n\n\ndef attributes_block")
put("tools/saipen_engine/runtime_namespace.py", s)
print("built", DEST)
